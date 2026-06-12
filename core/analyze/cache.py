"""Persistent analysis cache (prompt section 4: aggressive caching).

Keyed by (absolute path, file mtime, file size, parameter hash) so a
re-render of the same filename invalidates automatically. Stored as small
JSON files under the user config dir — survives Resolve restarts, keeps
repeated runs free.
"""

import hashlib
import json
import os
from typing import Any, Optional

from config.settings import cache_dir


def _key(path: str, params: dict) -> str:
    try:
        stat = os.stat(path)
        ident = "%s|%d|%d" % (os.path.abspath(path), int(stat.st_mtime), stat.st_size)
    except OSError:
        ident = os.path.abspath(path)
    blob = ident + "|" + json.dumps(params, sort_keys=True)
    return hashlib.sha1(blob.encode()).hexdigest()


def get(path: str, params: dict) -> Optional[Any]:
    f = os.path.join(cache_dir(), _key(path, params) + ".json")
    if not os.path.exists(f):
        return None
    try:
        with open(f, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None


def put(path: str, params: dict, value: Any) -> None:
    f = os.path.join(cache_dir(), _key(path, params) + ".json")
    try:
        with open(f, "w", encoding="utf-8") as fh:
            json.dump(value, fh)
    except OSError:
        pass  # cache is best-effort, never fatal
