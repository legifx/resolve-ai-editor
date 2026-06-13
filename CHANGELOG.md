# Changelog

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
