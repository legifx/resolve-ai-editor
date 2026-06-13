"""Local metadata signals for context auto-suggestion.

Token optimization (prompt section 4): we describe the video to the LLM with
a compact text summary built ENTIRELY from local metadata — clip filenames,
counts, durations, fps, resolution. No media bytes, no frames (frame sampling
is a separate, opt-in step in suggest.py). Clip filenames are often highly
descriptive ("interview_ceo.mov", "product_demo_4k.mov", "drone_beach.mov")
and cost nothing to read.
"""

import os
from typing import Optional

from core.timeline.bridge import ResolveBridge


def gather_signals(bridge: ResolveBridge) -> dict:
    """Collect a compact, local-only description of the current timeline."""
    clips = bridge.clips()
    fps = bridge.timeline_fps()
    total_frames = sum(c.duration_frames for c in clips)
    resolution = bridge.timeline_resolution()
    names = []
    for c in clips:
        # prefer the source filename; fall back to the clip name
        base = os.path.basename(c.file_path) if c.file_path else c.name
        if base:
            names.append(base)

    return {
        "timeline": bridge.current_timeline().GetName(),
        "clip_count": len(clips),
        "duration_seconds": round(total_frames / fps, 1) if fps else None,
        "fps": fps,
        "resolution": ("%dx%d" % resolution) if resolution else None,
        "clip_filenames": names,
    }


def signals_to_prompt(signals: dict) -> str:
    """Render signals as a short text block for the LLM (compact, no JSON
    noise)."""
    lines = [
        "Timeline: %s" % signals.get("timeline"),
        "Clips: %d, total ~%s s, %s fps, %s" % (
            signals.get("clip_count", 0),
            signals.get("duration_seconds"),
            signals.get("fps"),
            signals.get("resolution") or "unknown resolution"),
    ]
    names = signals.get("clip_filenames") or []
    if names:
        # cap the list so a huge timeline can't blow up the prompt
        shown = names[:40]
        lines.append("Clip filenames: " + ", ".join(shown))
        if len(names) > len(shown):
            lines.append("(+%d more clips)" % (len(names) - len(shown)))
    return "\n".join(lines)
