"""The engine per plugin copy: the installed plugin keeps today's engine, each git checkout of the plugin gets its own."""
import json
import re

from musicvideo import studio
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
