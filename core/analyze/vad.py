"""Optional webrtcvad-based voice activity detection.

Only used when the `webrtcvad` package is installed — the plugin works
without it (ffmpeg silencedetect is the default). webrtcvad is better at
keeping quiet-but-spoken passages (whispers, soft endings of sentences)
that pure loudness thresholds cut off.
"""

import contextlib
import wave
from typing import List, Optional

from .silence import Interval

try:
    import webrtcvad  # type: ignore
    HAS_WEBRTCVAD = True
except ImportError:
    webrtcvad = None
    HAS_WEBRTCVAD = False

_FRAME_MS = 30  # webrtcvad supports 10/20/30 ms frames


def detect_speech_vad(wav_path: str, aggressiveness: int = 2,
                      min_gap: float = 0.45) -> Optional[List[Interval]]:
    """Speech intervals from a mono 16 kHz PCM wav (see audio.extract_audio).

    Returns None when webrtcvad is unavailable so callers can fall back.
    aggressiveness: 0 (keep more) .. 3 (cut more), webrtcvad semantics.
    """
    if not HAS_WEBRTCVAD:
        return None
    vad = webrtcvad.Vad(aggressiveness)
    with contextlib.closing(wave.open(wav_path, "rb")) as wf:
        rate = wf.getframerate()
        if rate not in (8000, 16000, 32000, 48000) or wf.getnchannels() != 1:
            return None  # caller falls back to silencedetect
        pcm = wf.readframes(wf.getnframes())

    frame_bytes = int(rate * _FRAME_MS / 1000) * 2  # 16-bit mono
    speech_frames = []
    for off in range(0, len(pcm) - frame_bytes + 1, frame_bytes):
        t = off / 2 / rate
        is_speech = vad.is_speech(pcm[off:off + frame_bytes], rate)
        speech_frames.append((t, is_speech))

    # merge consecutive speech frames; bridge gaps shorter than min_gap
    intervals: List[Interval] = []
    seg_start = None
    last_speech_end = None
    for t, is_speech in speech_frames:
        if is_speech:
            if seg_start is None:
                seg_start = t
            last_speech_end = t + _FRAME_MS / 1000.0
        elif seg_start is not None and t - last_speech_end >= min_gap:
            intervals.append(Interval(seg_start, last_speech_end))
            seg_start = None
    if seg_start is not None:
        intervals.append(Interval(seg_start, last_speech_end))
    return intervals
