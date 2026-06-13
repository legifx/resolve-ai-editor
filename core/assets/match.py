"""Asset recommendation — which SFX goes where, and why.

Two layers:
1. A local, deterministic heuristic matcher (always available, free, fully
   testable): reads the timeline's cut points and maps them to SFX
   categories — a transition whoosh on each shot change, a riser/impact on
   the opening hook.
2. An OPTIONAL LLM refine pass (only if a provider is configured): it gets a
   compact summary — cut points + candidate asset names + optional
   genre/audience context, never any audio — and may re-pick assets and
   write better reasons. Any failure silently falls back to the heuristic.

This module only RECOMMENDS. Inserting the assets into the timeline is a
separate, explicit step (place.py) so the list/script mode and the
auto-insert mode stay cleanly separated (prompt section 3E).
"""

import json
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional

from core.timeline.bridge import ClipInfo

# Which category fits which moment. Hook prefers a riser/impact build; a plain
# shot change gets a transition whoosh.
_HOOK_PREFS = ("riser", "impact", "transition")
_CUT_PREFS = ("transition", "impact")


@dataclass
class Placement:
    frame: int            # timeline frame where the SFX should land
    timecode: str         # HH:MM:SS:FF for the UI
    moment: str           # "hook" | "cut"
    category: str         # chosen SFX category
    asset_path: Optional[str]
    asset_name: Optional[str]
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


def _timecode(frame: int, fps: float) -> str:
    fps_i = max(1, int(round(fps)))
    total = int(frame)
    ff = total % fps_i
    secs = total // fps_i
    return "%02d:%02d:%02d:%02d" % (secs // 3600, (secs // 60) % 60,
                                    secs % 60, ff)


def cut_points(clips: List[ClipInfo]):
    """Derive (frame, moment) edit points from timeline clips.

    The earliest clip start is the hook; every other clip boundary is a cut.
    """
    if not clips:
        return []
    ordered = sorted(clips, key=lambda c: c.timeline_start)
    points = [(ordered[0].timeline_start, "hook")]
    for c in ordered[1:]:
        points.append((c.timeline_start, "cut"))
    return points


def _by_category(index: Dict[str, dict]) -> Dict[str, List[dict]]:
    buckets: Dict[str, List[dict]] = {}
    for entry in index.values():
        if entry.get("kind") != "sfx":
            continue
        buckets.setdefault(entry.get("category", "other"), []).append(entry)
    for v in buckets.values():
        v.sort(key=lambda e: e["name"].lower())  # stable, deterministic
    return buckets


def _pick(buckets, prefs, rotation):
    """Pick an asset from the first non-empty preferred category, rotating
    through that category's assets so repeated cuts don't all get the same
    file. Returns (category, entry) or (prefs[0], None) if nothing fits."""
    for category in prefs:
        items = buckets.get(category)
        if items:
            i = rotation.get(category, 0)
            rotation[category] = i + 1
            return category, items[i % len(items)]
    return prefs[0], None


def recommend(clips: List[ClipInfo], index: Dict[str, dict], fps: float,
              context: Optional[dict] = None, provider=None) -> List[dict]:
    """Return a list of Placement dicts (the recommended SFX script).

    context: optional {genre, audience, topic} hints (Phase 5 feeds these).
    provider: optional AIProvider for the refine pass.
    """
    buckets = _by_category(index)
    rotation: Dict[str, int] = {}
    placements: List[Placement] = []

    for frame, moment in cut_points(clips):
        prefs = _HOOK_PREFS if moment == "hook" else _CUT_PREFS
        category, entry = _pick(buckets, prefs, rotation)
        if entry is None:
            placements.append(Placement(
                frame=frame, timecode=_timecode(frame, fps), moment=moment,
                category=category, asset_path=None, asset_name=None,
                reason=("No '%s' SFX in your library for this %s — "
                        "add one or connect another folder." % (category, moment))))
        else:
            reason = ("%s on the %s" % (category.capitalize(),
                      "opening hook" if moment == "hook" else "shot change"))
            placements.append(Placement(
                frame=frame, timecode=_timecode(frame, fps), moment=moment,
                category=category, asset_path=entry["path"],
                asset_name=entry["name"], reason=reason))

    result = [p.to_dict() for p in placements]
    if provider is not None:
        result = _llm_refine(result, buckets, context, provider)
    return result


def _llm_refine(placements: List[dict], buckets: Dict[str, List[dict]],
                context: Optional[dict], provider) -> List[dict]:
    """Optional: let the model re-pick assets + improve reasons. Compact
    payload only (names + markers, no audio). Falls back silently on any
    error so the heuristic result is never lost."""
    from core.ai.base import AIError

    candidates = {cat: [e["name"] for e in items]
                  for cat, items in buckets.items()}
    payload = {
        "cut_points": [{"i": i, "timecode": p["timecode"],
                        "moment": p["moment"], "category": p["category"]}
                       for i, p in enumerate(placements)],
        "candidates_by_category": candidates,
        "context": context or {},
    }
    system = ("You are a video sound designer. For each cut point pick the "
              "single best-fitting SFX from candidates_by_category (use the "
              "exact name) and give a one-line reason. Reply ONLY with a JSON "
              "array of objects {\"i\": int, \"asset_name\": str, "
              "\"reason\": str}. Keep reasons under 12 words.")
    try:
        resp = provider.complete(json.dumps(payload), system=system,
                                 max_tokens=800)
        chosen = json.loads(_extract_json_array(resp.text))
    except (AIError, ValueError, json.JSONDecodeError, KeyError):
        return placements  # heuristic stands

    # name -> path lookup for validation (model must pick a real candidate)
    name_to_path = {e["name"]: e["path"]
                    for items in buckets.values() for e in items}
    for item in chosen:
        try:
            i = int(item["i"])
            name = item["asset_name"]
        except (KeyError, ValueError, TypeError):
            continue
        if 0 <= i < len(placements) and name in name_to_path:
            placements[i]["asset_name"] = name
            placements[i]["asset_path"] = name_to_path[name]
            if item.get("reason"):
                placements[i]["reason"] = str(item["reason"])[:120]
    return placements


def _extract_json_array(text: str) -> str:
    """Pull the first [...] block out of a model reply (handles code fences)."""
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end < start:
        raise ValueError("no JSON array in model reply")
    return text[start:end + 1]
