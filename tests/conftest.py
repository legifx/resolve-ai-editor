import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """Keep settings + analysis cache out of the real user config dir."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    yield


@pytest.fixture(scope="session")
def tone_silence_wav(tmp_path_factory):
    """6 s wav: tone 0-2, silence 2-3.5, tone 3.5-5, silence 5-6."""
    path = str(tmp_path_factory.mktemp("media") / "tone_silence.wav")
    cmd = ["ffmpeg", "-y", "-v", "error",
           "-f", "lavfi", "-t", "2", "-i", "sine=frequency=440",
           "-f", "lavfi", "-t", "1.5", "-i", "anullsrc=r=16000:cl=mono",
           "-f", "lavfi", "-t", "1.5", "-i", "sine=frequency=300",
           "-f", "lavfi", "-t", "1", "-i", "anullsrc=r=16000:cl=mono",
           "-filter_complex", "[0][1][2][3]concat=n=4:v=0:a=1",
           "-ar", "16000", path]
    subprocess.run(cmd, check=True)
    return path
