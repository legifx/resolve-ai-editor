from core.assets.match import cut_points, recommend, _timecode
from core.timeline.bridge import ClipInfo


def clip(name, tl_start, tl_end, fps=25.0):
    return ClipInfo(name=name, file_path="/%s.mov" % name,
                    timeline_start=tl_start, timeline_end=tl_end,
                    source_start=0, source_end=tl_end - tl_start, fps=fps)


def fake_index():
    def e(name, cat):
        return {"path": "/lib/%s" % name, "name": name, "kind": "sfx",
                "category": cat, "tags": [], "duration": 0.5}
    items = [e("whoosh_a.wav", "transition"), e("whoosh_b.wav", "transition"),
             e("riser.wav", "riser"), e("boom.wav", "impact")]
    return {it["path"]: it for it in items}


def test_timecode():
    assert _timecode(0, 25.0) == "00:00:00:00"
    assert _timecode(25, 25.0) == "00:00:01:00"
    assert _timecode(513, 25.0) == "00:00:20:13"


def test_cut_points_hook_then_cuts():
    clips = [clip("a", 0, 500), clip("b", 500, 800), clip("c", 800, 1000)]
    pts = cut_points(clips)
    assert pts == [(0, "hook"), (500, "cut"), (800, "cut")]


def test_cut_points_orders_by_start():
    clips = [clip("b", 500, 800), clip("a", 0, 500)]
    assert cut_points(clips)[0] == (0, "hook")


def test_cut_points_empty():
    assert cut_points([]) == []


def test_recommend_maps_hook_and_cut():
    clips = [clip("a", 0, 500), clip("b", 500, 800)]
    recs = recommend(clips, fake_index(), 25.0)
    assert len(recs) == 2
    assert recs[0]["moment"] == "hook" and recs[0]["category"] == "riser"
    assert recs[1]["moment"] == "cut" and recs[1]["category"] == "transition"
    assert recs[0]["asset_name"] == "riser.wav"


def test_recommend_rotates_within_category():
    # three cuts, two transition assets -> a, b, a
    clips = [clip("a", 0, 500), clip("b", 500, 800),
             clip("c", 800, 1000), clip("d", 1000, 1200)]
    recs = recommend(clips, fake_index(), 25.0)
    cut_assets = [r["asset_name"] for r in recs if r["moment"] == "cut"]
    assert cut_assets == ["whoosh_a.wav", "whoosh_b.wav", "whoosh_a.wav"]


def test_recommend_no_matching_asset():
    # index with only UI sounds -> hook prefs (riser/impact/transition) miss
    idx = {"/lib/click.wav": {"path": "/lib/click.wav", "name": "click.wav",
           "kind": "sfx", "category": "ui", "tags": [], "duration": 0.2}}
    recs = recommend([clip("a", 0, 500)], idx, 25.0)
    assert recs[0]["asset_path"] is None
    assert "add one" in recs[0]["reason"].lower() or "No '" in recs[0]["reason"]


def test_recommend_ignores_non_sfx():
    idx = {"/lib/b.mov": {"path": "/lib/b.mov", "name": "b.mov", "kind": "vfx",
           "category": "transition", "tags": [], "duration": 2.0}}
    recs = recommend([clip("a", 0, 500), clip("b", 500, 800)], idx, 25.0)
    # vfx is not used for SFX placement -> no asset chosen
    assert all(r["asset_path"] is None for r in recs)


class _StubProvider:
    """Returns a canned JSON array re-picking the hook asset."""
    def __init__(self, reply): self._reply = reply
    def complete(self, prompt, system=None, max_tokens=1024):
        from core.ai.base import AIResponse
        return AIResponse(text=self._reply, input_tokens=1, output_tokens=1,
                          model="stub", provider="stub", cost_usd=0.0)


def test_llm_refine_overrides_pick():
    clips = [clip("a", 0, 500)]
    reply = '[{"i":0,"asset_name":"boom.wav","reason":"punchier hook"}]'
    recs = recommend(clips, fake_index(), 25.0, provider=_StubProvider(reply))
    assert recs[0]["asset_name"] == "boom.wav"
    assert recs[0]["reason"] == "punchier hook"


def test_llm_refine_falls_back_on_garbage():
    clips = [clip("a", 0, 500)]
    recs = recommend(clips, fake_index(), 25.0,
                     provider=_StubProvider("not json at all"))
    # heuristic pick stands
    assert recs[0]["asset_name"] == "riser.wav"


def test_llm_refine_rejects_unknown_asset():
    clips = [clip("a", 0, 500)]
    reply = '[{"i":0,"asset_name":"does_not_exist.wav","reason":"x"}]'
    recs = recommend(clips, fake_index(), 25.0, provider=_StubProvider(reply))
    assert recs[0]["asset_name"] == "riser.wav"  # unchanged
