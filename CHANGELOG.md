# Changelog

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
