"""SFX/VFX library indexing — local, cached, no LLM required.

Connect one or more folders; the index records path, name, type, duration
(ffprobe) and heuristic category/tags derived from the FILENAME. Filename
tagging is what most sound libraries (Soundly, etc.) rely on — it is honest
and free. An optional LLM enrichment pass exists in match.py; it is NOT run
here and never on every scan (prompt section 4: tag once, cache forever).

The index is persisted as one JSON file in the user config dir, keyed per
file by (mtime, size) so a re-scan only re-probes changed/new files.
"""

import json
import os
import re
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional

from config.settings import app_dir
from core.analyze.audio import FfmpegError, media_duration

AUDIO_EXTS = {".wav", ".mp3", ".aif", ".aiff", ".flac", ".ogg", ".m4a", ".aac"}
VIDEO_EXTS = {".mov", ".mp4", ".mxf", ".mkv", ".webm", ".avi"}
IMAGE_EXTS = {".png", ".gif", ".tga", ".exr", ".jpg", ".jpeg", ".webp"}

# Heuristic categories from filename keywords. Order matters — first hit wins.
# These mirror how editors name SFX packs; matching is substring, lowercased.
_CATEGORY_KEYWORDS = [
    ("transition", ("whoosh", "swoosh", "swish", "transition", "swipe",
                    "woosh", "pass", "movement")),
    ("impact", ("impact", "hit", "boom", "slam", "punch", "bass", "thud",
                "stinger", "braam")),
    ("riser", ("riser", "rise", "build", "uplifter", "sweep", "ramp")),
    ("ui", ("click", "pop", "tick", "beep", "blip", "notification", "tap")),
    ("ambient", ("ambient", "drone", "atmos", "atmosphere", "background",
                 "room", "loop")),
    ("music", ("music", "track", "song", "beat", "melody", "bgm")),
]

_TOKEN_RE = re.compile(r"[a-z0-9]+")


@dataclass
class AssetEntry:
    path: str
    name: str
    kind: str               # "sfx" | "vfx" | "image"
    category: str           # heuristic, see _CATEGORY_KEYWORDS, else "other"
    tags: List[str]         # filename tokens (+ optional cached LLM tags)
    duration: Optional[float]
    size: int
    mtime: int
    llm_description: Optional[str] = None  # filled by match.py enrichment, cached

    def to_dict(self) -> dict:
        return asdict(self)


def categorize(filename: str) -> str:
    low = filename.lower()
    for category, keywords in _CATEGORY_KEYWORDS:
        if any(k in low for k in keywords):
            return category
    return "other"


def _tags(filename: str) -> List[str]:
    stem = os.path.splitext(os.path.basename(filename))[0].lower()
    # drop pure-number tokens and 1-char noise
    return [t for t in _TOKEN_RE.findall(stem) if len(t) > 1 and not t.isdigit()]


def _kind(ext: str) -> Optional[str]:
    if ext in AUDIO_EXTS:
        return "sfx"
    if ext in VIDEO_EXTS:
        return "vfx"
    if ext in IMAGE_EXTS:
        return "image"
    return None


def scan_folders(folders: List[str]) -> List[str]:
    """Return absolute paths of all supported media files under the folders."""
    found = []
    seen = set()
    for folder in folders:
        if not os.path.isdir(folder):
            continue
        for root, _dirs, files in os.walk(folder):
            for fn in files:
                ext = os.path.splitext(fn)[1].lower()
                if _kind(ext) is None:
                    continue
                full = os.path.abspath(os.path.join(root, fn))
                if full not in seen:
                    seen.add(full)
                    found.append(full)
    return found


def _index_file() -> str:
    return os.path.join(app_dir(), "asset_index.json")


def load_index() -> Dict[str, dict]:
    try:
        with open(_index_file(), "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}


def save_index(index: Dict[str, dict]) -> None:
    tmp = _index_file() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(index, fh)
    os.replace(tmp, _index_file())


def build_index(folders: List[str], probe_duration: bool = True,
                progress=lambda msg: None) -> Dict[str, dict]:
    """Scan folders and return {path: AssetEntry-dict}, reusing cached entries
    whose (mtime, size) are unchanged. Only new/changed files are re-probed."""
    cached = load_index()
    paths = scan_folders(folders)
    index: Dict[str, dict] = {}
    probed = 0
    for path in paths:
        try:
            st = os.stat(path)
        except OSError:
            continue
        prev = cached.get(path)
        if prev and prev.get("mtime") == int(st.st_mtime) \
                and prev.get("size") == st.st_size:
            index[path] = prev  # unchanged — keep cache (incl. any LLM tags)
            continue

        ext = os.path.splitext(path)[1].lower()
        kind = _kind(ext)
        duration = None
        if probe_duration and kind in ("sfx", "vfx"):
            try:
                duration = round(media_duration(path), 3)
                probed += 1
                progress("probed %s" % os.path.basename(path))
            except FfmpegError:
                duration = None
        entry = AssetEntry(
            path=path, name=os.path.basename(path), kind=kind,
            category=categorize(path), tags=_tags(path),
            duration=duration, size=st.st_size, mtime=int(st.st_mtime))
        index[path] = entry.to_dict()
    save_index(index)
    progress("indexed %d assets (%d newly probed)" % (len(index), probed))
    return index
