"""Integration tests: full raw-cut pipeline on mock Resolve + real ffmpeg."""

import pytest

from config import settings
from core.cut import run_raw_cut
from core.timeline.bridge import CapabilityError, ResolveBridge
from core.timeline.mock import (MockMediaPoolItem, MockProject, MockResolve,
                                MockTimeline, MockTimelineItem)


def make_resolve(wav, n_clips=1):
    resolve = MockResolve(MockProject(fps=25.0))
    tl = resolve.project.current_timeline
    mp = MockMediaPoolItem(wav, 25.0)
    tl.items = [MockTimelineItem("c%d" % i, i * 150, (i + 1) * 150, 0, mp)
                for i in range(n_clips)]
    return resolve


def test_full_pipeline(tone_silence_wav):
    resolve = make_resolve(tone_silence_wav)
    report = run_raw_cut(ResolveBridge(resolve), settings.load())
    assert report["timeline"] == "Demo Timeline [AI Raw Cut]"
    assert report["segments"] == 2
    assert report["input_seconds"] == 6.0
    # tone parts are 2 s + 1.5 s plus padding on four edges
    assert 3.4 < report["output_seconds"] < 4.2
    # the new timeline really exists in the (mock) project
    names = [t.GetName() for t in resolve.project.timelines]
    assert "Demo Timeline [AI Raw Cut]" in names


def test_unique_name_on_second_run(tone_silence_wav):
    resolve = make_resolve(tone_silence_wav)
    bridge = ResolveBridge(resolve)
    run_raw_cut(bridge, settings.load())
    # back to original timeline, run again -> name suffix ' 2'
    resolve.project.current_timeline = resolve.project.timelines[0]
    report2 = run_raw_cut(bridge, settings.load())
    assert report2["timeline"] == "Demo Timeline [AI Raw Cut] 2"


def test_cache_hit_on_second_analysis(tone_silence_wav):
    resolve = make_resolve(tone_silence_wav)
    log = []
    run_raw_cut(ResolveBridge(resolve), settings.load(), log.append)
    resolve.project.current_timeline = resolve.project.timelines[0]
    log2 = []
    run_raw_cut(ResolveBridge(resolve), settings.load(), log2.append)
    assert any("silence analysis" in m for m in log)
    assert any("cache hit" in m for m in log2)


def test_shared_source_analyzed_once(tone_silence_wav):
    resolve = make_resolve(tone_silence_wav, n_clips=3)
    log = []
    report = run_raw_cut(ResolveBridge(resolve), settings.load(), log.append)
    assert report["clips"] == 3 and report["segments"] == 6
    assert sum("analysis" in m for m in log) == 1  # one file, one analysis


def test_empty_timeline_raises():
    resolve = MockResolve(MockProject())
    with pytest.raises(CapabilityError, match="no clips"):
        run_raw_cut(ResolveBridge(resolve), settings.load())


def test_clip_without_media_path_is_skipped(tone_silence_wav):
    resolve = make_resolve(tone_silence_wav)
    tl = resolve.project.current_timeline
    tl.items.append(MockTimelineItem("fusion_comp", 150, 200, 0, None))
    report = run_raw_cut(ResolveBridge(resolve), settings.load())
    assert report["skipped_clips"] == ["fusion_comp"]
    assert report["clips"] == 1


def test_settings_roundtrip():
    saved = settings.save({"noise_db": -40.0, "bogus_key": 1})
    assert saved["noise_db"] == -40.0
    assert "bogus_key" not in saved
    assert settings.load()["noise_db"] == -40.0


def make_resolve_res(wav, width, height):
    resolve = MockResolve(MockProject(fps=25.0))
    tl = MockTimeline("Src", 25.0, width=width, height=height)
    resolve.project.current_timeline = tl
    resolve.project.timelines = [tl]
    tl.items = [MockTimelineItem("c", 0, 150, 0, MockMediaPoolItem(wav, 25.0))]
    return resolve


def test_profile_report_fields(tone_silence_wav):
    resolve = make_resolve_res(tone_silence_wav, 1920, 1080)
    report = run_raw_cut(ResolveBridge(resolve), settings.load(),
                         profile_key="short")
    assert report["profile"] == "Short (TikTok / Reels / Shorts)"
    assert report["aspect_ratio"] == "9:16"
    assert report["recommendations"]
    # 16:9 timeline vs 9:16 profile -> warning
    assert report["aspect_warning"] and "9:16" in report["aspect_warning"]


def test_profile_aspect_match_no_warning(tone_silence_wav):
    resolve = make_resolve_res(tone_silence_wav, 1080, 1920)  # 9:16 source
    report = run_raw_cut(ResolveBridge(resolve), settings.load(),
                         profile_key="short")
    assert report["aspect_warning"] is None


def test_no_profile_no_profile_fields(tone_silence_wav):
    resolve = make_resolve_res(tone_silence_wav, 1920, 1080)
    report = run_raw_cut(ResolveBridge(resolve), settings.load())
    assert "profile" not in report
    assert "aspect_warning" not in report

