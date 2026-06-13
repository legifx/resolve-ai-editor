"""Key storage tests — force the file fallback so they're deterministic
regardless of the host keychain. The isolated_config fixture points the
config dir at a tmp path."""

import os

import pytest

import core.ai.keys as keys


@pytest.fixture(autouse=True)
def force_file_backend(monkeypatch):
    monkeypatch.setattr(keys, "HAS_KEYRING", False)
    yield


def test_set_get_delete_roundtrip():
    assert keys.get_key("openai") is None
    keys.set_key("openai", "sk-secret")
    assert keys.get_key("openai") == "sk-secret"
    keys.delete_key("openai")
    assert keys.get_key("openai") is None


def test_empty_key_deletes():
    keys.set_key("openrouter", "x")
    keys.set_key("openrouter", "")  # empty => delete
    assert keys.get_key("openrouter") is None


def test_unknown_provider_rejected():
    with pytest.raises(ValueError):
        keys.set_key("bogus", "x")


def test_fallback_file_is_0600():
    keys.set_key("anthropic", "sk-ant")
    mode = os.stat(keys._fallback_file()).st_mode & 0o777
    assert mode == 0o600


def test_status_reports_presence_not_value():
    keys.set_key("custom", "topsecret")
    s = keys.status()
    assert s["configured"]["custom"] is True
    assert s["configured"]["openai"] is False
    # the value must never appear in the status blob
    assert "topsecret" not in str(s)
    assert "not encrypted" in s["backend"]
