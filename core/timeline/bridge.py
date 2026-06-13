"""ResolveBridge — defensive wrapper around the DaVinci Resolve scripting API.

Design rules (see prompt section 1):
- Only documented API calls (GetProjectManager, GetCurrentTimeline,
  GetItemListInTrack, AppendToTimeline, ...). No private internals.
- Every capability is probed at runtime; missing features raise
  CapabilityError with a human-readable message instead of crashing.
- Free vs. Studio: when launched from the Scripts menu the `resolve`
  object is injected and works in BOTH editions. External attachment
  (DaVinciResolveScript import) is Studio-only — we try it as fallback
  and explain clearly when it is unavailable.
"""

import sys
from dataclasses import dataclass, field
from typing import Any, List, Optional


class CapabilityError(RuntimeError):
    """A Resolve API feature is unavailable in this edition/version."""


@dataclass
class ClipInfo:
    """Snapshot of a timeline item, in timeline + source frame coordinates."""
    name: str
    file_path: str
    timeline_start: int          # frame on the timeline where the clip starts
    timeline_end: int            # frame on the timeline where the clip ends (exclusive)
    source_start: int            # first used frame inside the source media
    source_end: int              # last used frame inside the source media (exclusive)
    fps: float
    track_index: int = 1
    media_pool_item: Any = field(default=None, repr=False)  # opaque Resolve handle

    @property
    def duration_frames(self) -> int:
        return self.timeline_end - self.timeline_start

    @property
    def duration_seconds(self) -> float:
        return self.duration_frames / self.fps if self.fps else 0.0


def acquire_resolve(injected: Any = None) -> Any:
    """Return a Resolve app object.

    Priority:
    1. `injected` — the `resolve` variable provided when running from the
       Scripts menu (works in Free AND Studio).
    2. External attach via DaVinciResolveScript (Studio-only).
    """
    if injected is not None:
        return injected
    try:
        import DaVinciResolveScript as dvr  # type: ignore
    except ImportError:
        raise CapabilityError(
            "DaVinciResolveScript not importable. Run this tool from "
            "Resolve's menu: Workspace > Scripts > resolve_ai_editor "
            "(works in the FREE edition). External attachment requires "
            "DaVinci Resolve STUDIO with scripting enabled "
            "(Preferences > System > General > External scripting using)."
        )
    resolve = dvr.scriptapp("Resolve")
    if resolve is None:
        raise CapabilityError(
            "Could not attach to a running DaVinci Resolve instance. "
            "Is Resolve running? Note: external scripting is Studio-only — "
            "in the free edition launch the script from Workspace > Scripts."
        )
    return resolve


def _call(obj: Any, method: str, *args: Any) -> Any:
    """Call a Resolve API method if it exists, else raise CapabilityError."""
    fn = getattr(obj, method, None)
    if fn is None:
        raise CapabilityError(
            "Resolve API method '%s' is not available in this Resolve "
            "version/edition. Please update Resolve (18.6+) or check the "
            "limitations section in the README." % method
        )
    return fn(*args)


class ResolveBridge:
    """All timeline read/write access goes through this class."""

    def __init__(self, resolve: Any):
        self.resolve = resolve

    # ---------- read ----------

    def project(self) -> Any:
        pm = _call(self.resolve, "GetProjectManager")
        if pm is None:
            raise CapabilityError("GetProjectManager returned nothing — is a project open?")
        project = _call(pm, "GetCurrentProject")
        if project is None:
            raise CapabilityError("No project is currently open in Resolve.")
        return project

    def current_timeline(self) -> Any:
        timeline = _call(self.project(), "GetCurrentTimeline")
        if timeline is None:
            raise CapabilityError(
                "No timeline is open. Open a timeline on the Edit page first.")
        return timeline

    def timeline_fps(self, timeline: Any = None) -> float:
        timeline = timeline or self.current_timeline()
        raw = _call(timeline, "GetSetting", "timelineFrameRate")
        try:
            return float(raw)
        except (TypeError, ValueError):
            return 24.0  # documented Resolve default

    def timeline_resolution(self, timeline: Any = None):
        """(width, height) of the timeline, or None if unavailable."""
        timeline = timeline or self.current_timeline()
        try:
            w = int(_call(timeline, "GetSetting", "timelineResolutionWidth"))
            h = int(_call(timeline, "GetSetting", "timelineResolutionHeight"))
            if w > 0 and h > 0:
                return (w, h)
        except (TypeError, ValueError, CapabilityError):
            pass
        return None

    def project_info(self) -> dict:
        """Compact status blob for the UI (capability probing happens here)."""
        info = {
            "connected": False, "project": None, "timeline": None,
            "fps": None, "video_tracks": 0, "clip_count": 0, "error": None,
        }
        try:
            project = self.project()
            info["project"] = _call(project, "GetName")
            timeline = self.current_timeline()
            info["timeline"] = _call(timeline, "GetName")
            info["fps"] = self.timeline_fps(timeline)
            info["video_tracks"] = int(_call(timeline, "GetTrackCount", "video"))
            info["clip_count"] = len(self.clips())
            info["connected"] = True
        except CapabilityError as exc:
            info["error"] = str(exc)
        return info

    def clips(self, track_index: int = 1) -> List[ClipInfo]:
        """Read video clips of one track as ClipInfo snapshots."""
        timeline = self.current_timeline()
        fps = self.timeline_fps(timeline)
        items = _call(timeline, "GetItemListInTrack", "video", track_index) or []
        clips = []
        for item in items:
            clips.append(self._clip_info(item, fps, track_index))
        return clips

    def _clip_info(self, item: Any, fps: float, track_index: int) -> ClipInfo:
        name = _call(item, "GetName")
        start = int(_call(item, "GetStart"))
        end = int(_call(item, "GetEnd"))

        # Source range: prefer the modern API (18.6+), fall back to LeftOffset.
        if hasattr(item, "GetSourceStartFrame"):
            src_start = int(item.GetSourceStartFrame())
            src_end = int(item.GetSourceEndFrame())
        elif hasattr(item, "GetLeftOffset"):
            src_start = int(item.GetLeftOffset())
            src_end = src_start + (end - start)
        else:
            # Last resort: assume the clip is used from frame 0.
            src_start, src_end = 0, end - start

        file_path = ""
        mp_item = None
        if hasattr(item, "GetMediaPoolItem"):
            mp_item = item.GetMediaPoolItem()
            if mp_item is not None and hasattr(mp_item, "GetClipProperty"):
                file_path = mp_item.GetClipProperty("File Path") or ""

        return ClipInfo(
            name=name, file_path=file_path,
            timeline_start=start, timeline_end=end,
            source_start=src_start, source_end=src_end,
            fps=fps, track_index=track_index, media_pool_item=mp_item,
        )

    # ---------- write (non-destructive only) ----------

    def create_cut_timeline(self, name: str, segments: List[dict]) -> Any:
        """Build a NEW timeline from keep-segments. The original timeline is
        never modified — deleting the new timeline is the 'undo'.

        segments: [{"media_pool_item": <handle>, "start_frame": int,
                    "end_frame": int}, ...] in source-frame coordinates.
        """
        if not segments:
            raise CapabilityError("Cut list is empty — nothing to apply.")
        project = self.project()
        media_pool = _call(project, "GetMediaPool")
        if media_pool is None:
            raise CapabilityError("Media Pool is not accessible via the API.")

        new_tl = _call(media_pool, "CreateEmptyTimeline", name)
        if not new_tl:
            raise CapabilityError(
                "Could not create timeline '%s' (name may already exist)." % name)
        # CreateEmptyTimeline makes the new timeline current; AppendToTimeline
        # then targets it. Both calls are documented Free+Studio API.
        clip_infos = [
            {
                "mediaPoolItem": seg["media_pool_item"],
                "startFrame": int(seg["start_frame"]),
                "endFrame": int(seg["end_frame"]),
            }
            for seg in segments
            if seg.get("media_pool_item") is not None
        ]
        if not clip_infos:
            raise CapabilityError(
                "None of the segments has a Media Pool item — cannot rebuild. "
                "(Compound/Fusion clips are not supported in Phase 1.)")
        appended = _call(media_pool, "AppendToTimeline", clip_infos)
        if not appended:
            raise CapabilityError(
                "AppendToTimeline failed — Resolve rejected the cut list.")
        return new_tl


if sys.version_info < (3, 6):  # Resolve bundles 3.6+; we target 3.6-3.13
    raise RuntimeError("resolve-ai-editor requires Python 3.6 or newer")
