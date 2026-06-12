"""MockResolve — minimal stand-in for the Resolve object hierarchy.

Used by the test suite (this repo is developed on a headless server without
Resolve) and by `plugin/resolve_ai_editor.py --demo` for UI development.
Mirrors only the documented API surface that ResolveBridge touches.
"""

from typing import List, Optional


class MockMediaPoolItem:
    def __init__(self, file_path: str, fps: float = 25.0):
        self._props = {"File Path": file_path, "FPS": str(fps)}

    def GetClipProperty(self, key: str) -> Optional[str]:
        return self._props.get(key)


class MockTimelineItem:
    def __init__(self, name, start, end, source_start, mp_item):
        self._name, self._start, self._end = name, start, end
        self._source_start = source_start
        self._mp_item = mp_item

    def GetName(self): return self._name
    def GetStart(self): return self._start
    def GetEnd(self): return self._end
    def GetSourceStartFrame(self): return self._source_start
    def GetSourceEndFrame(self): return self._source_start + (self._end - self._start)
    def GetMediaPoolItem(self): return self._mp_item


class MockTimeline:
    def __init__(self, name: str, fps: float = 25.0):
        self._name = name
        self._fps = fps
        self.items: List[MockTimelineItem] = []

    def GetName(self): return self._name
    def GetSetting(self, key):
        return str(self._fps) if key == "timelineFrameRate" else ""
    def GetTrackCount(self, kind): return 1
    def GetItemListInTrack(self, kind, index):
        return self.items if (kind == "video" and index == 1) else []


class MockMediaPool:
    def __init__(self, project):
        self._project = project
        self.append_calls: List[list] = []  # recorded for test assertions

    def CreateEmptyTimeline(self, name: str):
        if any(t.GetName() == name for t in self._project.timelines):
            return None  # Resolve behaviour: duplicate names fail
        tl = MockTimeline(name, self._project.current_timeline._fps)
        self._project.timelines.append(tl)
        self._project.current_timeline = tl
        return tl

    def AppendToTimeline(self, clip_infos: list):
        self.append_calls.append(clip_infos)
        tl = self._project.current_timeline
        cursor = tl.items[-1].GetEnd() if tl.items else 0
        appended = []
        for ci in clip_infos:
            dur = ci["endFrame"] - ci["startFrame"]
            item = MockTimelineItem("seg", cursor, cursor + dur,
                                    ci["startFrame"], ci["mediaPoolItem"])
            tl.items.append(item)
            appended.append(item)
            cursor += dur
        return appended


class MockProject:
    def __init__(self, name="Demo Project", fps: float = 25.0):
        self._name = name
        self.current_timeline = MockTimeline("Demo Timeline", fps)
        self.timelines = [self.current_timeline]
        self.media_pool = MockMediaPool(self)

    def GetName(self): return self._name
    def GetCurrentTimeline(self): return self.current_timeline
    def GetMediaPool(self): return self.media_pool


class MockProjectManager:
    def __init__(self, project): self._project = project
    def GetCurrentProject(self): return self._project


class MockResolve:
    """Entry point. `MockResolve.with_demo_timeline()` gives a ready scene."""

    def __init__(self, project: Optional[MockProject] = None):
        self.project = project or MockProject()

    def GetProjectManager(self):
        return MockProjectManager(self.project)

    @classmethod
    def with_demo_timeline(cls, fps: float = 25.0) -> "MockResolve":
        resolve = cls(MockProject(fps=fps))
        tl = resolve.project.current_timeline
        clip_a = MockMediaPoolItem("/demo/interview_a.mov", fps)
        clip_b = MockMediaPoolItem("/demo/broll_b.mov", fps)
        # two clips back to back: 0-500 and 500-800 timeline frames
        tl.items = [
            MockTimelineItem("interview_a.mov", 0, 500, 0, clip_a),
            MockTimelineItem("broll_b.mov", 500, 800, 100, clip_b),
        ]
        return resolve
