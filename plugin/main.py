"""Panel entry point.

Launched either:
- from Resolve's menu Workspace > Scripts (the generated launcher passes
  the injected `resolve` object) — works in FREE and STUDIO, or
- standalone for development:  python3 -m plugin.main --demo
"""

import sys
import webbrowser

from core.timeline.bridge import CapabilityError, ResolveBridge, acquire_resolve
from plugin.server import serve


def launch(resolve_obj=None, demo=False, open_browser=True, block=True):
    if demo:
        from plugin.demo import demo_resolve
        resolve_obj = demo_resolve()
        print("[demo] using MockResolve with a synthetic timeline")
    try:
        resolve = acquire_resolve(resolve_obj)
    except CapabilityError as exc:
        # No stack trace at the user — this is an expected condition.
        print("Resolve AI Editor: %s" % exc)
        return None

    bridge = ResolveBridge(resolve)
    server, url, state = serve(bridge)
    print("Resolve AI Editor panel: %s" % url)
    if open_browser:
        webbrowser.open(url)
    if block:
        # When run from the Scripts menu, keep serving until Resolve ends
        # the script's process or the user closes Resolve.
        try:
            import time
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            server.shutdown()
    return server, url, state


if __name__ == "__main__":
    launch(demo="--demo" in sys.argv,
           open_browser="--no-browser" not in sys.argv)
