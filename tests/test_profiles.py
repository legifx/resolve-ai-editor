from core.analyze.silence import Interval
from core.cut.engine import CutParams, segments_for_clip, split_long
from core.cut.profiles import (DEFAULT_PROFILE, PROFILES, aspect_check,
                               get_profile)
from core.timeline.bridge import ClipInfo


def clip(source_start=0, source_end=250, fps=25.0):
    return ClipInfo(name="c", file_path="/x.mov",
                    timeline_start=0, timeline_end=source_end - source_start,
                    source_start=source_start, source_end=source_end, fps=fps)


# ---- profile catalogue ----

def test_profiles_exist():
    assert set(PROFILES) == {"long_form", "short", "ad"}
    assert DEFAULT_PROFILE in PROFILES


def test_get_profile_falls_back():
    assert get_profile("nonexistent").key == DEFAULT_PROFILE
    assert get_profile("short").key == "short"


def test_short_is_more_aggressive_than_long():
    s, l = PROFILES["short"].cut_params, PROFILES["long_form"].cut_params
    assert s.min_silence < l.min_silence   # shorter pauses cut
    assert s.padding < l.padding           # tighter
    assert PROFILES["short"].hook_seconds < PROFILES["long_form"].hook_seconds


def test_profile_to_dict_has_recommendations():
    d = PROFILES["short"].to_dict()
    assert d["aspect_ratio"] == "9:16"
    assert isinstance(d["recommendations"], list) and d["recommendations"]


# ---- split_long (pacing) ----

def test_split_long_subdivides():
    out = split_long([Interval(0.0, 10.0)], 4.0)
    # 10s / 4 -> 3 equal pieces of ~3.33s, contiguous
    assert len(out) == 3
    assert out[0].start == 0.0 and abs(out[-1].end - 10.0) < 1e-9
    for a, b in zip(out, out[1:]):
        assert abs(a.end - b.start) < 1e-9  # contiguous, no gaps


def test_split_long_leaves_short_alone():
    ivs = [Interval(0.0, 3.0)]
    assert split_long(ivs, 4.0) == ivs


def test_split_long_disabled():
    ivs = [Interval(0.0, 10.0)]
    assert split_long(ivs, None) == ivs
    assert split_long(ivs, 0) == ivs


# ---- hook protection ----

def test_hook_forces_opening_kept():
    # no speech detected at all, but hook protects first 2 s
    params = CutParams(padding=0.0, min_keep=0.5)
    segs = segments_for_clip(clip(), [], params, hook_seconds=2.0)
    assert segs  # the hook segment survives
    assert segs[0][0] == 0
    assert segs[0][1] == 50  # 2.0 s * 25 fps


def test_hook_segment_exempt_from_min_keep():
    # hook 0.3 s is shorter than min_keep 0.5, but must NOT be dropped
    params = CutParams(padding=0.0, min_keep=0.5)
    segs = segments_for_clip(clip(), [], params, hook_seconds=0.3)
    assert segs and segs[0] == (0, 8)  # round(0.3*25)=round(7.5)=8


def test_no_hook_by_default():
    params = CutParams(padding=0.0, min_keep=0.5)
    assert segments_for_clip(clip(), [], params) == []


def test_max_segment_adds_edit_points():
    # one long kept stretch 0..10 s, profile splits at 4 s
    params = CutParams(padding=0.0, min_keep=0.1)
    segs = segments_for_clip(clip(source_end=250), [Interval(0, 10)],
                             params, max_segment_seconds=4.0)
    assert len(segs) == 3  # 10s -> 3 edit points
    # contiguous frame ranges
    for a, b in zip(segs, segs[1:]):
        assert a[1] == b[0]


# ---- aspect check ----

def test_aspect_match_no_warning():
    assert aspect_check((1920, 1080), "16:9") is None
    assert aspect_check((1080, 1920), "9:16") is None


def test_aspect_mismatch_warns():
    w = aspect_check((1920, 1080), "9:16")
    assert w and "9:16" in w and "1920x1080" in w


def test_aspect_unknown_resolution():
    assert aspect_check(None, "16:9") is None
    assert aspect_check((0, 0), "16:9") is None
