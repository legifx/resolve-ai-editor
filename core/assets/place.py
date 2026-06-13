"""Auto-insert mode — place recommended SFX onto the current timeline.

This is the second of the two asset modes (prompt section 3E). It takes the
recommendation list from match.recommend() and actually inserts the SFX, on a
dedicated new audio track, at each recommended record frame.

Additive and reversible: a new audio track is created and SFX are placed on
it; nothing existing is touched. Undo via Resolve Undo or by deleting the
added track.

UNTESTED on real Resolve — developed/verified headless against the mock.
Surfaced honestly in the README and UI.
"""

import os
from typing import Callable, Dict, List

from core.timeline.bridge import CapabilityError, ResolveBridge

ProgressFn = Callable[[str], None]


def place_assets(bridge: ResolveBridge, placements: List[dict],
                 index: Dict[str, dict], fps: float,
                 progress: ProgressFn = lambda msg: None) -> dict:
    """Insert the placements that reference a real asset. Returns a report."""
    usable = [p for p in placements if p.get("asset_path")]
    missing = [p for p in placements if not p.get("asset_path")]
    if not usable:
        raise CapabilityError(
            "None of the recommendations references an asset in your library — "
            "nothing to insert. Connect a folder with matching SFX first.")

    unique_paths = list({p["asset_path"] for p in usable})
    progress("importing %d asset(s)…" % len(unique_paths))
    items = bridge.import_media(unique_paths)

    progress("adding SFX audio track…")
    track_index = bridge.add_audio_track()

    to_place = []
    skipped_import = []
    for p in usable:
        item = items.get(p["asset_path"])
        if item is None:
            skipped_import.append(os.path.basename(p["asset_path"]))
            continue
        entry = index.get(p["asset_path"], {})
        dur_s = entry.get("duration") or 1.0  # fallback 1 s if unknown
        to_place.append({
            "item": item,
            "record_frame": int(p["frame"]),
            "duration_frames": max(1, int(round(dur_s * fps))),
            "track_index": track_index,
        })

    progress("placing %d SFX on track A%d…" % (len(to_place), track_index))
    placed = bridge.place_audio(to_place)
    return {
        "placed": placed,
        "track": "A%d" % track_index,
        "missing_asset": [p["moment"] for p in missing],
        "skipped_import": skipped_import,
    }
