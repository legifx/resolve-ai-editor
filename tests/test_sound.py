from core.ai.base import AIResponse
from core.sound import CURATED_SOURCES, MODES, research


class StubProvider:
    name = "stub"

    def __init__(self, reply, available=True):
        self._reply = reply
        self._available = available

    def available(self):
        return (self._available, "ok" if self._available else "no key")

    def complete(self, prompt, system=None, max_tokens=1024, images=None):
        return AIResponse(text=self._reply, input_tokens=1, output_tokens=1,
                          model="stub", provider="stub", cost_usd=0.0)


CTX = {"audience": "young adults", "genre": "travel vlog", "topic": "beach"}


# ---- royalty-free mode ----

def test_royalty_free_fallback_without_provider():
    r = research(CTX)
    assert r["mode"] == "royalty_free"
    assert len(r["suggestions"]) == 3
    assert len(r["sources"]) == len(CURATED_SOURCES)
    # every suggestion carries a license
    for s in r["suggestions"]:
        assert s["license"]
        assert "commercial_ok" in s


def test_curated_sources_have_license_flags():
    for s in CURATED_SOURCES:
        assert s["license"]
        assert isinstance(s["commercial_ok"], bool)
        assert isinstance(s["attribution_required"], bool)
        assert s["url"].startswith("http")


def test_royalty_free_uses_provider():
    reply = ('[{"style":"Lo-fi","description":"chill","search_terms":["lofi"]},'
             '{"style":"Tropical","description":"warm","search_terms":["tropical house"]},'
             '{"style":"Acoustic","description":"soft","search_terms":["acoustic"]}]')
    r = research(CTX, provider=StubProvider(reply))
    styles = [s["style"] for s in r["suggestions"]]
    assert "Lo-fi" in styles
    # AI suggestions still get a license attached
    assert all(s["license"] for s in r["suggestions"])


def test_royalty_free_falls_back_on_bad_ai():
    r = research(CTX, provider=StubProvider("garbage"))
    assert len(r["suggestions"]) == 3  # static fallback


# ---- trend mode (compliance) ----

def test_trend_disabled_by_default():
    r = research(CTX, mode="trend")
    assert r["enabled"] is False
    assert r["suggestions"] == []
    assert "does not scrape" in r["message"]


def test_trend_enabled_without_source():
    r = research(CTX, mode="trend", trend_enabled=True)
    assert r["enabled"] is True
    assert r["suggestions"] == []
    assert "no permitted source" in r["message"]


def test_trend_enabled_with_source_terms_only():
    r = research(CTX, mode="trend", trend_enabled=True,
                 trend_source="my-licensed-feed")
    assert r["source"] == "my-licensed-feed"
    assert r["suggestions"]                       # search terms present
    assert "search_terms" in r["suggestions"][0]
    # never fabricates tracks/links — only terms + a disclaimer
    assert "does not scrape" in r["message"]


def test_modes_constant():
    assert set(MODES) == {"royalty_free", "trend"}
