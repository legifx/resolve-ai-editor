from core.analyze.silence import Interval
from core.cut.engine import (CutParams, intersect, pad_and_merge,
                             segments_for_clip, summarize)
from core.timeline.bridge import ClipInfo


def clip(source_start=0, source_end=150, fps=25.0):
    return ClipInfo(name="c", file_path="/x.mov",
                    timeline_start=0, timeline_end=source_end - source_start,
                    source_start=source_start, source_end=source_end, fps=fps)


def test_intersect_clamps_and_drops():
    win = Interval(1.0, 5.0)
    ivs = [Interval(0.0, 2.0), Interval(4.5, 9.0), Interval(6.0, 7.0)]
    assert intersect(ivs, win) == [Interval(1.0, 2.0), Interval(4.5, 5.0)]


def test_pad_and_merge_overlap():
    win = Interval(0.0, 10.0)
    out = pad_and_merge([Interval(1.0, 2.0), Interval(2.1, 3.0)], 0.2, win)
    assert out == [Interval(0.8, 3.2)]  # padding bridges the 0.1 s gap


def test_pad_clamped_to_window():
    win = Interval(0.0, 3.0)
    out = pad_and_merge([Interval(0.05, 2.95)], 0.5, win)
    assert out == [Interval(0.0, 3.0)]


def test_segments_basic_mapping():
    # keeps at 0-2 s and 3.5-5 s, 25 fps, no trim
    params = CutParams(padding=0.0, min_keep=0.25)
    segs = segments_for_clip(clip(), [Interval(0, 2), Interval(3.5, 5)], params)
    assert segs == [(0, 50), (88, 125)]


def test_segments_respect_source_trim():
    # clip uses only source frames [100, 150) = seconds [4.0, 6.0)
    params = CutParams(padding=0.0, min_keep=0.25)
    segs = segments_for_clip(clip(source_start=100, source_end=150),
                             [Interval(0, 2), Interval(3.5, 5)], params)
    assert segs == [(100, 125)]  # only the 4.0-5.0 s part survives


def test_segments_drop_short():
    params = CutParams(padding=0.0, min_keep=0.5)
    segs = segments_for_clip(clip(), [Interval(1.0, 1.2)], params)
    assert segs == []


def test_summarize():
    c = clip()  # 150 frames @ 25 fps = 6 s
    stats = summarize([c], [[(0, 50), (88, 125)]])
    assert stats["clips"] == 1 and stats["segments"] == 2
    assert stats["input_seconds"] == 6.0
    assert stats["output_seconds"] == 3.48
    assert stats["removed_seconds"] == 2.52
