"""API key storage — OS keychain first, restricted file as fallback.

Honesty note (prompt section 8): without a crypto dependency there is no
real encryption in the stdlib. We therefore do NOT pretend: preferred path
is the OS keychain via `keyring` (optional dep). The fallback is a JSON
file with 0600 permissions in the user config dir — access-restricted but
NOT encrypted, and the UI says so. Keys are write-only through the API:
they can be stored and deleted, never read back out to the panel.
"""

import json
import os
from typing import Dict, Optional

from config.settings import app_dir

SERVICE = "resolve-ai-editor"
PROVIDERS = ("anthropic", "openai", "openrouter", "custom")

try:
    import keyring  # type: ignore
    import keyring.errors  # type: ignore

    def _probe_keyring():
        # A backend can be "present" yet unusable (no Secret Service daemon,
        # locked wallet). get_keyring() does NOT catch that — only a real
        # set/get/delete round trip does. Probe once with a throwaway entry.
        try:
            keyring.set_password(SERVICE, "__probe__", "1")
            ok = keyring.get_password(SERVICE, "__probe__") == "1"
            keyring.delete_password(SERVICE, "__probe__")
            return ok
        except Exception:
            return False

    HAS_KEYRING = _probe_keyring()
except ImportError:
    keyring = None
    HAS_KEYRING = False


def _fallback_file() -> str:
    return os.path.join(app_dir(), "keys.json")


def _read_fallback() -> Dict[str, str]:
    try:
        with open(_fallback_file(), "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}


def _write_fallback(data: Dict[str, str]) -> None:
    path = _fallback_file()
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    os.chmod(path, 0o600)


def set_key(provider: str, key: str) -> None:
    if provider not in PROVIDERS:
        raise ValueError("unknown provider: %s" % provider)
    if not key:
        return delete_key(provider)
    if HAS_KEYRING:
        try:
            keyring.set_password(SERVICE, provider, key)
            return
        except Exception:
            pass  # backend became unusable — fall through to file
    data = _read_fallback()
    data[provider] = key
    _write_fallback(data)


def get_key(provider: str) -> Optional[str]:
    if HAS_KEYRING:
        try:
            return keyring.get_password(SERVICE, provider)
        except Exception:
            return None
    return _read_fallback().get(provider)


def delete_key(provider: str) -> None:
    if HAS_KEYRING:
        try:
            keyring.delete_password(SERVICE, provider)
        except Exception:
            pass
    else:
        data = _read_fallback()
        data.pop(provider, None)
        _write_fallback(data)


def status() -> Dict[str, object]:
    """For the UI: which providers have a key (never the key itself)."""
    return {
        "backend": "keychain" if HAS_KEYRING else "file (0600, not encrypted)",
        "configured": {p: bool(get_key(p)) for p in PROVIDERS},
    }
