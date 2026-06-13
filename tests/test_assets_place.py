import pytest

from core.assets.place import place_assets
from core.timeline.bridge import CapabilityError, ResolveBridge
from core.timeline.mock import MockResolve


def placements():
    return [
        {"frame": 0, "moment": "hook", "category": "riser",
         "asset_path": "/lib/riser.wav", "asset_name": "riser.wav",
         "reason": "r"},
        {"frame": 500, "moment": "cut", "category": "transition",
         "asset_path": "/lib/whoosh.wav", "asset_name": "whoosh.wav",
         "reason": "w"},
    ]


def index():
    return {
        "/lib/riser.wav": {"duration": 1.2},
        "/lib/whoosh.wav": {"duration": 0.5},
    }


def test_place_inserts_on_new_track():
    resolve = MockResolve.with_demo_timeline(fps=25.0)
    bridge = ResolveBridge(resolve)
    report = place_assets(bridge, placements(), index(), 25.0)
    assert report["placed"] == 2
    assert report["track"] == "A2"          # a new audio track was added
    assert report["missing_asset"] == []

    mp = resolve.project.media_pool
    assert set(p.split("/")[-1] for p in mp.imported) == {"riser.wav", "whoosh.wav"}
    audio = [ci for call in mp.append_calls for ci in call
             if ci.get("mediaType") == 2]
    frames = sorted((ci["recordFrame"], ci["endFrame"]) for ci in audio)
    assert frames == [(0, 30), (500, 12)]   # 1.2s*25=30, 0.5s*25=12


def test_place_reports_missing():
    recs = placements() + [
        {"frame": 800, "moment": "cut", "category": "ui",
         "asset_path": None, "asset_name": None, "reason": "no ui sfx"}]
    report = place_assets(ResolveBridge(MockResolve.with_demo_timeline()),
                          recs, index(), 25.0)
    assert report["placed"] == 2
    assert report["missing_asset"] == ["cut"]


def test_place_nothing_to_insert():
    recs = [{"frame": 0, "moment": "hook", "category": "riser",
             "asset_path": None, "asset_name": None, "reason": "none"}]
    with pytest.raises(CapabilityError, match="nothing to insert"):
        place_assets(ResolveBridge(MockResolve.with_demo_timeline()),
                     recs, index(), 25.0)


def test_place_unknown_duration_falls_back():
    recs = [{"frame": 0, "moment": "hook", "category": "riser",
             "asset_path": "/lib/x.wav", "asset_name": "x.wav", "reason": "r"}]
    resolve = MockResolve.with_demo_timeline(fps=25.0)
    place_assets(ResolveBridge(resolve), recs, {}, 25.0)  # empty index
    audio = [ci for call in resolve.project.media_pool.append_calls
             for ci in call if ci.get("mediaType") == 2]
    assert audio[0]["endFrame"] == 25  # 1.0s fallback * 25 fps
