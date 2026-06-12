# Resolve AI Editor

**AI-assisted auto-editing for DaVinci Resolve — one click from raw footage
to a clean rough cut.** Open source (MIT), local-first, no telemetry.

> Status: **Phase 1 (MVP)** — the one-click raw cut works end-to-end.
> AI providers, cut profiles, SFX/VFX assets and sound research are planned
> phases (see roadmap) and are shown as honest placeholders in the UI.

![panel screenshot placeholder](docs/screenshot-panel.png)
*(screenshot/GIF placeholder)*

## What it does today (Phase 1)

- **Dockless panel** ("app in Resolve"): launched from
  `Workspace > Scripts`, opens a local web panel with tabs
  **Auto-Cut · Assets · Sound · Settings**. Works in Resolve **Free and
  Studio** (see limitations).
- **One-Click Raw Cut**: analyzes the audio of every clip on video track 1,
  detects silences and breathing pauses **100% locally** (ffmpeg
  `silencedetect`, optionally `webrtcvad`) — *no* LLM/API calls, *no* costs —
  and builds a **new timeline** `<name> [AI Raw Cut]` containing only the
  spoken segments.
- **Non-destructive**: your original timeline is never modified. Undo =
  delete the generated timeline.
- **Tunable**: silence threshold, minimum pause length, padding, minimum
  segment length, VAD aggressiveness — all in the Settings tab, persisted
  locally.
- **Cached**: analysis results are stored per file (path + mtime + size +
  parameters), so re-runs are instant.

### Why the cut looks the way it does (editing rationale)

- **Padding (~120 ms)** around each speech segment keeps breath onsets and
  sentence tails — cuts exactly on the waveform edge feel robotic.
- **Minimum segment length (~250 ms)** drops syllable-long slivers that read
  as flash frames.
- Overlapping padded segments are **merged** to avoid zero-length gaps.

These heuristics are documented in `core/cut/engine.py` and will grow into
full editing profiles (long-form / shorts / ads) in Phase 3.

## Installation

See **[INSTALL.md](INSTALL.md)**. Short version:

```bash
git clone https://github.com/legifx/resolve-ai-editor.git
cd resolve-ai-editor
python3 install.py        # writes a launcher into Resolve's Scripts menu
```

Requirements: DaVinci Resolve 18.6+ (Free or Studio), Python 3.6+, ffmpeg.

## Usage

1. Open your project and timeline in Resolve.
2. `Workspace > Scripts > Utility > Resolve AI Editor` — the panel opens in
   your browser.
3. Check the timeline status, adjust Settings if needed, hit
   **✂ Create Raw Cut**.
4. Resolve now contains a new timeline `<name> [AI Raw Cut]`. Review it;
   delete it if you don't like it (the original is untouched).

Developer demo without Resolve: `python3 -m plugin.main --demo`

## Honest limitations

| Topic | Reality |
|---|---|
| Resolve **Free vs. Studio** | The panel runs from the Scripts menu, which works in **both** editions. Blackmagic's official *Workflow Integration* docked panels and external scripting are **Studio-only**; a docked Electron panel is a possible later add-on for Studio users. |
| Linux | Resolve on Linux is Studio-only; the Scripts-menu path should work but is untested. Developed/tested headless on Linux against a mock; **real-Resolve testing so far: none — testers welcome.** |
| Retimed clips | Phase 1 assumes clip fps == timeline fps. Speed-ramped/retimed clips will cut at wrong positions — avoid running on them for now. |
| Compound/Fusion clips | Skipped (no source media path) and reported in the result. |
| Audio-only logic | Cuts are based on the audio of the **video clips on track 1**. Separate audio-track analysis comes later. |
| Trend sounds (TikTok/IG) | There is **no official trend-sound API**. The plugin will never scrape by default; Phase 5 ships royalty-free sources plus an off-by-default, clearly-labelled best-effort module. |
| AI features | Phase 1 contains **zero** AI/API calls. The provider layer (Claude/OpenAI/OpenRouter/custom, key storage in OS keychain, cost estimator) is Phase 2. |

## Privacy & security

- Local only: the panel server binds `127.0.0.1`, requires a random
  per-session token, serves only its own UI files.
- No telemetry, no hidden network access. Phase 1 makes **no** network
  requests at all.
- No API keys exist yet in this phase; when they arrive (Phase 2) they go
  into the OS keychain, never into the repo (`.gitignore` covers configs).

## Roadmap

1. ✅ **Phase 1 — Foundation:** panel, timeline access, local silence/VAD
   detection, one-click non-destructive raw cut, settings.
2. **Phase 2 — AI layer:** multi-provider abstraction (Anthropic Claude,
   OpenAI, OpenRouter free tier, generic OpenAI-compatible endpoints), key
   management, model routing, token/cost estimator.
3. **Phase 3 — Cut profiles:** long-form / shorts / ad pacing, hook logic,
   J/L-cuts, aspect-ratio handling.
4. **Phase 4 — Assets:** SFX/VFX folder indexing with cached AI tags;
   auto-placement *and* recommendation-list mode.
5. **Phase 5 — Context & sound:** audience/genre/topic filters with
   AI-suggested values; compliant sound research (royalty-free vs. optional
   trend mode).
6. **Phase 6 — Polish:** more tests, docs, packaging.

## Development

```bash
python3 -m pytest tests/      # 29 tests, needs ffmpeg, no Resolve required
python3 -m plugin.main --demo # run the panel against a mock timeline
```

Architecture: `plugin/` (panel + server) → `core/timeline` (defensive
Resolve API bridge) → `core/analyze` (local audio analysis) → `core/cut`
(pure cut-list engine). Everything Resolve-specific is isolated in
`core/timeline/bridge.py`; tests run against `core/timeline/mock.py`.

## License

MIT — see [LICENSE](LICENSE).
