# Resolve AI Editor

**AI-assisted auto-editing for DaVinci Resolve — one click from raw footage
to a clean rough cut.** Open source (MIT), local-first, no telemetry.

> Status: **Phases 1–5 done.** One-click raw cut (Phase 1), multi-provider
> AI layer (Phase 2), per-format edit profiles (Phase 3), an SFX/VFX asset
> library (Phase 4), and the genre/audience context layer + compliant sound
> research (Phase 5). Phase 6 is final polish.

![panel screenshot placeholder](docs/screenshot-panel.png)
*(screenshot/GIF placeholder)*

## Feature overview

| Tab | What it does | Phase |
|---|---|---|
| **Auto-Cut** | One-click raw cut (local silence/VAD), per-format edit profiles, live timeline status | 1, 3 |
| **Assets** | Connect SFX/VFX folders, local cached index, recommend a list *or* auto-insert on a new track | 4 |
| **Sound** | Video context (manual or AI-suggested) + compliant background-sound research | 5 |
| **Settings** | Auto-cut parameters; AI providers (keys, routing, cost) | 1, 2 |

## What it does

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

These heuristics are documented in `core/cut/engine.py`.

## Edit profiles (Phase 3)

The same footage is cut differently for a 20-minute YouTube video than for
a 30-second TikTok. Pick a profile in the Auto-Cut tab and it tunes the cut
for that format. Defined in `core/cut/profiles.py`:

| Profile | Aspect | Pacing | Hook protection | Edit points |
|---|---|---|---|---|
| **Long-form (YouTube)** | 16:9 | natural — keeps breathing room (longer min-pause, more padding) | first **4 s** | none — shots breathe |
| **Short (TikTok/Reels)** | 9:16 | aggressive — cuts pauses tightly for high energy | first **1 s** | every **4 s** (pattern interrupts) |
| **Ad / Promo** | 16:9 | tight but not frantic | first **2.5 s** | every **6 s** (product shot / CTA) |

**What a profile actually does to the cut** (all local, no LLM, no fakery):

- **Pacing** — long-form keeps more of the natural rhythm; Short strips
  pauses hard for that fast, punchy feel.
- **Hook protection** — the opening N seconds of the footage are *never*
  cut, so your cold-open / hook stays intact (a hard cut 0.5 s in kills it).
- **Edit points** — long kept stretches are subdivided into cut points so
  you have a place to drop B-roll or a pattern interrupt. The clip still
  plays seamlessly; this gives you the edit point, it does **not** generate
  a visual effect.

**What a profile only recommends** — because the Resolve *Free* API can't do
it from audio alone, the plugin tells you instead of pretending to: J-/L-cuts
on dialogue, auto-captions, aspect-ratio reframing (Studio "Smart Reframe" or
manual), and music beat-syncing. These appear as a checklist in the result,
and an aspect-ratio mismatch (e.g. a 16:9 timeline with the Short profile)
raises a clear warning — the plugin never alters your picture.

## SFX/VFX assets (Phase 4)

Connect one or more folders of sound effects (and video/image assets) in the
**Assets** tab. The plugin indexes them **locally** — filename, duration
(ffprobe), type, and a heuristic category/tags derived from the filename
(`whoosh_transition` → *transition*, `deep_impact` → *impact*, …). The index
is cached per file and only re-probes changed/new files; nothing is sent to
any API during indexing.

Then, for your current timeline, two modes (both required by design):

1. **List / script mode** — get a recommended SFX script: *which* effect, at
   *which* timecode, and *why* (hook → riser/impact, each shot change →
   transition whoosh). Touches nothing.
2. **Auto-insert mode** — the same recommendations placed onto a **new,
   dedicated audio track** at the right frames. Additive: it adds a track and
   deletes nothing, so undo is Resolve Undo or just deleting that track.

An optional **AI-refine** toggle sends only a compact summary (cut points +
candidate asset *names* + any genre/audience context — never audio) to your
configured provider to improve the picks; if no provider is available it
silently falls back to the local heuristic.

> Auto-insert is **untested on real Resolve** (this repo is developed
> headless against a mock). The list mode and the index are the safe,
> verified path; treat auto-insert as experimental until a real-Resolve
> tester confirms it.

## Context & sound research (Phase 5)

The **Sound** tab carries two related things.

**Video context** — optional *audience / genre / topic* filters. Fill them in
manually, or hit **Auto-suggest**: the plugin builds a compact, local-only
description of your timeline (clip filenames, counts, duration, fps,
resolution — clip names are usually very telling) and asks your AI provider to
infer the three fields. You edit and confirm; nothing is acted on silently. An
optional **frame-sample** toggle additionally sends a few small downscaled
JPEG frames to a vision-capable provider (Anthropic) — deliberately sparse to
keep token cost low; it falls back to metadata-only if vision isn't available.

**Background sound research** — three music directions for your video, in two
modes:

- **Royalty-free / commercial (default)** — directions tailored to your
  context (or a sensible static fallback), each pointing at a **real,
  license-tagged source** (Pixabay Music, YouTube Audio Library, Free Music
  Archive, Incompetech, ccMixter) with commercial-use and attribution flags.
  The license is always shown; the plugin never fabricates a track or a
  download link, and always reminds you to verify the current per-track terms.
- **Trend (off by default)** — an honest, clearly-labelled best-effort module.
  **There is no official, ToS-compliant API for TikTok/Instagram trend
  sounds, and this plugin does not scrape.** The mode does nothing unless you
  explicitly enable it *and* configure a source you have the right to query —
  and even then it only returns search terms for you to check on that source,
  making no hidden network requests.

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
| Retimed clips | The cut engine assumes clip fps == timeline fps. Speed-ramped/retimed clips will cut at wrong positions — avoid running on them for now. |
| Compound/Fusion clips | Skipped (no source media path) and reported in the result. |
| Audio-only logic | Cuts are based on the audio of the **video clips on track 1**. Separate audio-track analysis comes later. |
| Asset auto-insert | The list/recommend mode is verified; the **auto-insert** mode (writing SFX onto a new track) is implemented and mock-tested but **untested on real Resolve** — treat as experimental (see [VERIFY.md](VERIFY.md)). |
| Trend sounds (TikTok/IG) | There is **no official trend-sound API**. The plugin never scrapes; royalty-free sources are the default, with an off-by-default, clearly-labelled best-effort trend module. |
| AI features | The raw cut and asset indexing make **zero** API calls. The AI layer (Claude/OpenAI/OpenRouter/custom) is opt-in — no call is made unless you add a key and use a feature that needs it. |
| Key encryption | Keys go into the OS keychain when one is available (`pip install keyring`). On headless/locked systems they fall back to a `0600` JSON file that is access-restricted but **not encrypted** — the UI says so. Don't store keys on a shared machine without a keychain. |

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
2. ✅ **Phase 2 — AI layer:** multi-provider abstraction (Anthropic Claude,
   OpenAI, OpenRouter free tier, generic OpenAI-compatible endpoints), key
   management, model routing, token/cost estimator.
3. ✅ **Phase 3 — Cut profiles:** long-form / shorts / ad pacing, hook
   protection, pacing edit points, aspect-ratio warnings, and an honest
   recommendations checklist for non-automatable techniques.
4. ✅ **Phase 4 — Assets:** SFX/VFX folder indexing with cached tags;
   recommendation-list mode *and* auto-insert mode.
5. ✅ **Phase 5 — Context & sound:** audience/genre/topic filters with
   AI-suggested values (local signals + optional frames); compliant sound
   research (royalty-free vs. off-by-default trend mode).
6. ✅ **Phase 6 — Polish:** test/doc pass, real-Resolve verification
   checklist ([VERIFY.md](VERIFY.md)), packaging.

## Development

```bash
python3 -m pytest tests/      # 109 tests, needs ffmpeg, no Resolve required
python3 -m plugin.main --demo # run the panel against a mock timeline
```

### Project structure

```
resolve-ai-editor/
├─ plugin/              # entry + local web panel
│  ├─ main.py           #   launch() — from Resolve menu or --demo
│  ├─ server.py         #   stdlib HTTP server, 127.0.0.1 + token auth
│  ├─ demo.py           #   synthetic timeline for headless dev
│  └─ panel/            #   index.html · app.js · style.css
├─ core/
│  ├─ timeline/         # ResolveBridge (defensive API wrapper) + mock
│  ├─ analyze/          # ffmpeg silence / webrtcvad / cache
│  ├─ cut/              # pure cut-list engine + edit profiles
│  ├─ ai/               # provider abstraction, keys, routing, costs
│  ├─ assets/           # library index, recommender, placement
│  ├─ context/          # local signals, AI suggest, frame sampling
│  └─ sound/            # compliant sound research
├─ config/settings.py   # local settings (no secrets)
├─ tests/               # 109 tests — mocks only, no Resolve/network
├─ install.py           # writes the Scripts-menu launcher
└─ README · INSTALL · VERIFY · CHANGELOG · LICENSE
```

Data flow: `plugin/` (panel + server) → `core/timeline` (the **only**
Resolve-specific module) → `core/analyze` → `core/cut` → `core/ai` →
`core/assets` → `core/context` → `core/sound`. Everything Resolve-specific is
isolated in `core/timeline/bridge.py` and all AI calls in `core/ai/`; tests run
against mocks (`core/timeline/mock.py`, mocked HTTP) with no network or Resolve
required.

**Not yet verified on real Resolve** (developed headless) — see
[VERIFY.md](VERIFY.md) for the tester checklist.

## License

MIT — see [LICENSE](LICENSE).
