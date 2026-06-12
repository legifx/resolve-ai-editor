"""Cut-list engine — pure functions, no Resolve and no ffmpeg in here.

Editing rationale (documented per prompt section 3C):
- PADDING: hard cuts exactly at speech boundaries feel 'choppy' because
  natural speech has attack/decay; keeping ~100-150 ms around each
  segment preserves breath onsets and sentence tails.
- MIN_KEEP: segments shorter than ~250 ms read as flash frames; editors
  drop them rather than keep a syllable-long shot.
- MERGE: after padding, adjacent segments often overlap; merging them
  avoids zero-length gaps and duplicate frames in the rebuilt timeline.
"""

from dataclasses import dataclass
from typing import List, Tuple

from core.analyze.silence import Interval
from core.timeline.bridge import ClipInfo


@dataclass
class CutParams:
    padding: float = 0.12      # seconds kept before/after each speech segment
    min_keep: float = 0.25     # drop speech slivers shorter than this
    min_silence: float = 0.45  # pause length that qualifies as a cut point
    noise_db: float = -34.0    # silence loudness threshold (dBFS)

    @classmethod
    def from_settings(cls, s: dict) -> "CutParams":
        return cls(
            padding=float(s.get("padding", cls.padding)),
            min_keep=float(s.get("min_keep", cls.min_keep)),
            min_silence=float(s.get("min_silence", cls.min_silence)),
            noise_db=float(s.get("noise_db", cls.noise_db)),
        )


def intersect(intervals: List[Interval], window: Interval) -> List[Interval]:
    """Clamp intervals to a window, dropping everything outside."""
    out = []
    for iv in intervals:
        s, e = max(iv.start, window.start), min(iv.end, window.end)
        if e > s:
            out.append(Interval(s, e))
    return out


def pad_and_merge(keeps: List[Interval], padding: float,
                  window: Interval) -> List[Interval]:
    """Expand keeps by `padding` on both sides (clamped to window),
    then merge overlapping/adjacent results."""
    padded = [
        Interval(max(window.start, iv.start - padding),
                 min(window.end, iv.end + padding))
        for iv in sorted(keeps, key=lambda i: i.start)
    ]
    merged: List[Interval] = []
    for iv in padded:
        if merged and iv.start <= merged[-1].end:
            merged[-1] = Interval(merged[-1].start, max(merged[-1].end, iv.end))
        else:
            merged.append(iv)
    return merged


def segments_for_clip(clip: ClipInfo, keeps_file_seconds: List[Interval],
                      params: CutParams) -> List[Tuple[int, int]]:
    """Map speech intervals (seconds in the SOURCE FILE) to source-frame
    segments for this timeline clip.

    Only the part of the file the clip actually uses matters — a clip
    trimmed to source frames [100, 600) ignores speech outside it.

    Phase-1 limitation (documented in README): assumes clip fps equals
    timeline fps; retimed/speed-ramped clips are not supported yet.
    """
    fps = clip.fps
    window = Interval(clip.source_start / fps, clip.source_end / fps)
    keeps = intersect(keeps_file_seconds, window)
    keeps = pad_and_merge(keeps, params.padding, window)

    segments = []
    for iv in keeps:
        if iv.duration < params.min_keep:
            continue
        start_f = int(round(iv.start * fps))
        end_f = int(round(iv.end * fps))
        if end_f > start_f:
            segments.append((start_f, end_f))
    return segments


def summarize(clips: List[ClipInfo],
              all_segments: List[List[Tuple[int, int]]]) -> dict:
    """Stats for the UI: how much material the raw cut removes."""
    total_in = sum(c.duration_frames for c in clips)
    total_out = sum(e - s for segs in all_segments for (s, e) in segs)
    fps = clips[0].fps if clips else 25.0
    return {
        "clips": len(clips),
        "segments": sum(len(s) for s in all_segments),
        "input_seconds": round(total_in / fps, 2),
        "output_seconds": round(total_out / fps, 2),
        "removed_seconds": round((total_in - total_out) / fps, 2),
    }
