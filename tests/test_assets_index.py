import os

import pytest

from core.assets import index as ix


@pytest.fixture
def sfx_dir(tmp_path):
    """A folder with named SFX (silent wavs) + one unsupported file."""
    import subprocess
    files = {
        "whoosh_transition_01.wav": 0.5,
        "deep_impact_boom.wav": 0.8,
        "riser_build_up.wav": 1.2,
        "ui_click_soft.wav": 0.2,
    }
    for name, dur in files.items():
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-t", str(dur),
             "-i", "sine=frequency=300", str(tmp_path / name)], check=True)
    (tmp_path / "notes.txt").write_text("not media")
    return str(tmp_path)


def test_categorize():
    assert ix.categorize("whoosh_transition.wav") == "transition"
    assert ix.categorize("BIG_IMPACT_hit.wav") == "impact"
    assert ix.categorize("epic_riser.wav") == "riser"
    assert ix.categorize("ui_click.wav") == "ui"
    assert ix.categorize("ambient_drone.wav") == "ambient"
    assert ix.categorize("nondescript.wav") == "other"


def test_scan_only_media(sfx_dir):
    found = ix.scan_folders([sfx_dir])
    names = {os.path.basename(p) for p in found}
    assert "notes.txt" not in names
    assert len(found) == 4


def test_scan_ignores_missing_folder():
    assert ix.scan_folders(["/no/such/folder"]) == []


def test_build_index_fields(sfx_dir):
    idx = ix.build_index([sfx_dir])
    assert len(idx) == 4
    entry = next(e for e in idx.values() if "whoosh" in e["name"])
    assert entry["kind"] == "sfx"
    assert entry["category"] == "transition"
    assert "whoosh" in entry["tags"]
    assert entry["duration"] and 0.4 < entry["duration"] < 0.7


def test_index_cache_skips_unchanged(sfx_dir):
    log1 = []
    ix.build_index([sfx_dir], progress=log1.append)
    log2 = []
    ix.build_index([sfx_dir], progress=log2.append)
    # second pass probes nothing new
    assert any("(0 newly probed)" in m for m in log2)
    assert not any(m.startswith("probed ") for m in log2)


def test_index_reprobes_changed_file(sfx_dir):
    import subprocess
    ix.build_index([sfx_dir])
    target = os.path.join(sfx_dir, "ui_click_soft.wav")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-t", "0.6",
                    "-i", "sine=frequency=300", target], check=True)
    log = []
    ix.build_index([sfx_dir], progress=log.append)
    assert any("probed ui_click_soft.wav" in m for m in log)


def test_tags_drop_numbers_and_noise():
    tags = ix._tags("whoosh_01_a.wav")
    assert "whoosh" in tags
    assert "01" not in tags  # pure number dropped
    assert "a" not in tags   # 1-char dropped
