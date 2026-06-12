"""Silence / speech-pause detection — fully local, no LLM involved.

Default detector: ffmpeg `silencedetect` (zero Python dependencies).
Optional detector: webrtcvad (auto-used when installed, see vad.py).

All times are float seconds relative to the start of the media file.
"""

import re
from dataclasses import dataclass
from typing import List

from .audio import _run, FfmpegError, media_duration


@dataclass(frozen=True)
class Interval:
    start: float
    end: float

    @property
    def duration(self) -> float:
        return self.end - self.start


# ffmpeg prints e.g.:
#   [silencedetect @ 0x...] silence_start: 3.2452
#   [silencedetect @ 0x...] silence_end: 5.103 | silence_duration: 1.8578
_RE_START = re.compile(r"silence_start:\s*(-?[\d.]+)")
_RE_END = re.compile(r"silence_end:\s*(-?[\d.]+)")


def parse_silencedetect(stderr_text: str, total_duration: float) -> List[Interval]:
    """Parse ffmpeg silencedetect stderr into silence intervals.

    Handles the trailing case where silence runs until EOF (ffmpeg then
    emits a silence_start without a matching silence_end).
    """
    silences = []
    pending_start = None
    for line in stderr_text.splitlines():
        m = _RE_START.search(line)
        if m:
            pending_start = max(0.0, float(m.group(1)))
            continue
        m = _RE_END.search(line)
        if m and pending_start is not None:
            end = min(float(m.group(1)), total_duration)
            if end > pending_start:
                silences.append(Interval(pending_start, end))
            pending_start = None
    if pending_start is not None and total_duration > pending_start:
        silences.append(Interval(pending_start, total_duration))
    return silences


def detect_silences(path: str, noise_db: float = -34.0,
                    min_silence: float = 0.45) -> List[Interval]:
    """Run ffmpeg silencedetect over a media file (audio is decoded only,
    nothing is re-encoded or written)."""
    duration = media_duration(path)
    res = _run([
        "ffmpeg", "-v", "info", "-i", path,
        "-af", "silencedetect=noise=%gdB:d=%g" % (noise_db, min_silence),
        "-f", "null", "-"])
    stderr = res.stderr.decode(errors="replace")
    if res.returncode != 0:
        raise FfmpegError("silencedetect failed for %s: %s"
                          % (path, stderr[-300:]))
    return parse_silencedetect(stderr, duration)


def invert_silences(silences: List[Interval], total_duration: float,
                    min_keep: float = 0.15) -> List[Interval]:
    """Silence intervals -> speech/'keep' intervals covering the rest.

    min_keep drops micro-slivers between two silences (they cause
    single-frame flash cuts that look broken in the timeline).
    """
    keeps = []
    cursor = 0.0
    for s in sorted(silences, key=lambda i: i.start):
        if s.start - cursor >= min_keep:
            keeps.append(Interval(cursor, min(s.start, total_duration)))
        cursor = max(cursor, s.end)
    if total_duration - cursor >= min_keep:
        keeps.append(Interval(cursor, total_duration))
    return keeps
