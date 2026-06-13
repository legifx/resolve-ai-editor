"""Edit profiles — encode real editing heuristics per delivery format.

Why profiles exist (prompt section 3C): the same raw footage is cut very
differently for a 20-minute YouTube video vs. a 30-second TikTok. Pacing,
how much breathing room you keep, and how you treat the opening seconds all
change. Each profile tunes the LOCAL, actually-achievable cut parameters and
carries a checklist of the profi techniques that the Resolve Free API can NOT
perform automatically — those are surfaced as honest recommendations, not
faked.

What a profile changes automatically (real, audible/visible in the cut):
- cut_params: silence threshold, minimum pause length, padding, min segment
  length — i.e. how aggressively pauses are removed → the overall pacing.
- hook_seconds: the opening N seconds of the source are protected from cuts,
  so the hook/cold-open stays intact (a hard cut 0.5 s into the hook kills it).
- max_segment_seconds: long kept stretches are subdivided into edit points so
  no single clip runs longer than the target — gives you ready-made cut points
  to drop in B-roll / pattern interrupts (the clip still plays seamlessly; we
  do NOT pretend to insert visual interrupts we can't generate).

What a profile only RECOMMENDS (Resolve Free API can't do it from audio alone,
so we tell you instead of faking it): J-/L-cuts, auto-captions, aspect-ratio
reframing, music beat-syncing, CTA placement. See `recommendations`.
"""

from dataclasses import dataclass, field
from typing import List, Optional

from core.cut.engine import CutParams


@dataclass
class EditProfile:
    key: str
    label: str
    description: str
    aspect_ratio: str                 # target delivery aspect, e.g. "16:9"
    cut_params: CutParams
    hook_seconds: float               # protect first N s of source from cuts
    max_segment_seconds: Optional[float]  # subdivide longer kept clips; None=off
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "key": self.key, "label": self.label,
            "description": self.description, "aspect_ratio": self.aspect_ratio,
            "hook_seconds": self.hook_seconds,
            "max_segment_seconds": self.max_segment_seconds,
            "recommendations": list(self.recommendations),
        }


PROFILES = {
    # Long-form (YouTube): viewers tolerate — and prefer — a natural rhythm.
    # Keep more breathing room (longer min_silence, generous padding) so the
    # delivery doesn't feel machine-gunned. Protect a longer cold-open.
    "long_form": EditProfile(
        key="long_form", label="Long-form (YouTube)",
        description="Natural pacing, keeps breathing room, protects the intro.",
        aspect_ratio="16:9",
        cut_params=CutParams(noise_db=-34.0, min_silence=0.60,
                             padding=0.15, min_keep=0.40),
        hook_seconds=4.0,
        max_segment_seconds=None,   # no forced pacing — let shots breathe
        recommendations=[
            "Use J-/L-cuts on dialogue (lead audio in / carry it out) — do this "
            "manually on the audio track; the API can't offset A/V from audio alone.",
            "Add chapter markers at topic changes for retention + navigation.",
            "Keep the first 4 s (the hook) intact — it is protected from cuts.",
            "Consider B-roll over longer talking-head stretches to hold attention.",
        ]),

    # Short (TikTok / Reels / YT Shorts): fast, punchy, vertical. Cut pauses
    # aggressively (short min_silence, minimal padding) for high energy, hook
    # in the first second, and add frequent edit points for pattern interrupts.
    "short": EditProfile(
        key="short", label="Short (TikTok / Reels / Shorts)",
        description="Aggressive pacing, instant hook, frequent edit points, 9:16.",
        aspect_ratio="9:16",
        cut_params=CutParams(noise_db=-32.0, min_silence=0.30,
                             padding=0.05, min_keep=0.20),
        hook_seconds=1.0,
        max_segment_seconds=4.0,    # no shot longer than ~4 s without a cut point
        recommendations=[
            "Captions are effectively mandatory — most viewers watch muted. "
            "Resolve Studio can auto-transcribe; Free needs a manual/3rd-party pass.",
            "Hook must land in the first ~1 s — it is protected from cuts.",
            "Drop a pattern interrupt (B-roll, zoom, text pop) at each edit point.",
            "Reframe to 9:16 — Studio 'Smart Reframe' or manual; the API can't "
            "auto-reframe the picture.",
        ]),

    # Ad / promo: tight and persuasive, but not as frantic as a Short. Medium
    # pacing, protect the opening value-prop, edit points for product shots.
    "ad": EditProfile(
        key="ad", label="Ad / Promo",
        description="Tight, persuasive pacing with room for a product shot + CTA.",
        aspect_ratio="16:9",
        cut_params=CutParams(noise_db=-33.0, min_silence=0.40,
                             padding=0.10, min_keep=0.30),
        hook_seconds=2.5,
        max_segment_seconds=6.0,
        recommendations=[
            "Open with the value proposition — first 2.5 s are protected.",
            "Reserve the last edit points for a clear CTA + product/logo shot.",
            "Sync hard cuts to the music beat (manual — needs the chosen track).",
            "Keep total runtime tight; trim any segment that doesn't sell.",
        ]),
}

DEFAULT_PROFILE = "long_form"


def get_profile(key: str) -> EditProfile:
    return PROFILES.get(key) or PROFILES[DEFAULT_PROFILE]


def _aspect_value(spec: str) -> Optional[float]:
    try:
        w, h = spec.split(":")
        return float(w) / float(h)
    except (ValueError, ZeroDivisionError):
        return None


def aspect_check(resolution, target_aspect: str) -> Optional[str]:
    """Compare the timeline's actual aspect to the profile target.

    Returns a human-readable warning string if they differ meaningfully, or
    None if they match / the resolution is unknown. We only WARN — the Free
    API can't reframe the picture for you (Studio 'Smart Reframe' or a manual
    crop is required), so faking a reframe is not an option.
    """
    if not resolution:
        return None
    width, height = resolution
    if height <= 0:
        return None
    actual = width / height
    target = _aspect_value(target_aspect)
    if target is None:
        return None
    # 5% tolerance handles e.g. 1080x1920 vs exact 9:16
    if abs(actual - target) / target > 0.05:
        return ("Timeline is %dx%d (~%.2f:1) but the '%s' profile targets "
                "%s. Reframe manually or with Studio 'Smart Reframe' — the "
                "plugin does not alter the picture." %
                (width, height, actual, target_aspect, target_aspect))
    return None
