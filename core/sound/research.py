"""Background-sound research — COMPLIANT by construction (prompt section 3G).

Two modes:

1. "royalty_free" (DEFAULT) — suggests 3 background-music directions for the
   video's genre and points at LICENSED / royalty-free sources, always with
   the license attached. Works against the curated source list below; if a
   provider is configured it tailors the 3 directions to the context.

2. "trend" (OFF BY DEFAULT) — a clearly-labelled best-effort module. There is
   NO official, ToS-compliant API for TikTok/Instagram trend sounds, and this
   plugin does NOT scrape. The mode does nothing unless the user explicitly
   enables it AND configures a source they are permitted to use. Even then it
   only produces search terms for the user to check on that source — it makes
   no hidden network requests.

Nothing here fabricates a track or a download link. It returns research help
(directions + search terms + real, license-tagged sources).
"""

from dataclasses import asdict, dataclass
from typing import List, Optional

MODES = ("royalty_free", "trend")

# Curated, real royalty-free / licensed sources. license/commercial flags
# reflect each platform's general terms — the UI tells users to verify the
# current per-track license, since terms can change.
CURATED_SOURCES = [
    {"name": "Pixabay Music", "url": "https://pixabay.com/music/",
     "license": "Pixabay Content License", "commercial_ok": True,
     "attribution_required": False,
     "note": "Royalty-free, usable in ads; no attribution required."},
    {"name": "YouTube Audio Library", "url": "https://studio.youtube.com/",
     "license": "YouTube Audio Library License", "commercial_ok": True,
     "attribution_required": False,
     "note": "Free for any use; some tracks ask for attribution — check the badge."},
    {"name": "Free Music Archive", "url": "https://freemusicarchive.org/",
     "license": "Various Creative Commons", "commercial_ok": True,
     "attribution_required": True,
     "note": "License varies per track (CC0 / CC-BY / NC) — verify each one."},
    {"name": "Incompetech (Kevin MacLeod)", "url": "https://incompetech.com/music/",
     "license": "CC BY 4.0", "commercial_ok": True,
     "attribution_required": True,
     "note": "Commercial use OK with attribution."},
    {"name": "ccMixter", "url": "http://ccmixter.org/",
     "license": "Various Creative Commons", "commercial_ok": True,
     "attribution_required": True,
     "note": "License varies per track — check before commercial use."},
]


@dataclass
class SoundSuggestion:
    style: str
    description: str
    search_terms: List[str]
    recommended_source: str
    license: str
    commercial_ok: bool

    def to_dict(self) -> dict:
        return asdict(self)


# Static fallback directions when no AI provider is configured. Keyed loosely
# by genre keyword; "default" covers anything else.
_FALLBACK = {
    "default": [
        ("Upbeat / energetic", "Driving, positive bed for general content.",
         ["upbeat", "energetic", "positive corporate"]),
        ("Calm / ambient", "Soft underscore that stays out of the way.",
         ["ambient", "calm", "background underscore"]),
        ("Cinematic", "Building, emotive score for impact moments.",
         ["cinematic", "inspirational", "epic build"]),
    ],
}


def _commercial_source():
    """Pick a default commercial-safe source for recommendations."""
    for s in CURATED_SOURCES:
        if s["commercial_ok"] and not s["attribution_required"]:
            return s
    return CURATED_SOURCES[0]


def _fallback_suggestions() -> List[SoundSuggestion]:
    src = _commercial_source()
    out = []
    for style, desc, terms in _FALLBACK["default"]:
        out.append(SoundSuggestion(
            style=style, description=desc, search_terms=terms,
            recommended_source=src["name"], license=src["license"],
            commercial_ok=src["commercial_ok"]))
    return out


def _ai_suggestions(context: dict, provider) -> Optional[List[SoundSuggestion]]:
    """Ask the model for 3 context-fitted directions. None on any failure."""
    import json
    from core.ai.base import AIError

    src = _commercial_source()
    payload = {
        "context": {k: context.get(k, "") for k in ("audience", "genre", "topic")},
        "must_be": "royalty-free / commercially licensable background music",
    }
    system = (
        "You are a music supervisor. Suggest exactly 3 distinct background-"
        "music directions for this video. Reply ONLY with a JSON array of 3 "
        'objects {"style": str, "description": str, "search_terms": [str]}. '
        "search_terms are 2-4 short phrases to search a royalty-free library. "
        "Keep style under 6 words, description under 16 words.")
    try:
        resp = provider.complete(json.dumps(payload), system=system,
                                 max_tokens=500)
        arr = json.loads(_extract_json_array(resp.text))
    except (AIError, ValueError, json.JSONDecodeError):
        return None
    out = []
    for item in arr[:3]:
        try:
            out.append(SoundSuggestion(
                style=str(item["style"])[:60],
                description=str(item.get("description", ""))[:160],
                search_terms=[str(t)[:40] for t in item.get("search_terms", [])][:4],
                recommended_source=src["name"], license=src["license"],
                commercial_ok=src["commercial_ok"]))
        except (KeyError, TypeError):
            continue
    return out or None


def research(context: dict, mode: str = "royalty_free", provider=None,
             trend_enabled: bool = False, trend_source: str = "") -> dict:
    """Return sound research for the given mode. Always compliant."""
    if mode == "trend":
        return _trend(context, provider, trend_enabled, trend_source)

    # royalty_free (default)
    suggestions = None
    if provider is not None:
        ok, _ = provider.available()
        if ok:
            suggestions = _ai_suggestions(context, provider)
    if suggestions is None:
        suggestions = _fallback_suggestions()
    return {
        "mode": "royalty_free",
        "ai_used": suggestions is not None and provider is not None
                   and len(suggestions) == 3 and provider.available()[0],
        "suggestions": [s.to_dict() for s in suggestions],
        "sources": CURATED_SOURCES,
        "license_note": ("Always verify the current per-track license before "
                         "use, especially for ads — terms can change."),
    }


def _trend(context: dict, provider, trend_enabled: bool,
           trend_source: str) -> dict:
    """The clearly-labelled, off-by-default best-effort trend module."""
    disclaimer = (
        "There is no official, ToS-compliant API for TikTok/Instagram trend "
        "sounds, and this plugin does not scrape. Trend mode is off by default "
        "and makes no hidden network requests.")
    if not trend_enabled:
        return {"mode": "trend", "enabled": False, "suggestions": [],
                "message": "Trend mode is disabled. " + disclaimer}
    if not trend_source.strip():
        return {"mode": "trend", "enabled": True, "suggestions": [],
                "message": ("Trend mode is on but no permitted source is "
                            "configured. Add a source you have the right to "
                            "query (Settings). " + disclaimer)}
    # Enabled + source: produce search TERMS only (no scraping, no fetch).
    terms = _trend_terms(context, provider)
    return {
        "mode": "trend", "enabled": True, "source": trend_source.strip(),
        "suggestions": terms,
        "message": ("Best-effort search terms — check them yourself on your "
                    "configured source. " + disclaimer),
    }


def _trend_terms(context: dict, provider) -> List[dict]:
    import json
    from core.ai.base import AIError
    if provider is None:
        genre = context.get("genre", "")
        return [{"search_terms": [genre + " trending", "viral " + genre,
                                  "popular " + genre]}]
    try:
        ok, _ = provider.available()
        if not ok:
            raise AIError("no provider")
        resp = provider.complete(
            json.dumps({k: context.get(k, "") for k in ("genre", "audience", "topic")}),
            system=("Suggest 5 short search phrases someone might use to find "
                    "currently popular background sounds for this kind of video "
                    "on a social platform. Reply ONLY with a JSON array of "
                    "strings."),
            max_tokens=200)
        arr = json.loads(_extract_json_array(resp.text))
        return [{"search_terms": [str(t)[:40] for t in arr][:8]}]
    except (AIError, ValueError, json.JSONDecodeError):
        genre = context.get("genre", "")
        return [{"search_terms": [genre + " trending", "viral " + genre]}]


def _extract_json_array(text: str) -> str:
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end < start:
        raise ValueError("no JSON array in model reply")
    return text[start:end + 1]
