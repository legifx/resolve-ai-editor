# Verifying on real DaVinci Resolve

This project is developed **headless** — every module is tested against a mock
of the Resolve API (`core/timeline/mock.py`), and the full pytest suite passes
with no Resolve installed. What has **not** happened yet is a run against a real
DaVinci Resolve install on Windows or macOS.

This checklist is for a tester with real Resolve. Work through it top to bottom;
each step has a clear **PASS** condition. Please report results (see *Reporting*
at the end) — even "everything passed" is valuable.

> Edition note: the plugin launches from **Workspace > Scripts**, which works in
> both **Free** and **Studio**. External scripting and Workflow-Integration
> panels are Studio-only, but this plugin does not use them. If something here
> fails specifically in Free, note your edition.

---

## 0. Setup

- [ ] Resolve 18.6+ installed (note exact version + Free/Studio + OS).
- [ ] `ffmpeg` and `ffprobe` on PATH (`ffmpeg -version` works in a terminal).
      On macOS, GUI apps don't inherit your shell PATH — if step 1 reports
      ffmpeg missing, install via Homebrew and re-login.
- [ ] `git clone` the repo, `python3 install.py`, confirm it prints the
      installed launcher path.
- [ ] Restart Resolve. **PASS:** *Workspace > Scripts > Utility > Resolve AI
      Editor* exists.

---

## 1. Panel launches & reads the timeline (Phase 1 core)

- [ ] Open a project, open a timeline with a few talking-head clips that have
      audible pauses/silence.
- [ ] Run the menu item. **PASS:** your browser opens the panel at
      `http://127.0.0.1:<port>/?token=…` and the **Auto-Cut** tab shows the
      correct **Project**, **Timeline**, **FPS**, and **Clips (V1)** count,
      with a green "Resolve connected" badge.
- [ ] Note whether the **Detector** line says `ffmpeg silencedetect` or
      `webrtcvad + ffmpeg`.

If the badge is red / shows an error, copy the error text — that is the most
important thing to report.

---

## 2. One-click raw cut (Phase 1)

- [ ] On the Auto-Cut tab, leave the profile on **Manual**, click
      **✂ Create Raw Cut**.
- [ ] Watch the progress log (silence analysis → creating timeline).
- [ ] **PASS:** a new timeline named `<original> [AI Raw Cut]` appears in the
      Media Pool, the original timeline is **unchanged**, and the new timeline
      plays back with silences removed.
- [ ] Confirm the result stats (segments / removed / result seconds) look
      plausible for your footage.
- [ ] **Undo test:** delete the new timeline — original is intact. **PASS.**

Edge cases worth trying: a timeline with one clip; a timeline where clips share
the same source file; a timeline containing a compound/Fusion clip (it should be
*skipped and reported*, not crash).

---

## 3. Edit profiles (Phase 3)

- [ ] Re-run with profile **Short (TikTok/Reels)** on a 16:9 timeline.
      **PASS:** result is cut more aggressively than Manual, **and** an
      aspect-ratio warning appears (16:9 timeline vs 9:16 target).
- [ ] Re-run with **Long-form**. **PASS:** the opening seconds (hook) are kept
      intact even if they contain a pause; pacing is gentler.
- [ ] Confirm the per-profile **recommended manual steps** checklist shows in
      the result.

---

## 4. AI providers (Phase 2)

Only if you have an API key to test with (optional).

- [ ] Settings tab → AI Providers. Note the **key backend** line — is it your
      OS keychain, or the `0600 file (not encrypted)` fallback?
- [ ] Paste a key (e.g. OpenRouter free, or Anthropic), **Save**. **PASS:** the
      state shows "✓ stored" and the field clears (write-only).
- [ ] Set the matching tier provider/model under **Model Routing**, **Save
      routing**, then **Test**. **PASS:** it reports a reply + token counts +
      cost (or "cost unknown" for an unlisted model). A wrong key should give a
      clean "invalid API key", not a crash.

---

## 5. SFX/VFX assets (Phase 4)

- [ ] Assets tab → add a folder containing some named SFX (e.g. files with
      `whoosh`, `impact`, `riser` in the name), **Scan**. **PASS:** the count
      shows the number indexed and the kinds.
- [ ] **List recommendations**. **PASS:** you get a list mapping timecodes to
      SFX (hook → riser/impact, cuts → transition), with reasons. Cuts with no
      matching asset are shown in amber, not errors.
- [ ] **(Experimental) Auto-insert on new track** — this is the **least-tested
      path**; verify carefully:
  - **PASS:** a new audio track is added, the recommended SFX are placed on it
    at the right times, and **nothing else in the timeline changed**.
  - If it misplaces clips, places on the wrong track, or errors — capture the
    exact behaviour. This is the most valuable thing to report.

---

## 6. Context & sound (Phase 5)

- [ ] Sound tab → **Auto-suggest from timeline** (needs an AI key). **PASS:**
      audience/genre/topic fields populate with plausible values you can edit.
      (Optionally tick *sample frames* with an Anthropic key to test vision.)
- [ ] **Background Sound Research**, mode **Royalty-free**. **PASS:** 3
      directions + a list of real license-tagged sources.
- [ ] Switch to **Trend**. **PASS:** it is **off** and explains why; enabling it
      without a source asks for one; with a source it returns only search terms.
      **No track is ever downloaded or scraped.**

---

## Reporting

Open a GitHub issue with:

1. Resolve version, edition (Free/Studio), OS + version.
2. Which step number failed and the **exact** on-screen text / error.
3. For crashes: run Resolve from a terminal if you can, and include any Python
   traceback printed there.
4. For the raw cut / auto-insert: a one-line description of what the timeline
   looked like before vs. after.

Passing steps are useful too — a note of "steps 1–6 all PASS on Resolve 19.0
Studio / macOS 14" lets us drop the "untested on real Resolve" caveats.
