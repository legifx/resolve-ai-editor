"""Provider + router tests. No real network calls — the OpenAI-compatible
HTTP layer is mocked so we exercise parsing and error mapping deterministically.
"""

import io
import json
import urllib.error

import pytest

import core.ai.keys as keys
from core.ai.anthropic_provider import AnthropicProvider
from core.ai.base import AIError
from core.ai.openai_compat import OpenAICompatProvider
from core.ai.router import build_provider, get_provider_for_tier
from config import settings


@pytest.fixture(autouse=True)
def file_backend(monkeypatch):
    monkeypatch.setattr(keys, "HAS_KEYRING", False)
    yield


# ---- router ----

def test_router_defaults():
    s = settings.load()
    routine = get_provider_for_tier("routine", s)
    complex_ = get_provider_for_tier("complex", s)
    assert routine.name == "openrouter"
    assert complex_.name == "anthropic"


def test_router_unknown_tier():
    with pytest.raises(AIError):
        get_provider_for_tier("nope", settings.load())


def test_build_custom_uses_base_url():
    p = build_provider("custom", "my-model", "https://host/v1")
    assert isinstance(p, OpenAICompatProvider)
    assert p.base_url == "https://host/v1"


# ---- availability guards (no key / no endpoint) ----

def test_openai_compat_unavailable_without_key():
    p = OpenAICompatProvider("openai", "gpt-4o-mini")
    ok, reason = p.available()
    assert not ok and "key" in reason.lower()


def test_custom_unavailable_without_url():
    p = OpenAICompatProvider("custom", "m")  # no base_url
    ok, reason = p.available()
    assert not ok and "endpoint" in reason.lower()


def test_anthropic_guard_message():
    # Either the SDK is missing or the key is — both must give a clear hint.
    p = AnthropicProvider()
    ok, reason = p.available()
    assert not ok
    assert ("pip install anthropic" in reason) or ("key" in reason.lower())


# ---- OpenAI-compatible parsing (mocked urlopen) ----

def _fake_response(body: dict):
    class _Resp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return json.dumps(body).encode()
    return _Resp()


def test_openai_compat_parses_completion(monkeypatch):
    keys.set_key("openai", "sk-test")
    p = OpenAICompatProvider("openai", "gpt-4o-mini")

    def fake_urlopen(req, timeout=None):
        # assert auth header + payload shape were built correctly
        assert req.headers["Authorization"] == "Bearer sk-test"
        sent = json.loads(req.data.decode())
        assert sent["model"] == "gpt-4o-mini"
        assert sent["messages"][-1]["content"] == "hello"
        return _fake_response({
            "choices": [{"message": {"content": "world"}}],
            "usage": {"prompt_tokens": 7, "completion_tokens": 3},
        })

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    resp = p.complete("hello", max_tokens=16)
    assert resp.text == "world"
    assert resp.input_tokens == 7 and resp.output_tokens == 3
    assert resp.provider == "openai" and resp.cost_usd is not None


def test_openai_compat_system_prompt_prepended(monkeypatch):
    keys.set_key("openai", "sk-test")
    p = OpenAICompatProvider("openai", "gpt-4o-mini")
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["msgs"] = json.loads(req.data.decode())["messages"]
        return _fake_response({"choices": [{"message": {"content": "ok"}}],
                               "usage": {}})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    p.complete("q", system="be terse")
    assert captured["msgs"][0] == {"role": "system", "content": "be terse"}


def test_openai_compat_maps_401(monkeypatch):
    keys.set_key("openrouter", "bad")
    p = OpenAICompatProvider("openrouter", "x")

    def fake_urlopen(req, timeout=None):
        raise urllib.error.HTTPError(
            req.full_url, 401, "Unauthorized", {},
            io.BytesIO(b'{"error":{"message":"nope"}}'))

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    with pytest.raises(AIError, match="invalid API key"):
        p.complete("q")


def test_openai_compat_network_error(monkeypatch):
    keys.set_key("openai", "k")
    p = OpenAICompatProvider("openai", "gpt-4o-mini")

    def fake_urlopen(req, timeout=None):
        raise urllib.error.URLError("no route")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    with pytest.raises(AIError, match="network error"):
        p.complete("q")


def test_openai_compat_bad_shape(monkeypatch):
    keys.set_key("openai", "k")
    p = OpenAICompatProvider("openai", "gpt-4o-mini")

    def fake_urlopen(req, timeout=None):
        return _fake_response({"unexpected": True})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    with pytest.raises(AIError, match="unexpected response"):
        p.complete("q")
