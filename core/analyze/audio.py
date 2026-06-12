"""ffmpeg helpers — audio extraction and media probing. 100% local."""

import json
import os
import subprocess
import tempfile


class FfmpegError(RuntimeError):
    pass


def _run(cmd, timeout=600):
    try:
        return subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=timeout, check=False)
    except FileNotFoundError:
        raise FfmpegError(
            "ffmpeg/ffprobe not found on PATH. Install it first — "
            "see INSTALL.md (it is the only system dependency).")
    except subprocess.TimeoutExpired:
        raise FfmpegError("ffmpeg timed out on: %s" % " ".join(cmd[:4]))


def media_duration(path: str) -> float:
    """Duration in seconds via ffprobe."""
    res = _run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "json", path])
    if res.returncode != 0:
        raise FfmpegError("ffprobe failed for %s: %s"
                          % (path, res.stderr.decode(errors="replace")[-300:]))
    try:
        return float(json.loads(res.stdout)["format"]["duration"])
    except (KeyError, ValueError, json.JSONDecodeError):
        raise FfmpegError("Could not read duration of %s" % path)


def extract_audio(path: str, out_path: str = None,
                  sample_rate: int = 16000) -> str:
    """Extract mono 16 kHz WAV (ideal input for VAD). Returns the wav path."""
    if not os.path.exists(path):
        raise FfmpegError("Media file not found: %s" % path)
    if out_path is None:
        fd, out_path = tempfile.mkstemp(suffix=".tmp.wav")
        os.close(fd)
    res = _run([
        "ffmpeg", "-y", "-v", "error", "-i", path,
        "-vn", "-ac", "1", "-ar", str(sample_rate),
        "-acodec", "pcm_s16le", out_path])
    if res.returncode != 0:
        raise FfmpegError("Audio extraction failed for %s: %s"
                          % (path, res.stderr.decode(errors="replace")[-300:]))
    return out_path
