"""Demo mode — UI development without DaVinci Resolve installed.

Builds a MockResolve whose timeline points at a synthetic media file
(tone/silence pattern) generated once with ffmpeg, so the full raw-cut
pipeline runs for real.
"""

import os
import subprocess

from config.settings import app_dir
from core.timeline.mock import (MockMediaPoolItem, MockProject, MockResolve,
                                MockTimelineItem)

_FPS = 25.0


def _demo_wav() -> str:
    path = os.path.join(app_dir(), "demo_media.wav")
    if os.path.exists(path):
        return path
    # speech(2s) silence(1.5s) speech(1.5s) silence(1s) — ffmpeg 4.x syntax
    cmd = ["ffmpeg", "-y", "-v", "error",
           "-f", "lavfi", "-t", "2", "-i", "sine=frequency=440",
           "-f", "lavfi", "-t", "1.5", "-i", "anullsrc=r=16000:cl=mono",
           "-f", "lavfi", "-t", "1.5", "-i", "sine=frequency=300",
           "-f", "lavfi", "-t", "1", "-i", "anullsrc=r=16000:cl=mono",
           "-filter_complex", "[0][1][2][3]concat=n=4:v=0:a=1",
           "-ar", "16000", path]
    subprocess.run(cmd, check=True)
    return path


def demo_resolve() -> MockResolve:
    wav = _demo_wav()
    resolve = MockResolve(MockProject(name="Demo Project", fps=_FPS))
    tl = resolve.project.current_timeline
    mp = MockMediaPoolItem(wav, _FPS)
    tl.items = [MockTimelineItem(os.path.basename(wav), 0, 150, 0, mp)]
    return resolve
