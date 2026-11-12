"""Engines of plugin checkouts that no longer exist (a merged and removed worktree) are removed by doctor; anything
in doubt is kept."""
import json
import os
import stat
import sys

import pytest

from musicvideo import studio
from test_mv_engine import dev_copy, installed_engine, sleeper, write_lease  # noqa: F401 (sleeper is a fixture)


def engines(tmp_path):
    return tmp_path / "install" / "engines"


def engine(tmp_path, name, checkout=None, owner=None):
    """A checkout's engine with some packages; its .owner.json names `checkout` (or holds `owner` as given)."""
    rt = installed_engine(engines(tmp_path) / name, '{"v": 1}')
    if owner is not None:
        (rt / studio.OWNER).write_text(owner, encoding="utf-8")
    elif checkout is not None:
        (rt / studio.OWNER).write_text(json.dumps({"checkout": str(checkout), "created": "2026-11-01T00:00:00Z",
                                                   "last_used": "2026-11-01T00:00:00Z", "used_at": 0}),
                                       encoding="utf-8")
    return rt


@pytest.fixture
def here(tmp_path, monkeypatch):
    """This command runs from the checkout `plugins`; `gone` was a worktree beside it, now removed."""
    monkeypatch.setattr(studio, "PLUGIN_STUDIO", dev_copy(tmp_path, "plugins", lock='{"v": 1}'))
    return tmp_path


def test_an_engine_whose_checkout_is_gone_is_removed(here):
    rt = engine(here, "gone-1234abcd", here / "gone")
    removed = studio.prune_engines()
    assert not rt.exists()
    assert [(r.engine, r.checkout, r.removed) for r in removed] == [(rt, str(here / "gone"), True)]
    assert removed[0].freed > 0
    assert not list((here / "install").glob(".trash/*"))  # nothing left half-way


def test_an_engine_whose_checkout_exists_is_kept(here):
    (here / "other").mkdir()
    rt = engine(here, "other-1234abcd", here / "other")
    assert studio.prune_engines() == [] and rt.is_dir()


def test_a_leased_engine_is_kept(here, sleeper):  # noqa: F811
    rt = engine(here, "gone-1234abcd", here / "gone")
    write_lease(rt, sleeper.pid, here / "gone" / "music-video" / "studio")
    [kept] = studio.prune_engines()
    assert not kept.removed and "in use by music-video 0.6.7" in kept.why
    assert (rt / "node_modules/remotion/index.js").is_file()


@pytest.mark.parametrize("owner", [None, "{", "[]", '{"created": "2026-11-01T00:00:00Z"}', '{"checkout": ""}',
                                   '{"checkout": 7}', '{"checkout": "relative/path"}'])
def test_an_engine_with_no_readable_owner_is_kept(here, owner):
    rt = engine(here, "unknown-1234abcd", owner=owner)
    assert studio.prune_engines() == [] and (rt / "node_modules/remotion/index.js").is_file()


def test_the_installed_engine_is_never_touched(here):
    rt = installed_engine(here / "install" / "engine", '{"v": 1}')
    (rt / studio.OWNER).write_text(json.dumps({"checkout": str(here / "gone")}), encoding="utf-8")
    assert studio.prune_engines() == [] and rt.is_dir()


def test_the_current_engine_is_never_touched(here, monkeypatch):
    rt = engine(here, "mine-1234abcd", here / "gone")  # its record says gone, but this command runs from it
    monkeypatch.setenv("MV_ENGINE_DIR", str(rt))
    assert studio.prune_engines() == [] and rt.is_dir()


def test_a_checkout_on_a_missing_disk_is_kept(here):
    # An unplugged drive: the checkout's folder is gone because its parent is. It may come back.
    rt = engine(here, "far-1234abcd", here / "Volumes" / "Backup" / "plugins")
    assert studio.prune_engines() == [] and rt.is_dir()


def test_links_inside_an_engine_are_removed_not_followed(here):
    video = here / "My Videos" / "night-drive"
    video.mkdir(parents=True)
    (video / "index.tsx").write_text("keep me", encoding="utf-8")
    rt = engine(here, "gone-1234abcd", here / "gone")
    (rt / ".entries" / "night-drive").mkdir(parents=True)
    studio._link_dir(rt / ".entries" / "night-drive" / "src", video)  # a junction on Windows
    studio.prune_engines()
    assert not rt.exists() and (video / "index.tsx").read_text(encoding="utf-8") == "keep me"


def test_read_only_files_and_folders_are_removed(here):
    rt = engine(here, "gone-1234abcd", here / "gone")
    pkg = rt / "node_modules" / "locked"
    pkg.mkdir()
    (pkg / "a.js").write_text("x", encoding="utf-8")
    os.chmod(pkg / "a.js", stat.S_IREAD)
    if sys.platform != "win32":
        os.chmod(pkg, stat.S_IREAD | stat.S_IEXEC)
    [r] = studio.prune_engines()
    assert r.removed and not rt.exists()


def test_freed_space_leaves_out_files_shared_by_hard_links(here):
    src = installed_engine(here / "install" / "engine", '{"v": 1}')
    big = src / "node_modules" / "big.bin"
    big.write_bytes(b"x" * 50_000)
    rt = engine(here, "gone-1234abcd", here / "gone")
    os.link(big, rt / "node_modules" / "big.bin")  # seeded: the installed engine keeps these bytes
    (rt / "node_modules" / "own.bin").write_bytes(b"y" * 20_000)
    [r] = studio.prune_engines()
    assert 20_000 <= r.freed < 50_000 and big.read_bytes() == b"x" * 50_000


def test_an_interrupted_removal_is_finished_next_time(here):
    left = here / "install" / ".trash" / "gone-1234abcd-0000"
    (left / "node_modules").mkdir(parents=True)
    (left / "node_modules" / "a.js").write_text("x", encoding="utf-8")
    studio.prune_engines()
    assert not left.exists()


def test_doctor_removes_them_and_says_what_it_freed(here, monkeypatch, capsys):
    from musicvideo import doctor
    installed_engine(here / "install" / "engine", '{"v": 1}')
    rt = engine(here, "gone-1234abcd", here / "gone")
    monkeypatch.setattr(doctor.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(doctor, "_node_major", lambda: 22)
    assert doctor.run_doctor(install=False) == 0
    out = capsys.readouterr().out
    assert f"removed the engine of the removed checkout {here / 'gone'}" in out and "freed" in out
    assert not rt.exists() and studio.is_installed(studio.runtime_dir())
