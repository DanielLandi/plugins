"""The engine per plugin copy: the installed plugin keeps today's engine, each git checkout of the plugin gets its own."""
import json
import os
import re

import pytest

from musicvideo import studio
from musicvideo.errors import MVError
from musicvideo.workspace import folder_key


def _studio_dir(folder, lock):
    folder.mkdir(parents=True)
    (folder / "package-lock.json").write_text(lock, encoding="utf-8")
    return folder


def installed_copy(tmp_path, lock="{}"):
    """The plugin as Claude Code runs it: a versioned copy in its plugin cache, in no git repo."""
    return _studio_dir(tmp_path / "plugins" / "cache" / "some-marketplace" / "music-video" / "0.6.8" / "studio", lock)


def dev_copy(tmp_path, name, worktree=False, lock="{}"):
    """A git checkout of the plugins repo (`<repo>/music-video/studio`), or a linked worktree of one."""
    repo = tmp_path / name
    repo.mkdir(parents=True)
    if worktree:
        (repo / ".git").write_text(f"gitdir: {tmp_path / 'main' / '.git' / 'worktrees' / name}\n", encoding="utf-8")
    else:
        (repo / ".git").mkdir()
    return _studio_dir(repo / "music-video" / "studio", lock)


def test_installed_plugin_uses_todays_engine(tmp_path, monkeypatch):
    monkeypatch.setattr(studio, "PLUGIN_STUDIO", installed_copy(tmp_path))
    assert studio.plugin_checkout() is None
    assert studio.runtime_dir() == tmp_path / "install" / "engine"


def test_two_plugin_checkouts_get_distinct_engines(tmp_path, monkeypatch):
    a, b = dev_copy(tmp_path, "plugins"), dev_copy(tmp_path, "wt", worktree=True)
    monkeypatch.setattr(studio, "PLUGIN_STUDIO", a)
    assert studio.plugin_checkout() == tmp_path / "plugins"
    ra = studio.runtime_dir()
    monkeypatch.setattr(studio, "PLUGIN_STUDIO", b)
    rb = studio.runtime_dir()
    assert ra.parent == rb.parent == tmp_path / "install" / "engines"
    assert ra != rb and ra.name.startswith("plugins-") and rb.name.startswith("wt-")


def test_engine_dir_env_overrides(tmp_path, monkeypatch):
    monkeypatch.setenv("MV_ENGINE_DIR", str(tmp_path / "mine"))
    assert studio.runtime_dir() == tmp_path / "mine"


def test_folder_key_is_readable_stable_and_distinct(tmp_path):
    a, b = tmp_path / "x" / "My Clone é", tmp_path / "y" / "My Clone é"
    assert folder_key(a) == folder_key(a) and folder_key(a) != folder_key(b)
    assert re.fullmatch(r"my-clone-[0-9a-f]{8}", folder_key(a))
    assert len(folder_key(tmp_path / ("n" * 60)).rsplit("-", 1)[0]) == 24
    assert re.fullmatch(r"x-[0-9a-f]{8}", folder_key(tmp_path / "ééé"))


def test_dev_engine_records_its_checkout(tmp_path, monkeypatch):
    monkeypatch.setattr(studio, "PLUGIN_STUDIO", dev_copy(tmp_path, "plugins"))
    rt = studio.runtime_dir()
    studio.touch_owner(rt)
    owner = json.loads((rt / studio.OWNER).read_text(encoding="utf-8"))
    assert owner["checkout"] == str(tmp_path / "plugins") and owner["created"] and owner["last_used"]


def test_installed_engine_has_no_owner_file(tmp_path, monkeypatch):
    monkeypatch.setattr(studio, "PLUGIN_STUDIO", installed_copy(tmp_path))
    rt = studio.runtime_dir()
    studio.touch_owner(rt)
    assert not (rt / studio.OWNER).exists()


def test_old_cache_engine_migrates_to_the_installed_engine_only(tmp_path, monkeypatch):
    monkeypatch.setattr(studio, "PLUGIN_STUDIO", dev_copy(tmp_path, "plugins"))
    (tmp_path / "cache" / "studio" / "node_modules").mkdir(parents=True)
    assert studio.migrate_old_runtime() is True
    assert (tmp_path / "install" / "engine" / "node_modules").is_dir()


def installed_engine(root, lock_text):
    """An engine whose packages doctor installed: modules, Remotion's browser, tool caches and a .bin link."""
    for rel, text in {"package-lock.json": lock_text, "node_modules/remotion/index.js": "remotion",
                      "node_modules/.remotion/chrome/bin": "browser", "node_modules/.cache/w.json": "{}",
                      "node_modules/.vite/deps.json": "{}"}.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")
    try:
        (root / "node_modules/.bin").mkdir()
        os.symlink("../remotion/index.js", root / "node_modules/.bin/remotion")
    except OSError:  # Windows without Developer Mode: no symlinks
        pass
    (root / studio.LOCK_STAMP).write_text(studio.lock_hash(root), encoding="utf-8")
    return root


def test_seed_hard_links_modules_when_locks_match(tmp_path, monkeypatch):
    src = installed_engine(tmp_path / "install" / "engine", '{"v": 1}')
    monkeypatch.setattr(studio, "PLUGIN_STUDIO", dev_copy(tmp_path, "plugins", lock='{"v": 1}'))
    rt = studio.ensure_ready()  # no doctor needed
    assert rt != src
    a, b = src / "node_modules/remotion/index.js", rt / "node_modules/remotion/index.js"
    assert os.stat(a).st_ino == os.stat(b).st_ino
    assert (rt / "node_modules/.remotion/chrome/bin").read_text(encoding="utf-8") == "browser"
    assert not (rt / "node_modules/.cache").exists() and not (rt / "node_modules/.vite").exists()
    if (src / "node_modules/.bin/remotion").is_symlink():
        assert (rt / "node_modules/.bin/remotion").is_symlink()
        assert (rt / "node_modules/.bin/remotion").read_text(encoding="utf-8") == "remotion"
    assert studio.is_installed(rt)


def test_seed_falls_back_to_doctor_when_locks_differ(tmp_path, monkeypatch):
    installed_engine(tmp_path / "install" / "engine", '{"v": 1}')
    monkeypatch.setattr(studio, "PLUGIN_STUDIO", dev_copy(tmp_path, "plugins", lock='{"v": 2}'))
    with pytest.raises(MVError, match="music-video doctor"):
        studio.ensure_ready()
    assert not (studio.runtime_dir() / "node_modules").exists()


def test_no_installed_engine_says_doctor(tmp_path, monkeypatch):
    monkeypatch.setattr(studio, "PLUGIN_STUDIO", dev_copy(tmp_path, "plugins"))
    with pytest.raises(MVError, match="music-video doctor"):
        studio.ensure_ready()


def test_seed_from_another_checkouts_engine(tmp_path, monkeypatch):
    monkeypatch.setattr(studio, "PLUGIN_STUDIO", dev_copy(tmp_path, "a", lock='{"v": 3}'))
    installed_engine(studio.runtime_dir(), '{"v": 3}')
    monkeypatch.setattr(studio, "PLUGIN_STUDIO", dev_copy(tmp_path, "b", lock='{"v": 3}'))
    assert studio.is_installed(studio.ensure_ready())


def test_seeded_engine_survives_a_reinstall_of_its_source(tmp_path, monkeypatch):
    src = installed_engine(tmp_path / "install" / "engine", '{"v": 1}')
    monkeypatch.setattr(studio, "PLUGIN_STUDIO", dev_copy(tmp_path, "plugins", lock='{"v": 1}'))
    rt = studio.ensure_ready()
    f = src / "node_modules/remotion/index.js"
    f.unlink()  # npm ci removes and re-extracts: new files, new inodes
    f.write_text("reinstalled", encoding="utf-8")
    assert (rt / "node_modules/remotion/index.js").read_text(encoding="utf-8") == "remotion"


def test_seed_copies_when_links_fail(tmp_path, monkeypatch):
    src = installed_engine(tmp_path / "install" / "engine", '{"v": 1}')
    monkeypatch.setattr(studio, "PLUGIN_STUDIO", dev_copy(tmp_path, "plugins", lock='{"v": 1}'))

    def no_links(*_a, **_k):
        raise OSError("hard links not supported")
    monkeypatch.setattr(os, "link", no_links)
    rt = studio.ensure_ready()
    a, b = src / "node_modules/remotion/index.js", rt / "node_modules/remotion/index.js"
    assert b.read_text(encoding="utf-8") == "remotion" and os.stat(a).st_ino != os.stat(b).st_ino
    assert not (rt / "node_modules/.cache").exists()


def test_interrupted_seed_is_redone(tmp_path, monkeypatch):
    installed_engine(tmp_path / "install" / "engine", '{"v": 1}')
    monkeypatch.setattr(studio, "PLUGIN_STUDIO", dev_copy(tmp_path, "plugins", lock='{"v": 1}'))
    half = studio.runtime_dir() / "node_modules" / "half.js"  # a seed stopped mid-way: no lock stamp
    half.parent.mkdir(parents=True)
    half.write_text("x", encoding="utf-8")
    rt = studio.ensure_ready()
    assert not half.exists() and (rt / "node_modules/remotion/index.js").is_file()


def test_doctor_seeds_a_checkouts_engine_instead_of_installing(tmp_path, monkeypatch, capsys):
    from musicvideo import doctor
    installed_engine(tmp_path / "install" / "engine", '{"v": 1}')
    monkeypatch.setattr(studio, "PLUGIN_STUDIO", dev_copy(tmp_path, "plugins", lock='{"v": 1}'))
    monkeypatch.setattr(doctor.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(doctor, "_node_major", lambda: 22)

    def no_install(rt):
        raise AssertionError("npm ci must not run when a seed exists")
    monkeypatch.setattr(studio, "install", no_install)
    assert doctor.run_doctor() == 0
    out = capsys.readouterr().out
    assert "seeded from" in out and f"for the checkout {tmp_path / 'plugins'}" in out
    assert studio.is_installed(studio.runtime_dir())
