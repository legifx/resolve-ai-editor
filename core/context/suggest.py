"""Auto-suggest audience / genre / topic from local signals (+ optional
frames). The suggestion is a STARTING POINT — the user edits or overrides
every field. We never act on it silently.
"""

import json
from typing import List, Optional

from core.context.signals import gather_signals, signals_to_prompt

FIELDS = ("audience", "genre", "topic")

_SYSTEM = (
    "You are a video producer. From the metadata (and frames if provided), "
    "infer the likely target audience, genre, and topic of this video. Be "
    "concise and concrete. Reply ONLY with a JSON object: "
    '{"audience": str, "genre": str, "topic": str, "confidence": '
    '"low"|"medium"|"high", "note": str}. Keep each field under 12 words. '
    "If you cannot tell, say so in the field (e.g. \"unclear\") rather than "
    "guessing wildly.")


def suggest_context(bridge, provider, use_frames: bool = False,
                    max_frames: int = 3, progress=lambda m: None) -> dict:
    """Return a suggested context dict. Requires an available provider.

    use_frames: opt-in. Samples a few frames from the video clips and sends
    them to a vision-capable provider (Anthropic). Falls back to
    metadata-only if frame sampling or vision is unavailable — and says so.
    """
    from core.ai.base import AIError

    signals = gather_signals(bridge)
    prompt = signals_to_prompt(signals)
    images: List[dict] = []
    frame_note = "metadata only"

    if use_frames:
        from core.context.frames import sample_timeline_frames, HAS_VISION
        if not HAS_VISION(provider):
            frame_note = ("frames requested but this provider has no vision "
                          "support — used metadata only")
        else:
            progress("sampling frames…")
            images = sample_timeline_frames(bridge, max_frames)
            frame_note = ("%d frame(s) + metadata" % len(images)
                          if images else "no decodable frames — metadata only")

    try:
        if images:
            resp = provider.complete(prompt, system=_SYSTEM,
                                     max_tokens=400, images=images)
        else:
            resp = provider.complete(prompt, system=_SYSTEM, max_tokens=400)
        data = json.loads(_extract_json_object(resp.text))
    except (AIError, ValueError, json.JSONDecodeError, TypeError) as exc:
        raise AIError("Context suggestion failed: %s" % exc)

    out = {f: str(data.get(f, "")).strip() for f in FIELDS}
    out["confidence"] = data.get("confidence", "low")
    out["note"] = str(data.get("note", ""))[:200]
    out["basis"] = frame_note
    out["signals"] = signals  # so the UI can show what it saw
    return out


def _extract_json_object(text: str) -> str:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("no JSON object in model reply")
    return text[start:end + 1]
