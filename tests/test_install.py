"""Installer tests — paths, launcher write/verify, uninstall, check mode."""

import os
import sys

import pytest

import install


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    # expanduser on win32 also consults USERPROFILE/APPDATA; tests run on posix
    return str(tmp_path)


def test_scripts_dirs_nonempty_user_first():
    dirs = install.scripts_dirs()
    assert dirs and all("Utility" in d for d in dirs)


def test_resolve_root_is_ancestor():
    d = install.scripts_dirs()[0]
    root = install._resolve_root(d)
    assert d.startswith(root)
    assert root != d


def test_preferred_target_default_when_no_resolve(fake_home):
    target, found = install.preferred_target_dir()
    assert found is False
    assert target == install.scripts_dirs()[0]


def test_preferred_target_detects_existing_resolve(fake_home):
    d = install.scripts_dirs()[0]
    os.makedirs(install._resolve_root(d), exist_ok=True)
    target, found = install.preferred_target_dir()
    assert found is True
    assert target == d


def test_launcher_template_compiles():
    src = install.LAUNCHER.format(repo="/some/repo/path")
    compile(src, "launcher", "exec")
    assert "/some/repo/path" in src


def test_install_then_uninstall(fake_home):
    assert install.install_launcher() is True
    path = install.launcher_path()
    assert os.path.isfile(path)
    # the written launcher is valid python
    with open(path) as fh:
        compile(fh.read(), path, "exec")
    install.uninstall_launcher()
    assert not os.path.exists(path)


def test_check_mode_changes_nothing(fake_home, capsys):
    rc = install.main(["--check"])
    assert rc in (0, 1)  # 1 only if ffmpeg/python missing
    # nothing written
    assert not os.path.exists(install.launcher_path())


def test_check_python_true_on_current():
    assert install.check_python() is True


def test_check_optional_deps_returns_list():
    missing = install.check_optional_deps()
    assert isinstance(missing, list)
