# Changelog

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
