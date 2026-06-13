"""Local panel server — stdlib only, binds 127.0.0.1 exclusively.

Security model (prompt section 5):
- loopback bind only, random per-session token required on every request
  (blocks other local users and DNS-rebinding/CSRF from web pages)
- no eval, no remote code, JSON in/out only
- serves only files inside plugin/panel/
"""

import json
import os
import secrets
import socketserver
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from config import settings
from core.ai import keys as ai_keys
from core.ai.base import AIError
from core.ai.router import DEFAULT_ROUTING, TIERS, get_provider_for_tier
from core.analyze.vad import HAS_WEBRTCVAD
from core.assets import build_index, place_assets, recommend
from core.assets.index import load_index
from core.context import suggest_context
from core.sound import MODES, research
from core.cut import run_raw_cut
from core.cut.profiles import DEFAULT_PROFILE, PROFILES
from core.timeline.bridge import CapabilityError

PANEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "panel")
VERSION = "0.2.0"

_MIME = {".html": "text/html; charset=utf-8",
         ".js": "application/javascript", ".css": "text/css"}


class AppState:
    def __init__(self, bridge):
        self.bridge = bridge
        self.token = secrets.token_urlsafe(16)
        self.lock = threading.Lock()
        self.running = False
        self.log = []
        self.report = None
        self.error = None

    def start_job(self, profile_key=None):
        with self.lock:
            if self.running:
                return False
            self.running, self.log, self.report, self.error = True, [], None, None
            self.profile_key = profile_key
        threading.Thread(target=self._worker, daemon=True).start()
        return True

    def _worker(self):
        def progress(msg):
            with self.lock:
                self.log.append(msg)
        try:
            report = run_raw_cut(self.bridge, settings.load(), progress,
                                 profile_key=self.profile_key)
            with self.lock:
                self.report = report
        except (CapabilityError, Exception) as exc:  # never crash the panel
            with self.lock:
                self.error = str(exc)
        finally:
            with self.lock:
                self.running = False

    def job_status(self):
        with self.lock:
            return {"running": self.running, "log": list(self.log),
                    "report": self.report, "error": self.error}


class _Handler(BaseHTTPRequestHandler):
    state = None  # injected by serve()

    # ---- helpers ----
    def _json(self, payload, code=200):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self):
        host = (self.headers.get("Host") or "").split(":")[0]
        if host not in ("127.0.0.1", "localhost"):
            return False
        token = (self.headers.get("X-Token")
                 or parse_qs(urlparse(self.path).query).get("token", [""])[0])
        return secrets.compare_digest(token, self.state.token)

    def log_message(self, *args):  # silence default stderr noise
        pass

    # ---- routes ----
    def do_GET(self):
        if not self._authorized():
            return self._json({"error": "unauthorized"}, 403)
        path = urlparse(self.path).path
        if path == "/":
            return self._file("index.html")
        if path.startswith("/static/"):
            return self._file(path[len("/static/"):])
        if path == "/api/status":
            info = self.state.bridge.project_info()
            return self._json({"resolve": info, "vad_available": HAS_WEBRTCVAD,
                               "version": VERSION})
        if path == "/api/settings":
            return self._json(settings.load())
        if path == "/api/job":
            return self._json(self.state.job_status())
        if path == "/api/ai/status":
            return self._json(self._ai_status())
        if path == "/api/profiles":
            return self._json({
                "default": DEFAULT_PROFILE,
                "profiles": [p.to_dict() for p in PROFILES.values()],
            })
        if path == "/api/assets/status":
            return self._json(self._assets_status())
        if path == "/api/context":
            cfg = settings.load()
            return self._json({
                "context": cfg.get("context", {}),
                "trend_enabled": cfg.get("sound_trend_enabled", False),
                "trend_source": cfg.get("sound_trend_source", ""),
            })
        self._json({"error": "not found"}, 404)

    def _assets_status(self):
        idx = load_index()
        cfg = settings.load()
        by_kind = {}
        for e in idx.values():
            by_kind[e.get("kind", "?")] = by_kind.get(e.get("kind", "?"), 0) + 1
        return {
            "folders": cfg.get("asset_folders", []),
            "indexed": len(idx),
            "by_kind": by_kind,
        }

    def _ai_status(self):
        """AI config for the UI. Never returns key values — only whether a
        key is present, plus per-tier provider availability."""
        cfg = settings.load()
        s = ai_keys.status()
        tiers = {}
        for tier in TIERS:
            try:
                provider = get_provider_for_tier(tier, cfg)
                ok, reason = provider.available()
                tiers[tier] = {"provider": provider.name,
                               "model": provider.model,
                               "ready": ok, "reason": reason}
            except AIError as exc:
                tiers[tier] = {"provider": None, "model": None,
                               "ready": False, "reason": str(exc)}
        return {
            "key_backend": s["backend"],
            "keys": s["configured"],         # {provider: bool}
            "routing": cfg.get("ai_routing", DEFAULT_ROUTING),
            "custom_base_url": cfg.get("ai_custom_base_url", ""),
            "tiers": tiers,
        }

    def do_POST(self):
        if not self._authorized():
            return self._json({"error": "unauthorized"}, 403)
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode() or "{}")
        except json.JSONDecodeError:
            return self._json({"error": "invalid JSON"}, 400)

        if path == "/api/settings":
            return self._json(settings.save(payload))
        if path == "/api/rawcut":
            profile_key = payload.get("profile") or None
            if profile_key and profile_key not in PROFILES:
                return self._json({"error": "unknown profile"}, 400)
            if not self.state.start_job(profile_key):
                return self._json({"error": "a job is already running"}, 409)
            return self._json({"started": True})
        if path == "/api/ai/key":
            return self._ai_set_key(payload)
        if path == "/api/ai/test":
            return self._ai_test(payload)
        if path == "/api/assets/folders":
            folders = payload.get("folders")
            if not isinstance(folders, list):
                return self._json({"error": "folders must be a list"}, 400)
            settings.save({"asset_folders": [str(f) for f in folders]})
            return self._json(self._assets_status())
        if path == "/api/assets/scan":
            return self._assets_scan()
        if path == "/api/assets/recommend":
            return self._assets_recommend(bool(payload.get("use_ai")))
        if path == "/api/assets/place":
            return self._assets_place(bool(payload.get("use_ai")))
        if path == "/api/context":
            return self._context_save(payload)
        if path == "/api/context/suggest":
            return self._context_suggest(bool(payload.get("use_frames")))
        if path == "/api/sound/research":
            return self._sound_research(payload)
        self._json({"error": "not found"}, 404)

    # ---- context & sound ----

    def _context_save(self, payload):
        ctx = payload.get("context") or {}
        clean = {k: str(ctx.get(k, "")) for k in ("audience", "genre", "topic")}
        update = {"context": clean}
        if "trend_enabled" in payload:
            update["sound_trend_enabled"] = bool(payload["trend_enabled"])
        if "trend_source" in payload:
            update["sound_trend_source"] = str(payload["trend_source"])
        settings.save(update)
        return self._json({"ok": True, "context": clean})

    def _provider_or_none(self):
        try:
            provider = get_provider_for_tier("complex", settings.load())
            ok, reason = provider.available()
            return (provider, None) if ok else (None, reason)
        except AIError as exc:
            return None, str(exc)

    def _context_suggest(self, use_frames):
        provider, reason = self._provider_or_none()
        if provider is None:
            return self._json({"error": "AI provider needed: " + (reason or "")})
        try:
            out = suggest_context(self.state.bridge, provider,
                                  use_frames=use_frames)
        except (AIError, CapabilityError, Exception) as exc:
            return self._json({"error": str(exc)})
        return self._json({"ok": True, "suggestion": out})

    def _sound_research(self, payload):
        mode = payload.get("mode", "royalty_free")
        if mode not in MODES:
            return self._json({"error": "unknown mode"}, 400)
        cfg = settings.load()
        provider, _ = self._provider_or_none()  # None is fine — falls back
        try:
            result = research(
                cfg.get("context", {}), mode=mode, provider=provider,
                trend_enabled=cfg.get("sound_trend_enabled", False),
                trend_source=cfg.get("sound_trend_source", ""))
        except Exception as exc:
            return self._json({"error": str(exc)})
        return self._json(result)

    # ---- assets ----

    def _assets_scan(self):
        folders = settings.load().get("asset_folders", [])
        if not folders:
            return self._json({"error": "No folders connected. Add one first."}, 400)
        try:
            idx = build_index(folders)
        except Exception as exc:  # ffprobe/IO — never crash the panel
            return self._json({"error": "scan failed: %s" % exc}, 500)
        return self._json(self._assets_status())

    def _recommendations(self, use_ai):
        """Shared by recommend + place: read timeline, build the SFX script."""
        idx = load_index()
        if not idx:
            raise CapabilityError("Asset library is empty — connect a folder "
                                  "and scan it first (Assets tab).")
        clips = self.state.bridge.clips()
        if not clips:
            raise CapabilityError("Timeline has no clips on video track 1.")
        fps = self.state.bridge.timeline_fps()
        provider = None
        if use_ai:
            try:
                provider = get_provider_for_tier("complex", settings.load())
                ok, _ = provider.available()
                if not ok:
                    provider = None  # silently fall back to heuristic
            except AIError:
                provider = None
        recs = recommend(clips, idx, fps, provider=provider)
        return recs, idx, fps

    def _assets_recommend(self, use_ai):
        try:
            recs, _idx, _fps = self._recommendations(use_ai)
        except (CapabilityError, Exception) as exc:
            return self._json({"error": str(exc)})
        return self._json({"placements": recs, "ai_used": bool(use_ai)})

    def _assets_place(self, use_ai):
        try:
            recs, idx, fps = self._recommendations(use_ai)
            report = place_assets(self.state.bridge, recs, idx, fps)
        except (CapabilityError, Exception) as exc:
            return self._json({"error": str(exc)})
        return self._json({"ok": True, "report": report})

    def _ai_set_key(self, payload):
        """Store or clear an API key. Write-only — never echoed back."""
        provider = payload.get("provider")
        if provider not in ai_keys.PROVIDERS:
            return self._json({"error": "unknown provider"}, 400)
        try:
            ai_keys.set_key(provider, payload.get("key") or "")
        except ValueError as exc:
            return self._json({"error": str(exc)}, 400)
        return self._json({"ok": True, "configured": bool(ai_keys.get_key(provider))})

    def _ai_test(self, payload):
        """Cheap end-to-end probe of a tier's configured provider."""
        tier = payload.get("tier")
        if tier not in TIERS:
            return self._json({"error": "unknown tier"}, 400)
        try:
            provider = get_provider_for_tier(tier, settings.load())
            resp = provider.complete(
                "Reply with the single word: ok", max_tokens=16)
        except AIError as exc:
            return self._json({"ok": False, "error": str(exc)})
        return self._json({
            "ok": True, "provider": resp.provider, "model": resp.model,
            "reply": resp.text.strip()[:80],
            "input_tokens": resp.input_tokens,
            "output_tokens": resp.output_tokens,
            "cost_usd": resp.cost_usd,
        })

    def _file(self, rel):
        full = os.path.realpath(os.path.join(PANEL_DIR, rel))
        if not full.startswith(os.path.realpath(PANEL_DIR) + os.sep) \
                and full != os.path.join(os.path.realpath(PANEL_DIR), rel):
            return self._json({"error": "forbidden"}, 403)
        if not os.path.isfile(full):
            return self._json({"error": "not found"}, 404)
        with open(full, "rb") as fh:
            body = fh.read()
        self.send_response(200)
        ext = os.path.splitext(full)[1]
        self.send_header("Content-Type", _MIME.get(ext, "application/octet-stream"))
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class _ThreadingServer(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def serve(bridge, port=0):
    """Start the panel server on 127.0.0.1. Returns (server, url, state).
    port=0 lets the OS pick a free port."""
    state = AppState(bridge)
    handler = type("BoundHandler", (_Handler,), {"state": state})
    server = _ThreadingServer(("127.0.0.1", port), handler)
    url = "http://127.0.0.1:%d/?token=%s" % (server.server_address[1], state.token)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, url, state
