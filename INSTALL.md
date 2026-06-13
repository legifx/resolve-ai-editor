# Installation

## 1. Requirements

| What | Why | Check |
|---|---|---|
| DaVinci Resolve 18.6+ (Free **or** Studio) | host application | — |
| Python 3.6+ | plugin runtime (Resolve runs menu scripts with its configured Python) | `python3 --version` |
| **ffmpeg** (incl. ffprobe) | local audio analysis — the only system dependency | `ffmpeg -version` |

Install ffmpeg:

- **Windows:** `winget install ffmpeg` (or download from ffmpeg.org and add to PATH)
- **macOS:** `brew install ffmpeg`
- **Linux:** `sudo apt install ffmpeg`

Optional (better speech detection): `pip install webrtcvad` — auto-detected,
everything works without it.

## 2. Install the plugin

```bash
git clone https://github.com/legifx/resolve-ai-editor.git
cd resolve-ai-editor
python3 install.py
```

`install.py` writes a one-file launcher named **“Resolve AI Editor.py”** into
Resolve's user scripts folder:

| OS | Launcher location |
|---|---|
| Windows | `%APPDATA%\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility\` |
| macOS | `~/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility/` |
| Linux | `~/.local/share/DaVinciResolve/Fusion/Scripts/Utility/` |

The launcher only contains the absolute path to your cloned repo — keep the
repo where it is (or re-run `install.py` after moving it).

## 3. Run it

1. Start Resolve, open a project **and a timeline**.
2. Menu: **Workspace > Scripts > Utility > Resolve AI Editor**
   (restart Resolve once if the entry is missing).
3. Your browser opens `http://127.0.0.1:<port>/?token=…` — that's the panel.
   It only listens on localhost and requires the session token.

## 4. Uninstall

```bash
python3 install.py --uninstall   # removes the launcher
```

Then delete the cloned repo folder and (optionally) the config dir:
`~/.config/resolve-ai-editor` (Linux), `~/Library/Application
Support/resolve-ai-editor` (macOS), `%APPDATA%\resolve-ai-editor` (Windows).

## Troubleshooting

- **“ffmpeg/ffprobe not found”** — install ffmpeg and make sure it's on the
  PATH that Resolve sees (on macOS, GUI apps don't inherit your shell PATH;
  installing via Homebrew into `/opt/homebrew/bin` plus a logout/login
  usually fixes it).
- **Panel says “not connected”** — open a project and a timeline in Resolve,
  the status refreshes automatically every 5 s.
- **“No timeline is open”** — switch to the Edit page and click into the
  timeline once.
- **Script entry missing in the menu** — verify the launcher file exists at
  the path above; restart Resolve.

## Tested platforms (honest list)

- Linux (headless, against the mock + ffmpeg pipeline, full test suite): ✅
- Windows + real Resolve: **not yet tested** — reports welcome
- macOS + real Resolve: **not yet tested** — reports welcome

If you have real Resolve, please run through **[VERIFY.md](VERIFY.md)** — a
step-by-step checklist with pass criteria for every feature. Reporting back
(pass or fail) is what lets us drop the "untested on real Resolve" caveats.
