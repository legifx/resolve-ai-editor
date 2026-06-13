import pytest

from core.ai.base import AIError, AIResponse
from core.context import gather_signals, suggest_context
from core.context.signals import signals_to_prompt
from core.timeline.bridge import ResolveBridge
from core.timeline.mock import MockResolve


class StubProvider:
    name = "stub"
    supports_vision = False

    def __init__(self, reply):
        self._reply = reply

    def available(self):
        return True, "ok"

    def complete(self, prompt, system=None, max_tokens=1024, images=None):
        self.last_prompt = prompt
        self.last_images = images
        return AIResponse(text=self._reply, input_tokens=1, output_tokens=1,
                          model="stub", provider="stub", cost_usd=0.0)


def bridge():
    return ResolveBridge(MockResolve.with_demo_timeline())


def test_gather_signals():
    sig = gather_signals(bridge())
    assert sig["clip_count"] == 2
    assert "interview_a.mov" in sig["clip_filenames"]
    assert sig["resolution"] == "1920x1080"
    assert sig["fps"] == 25.0


def test_signals_to_prompt_compact():
    txt = signals_to_prompt(gather_signals(bridge()))
    assert "interview_a.mov" in txt
    assert "Clips: 2" in txt


def test_signals_caps_filenames():
    # synthesize many clips
    sig = {"timeline": "T", "clip_count": 100, "duration_seconds": 60,
           "fps": 25, "resolution": "1920x1080",
           "clip_filenames": ["clip%d.mov" % i for i in range(100)]}
    txt = signals_to_prompt(sig)
    assert "+60 more clips" in txt


def test_suggest_parses_json():
    reply = ('{"audience":"gamers","genre":"lets play","topic":"fps",'
             '"confidence":"high","note":"clear"}')
    out = suggest_context(bridge(), StubProvider(reply))
    assert out["audience"] == "gamers"
    assert out["genre"] == "lets play"
    assert out["confidence"] == "high"
    assert out["basis"] == "metadata only"
    assert "signals" in out


def test_suggest_handles_extra_text_around_json():
    reply = 'Here you go:\n{"audience":"a","genre":"g","topic":"t"}\nThanks!'
    out = suggest_context(bridge(), StubProvider(reply))
    assert out["genre"] == "g"


def test_suggest_raises_on_garbage():
    with pytest.raises(AIError):
        suggest_context(bridge(), StubProvider("not json at all"))


def test_suggest_no_frames_when_provider_lacks_vision():
    # use_frames requested but stub has supports_vision=False -> metadata only
    reply = '{"audience":"a","genre":"g","topic":"t"}'
    stub = StubProvider(reply)
    out = suggest_context(bridge(), stub, use_frames=True)
    assert "metadata only" in out["basis"]
    assert stub.last_images is None
