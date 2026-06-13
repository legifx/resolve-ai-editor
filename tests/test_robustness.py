"""Error-path / graceful-degradation tests — the things that must not crash
the panel in the field."""

import json

import pytest

from core.analyze import audio


# ---- ffmpeg missing ----

def test_ffmpeg_missing_gives_install_hint(monkeypatch):
    def boom(*a, **k):
        raise FileNotFoundError()
    monkeypatch.setattr("subprocess.run", boom)
    with pytest.raises(audio.FfmpegError, match="INSTALL.md"):
        audio.media_duration("/whatever.wav")


def test_extract_audio_missing_file():
    with pytest.raises(audio.FfmpegError, match="not found"):
        audio.extract_audio("/no/such/file.wav")


# ---- settings resilience ----

def test_settings_corrupt_file_falls_back_to_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from config import settings
    # write garbage into the settings file
    with open(settings._settings_file(), "w") as fh:
        fh.write("{ not valid json")
    loaded = settings.load()
    assert loaded["noise_db"] == settings.DEFAULTS["noise_db"]


def test_settings_save_only_known_keys(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from config import settings
    saved = settings.save({"padding": 0.2, "evil": "x"})
    assert saved["padding"] == 0.2
    assert "evil" not in saved


# ---- analysis cache resilience ----

def test_cache_miss_and_corrupt(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from core.analyze import cache
    assert cache.get("/x", {"p": 1}) is None       # miss
    cache.put("/x", {"p": 1}, {"v": 2})
    assert cache.get("/x", {"p": 1}) == {"v": 2}    # hit
    # corrupt the cache file -> get returns None, not a crash
    import os
    f = [os.path.join(cache.cache_dir(), n)
         for n in os.listdir(cache.cache_dir())][0]
    with open(f, "w") as fh:
        fh.write("garbage")
    assert cache.get("/x", {"p": 1}) is None


# ---- server route guards (headless) ----

@pytest.fixture
def panel():
    from plugin.main import launch
    server, url, state = launch(demo=True, open_browser=False, block=False)
    base = url.split("/?")[0]
    yield base, state.token, state
    server.shutdown()


def _req(base, token, path, data=None, method=None):
    import urllib.request
    import urllib.error
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(base + path, data=body,
                                 headers={"X-Token": token,
                                          "Content-Type": "application/json"})
    if method:
        req.get_method = lambda: method
    try:
        return urllib.request.urlopen(req).status, \
            json.loads(urllib.request.urlopen(req).read())
    except urllib.error.HTTPError as e:
        return e.code, None


def test_unknown_route_404(panel):
    base, token, _ = panel
    code, _ = _req(base, token, "/api/does-not-exist")
    assert code == 404


def test_invalid_json_400(panel):
    import urllib.request
    import urllib.error
    base, token, _ = panel
    req = urllib.request.Request(base + "/api/settings", data=b"{bad json",
                                 headers={"X-Token": token,
                                          "Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req)
        assert False, "should have 400'd"
    except urllib.error.HTTPError as e:
        assert e.code == 400


def test_all_get_endpoints_respond(panel):
    """Smoke: every GET endpoint returns 200 with the demo timeline."""
    base, token, _ = panel
    for path in ("/api/status", "/api/settings", "/api/job", "/api/profiles",
                 "/api/ai/status", "/api/assets/status", "/api/context"):
        code, body = _req(base, token, path)
        assert code == 200, path
        assert body is not None, path
