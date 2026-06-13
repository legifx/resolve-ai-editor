# Changelog

## 1.1.1 — Fix: unstyled panel / dead buttons (2026-06-13)

- **Bug:** the panel loaded as unstyled HTML and no buttons worked. The
  server required the session token on *every* request, but the browser
  fetches `/static/style.css` and `/static/app.js` from plain
  `<link>`/`<script>` tags that carry no token — so CSS and JS were
  rejected with 403 and never loaded.
- **Fix:** static UI assets (`/`, `/static/*`) are now served without the
  token (they contain no secrets); only `/api/*` stays token-protected.
  `app.js` still reads the token from the page URL and sends it on every
  API call. Added 2 tests pinning this down. 128 total.

## 1.1.0 — Better installer (2026-06-13)

- `install.py` is now a proper installer: pre-flight checks (Python
  version, ffmpeg/ffprobe on PATH), optional-dependency detection
  (anthropic / keyring / webrtcvad), and Resolve-data-folder
  auto-detection (writes to the folder Resolve actually uses, else the
  user-level default).
- New flags: `--check` (checks only, no changes), `--with-deps`
  (pip-install optional packages), `--uninstall` (removes the launcher
  from every candidate folder, leaves config/keys untouched). Colored,
  readable output; verifies the launcher after writing.
- 9 installer tests (paths, Resolve detection, write/verify/uninstall,
  check mode, launcher compiles). 126 total.
- INSTALL.md documents the new options.

## 1.0.0 — Phase 6: Polish (2026-06-13)

- All six planned phases complete; panel version bumped to 1.0.0.
- **[VERIFY.md](VERIFY.md)**: step-by-step real-Resolve verification
  checklist with pass criteria for every feature (this is the one thing
  the headless dev environment can't do — testers welcome).
- README: feature/tab overview, full project-structure tree, updated
  limitations table (asset auto-insert flagged experimental).
- 8 robustness tests: ffmpeg-missing install hint, corrupt
  settings/cache fallback, server 404/400 guards, all-GET-endpoints
  smoke. 117 total.
- Verified: full suite green, install.py launcher template compiles, all
  modules byte-compile.

## 0.5.0 — Phase 5: Context & Sound (2026-06-13)

- `core/context/`: auto-suggest audience / genre / topic from **local**
  signals (clip filenames, counts, duration, fps, resolution — compact,
  token-sparing) via the AI layer; user edits/overrides every field.
  Optional sparse frame sampling (ffmpeg → small JPEGs) for
  vision-capable providers (Anthropic), degrading to metadata-only
  cleanly. `AnthropicProvider` gained vision (`images=`).
- `core/sound/`: compliant background-sound research, two modes:
  - **royalty_free (default)** — 3 context-fitted music directions (AI
    or static fallback) + curated, real, license-tagged sources
    (Pixabay, YouTube Audio Library, FMA, Incompetech, ccMixter) with
    commercial/attribution flags. Never fabricates a track.
  - **trend (off by default)** — no official trend API exists and the
    plugin does not scrape. Does nothing unless explicitly enabled AND a
    permitted source is configured; even then returns search terms only,
    no fetch.
- Panel: Sound tab — context fields + AI auto-suggest (frame-sample
  toggle), royalty-free vs trend modes with the no-scrape disclaimer and
  per-source licenses.
- 20 new tests (signals, suggest parse/fallback/vision-gate, frame
  extraction on real video, sound both modes + compliance guards). 109 total.

## 0.4.0 — Phase 4: SFX/VFX Assets (2026-06-13)

- `core/assets/index.py`: connect folders, scan audio/video/image,
  ffprobe duration, kind + heuristic category/tags from filename.
  Persistent JSON index keyed per file by (mtime, size) — re-scan only
  re-probes changed/new files (tag once, cache forever).
- `core/assets/match.py`: deterministic recommender mapping timeline cut
  points to SFX categories (hook → riser/impact, shot change →
  transition), returning a {timecode, asset, reason} script. Optional
  LLM refine pass (compact names + markers only, silent heuristic
  fallback on any error).
- Two modes, cleanly separated (prompt 3E): **list/script** (recommend,
  touches nothing) and **auto-insert** (`core/assets/place.py` + bridge
  `import_media`/`add_audio_track`/`place_audio`). Auto-insert is
  additive — adds a dedicated SFX audio track, deletes nothing; undo via
  Resolve Undo or by deleting the track. Untested on real Resolve.
- Panel: Assets tab — connect folders, scan with live count, list
  recommendations (AI-refine toggle), or auto-insert.
- 22 new tests (index/scan/cache/tags, matcher heuristic + rotation +
  LLM refine/fallback, placement on mock). 89 total.

## 0.3.0 — Phase 3: Edit Profiles (2026-06-13)

- `core/cut/profiles.py`: three editing profiles with real, documented
  heuristics:
  - **Long-form (YouTube, 16:9)** — natural pacing, more breathing room,
    4 s hook protection.
  - **Short (TikTok/Reels/Shorts, 9:16)** — aggressive pause removal,
    1 s hook, edit points every 4 s for pattern interrupts.
  - **Ad/Promo (16:9)** — tight pacing, 2.5 s hook protection, edit
    points for product shot + CTA.
- Each profile applies what the Free API can actually do (pacing via cut
  params, hook protection, pacing edit points) and surfaces a checklist
  of techniques it cannot automate (J/L-cuts, captions, reframe,
  beat-sync) as honest recommendations — never faked.
- Engine: `split_long()` pacing subdivision; `segments_for_clip()` hook
  protection (force-keep opening N s, exempt from the min-keep filter)
  and max-segment subdivision.
- Aspect-ratio check: warns when the timeline format differs from the
  profile target (no fake reframe). Source resolution captured before the
  new timeline becomes current.
- Panel: Edit-profile dropdown in the Auto-Cut tab; report shows profile,
  aspect warning, and the recommendations checklist.
- 17 new tests (profiles, split/hook/pacing, aspect check, per-profile
  integration). 67 total.

## 0.2.0 — Phase 2: AI Layer (2026-06-13)

- Multi-provider abstraction (`core/ai`): one `AIProvider` interface,
  `AIResponse` with token + cost tracking.
- Anthropic provider via the official `anthropic` SDK (optional dep;
  adaptive thinking on 4.6+ models; default `claude-opus-4-8`).
- OpenAI / OpenRouter / custom OpenAI-compatible endpoints via a
  stdlib-only HTTP client (zero hard deps for these).
- Key storage: OS keychain (`keyring`) preferred, with a real
  set/get/delete round-trip probe; honest 0600-file fallback labelled
  "not encrypted". Keys are write-only through the panel API.
- Model routing by task tier (routine → cheap/free, complex → strong),
  user-configurable in Settings.
- Local token/cost estimator with a cached price table (unknown models
  report `cost=None`, never a fabricated number).
- Panel: Settings tab gains AI Providers (per-provider key inputs,
  write-only) + Model Routing (provider/model per tier, custom base URL,
  live Test buttons reporting tokens + cost).
- 21 new tests (costs, keys, router, provider guards, mocked
  OpenAI-compatible parsing + error mapping). 50 total.

## 0.1.0 — Phase 1: Foundation (2026-06-12)

- ResolveBridge: defensive wrapper over the documented scripting API,
  runtime capability checks, clear errors for Free/Studio/version gaps.
- Local analysis: ffmpeg `silencedetect` (default) + optional `webrtcvad`;
  persistent per-file analysis cache.
- Raw-cut engine: pad/merge/min-keep heuristics with documented editing
  rationale; source-trim aware frame mapping.
- One-click raw cut: builds a NEW `<name> [AI Raw Cut]` timeline
  (non-destructive; undo = delete it), unique-name retry, skip report for
  compound/Fusion clips.
- Web panel (localhost-only, token-auth): Auto-Cut, Settings (persisted),
  honest Phase-4/5 placeholders for Assets & Sound.
- `install.py` launcher installer for Win/macOS/Linux Scripts menu;
  `python3 -m plugin.main --demo` for development without Resolve.
- 29 pytest tests (parser, engine, bridge, full pipeline integration).
