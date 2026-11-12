"""The engine per plugin copy: the installed plugin keeps today's engine, each git checkout of the plugin gets its own."""
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

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
        os.symlink(os.path.join("..", "remotion", "index.js"), root / "node_modules/.bin/remotion")
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


SCRIPTS = Path(studio.__file__).resolve().parents[1]
HOLD = """
import sys, time
sys.path.insert(0, sys.argv[1])
from pathlib import Path
from musicvideo import studio
with studio.engine_lock(Path(sys.argv[2])):
    print("held", flush=True)
    time.sleep(float(sys.argv[3]))
"""


def hold_lock(rt, seconds):
    """Another music-video process holding the engine lock for a while."""
    child = subprocess.Popen([sys.executable, "-c", HOLD, str(SCRIPTS), str(rt), str(seconds)],
                             stdout=subprocess.PIPE, text=True, encoding="utf-8")
    assert child.stdout.readline().strip() == "held"
    return child


def test_engine_lock_serialises_two_commands(tmp_path):
    rt = tmp_path / "install é" / "engine"
    child = hold_lock(rt, seconds=1.5)
    t = time.monotonic()
    with studio.engine_lock(rt, notice_after=0.2):
        assert time.monotonic() - t > 1.0
    child.wait()


def test_engine_lock_gives_up_with_a_message(tmp_path, capsys):
    rt = tmp_path / "install é" / "engine"
    child = hold_lock(rt, seconds=5)
    try:
        with pytest.raises(MVError, match="updating the engine"):
            with studio.engine_lock(rt, timeout=0.5, notice_after=0.1):
                pass
        assert "waiting for another music-video command" in capsys.readouterr().err
    finally:
        child.kill()
        child.wait()


def test_engine_lock_is_free_again_after_use(tmp_path):
    rt = tmp_path / "install é" / "engine"
    with studio.engine_lock(rt):
        pass
    with studio.engine_lock(rt, timeout=0.5):
        pass


def test_doctor_moves_an_old_cache_engine_before_taking_the_lock(tmp_path, monkeypatch, capsys):
    from musicvideo import doctor
    monkeypatch.setattr(studio, "PLUGIN_STUDIO", installed_copy(tmp_path, lock='{"v": 1}'))
    installed_engine(tmp_path / "cache" / "studio", '{"v": 1}')  # where 0.1.0 installed it
    monkeypatch.setattr(doctor.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(doctor, "_node_major", lambda: 22)
    assert doctor.run_doctor(install=False) == 0
    assert f"moved the engine from the cache to {tmp_path / 'install' / 'engine'}" in capsys.readouterr().out
    assert studio.is_installed(tmp_path / "install" / "engine")


@pytest.fixture
def sleeper():
    """A live process to hold a lease (as a render running in another session would)."""
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    yield child
    child.kill()
    child.wait()


def write_lease(rt, pid, source, started=None, version="0.6.7", video="night-drive"):
    (rt / studio.LEASES).mkdir(parents=True, exist_ok=True)
    path = rt / studio.LEASES / f"{pid}-test.json"
    path.write_text(json.dumps({"pid": pid, "started": time.time() if started is None else started,
                                "version": version, "source": str(source), "video": video}), encoding="utf-8")
    return path


@pytest.fixture
def shared_engine(tmp_path, monkeypatch):
    """One engine used by two plugin copies (two installed versions across an update share install/engine)."""
    monkeypatch.setattr(studio, "PLUGIN_STUDIO", installed_copy(tmp_path, lock='{"v": 1}'))
    rt = installed_engine(tmp_path / "install" / "engine", '{"v": 1}')
    studio.ensure_ready()  # synced: nothing left to copy
    return rt


def test_sync_from_another_source_refuses_while_leased(shared_engine, sleeper):
    write_lease(shared_engine, sleeper.pid, "/other/studio")
    (studio.PLUGIN_STUDIO / "kit.ts").write_text("changed", encoding="utf-8")
    with pytest.raises(MVError, match=r"in use by music-video 0\.6\.7 \(pid \d+, video night-drive\)"):
        studio.ensure_ready()
    assert not (shared_engine / "kit.ts").exists()


def test_same_source_or_empty_plan_proceeds_while_leased(shared_engine, sleeper):
    other = write_lease(shared_engine, sleeper.pid, "/other/studio")
    assert studio.ensure_ready() == shared_engine  # nothing to sync: the other copy's render is not touched
    other.unlink()
    write_lease(shared_engine, sleeper.pid, studio.PLUGIN_STUDIO)
    (studio.PLUGIN_STUDIO / "kit.ts").write_text("mine", encoding="utf-8")
    assert studio.ensure_ready() == shared_engine  # my own edits under my own render: proceed, as today
    assert (shared_engine / "kit.ts").read_text(encoding="utf-8") == "mine"


def test_dead_or_old_lease_is_ignored_and_removed(shared_engine, sleeper):
    gone = subprocess.Popen([sys.executable, "-c", "pass"])
    gone.wait()
    dead = write_lease(shared_engine, gone.pid, "/other/studio")
    old = write_lease(shared_engine, sleeper.pid, "/other/studio", started=time.time() - 49 * 3600)
    (shared_engine / studio.LEASES / "junk.json").write_text("{", encoding="utf-8")
    assert studio.live_leases(shared_engine) == []
    assert not dead.exists() and not old.exists() and not list((shared_engine / studio.LEASES).iterdir())


def test_install_refuses_while_leased(shared_engine, sleeper, monkeypatch):
    write_lease(shared_engine, sleeper.pid, "/other/studio")
    ran = []
    monkeypatch.setattr(studio.shutil, "which", lambda name: f"/usr/bin/{name}")
    real = subprocess.run
    monkeypatch.setattr(studio.subprocess, "run",  # npm is faked; ps (who holds the lease) runs for real
                        lambda cmd, *a, **k: real(cmd, *a, **k) if cmd[0] == "ps" else ran.append(cmd))
    with pytest.raises(MVError, match="in use by music-video"):
        studio.install(shared_engine)
    assert ran == []


def test_sync_plan_matches_sync_runtime(tmp_path):
    src, dest = tmp_path / "src", tmp_path / "rt"
    for rel in ("kit/a.ts", "kit/gone.ts", "node_modules/x.js"):
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        (src / rel).write_text(rel, encoding="utf-8")
    assert studio.sync_plan(src, dest) == (["kit/a.ts", "kit/gone.ts"], [])
    studio.sync_runtime(src, dest)
    assert studio.sync_plan(src, dest) == ([], [])
    (src / "kit/gone.ts").unlink()
    assert studio.sync_plan(src, dest) == ([], ["kit/gone.ts"])


def test_doctor_refuses_to_sync_over_another_sources_render(shared_engine, sleeper, monkeypatch, capsys):
    # The make skill runs doctor first in every session: after a plugin update it must not sync over a render
    # still running from the previous version.
    from musicvideo import doctor
    write_lease(shared_engine, sleeper.pid, "/other/studio")
    (studio.PLUGIN_STUDIO / "kit.ts").write_text("changed", encoding="utf-8")
    monkeypatch.setattr(doctor.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(doctor, "_node_major", lambda: 22)
    assert doctor.run_doctor() == 1
    assert "in use by music-video 0.6.7" in capsys.readouterr().out
    assert not (shared_engine / "kit.ts").exists()


def test_seed_refuses_while_the_engine_is_in_use(tmp_path, monkeypatch, sleeper):
    # A pull changed this checkout's lock while one of its own renders runs: re-seeding would replace node_modules
    # under it, as npm ci would.
    installed_engine(tmp_path / "install" / "engine", '{"v": 2}')
    monkeypatch.setattr(studio, "PLUGIN_STUDIO", dev_copy(tmp_path, "plugins", lock='{"v": 2}'))
    # A different size from the new lock: sync compares size and mtime, and Windows file times are coarse.
    mine = installed_engine(studio.runtime_dir(), '{"v": "old"}')
    before = os.stat(mine / "node_modules/remotion/index.js").st_ino
    write_lease(mine, sleeper.pid, studio.PLUGIN_STUDIO)
    with pytest.raises(MVError, match="in use by music-video"):
        studio.ensure_ready()
    assert os.stat(mine / "node_modules/remotion/index.js").st_ino == before


def test_install_clears_the_stamp_before_npm_runs(tmp_path, monkeypatch):
    # npm ci deletes and re-extracts node_modules: while it runs, the engine must not look installed (a checkout
    # seeding from it then would link a half-extracted tree).
    rt = installed_engine(tmp_path / "install" / "engine", '{"v": 1}')
    seen = []
    monkeypatch.setattr(studio.shutil, "which", lambda name: f"/usr/bin/{name}")

    def npm(cmd, cwd):
        seen.append(studio.is_installed(rt))
        return subprocess.CompletedProcess(cmd, 1)
    monkeypatch.setattr(studio.subprocess, "run", npm)
    with pytest.raises(MVError, match="npm ci failed"):
        studio.install(rt)
    assert seen == [False] and not studio.is_installed(rt)


def test_a_folder_that_refuses_locks_fails_at_once_not_as_busy(tmp_path, monkeypatch):
    # A network drive may refuse locks outright (ENOLCK, ENOTSUP): waiting 10 minutes for "another command" misleads.
    import errno
    from musicvideo import filelock
    if sys.platform == "win32":
        import msvcrt
        target, name = msvcrt, "locking"
    else:
        import fcntl
        target, name = fcntl, "flock"

    def refuse(*_a, **_k):
        raise OSError(errno.ENOLCK, "No locks available")
    monkeypatch.setattr(target, name, refuse)
    t = time.monotonic()
    with pytest.raises(MVError, match=r"cannot lock .*\.lock.*No locks available") as e:
        with filelock.file_lock(tmp_path / "engine" / ".lock", timeout=5, busy="another command is updating it"):
            pass
    assert time.monotonic() - t < 1 and "another command" not in str(e.value)


def test_seed_gives_the_engine_its_own_hidden_npm_lockfile(tmp_path, monkeypatch):
    # npm rewrites node_modules/.package-lock.json in place: a hard link would let one engine's npm edit the other's.
    src = installed_engine(tmp_path / "install" / "engine", '{"v": 1}')
    (src / "node_modules/.package-lock.json").write_text('{"packages": {}}', encoding="utf-8")
    monkeypatch.setattr(studio, "PLUGIN_STUDIO", dev_copy(tmp_path, "plugins", lock='{"v": 1}'))
    rt = studio.ensure_ready()
    a, b = src / "node_modules/.package-lock.json", rt / "node_modules/.package-lock.json"
    assert b.read_text(encoding="utf-8") == '{"packages": {}}' and os.stat(a).st_ino != os.stat(b).st_ino
    assert os.stat(src / "node_modules/remotion/index.js").st_ino == os.stat(rt / "node_modules/remotion/index.js").st_ino


def test_seed_says_so_when_it_must_copy_the_packages(tmp_path, monkeypatch, capsys):
    # Copying is about 1.7 GB: never silently.
    installed_engine(tmp_path / "install" / "engine", '{"v": 1}')
    monkeypatch.setattr(studio, "PLUGIN_STUDIO", dev_copy(tmp_path, "plugins", lock='{"v": 1}'))

    def no_links(*_a, **_k):
        raise OSError("hard links not supported")
    monkeypatch.setattr(os, "link", no_links)
    rt = studio.ensure_ready()
    err = capsys.readouterr().err
    assert "hard links not supported" in err and "copying" in err and str(rt / "node_modules") in err


def test_seed_copies_what_a_symlink_points_to_when_symlinks_fail(tmp_path, monkeypatch):
    # Windows without Developer Mode cannot make symlinks: no traceback, the engine still works.
    src = installed_engine(tmp_path / "install" / "engine", '{"v": 1}')
    if not (src / "node_modules/.bin/remotion").is_symlink():
        pytest.skip("no symlinks on this machine")
    os.symlink("remotion", src / "node_modules/linked", target_is_directory=True)  # a linked package (a folder)
    monkeypatch.setattr(studio, "PLUGIN_STUDIO", dev_copy(tmp_path, "plugins", lock='{"v": 1}'))

    def no_symlinks(*_a, **_k):
        raise OSError("symbolic links not permitted")
    monkeypatch.setattr(os, "symlink", no_symlinks)
    rt = studio.ensure_ready()
    shim = rt / "node_modules/.bin/remotion"
    assert not shim.is_symlink() and shim.read_text(encoding="utf-8") == "remotion"
    assert (rt / "node_modules/linked/index.js").read_text(encoding="utf-8") == "remotion"
    a, b = src / "node_modules/remotion/index.js", rt / "node_modules/remotion/index.js"
    assert os.stat(a).st_ino == os.stat(b).st_ino  # the rest is still linked, not copied
    assert studio.is_installed(rt)


def test_an_interrupted_owner_write_leaves_the_old_record_whole(tmp_path, monkeypatch):
    monkeypatch.setattr(studio, "PLUGIN_STUDIO", dev_copy(tmp_path, "plugins"))
    rt = studio.runtime_dir()
    rt.mkdir(parents=True)
    old = {"created": "2026-01-01T00:00:00Z", "checkout": "/somewhere/else", "used_at": 0}
    (rt / studio.OWNER).write_text(json.dumps(old), encoding="utf-8")
    real = Path.write_text

    def half(self, text, *a, **k):  # the disk fills (or the command is stopped) half-way through the write
        real(self, text[: len(text) // 2], *a, **k)
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(Path, "write_text", half)
    studio.touch_owner(rt)  # the record is a hint for finding stale engines: never fatal to the command
    monkeypatch.undo()
    assert json.loads((rt / studio.OWNER).read_text(encoding="utf-8")) == old
    assert [p.name for p in rt.iterdir()] == [studio.OWNER]


def test_the_lease_is_taken_before_the_engine_lock_is_let_go(shared_engine, monkeypatch):
    # Taken after the lock, another plugin copy could take the lock in between, see no lease and sync over the
    # engine this command is about to use.
    from musicvideo import filelock
    real, seen = studio.take_lease, []

    def take(rt, video_id):
        with open(rt / ".lock", "a+b") as fd:  # held by someone else, it cannot be taken from a second handle
            free = filelock._try_lock(fd, rt / ".lock")
            if free:
                filelock._unlock(fd)
        seen.append(free)
        return real(rt, video_id)
    monkeypatch.setattr(studio, "take_lease", take)
    try:
        assert studio.ensure_ready("night-drive") == shared_engine
        assert seen == [False]
        assert [x["video"] for x in studio.live_leases(shared_engine)] == ["night-drive"]
    finally:
        studio.release_leases()


def test_dead_leases_are_swept_even_when_nothing_is_to_sync(shared_engine):
    gone = subprocess.Popen([sys.executable, "-c", "pass"])
    gone.wait()
    dead = write_lease(shared_engine, gone.pid, "/other/studio")
    assert studio.ensure_ready() == shared_engine
    assert not dead.exists()


def test_a_lease_whose_pid_now_names_a_newer_process_is_stale(shared_engine, sleeper):
    # The command that wrote it died and its pid went to another process (here the sleeper, started after it).
    reused = write_lease(shared_engine, sleeper.pid, "/other/studio", started=time.time() - 3600)
    assert studio.live_leases(shared_engine) == [] and not reused.exists()


def test_a_refusal_names_the_lease_to_delete(shared_engine, sleeper):
    lease = write_lease(shared_engine, sleeper.pid, "/other/studio")
    (studio.PLUGIN_STUDIO / "kit.ts").write_text("changed", encoding="utf-8")
    with pytest.raises(MVError) as e:
        studio.ensure_ready()
    assert str(lease) in str(e.value)
