# music-video engine isolation (concurrency phase 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Two music-video commands, from different plugin copies or for different videos, can run at once without
overwriting, pruning or reinstalling each other's engine. Two `web` builds can run at once without swapping song data
(#18).

**Architecture:**
- **One engine per plugin checkout.** The installed plugin keeps `<install>/engine`. Each git checkout of the plugin
  gets `<install>/engines/<key>`, and its `node_modules` is seeded by hard links from an engine that has the same lock.
- **Locks and leases.**
  - An exclusive file lock serialises changes to an engine.
  - A lease file per running command stops another plugin copy from re-syncing, or `npm ci`, under that command.
- **Web staging.** The `web` build stages its song data in a temporary folder per run, beside the video's entry.

**Tech Stack:** Python 3 stdlib (`fcntl`/`msvcrt`, `ctypes`, `os.link`), pytest, TypeScript + Vite (`studio/tools/web.ts`).

**Spec:** `docs/superpowers/specs/2026-11-01-music-video-concurrency-design.md`: §2.2, §4.5, §4.7, §8 phase 1,
§9.2, and §10 as settled on 2026-11-03.

## Global Constraints

- Windows and macOS. CI runs `uv run pytest -q` on `macos-latest` and `windows-latest`. Every file read and write
  passes `encoding="utf-8"`, and subprocesses take argument lists.
- No new Python dependency: stdlib only.
- **No change for the installed plugin.** A plugin copy with no `.git` at `PLUGIN_STUDIO.parent` or
  `PLUGIN_STUDIO.parents[1]` keeps `install_dir()/"engine"`, with today's `.entries/<id>`, `.synced.json` and
  `.installed-lock`.
- The existing tests pass unchanged, except `test_the_engine_lives_in_the_install_folder`. Task 1 rewrites it, because
  pytest runs from a git checkout, which is now a dev checkout.
- `npm ci` stays a `doctor`-only step. `ensure_ready()` never touches the network.
- The engine lock is **not re-entrant**: take it only in `ensure_ready()` and `run_doctor()`, never inside `install`,
  `sync_runtime` or `seed_modules`.
- Version: 0.6.8, set in `music-video/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` and
  `music-video/scripts/musicvideo/__init__.py`. `tests/test_mv_packaging.py` checks that they agree.
- Gates: `uv run pytest -q`, and on this Mac `uv run pytest -m studio -q`, which needs the engine `doctor` installed.

## Review Focus

- **An interrupted seed** (Ctrl-C mid-link) leaves `node_modules` without `.installed-lock`. The next command must
   discard it and seed again, not fail or use half a tree. Test in Task 2.
- **A command killed with `kill -9`** leaves its lease behind. Its pid is dead, so the next command ignores and deletes
  it. If the pid is reused, the 48 h cap ends the lease. Test in Task 4.
- **An install folder with a space and `é`** (as on real machines) must work for the lock file, the lease folder and
  hard links. Tests in Tasks 3 and 4 use such a path.
- **A dev checkout on a machine with no installed engine** gets a one-line "run music-video doctor", as today. `doctor`
  then installs into the dev engine. Test in Task 2.
- **A `web` build that fails mid-way** (a bad `web.tsx`) leaves no `web-data-*` folder behind. Source check in Task 5.

---

### Task 1: One engine per plugin checkout

**Files:**
- Modify: `music-video/scripts/musicvideo/workspace.py` (add `folder_key`)
- Modify: `music-video/scripts/musicvideo/studio.py:38-49` (`runtime_dir`, `migrate_old_runtime`; add `plugin_checkout`, `touch_owner`)
- Modify: `music-video/scripts/musicvideo/doctor.py` (engine line)
- Create: `tests/test_mv_engine.py`
- Modify: `tests/test_mv_studio.py:119-120`

**Interfaces:**
- Produces:
  - `workspace.folder_key(root: Path) -> str`, which phase 2 reuses for lane keys
  - `studio.plugin_checkout(studio_dir: Path | None = None) -> Path | None`
  - `studio.runtime_dir() -> Path`
  - `studio.touch_owner(rt: Path) -> None`
  - `studio.OWNER = ".owner.json"`
  - test helpers in `tests/test_mv_engine.py`: `installed_copy(tmp_path) -> Path` and `dev_copy(tmp_path, name, worktree=False, lock='{}') -> Path`. Each returns a `studio/` folder holding `package-lock.json`.

- [ ] **Step 1: Write the failing tests** in `tests/test_mv_engine.py`
  - Helpers:
    - `installed_copy` builds `tmp/plugins/cache/daniellandi/music-video/0.6.8/studio`.
    - `dev_copy` builds `tmp/<name>/.git/` (a directory), or with `worktree=True` a `.git` *file* holding `gitdir: …`, plus `tmp/<name>/music-video/studio`.

```python
def test_installed_plugin_uses_todays_engine(tmp_path, monkeypatch):
    monkeypatch.setattr(studio, "PLUGIN_STUDIO", installed_copy(tmp_path))
    assert studio.plugin_checkout() is None
    assert studio.runtime_dir() == tmp_path / "install" / "engine"

def test_two_plugin_checkouts_get_distinct_engines(tmp_path, monkeypatch):
    a, b = dev_copy(tmp_path, "plugins"), dev_copy(tmp_path, "wt", worktree=True)
    monkeypatch.setattr(studio, "PLUGIN_STUDIO", a); ra = studio.runtime_dir()
    monkeypatch.setattr(studio, "PLUGIN_STUDIO", b); rb = studio.runtime_dir()
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

def test_dev_engine_records_its_checkout(tmp_path, monkeypatch):
    monkeypatch.setattr(studio, "PLUGIN_STUDIO", dev_copy(tmp_path, "plugins"))
    rt = studio.runtime_dir(); studio.touch_owner(rt)
    owner = json.loads((rt / studio.OWNER).read_text(encoding="utf-8"))
    assert owner["checkout"] == str(tmp_path / "plugins") and owner["created"] and owner["last_used"]

def test_old_cache_engine_migrates_to_the_installed_engine_only(tmp_path, monkeypatch):
    monkeypatch.setattr(studio, "PLUGIN_STUDIO", dev_copy(tmp_path, "plugins"))
    (tmp_path / "cache" / "studio" / "node_modules").mkdir(parents=True)
    assert studio.migrate_old_runtime() is True
    assert (tmp_path / "install" / "engine" / "node_modules").is_dir()
```

  Rewrite `test_the_engine_lives_in_the_install_folder` in `tests/test_mv_studio.py`: it sets `PLUGIN_STUDIO` to a
  folder with no `.git` around it before asserting `install/engine`.

- [ ] **Step 2: Run them and check they fail**
  - Run: `uv run pytest tests/test_mv_engine.py tests/test_mv_studio.py -q`
  - Expected: FAIL, with `ImportError: folder_key` and `AttributeError: plugin_checkout`.

- [ ] **Step 3: Implement**
  - `folder_key(root)`:
    - The slug is `root.name` lowercased, with each run of characters outside `[a-z0-9]` turned into a single `-`, stripped of `-`, cut to 24 characters, and `"x"` if empty.
    - Then `-`, then the first 8 hex of `sha256(os.path.normcase(str(root.resolve())).encode("utf-8"))`.
  - `plugin_checkout()`: the first of `studio_dir.parent` and `studio_dir.parents[1]` that has a `.git` (file or directory), else `None`.
  - `runtime_dir()`:
    - `MV_ENGINE_DIR` (`expanduser().resolve()`) if set.
    - Else `install_dir()/"engine"` for an installed copy.
    - Else `install_dir()/"engines"/folder_key(checkout)`.
  - `touch_owner(rt)`:
    - Only for a dev checkout.
    - Writes `{"checkout", "created", "last_used"}` as ISO times, then rewrites `last_used` only when it is over an hour old.
    - Called at the end of `ensure_ready()` and by `doctor`.
  - `migrate_old_runtime()` always moves to `install_dir()/"engine"`.
  - `doctor` prints `ok   video engine for the checkout <checkout> in <rt>` for a dev engine, and today's line otherwise.

- [ ] **Step 4: Run the full suite**
  - Run: `uv run pytest -q`
  - Expected: PASS. `test_not_installed_says_doctor` keeps passing because it points `PLUGIN_STUDIO` at a tree with no `.git`.

- [ ] **Step 5: Commit**: `music-video: one engine per plugin checkout`

### Task 2: Seed a new engine's packages by hard links

**Files:**
- Modify: `music-video/scripts/musicvideo/studio.py` (add `SEED_SKIP`, `find_seed`, `link_tree`, `seed_modules`; `ensure_ready`)
- Modify: `music-video/scripts/musicvideo/doctor.py` (seed before `install`)
- Test: `tests/test_mv_engine.py`

**Interfaces:**
- Consumes: `runtime_dir`, `plugin_checkout`, `is_installed`, `lock_hash`, `LOCK_STAMP`.
- Produces:
  - `studio.SEED_SKIP = {".cache", ".vite", ".vite-temp"}`: names directly under `node_modules` that are never linked.
  - `studio.find_seed(rt: Path) -> Path | None`
  - `studio.link_tree(src: Path, dest: Path, skip: set[str] = frozenset()) -> None`
  - `studio.seed_modules(rt: Path) -> Path | None`: the engine it seeded from, or `None`.

- [ ] **Step 1: Write the failing tests**
  - Helper `installed_engine(root, lock_text)`. It builds `root/package-lock.json` and these files under `root/node_modules/`:
    - `remotion/index.js`
    - `.remotion/chrome/bin`
    - `.cache/w.json`
    - `.vite/deps.json`
    - `.bin/remotion`, a symlink to `../remotion/index.js`, where `os.symlink` works
  - Then it writes `root/.installed-lock = lock_hash(root)`.

```python
def test_seed_hard_links_modules_when_locks_match(tmp_path, monkeypatch):
    src = installed_engine(tmp_path / "install" / "engine", '{"v": 1}')
    monkeypatch.setattr(studio, "PLUGIN_STUDIO", dev_copy(tmp_path, "plugins", lock='{"v": 1}'))
    rt = studio.ensure_ready()                      # no doctor needed
    a, b = src / "node_modules/remotion/index.js", rt / "node_modules/remotion/index.js"
    assert os.stat(a).st_ino == os.stat(b).st_ino
    assert (rt / "node_modules/.remotion/chrome/bin").is_file()
    assert not (rt / "node_modules/.cache").exists() and not (rt / "node_modules/.vite").exists()
    assert studio.is_installed(rt)

def test_seed_falls_back_to_doctor_when_locks_differ(...)      # src lock {"v": 1}, checkout {"v": 2} → MVError "music-video doctor"
def test_no_installed_engine_says_doctor(...)                  # nothing under install/ → MVError "music-video doctor"
def test_seeded_engine_survives_a_reinstall_of_its_source(...)  # unlink + rewrite src file (as npm ci) → rt's file keeps old text
def test_seed_copies_when_links_fail(...)                       # monkeypatch os.link to raise OSError → files present, different st_ino
def test_interrupted_seed_is_redone(...)                        # rt/node_modules/half.js exists, no stamp → after ensure_ready, half.js gone, seeded tree present
```

- [ ] **Step 2: Run them and check they fail**
  - Run: `uv run pytest tests/test_mv_engine.py -q -k seed`
  - Expected: FAIL.

- [ ] **Step 3: Implement**
  - `find_seed(rt)`:
    - Candidates: `install_dir()/"engine"`, then `sorted((install_dir()/"engines").iterdir())`, excluding `rt`.
    - Returns the first that `is_installed(c)` and whose `LOCK_STAMP` text equals `lock_hash(rt)`.
  - `link_tree`:
    - Walks with `os.scandir`. Recreates directories, recreates symlinks with `os.readlink` + `os.symlink`, and `os.link`s files.
    - Skips `skip` names at the top level only.
    - On the first `OSError`, it removes the partial `dest` and runs `shutil.copytree(src, dest, symlinks=True, ignore=…)` for the same skip set.
  - `seed_modules(rt)`:
    - Returns `None` without a seed source.
    - Otherwise removes `rt/"node_modules"` (`shutil.rmtree`, ignoring a missing folder), runs `link_tree(seed/"node_modules", rt/"node_modules", SEED_SKIP)`, writes `rt/LOCK_STAMP = lock_hash(rt)`, and returns the seed.
  - `ensure_ready()`:
    - After sync, if not installed, calls `seed_modules`.
    - When it seeds, prints `seeded the engine for this checkout from <seed>` to stderr.
    - Then runs today's check.
  - `doctor`: tries `seed_modules` before `install`, and prints `ok   video engine seeded from <seed>`.

- [ ] **Step 4: Run the suite**
  - Run: `uv run pytest -q`
  - Expected: PASS. The symlink assertion is skipped where `os.symlink` raises `OSError` (Windows without Developer Mode).

- [ ] **Step 5: Commit**: `music-video: seed a checkout's engine by hard links`

### Task 3: Engine lock

**Files:**
- Modify: `music-video/scripts/musicvideo/studio.py` (add `engine_lock`; use it in `ensure_ready`)
- Modify: `music-video/scripts/musicvideo/doctor.py` (hold it around migrate, sync, seed and install)
- Test: `tests/test_mv_engine.py`

**Interfaces:**
- Produces: `studio.engine_lock(rt: Path, timeout: float = 600.0, notice_after: float = 2.0)`, a `contextlib.contextmanager` around the lock file `rt/".lock"`.

- [ ] **Step 1: Write the failing tests.** These use a helper process,
  `subprocess.Popen([sys.executable, "-c", HOLD, str(rt), "1.5"])`. `HOLD` imports `musicvideo.studio` with
  `sys.path` set to `music-video/scripts`, takes `engine_lock(rt)`, prints `held`, sleeps, and exits. The parent waits
  for `held` on stdout.

```python
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
    with pytest.raises(MVError, match="updating the engine"):
        with studio.engine_lock(rt, timeout=0.5, notice_after=0.1):
            pass
    assert "waiting for another music-video command" in capsys.readouterr().err
    child.kill()
```

- [ ] **Step 2: Run them and check they fail**
  - Run: `uv run pytest tests/test_mv_engine.py -q -k lock`
  - Expected: FAIL.

- [ ] **Step 3: Implement**
  - The lock: `rt.mkdir(parents=True, exist_ok=True)`, then open `rt/".lock"` in `"a+b"` mode.
    - POSIX: `fcntl.flock(fd, LOCK_EX | LOCK_NB)`.
    - Windows: `fd.seek(0)` and `msvcrt.locking(fd.fileno(), msvcrt.LK_NBLCK, 1)`.
    - Poll every 0.1 s.
  - Messages:
    - After `notice_after`, print `waiting for another music-video command to finish updating the engine…` to stderr, once.
    - After `timeout`, raise `MVError("another music-video command has been updating the engine in <rt> for 10 minutes: try again when it ends")`, with minutes computed from `timeout`.
  - Release in `finally`.
  - Take the lock in `ensure_ready()` around sync and seed, and in `run_doctor` around migrate, sync, seed and install.

- [ ] **Step 4: Run the suite**
  - Run: `uv run pytest -q`
  - Expected: PASS.

- [ ] **Step 5: Commit**: `music-video: an engine lock around sync, seed and install`

### Task 4: Leases

**Files:**
- Modify: `music-video/scripts/musicvideo/studio.py` (add `sync_plan`, `pid_alive`, `take_lease`, `live_leases`, `release_leases`; refactor `sync_runtime` onto `sync_plan`; check leases in `ensure_ready` and `install`)
- Modify: `music-video/scripts/musicvideo/cli.py:328-333` (`_prepare` takes a lease), `cli.py:547-555` (`main` releases in `finally`)
- Test: `tests/test_mv_engine.py`

**Interfaces:**
- Consumes: `engine_lock`.
- Produces:
  - `studio.LEASES = ".leases"`
  - `studio.LEASE_MAX_AGE = 48 * 3600`
  - `studio.sync_plan(src: Path, dest: Path) -> tuple[list[str], list[str]]`: the paths to copy and to delete, relative and in POSIX form.
  - `studio.pid_alive(pid: int) -> bool`
  - `studio.take_lease(rt: Path, video_id: str) -> Path`
  - `studio.live_leases(rt: Path) -> list[dict]`
  - `studio.release_leases() -> None`

- [ ] **Step 1: Write the failing tests.**
  - A live lease is written for a sleeping child: `subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])`, with a hand-written lease JSON naming its pid. The child is killed in `finally`.
  - The engine is shared through `MV_ENGINE_DIR`, so a lease's `source` can differ from `PLUGIN_STUDIO`.

```python
def test_sync_from_another_source_refuses_while_leased(...):   # src changed + live lease, source "/other/studio", version "0.6.7"
    with pytest.raises(MVError, match=r"in use by music-video 0\.6\.7 .*video night-drive"): studio.ensure_ready()
def test_same_source_or_empty_plan_proceeds_while_leased(...)  # lease source == str(PLUGIN_STUDIO) → ok; other source + nothing to sync → ok
def test_dead_or_old_lease_is_ignored_and_removed(...)          # pid of an exited child; and a live pid with started = now - 49 h → both files deleted, list empty
def test_install_refuses_while_leased(...)                      # monkeypatch shutil.which("npm"); MVError "in use"; npm never called
def test_a_command_holds_a_lease_while_it_runs(mv_ws, web_video)  # fake run_node records live_leases(rt) → one lease, video "night-drive"; after main(): .leases empty
def test_sync_plan_matches_sync_runtime(...)                    # plan for the tree in test_sync_copies_updates_and_prunes == what sync_runtime then does
```

- [ ] **Step 2: Run them and check they fail**
  - Run: `uv run pytest tests/test_mv_engine.py tests/test_mv_web.py -q -k "lease or plan"`
  - Expected: FAIL.

- [ ] **Step 3: Implement**
  - `pid_alive`:
    - POSIX: `os.kill(pid, 0)`. `ProcessLookupError` → False, `PermissionError` → True.
    - Windows: `ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)` and `GetExitCodeProcess`; alive when the code is 259, then `CloseHandle`. Never `os.kill` on Windows.
  - Lease files:
    - Each file is `rt/LEASES/<pid>-<secrets.token_hex(4)>.json` holding `{"pid", "started": time.time(), "version": __version__, "source": str(PLUGIN_STUDIO), "video": video_id}`.
    - `take_lease` appends the path to the module list `_held`.
    - `live_leases` deletes unreadable, dead or over-age files.
  - `ensure_ready()` under the lock: if `sync_plan` is non-empty and a live lease has another `source`, raise `MVError(f"the engine is in use by music-video {version} (pid {pid}, video {video}): wait for it to finish, then run again")`.
  - `install(rt)`: raise the same message before `npm ci` when any lease is live.
  - `_prepare`: call `studio.take_lease(rt, video_id)` right after `ensure_ready()`.
  - `main`: `try: … finally: studio.release_leases()`.

- [ ] **Step 4: Run the suite**
  - Run: `uv run pytest -q`
  - Expected: PASS.

- [ ] **Step 5: Commit**: `music-video: leases keep another plugin copy from changing an engine in use`

### Task 5: Song data staged per `web` run (#18)

**Files:**
- Modify: `music-video/studio/tools/web.ts:50-64` (staging), `:90-105` (alias), and wrap the build in `try/finally`
- Modify: `music-video/studio/web/main.tsx:12`
- Test: `tests/test_mv_web.py`; `tests/test_mv_e2e.py` (studio-marked)

**Interfaces:**
- Consumes: `MV_WEB_ENTRY`, already passed by `cmd_web`. Its folder is `.entries/<id>/`.
- Produces: the import specifier `@mv/web-data/score.json?url`, resolved by a Vite alias to this run's staging folder.

- [ ] **Step 1: Write the failing tests**

```python
def test_web_stages_song_data_per_run():
    ts = (studio.PLUGIN_STUDIO / "tools" / "web.ts").read_text(encoding="utf-8")
    page = (studio.PLUGIN_STUDIO / "web" / "main.tsx").read_text(encoding="utf-8")
    assert "join(web, '.data')" not in ts and "mkdtempSync(join(dirname(entryFile), 'web-data-'))" in ts
    assert "finally" in ts and "rmSync(stage" in ts
    assert "from '@mv/web-data/score.json?url'" in page and "./.data/" not in page
```

  In `tests/test_mv_e2e.py`, under `pytest.mark.studio`, add `test_two_web_builds_at_once_keep_their_own_song_data`:
  - Make two template videos, `smoke-a` and `smoke-b`, each with a `web.tsx` from the template.
  - Copy the fixture song into each one's `public/`. In `smoke-b`'s `analysis.json`, set `"bpm"` to a different number.
  - Run both `main(["web", id])` calls in two threads.
  - Assert that each `results_for(id)/web/assets/score-*.json` carries its own bpm.

- [ ] **Step 2: Run them and check they fail**
  - Run: `uv run pytest tests/test_mv_web.py -q -k per_run`
  - Expected: FAIL.

- [ ] **Step 3: Implement**
  - `const stage = mkdtempSync(join(dirname(entryFile), 'web-data-'));` and write `score.json` there.
  - Add the alias `{ find: /^@mv\/web-data\/score\.json/, replacement: join(stage, 'score.json') }`.
  - Wrap everything from the staging to the README write in `try { … } finally { rmSync(stage, { recursive: true, force: true }); }`.
  - `main.tsx` imports `scoreUrl from '@mv/web-data/score.json?url'`, and its comment names the alias.

- [ ] **Step 4: Run the suite and the engine gate**
  - Run: `uv run pytest -q && uv run pytest -m studio -q`
  - Expected: PASS. The studio run seeds `engines/<key>` for this worktree from the installed engine, by hard links, in seconds.

- [ ] **Step 5: Commit**: `music-video: stage web song data per run (#18)`

### Task 6: Release 0.6.8

**Files:**
- Modify: `music-video/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `music-video/scripts/musicvideo/__init__.py` (0.6.8)
- Modify: `music-video/CHANGELOG.md`, `music-video/README.md` (folders table: `engines/<checkout>`)

- [ ] **Step 1:** Bump the three versions and run `uv run pytest tests/test_mv_packaging.py -q`. Expected: PASS.
- [ ] **Step 2:** Write the CHANGELOG entry `## 0.6.8`:
  - A git checkout of the plugin uses its own engine, seeded by hard links.
  - An engine lock, and leases.
  - Two `web` builds at once no longer swap song data (#18).
  - No change for the installed plugin.
- [ ] **Step 3:** Add a README row for `engines/` under the install folder.
- [ ] **Step 4:** Run `uv run pytest -q`. Expected: PASS.
- [ ] **Step 5: Commit**: `music-video 0.6.8: engine per checkout, engine lock, per-run web staging`
