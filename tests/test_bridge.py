import pytest

from core.timeline.bridge import CapabilityError, ResolveBridge, acquire_resolve
from core.timeline.mock import MockResolve


@pytest.fixture
def bridge():
    return ResolveBridge(MockResolve.with_demo_timeline())


def test_acquire_prefers_injected_object():
    sentinel = object()
    assert acquire_resolve(sentinel) is sentinel


def test_acquire_without_resolve_raises_clear_error():
    with pytest.raises(CapabilityError) as exc:
        acquire_resolve(None)
    assert "Workspace > Scripts" in str(exc.value)


def test_project_info(bridge):
    info = bridge.project_info()
    assert info["connected"] is True
    assert info["project"] == "Demo Project"
    assert info["fps"] == 25.0 and info["clip_count"] == 2


def test_clips_snapshot(bridge):
    clips = bridge.clips()
    assert [c.name for c in clips] == ["interview_a.mov", "broll_b.mov"]
    b = clips[1]
    assert (b.timeline_start, b.timeline_end) == (500, 800)
    assert (b.source_start, b.source_end) == (100, 400)
    assert b.file_path == "/demo/broll_b.mov"


def test_create_cut_timeline_appends_segments(bridge):
    mp_item = bridge.clips()[0].media_pool_item
    segs = [{"media_pool_item": mp_item, "start_frame": 0, "end_frame": 50},
            {"media_pool_item": mp_item, "start_frame": 88, "end_frame": 125}]
    tl = bridge.create_cut_timeline("Cut v1", segs)
    assert tl.GetName() == "Cut v1"
    assert [(i.GetStart(), i.GetEnd()) for i in tl.items] == [(0, 50), (50, 87)]


def test_create_cut_timeline_duplicate_name_fails(bridge):
    mp_item = bridge.clips()[0].media_pool_item
    segs = [{"media_pool_item": mp_item, "start_frame": 0, "end_frame": 10}]
    bridge.create_cut_timeline("Cut v1", segs)
    with pytest.raises(CapabilityError, match="already exist"):
        bridge.create_cut_timeline("Cut v1", segs)


def test_create_cut_timeline_empty_list(bridge):
    with pytest.raises(CapabilityError, match="empty"):
        bridge.create_cut_timeline("x", [])


def test_segments_without_media_pool_item(bridge):
    with pytest.raises(CapabilityError, match="Media Pool"):
        bridge.create_cut_timeline(
            "x", [{"media_pool_item": None, "start_frame": 0, "end_frame": 5}])
