"""User settings + cache locations. Local only, never synced anywhere.

API keys are NOT handled here in Phase 1 — the AI provider layer
(Phase 2) will add OS-keychain storage. This module must never hold
secrets in plain text.
"""

import json
import os
import sys
import tempfile

APP_NAME = "resolve-ai-editor"

DEFAULTS = {
    # Auto-cut parameters (UI: Auto-Cut tab)
    "noise_db": -34.0,       # loudness threshold for 'silence'
    "min_silence": 0.45,     # seconds of quiet before we call it a pause
    "padding": 0.12,         # seconds kept before/after each speech segment
    "min_keep": 0.25,        # drop speech slivers shorter than this
    "use_vad": True,         # prefer webrtcvad when installed
    "vad_aggressiveness": 2, # 0..3
}


def app_dir() -> str:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    path = os.path.join(base, APP_NAME)
    os.makedirs(path, exist_ok=True)
    return path


def cache_dir() -> str:
    path = os.path.join(app_dir(), "analysis_cache")
    os.makedirs(path, exist_ok=True)
    return path


def _settings_file() -> str:
    return os.path.join(app_dir(), "settings.json")


def load() -> dict:
    merged = dict(DEFAULTS)
    try:
        with open(_settings_file(), "r", encoding="utf-8") as fh:
            stored = json.load(fh)
        merged.update({k: stored[k] for k in DEFAULTS if k in stored})
    except (OSError, json.JSONDecodeError):
        pass
    return merged


def save(values: dict) -> dict:
    """Persist only known keys (atomic write). Returns the merged result."""
    current = load()
    current.update({k: values[k] for k in DEFAULTS if k in values})
    fd, tmp = tempfile.mkstemp(dir=app_dir(), suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(current, fh, indent=2)
    os.replace(tmp, _settings_file())
    return current
