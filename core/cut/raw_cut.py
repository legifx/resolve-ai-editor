"""One-click raw cut orchestration.

Flow (all local, no LLM):
  read clips -> analyze each unique source file (cached) -> build
  keep-segments -> create a NEW timeline '<name> [AI Raw Cut]'.

Non-destructive by design: the original timeline is never touched.
Undo = delete the generated timeline (or just switch back).
"""

import os
from typing import Callable, List, Optional

from core.analyze import audio, cache
from core.analyze.silence import Interval, detect_silences, invert_silences
from core.analyze.vad import detect_speech_vad, HAS_WEBRTCVAD
from core.cut.engine import CutParams, segments_for_clip, summarize
from core.cut.profiles import aspect_check, get_profile
from core.timeline.bridge import CapabilityError, ResolveBridge

ProgressFn = Callable[[str], None]


def _keeps_for_file(path: str, params: CutParams, use_vad: bool,
                    vad_aggressiveness: int,
                    progress: ProgressFn) -> List[Interval]:
    """Speech ('keep') intervals for one media file, with persistent cache."""
    cache_params = {
        "v": 1, "noise_db": params.noise_db, "min_silence": params.min_silence,
        "vad": bool(use_vad and HAS_WEBRTCVAD), "vad_aggr": vad_aggressiveness,
    }
    cached = cache.get(path, cache_params)
    if cached is not None:
        progress("cache hit: %s" % os.path.basename(path))
        return [Interval(s, e) for s, e in cached]

    duration = audio.media_duration(path)
    keeps: Optional[List[Interval]] = None
    if use_vad and HAS_WEBRTCVAD:
        progress("VAD analysis: %s" % os.path.basename(path))
        wav = audio.extract_audio(path)
        try:
            keeps = detect_speech_vad(wav, vad_aggressiveness,
                                      min_gap=params.min_silence)
        finally:
            try:
                os.remove(wav)
            except OSError:
                pass
    if keeps is None:  # default path: ffmpeg silencedetect
        progress("silence analysis: %s" % os.path.basename(path))
        silences = detect_silences(path, params.noise_db, params.min_silence)
        keeps = invert_silences(silences, duration, min_keep=params.min_keep)

    cache.put(path, cache_params, [[iv.start, iv.end] for iv in keeps])
    return keeps


def run_raw_cut(bridge: ResolveBridge, settings: dict,
                progress: ProgressFn = lambda msg: None,
                profile_key: str = None) -> dict:
    """Execute the one-click raw cut. Returns a report dict for the UI.

    profile_key selects an EditProfile (long_form / short / ad). When given,
    the profile's tuned cut params, hook protection and pacing apply, and the
    report carries an aspect-ratio warning + a recommendations checklist.
    When None, the user's manual Settings params are used (Phase-1 behaviour).
    """
    profile = get_profile(profile_key) if profile_key else None
    if profile is not None:
        params = profile.cut_params
        hook_seconds = profile.hook_seconds
        max_segment = profile.max_segment_seconds
    else:
        params = CutParams.from_settings(settings)
        hook_seconds, max_segment = 0.0, None
    use_vad = bool(settings.get("use_vad", True))
    vad_aggr = int(settings.get("vad_aggressiveness", 2))

    clips = bridge.clips()
    if not clips:
        raise CapabilityError("Timeline has no clips on video track 1.")
    # Capture the SOURCE timeline's resolution now — create_cut_timeline below
    # switches the current timeline to the new one (Resolve makes a freshly
    # created timeline current), after which this would read the wrong one.
    source_resolution = bridge.timeline_resolution()

    # analyze each unique file once (multiple clips often share a source)
    keeps_by_file = {}
    skipped = []
    for clip in clips:
        if not clip.file_path:
            skipped.append(clip.name)
            continue
        if clip.file_path not in keeps_by_file:
            keeps_by_file[clip.file_path] = _keeps_for_file(
                clip.file_path, params, use_vad, vad_aggr, progress)

    analyzed = [c for c in clips if c.file_path]
    # the hook lives at the very start of the finished video = the clip with
    # the smallest timeline_start; protect only that one's opening seconds.
    first_clip = min(analyzed, key=lambda c: c.timeline_start) if analyzed else None
    all_segments = [
        segments_for_clip(
            c, keeps_by_file[c.file_path], params,
            hook_seconds=hook_seconds if c is first_clip else 0.0,
            max_segment_seconds=max_segment)
        for c in analyzed
    ]

    cut_list = [
        {"media_pool_item": clip.media_pool_item,
         "start_frame": start, "end_frame": end}
        for clip, segs in zip(analyzed, all_segments)
        for (start, end) in segs
    ]
    if not cut_list:
        raise CapabilityError(
            "No speech segments found — thresholds may be too aggressive. "
            "Try a lower 'silence threshold' (e.g. -40 dB) in Settings.")

    # unique timeline name: '<orig> [AI Raw Cut]', then ' 2', ' 3', ...
    base = "%s [AI Raw Cut]" % bridge.current_timeline().GetName()
    new_tl = None
    for n in range(1, 50):
        name = base if n == 1 else "%s %d" % (base, n)
        try:
            progress("creating timeline: %s" % name)
            new_tl = bridge.create_cut_timeline(name, cut_list)
            break
        except CapabilityError as exc:
            if "already exist" not in str(exc):
                raise
    if new_tl is None:
        raise CapabilityError("Could not find a free timeline name.")

    report = summarize(analyzed, all_segments)
    report["timeline"] = name
    report["skipped_clips"] = skipped  # e.g. compound/Fusion clips
    if profile is not None:
        report["profile"] = profile.label
        report["aspect_ratio"] = profile.aspect_ratio
        report["recommendations"] = list(profile.recommendations)
        warning = aspect_check(source_resolution, profile.aspect_ratio)
        report["aspect_warning"] = warning  # None when it matches
    return report
