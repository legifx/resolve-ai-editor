"""Optional, sparse frame sampling for context auto-suggestion.

Extracts a FEW small JPEG frames from the timeline's video clips via ffmpeg
and returns them as base64 image blocks for a vision-capable provider. This
is the "sparing frame samples" path from prompt section 3F/4 — deliberately
few and downscaled to keep vision token cost low.

Only Anthropic (with the SDK) currently supports vision here; HAS_VISION
gates it so callers degrade to metadata-only cleanly.
"""

import base64
import os
import subprocess
import tempfile
from typing import List

from core.analyze.audio import media_duration, FfmpegError

VIDEO_EXTS = {".mov", ".mp4", ".mxf", ".mkv", ".webm", ".avi", ".m4v"}
_MAX_WIDTH = 512  # downscale — keeps vision tokens modest


def HAS_VISION(provider) -> bool:
    return bool(getattr(provider, "supports_vision", False))


def _extract_one(path: str, at_seconds: float) -> str:
    """Extract a single downscaled JPEG frame; return base64 string or ''."""
    fd, out = tempfile.mkstemp(suffix=".jpg")
    os.close(fd)
    try:
        res = subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-ss", "%.3f" % max(0.0, at_seconds),
             "-i", path, "-frames:v", "1",
             "-vf", "scale=%d:-1" % _MAX_WIDTH, "-q:v", "5", out],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        if res.returncode != 0 or not os.path.getsize(out):
            return ""
        with open(out, "rb") as fh:
            return base64.standard_b64encode(fh.read()).decode("ascii")
    except (OSError, subprocess.TimeoutExpired):
        return ""
    finally:
        try:
            os.remove(out)
        except OSError:
            pass


def sample_timeline_frames(bridge, max_frames: int = 3) -> List[dict]:
    """Sample up to max_frames frames spread across the video clips.

    Returns image blocks: [{"media_type": "image/jpeg", "data": <base64>}, ...].
    Skips clips that aren't decodable video files (e.g. the headless mock's
    placeholder paths) — returns [] if none work, so the caller degrades to
    metadata-only.
    """
    clips = [c for c in bridge.clips()
             if c.file_path
             and os.path.splitext(c.file_path)[1].lower() in VIDEO_EXTS
             and os.path.exists(c.file_path)]
    if not clips:
        return []

    # pick evenly spaced clips, sample the middle of each
    step = max(1, len(clips) // max_frames)
    chosen = clips[::step][:max_frames]
    images = []
    for clip in chosen:
        try:
            dur = media_duration(clip.file_path)
        except FfmpegError:
            continue
        b64 = _extract_one(clip.file_path, dur / 2.0)
        if b64:
            images.append({"media_type": "image/jpeg", "data": b64})
    return images
