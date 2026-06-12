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
from core.analyze.vad import HAS_WEBRTCVAD
from core.cut import run_raw_cut
from core.timeline.bridge import CapabilityError

PANEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "panel")
VERSION = "0.1.0"

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

    def start_job(self):
        with self.lock:
            if self.running:
                return False
            self.running, self.log, self.report, self.error = True, [], None, None
        threading.Thread(target=self._worker, daemon=True).start()
        return True

    def _worker(self):
        def progress(msg):
            with self.lock:
                self.log.append(msg)
        try:
            report = run_raw_cut(self.bridge, settings.load(), progress)
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
        self._json({"error": "not found"}, 404)

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
            if not self.state.start_job():
                return self._json({"error": "a job is already running"}, 409)
            return self._json({"started": True})
        self._json({"error": "not found"}, 404)

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
