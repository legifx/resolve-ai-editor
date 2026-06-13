import base64
import subprocess

import pytest

from core.context.frames import (HAS_VISION, _extract_one,
                                 sample_timeline_frames)
from core.timeline.bridge import ResolveBridge
from core.timeline.mock import (MockMediaPoolItem, MockProject, MockResolve,
                                MockTimeline, MockTimelineItem)


@pytest.fixture
def video(tmp_path):
    path = str(tmp_path / "clip.mp4")
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-t", "2",
         "-i", "testsrc=size=320x240:rate=25", path], check=True)
    return path


def test_extract_one_returns_base64(video):
    b64 = _extract_one(video, 1.0)
    assert b64
    # decodes cleanly and looks like a JPEG (starts with 0xFFD8)
    raw = base64.b64decode(b64)
    assert raw[:2] == b"\xff\xd8"


def test_extract_one_bad_path():
    assert _extract_one("/no/such/file.mp4", 0.0) == ""


def test_has_vision_flag():
    class Yes:
        supports_vision = True
    class No:
        supports_vision = False
    assert HAS_VISION(Yes()) is True
    assert HAS_VISION(No()) is False


def test_sample_frames_from_real_video(video):
    resolve = MockResolve(MockProject(fps=25.0))
    tl = resolve.project.current_timeline
    tl.items = [MockTimelineItem("clip.mp4", 0, 50, 0,
                                 MockMediaPoolItem(video, 25.0))]
    frames = sample_timeline_frames(ResolveBridge(resolve), max_frames=2)
    assert len(frames) == 1
    assert frames[0]["media_type"] == "image/jpeg"
    assert frames[0]["data"]


def test_sample_frames_skips_nonexistent_paths():
    # the default demo timeline points at /demo/*.mov which don't exist
    resolve = MockResolve.with_demo_timeline()
    assert sample_timeline_frames(ResolveBridge(resolve)) == []
