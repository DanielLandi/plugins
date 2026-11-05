# music-video project lanes (concurrency phase 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A music-video session started in a git worktree of the project folder works on that worktree's specs and
video code, with its own work folders, video finals and engine entries, while songs, albums and the download budget
stay shared. Nothing changes for a project folder that is not a linked worktree.

**Architecture:**
- **Lane detection by file reads.** A new module reads `.git` files, `commondir` and `worktrees/*/gitdir` (no `git`
  binary). A project folder inside a *linked* worktree is a lane, keyed `folder_key(<worktree root>)`.
- **The workspace knows its lane.** `workspace_home()` maps the saved workspace into the worktree the cwd is in.
  `Workspace` gains `lane` and `main_home`. `work_for` and `results_for` move under `.lanes/<key>` in a lane, and the
  new `song_dir` stays shared.
- **Engine entries per lane.** `.entries/.lane-<key>/<id>/` in a lane, `.entries/<id>/` as today otherwise.
- **One budget.** `downloaded` and `status` count the specs of every worktree of the repo, once each.

**Tech Stack:** Python 3 stdlib (`pathlib`, `hashlib`), PyYAML (already a dependency), pytest.

**Spec:** `docs/superpowers/specs/2026-11-01-music-video-concurrency-design.md`: §2.1, §2.3, §3, §4.1–§4.4, §4.6,
§4.8, §5, §6, §8 phase 2, §9.1, and §10 as settled on 2026-11-03 (items 1 and 2 are binding: lane finals under
`results_dir/.lanes/<key>/`; song steps allowed in a lane, one budget across worktrees).

## Global Constraints

- **No change for a main checkout.** A project folder that is not inside a linked git worktree resolves to today's
  paths, byte for byte: `work_dir/<id>`, `results_dir/<id>`, `results_dir/albums/<a>`, `.entries/<id>`, the same
  `settings.json` writes and the same command output. The existing tests (`test_mv_workspace.py`,
  `test_mv_studio.py`, `test_mv_studio_cli.py`, `test_mv_video_paths.py`, `test_mv_web.py`, `test_mv_budget.py`,
  `test_mv_ingest.py`, `test_mv_engine.py`) pass unchanged: they are the contract.
- The cwd is consulted **only** inside a linked worktree. A plain folder or a main checkout holding a `config.yaml`
  never overrides the saved workspace.
- `remember_home()` is never called when the home is a lane.
- No `git` subprocess anywhere in lane detection: file reads only, so it works on Windows without git on PATH.
- Lane key = `workspace.folder_key(<worktree root>)` (phase 1's function, unchanged): `<slug ≤24>-<hash8>`.
- Lane folder names: `work_dir/.lanes/<key>/<id>`, `results_dir/.lanes/<key>/<id>`, `<engine>/.entries/.lane-<key>/<id>`.
  `LANES = ".lanes"`. A video id never starts with a dot (`studio.ID_RE`), so none of these can collide with an id.
- Windows and macOS. CI runs `uv run pytest -q` on `macos-latest` and `windows-latest`. Every file read and write
  passes `encoding="utf-8"`.
- No new Python dependency.
- The test suite is often run from a linked worktree *of this plugins repo*. Every test that depends on the cwd sets
  it with `monkeypatch.chdir`; no test may assume the cwd is outside a worktree.
- Lane tests compare paths with `.resolve()` on both sides (macOS `tmp_path` sits behind the `/var` → `/private/var`
  symlink, and `Path.cwd()` returns the resolved form).
- Public repo: no personal names, paths or seasonal-holiday references in code, tests or docs
  (`tests/test_mv_privacy.py`).
- Version: **0.8.0**, set in `music-video/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` and
  `music-video/scripts/musicvideo/__init__.py`. `tests/test_mv_packaging.py` checks that they agree.
- Gates: `uv run pytest -q`; on the Mac, also `uv run pytest -m studio -q` (no engine code changes beyond entry paths,
  but the gate renders through `write_entry`).
- Out of scope (phase 3): timing seeding from the main checkout, the `lanes` command, `doctor --prune-engines`, free
  ports for `edit-timing` and `sections` in a lane. The plugins#19 follow-ups stay in that issue.

## Review Focus

- **A gitignored `private-names.txt`** (the normal case: it holds private names) is absent from a fresh worktree.
  `validate` and `ingest` in that lane would then check nothing. Expected: the main checkout's names still apply.
  Test in Task 2.
- **A git submodule, or a clone made with `--separate-git-dir`**, has a `.git` *file* but no `commondir`. Expected:
  not a lane, today's paths. Test in Task 1.
- **A worktree whose folder was deleted but never pruned** still has an entry in `<common>/worktrees/`. Expected:
  `downloaded` and `status` skip it without an error. Test in Task 5.
- **A relative `results_dir`** (results kept inside the project folder). Expected: in a lane the song is still filed
  into the main checkout's results, and the spec's `kept.file` stays valid after the branch merges and the worktree
  goes. Test in Task 2 (resolution) and Task 5 (ingest).
- **A worktree of a branch made before the workspace folder existed** (the mapped sub-folder is missing in the
  worktree). Expected: no mapping, the saved workspace as today, never an error. Test in Task 2.

---

### Task 1: Read git worktrees from files

**Files:**
- Create: `music-video/scripts/musicvideo/worktrees.py`
- Modify: `tests/mv_fixtures.py` (add `fake_repo`, `fake_worktree`, `Lanes`, fixture `mv_lane`)
- Create: `tests/test_mv_lanes.py`

**Interfaces:**
- Produces:
  - `worktrees.Worktree`: frozen dataclass `root: Path` (the folder holding the `.git` file), `main: Path` (the main
    working tree), `common: Path` (the common git dir, `main/.git`).
  - `worktrees.git_root(folder: Path) -> Path | None`: the nearest of `folder.absolute()` and its parents holding a
    `.git` (file or directory).
  - `worktrees.linked_worktree(folder: Path) -> Worktree | None`
  - `worktrees.repo_worktrees(folder: Path) -> tuple[Path, list[Path]] | None`: `(main root, linked worktree roots
    that still exist)` for any folder in a main checkout or a linked worktree; `None` outside git.
  - In `tests/mv_fixtures.py`:
    - `fake_repo(root: Path) -> Path`: makes `root/.git/` (a directory) and returns `root`.
    - `fake_worktree(main: Path, root: Path, relative: bool = False) -> Path`: makes the admin dir
      `main/.git/worktrees/<root.name>/` with `gitdir` (`<root>/.git`) and `commondir` (`../..`), and the file
      `root/.git` holding `gitdir: <admin dir>` (relative to `root` when `relative=True`, as git ≥ 2.48 writes with
      `worktree.useRelativePaths`). Returns `root`.
    - `Lanes = namedtuple("Lanes", "main a b")`.
    - Fixture `mv_lane(mv_ws, tmp_path) -> Lanes`: `fake_repo(mv_ws.home)`, two worktrees at
      `tmp_path/"worktrees"/"lane-a"` and `…/"lane-b"`, each with `specs/` and `videos/` copied from main and **no**
      `config.yaml` (so the fallback is exercised by default). `MUSIC_VIDEO_HOME` is left pointing at main.

- [ ] **Step 1: Write the failing tests** in `tests/test_mv_lanes.py`

```python
def test_linked_worktree_reads_git_files(tmp_path):
    main = fake_repo(tmp_path / "proj")
    for rel in (False, True):
        w = fake_worktree(main, tmp_path / f"wt-{rel}", relative=rel)
        (w / "sub").mkdir()
        found = linked_worktree(w / "sub")
        assert found.root.resolve() == w.resolve() and found.main.resolve() == main.resolve()
        assert found.common.resolve() == (main / ".git").resolve()

def test_main_checkout_and_plain_folder_are_not_lanes(tmp_path):
    assert linked_worktree(fake_repo(tmp_path / "proj")) is None
    assert linked_worktree(tmp_path) is None

def test_submodule_is_not_a_lane(tmp_path):
    sub = tmp_path / "proj" / "sub"
    (tmp_path / "proj" / ".git" / "modules" / "sub").mkdir(parents=True); sub.mkdir()
    (sub / ".git").write_text("gitdir: ../.git/modules/sub\n", encoding="utf-8")      # no commondir
    assert linked_worktree(sub) is None

def test_repo_worktrees_lists_live_worktrees_only(tmp_path):
    main = fake_repo(tmp_path / "proj")
    a, b = fake_worktree(main, tmp_path / "a"), fake_worktree(main, tmp_path / "b")
    shutil.rmtree(b)                                                                    # deleted, never pruned
    for start in (main, a):
        m, linked = repo_worktrees(start)
        assert m.resolve() == main.resolve() and [p.resolve() for p in linked] == [a.resolve()]
    assert repo_worktrees(tmp_path / "elsewhere") is None

@pytest.mark.skipif(not shutil.which("git"), reason="git not installed")
def test_real_git_worktree_is_detected(tmp_path):
    # git init proj; one empty commit (-c user.name=t -c user.email=t@example.com); git worktree add ../real
    ...
    assert linked_worktree(tmp_path / "real").main.resolve() == (tmp_path / "proj").resolve()
```

- [ ] **Step 2: Run them and check they fail**
  - Run: `uv run pytest tests/test_mv_lanes.py -q`
  - Expected: FAIL with `ModuleNotFoundError: musicvideo.worktrees`.

- [ ] **Step 3: Implement `worktrees.py`**
  - `linked_worktree`: `root = git_root(folder)`; `root/.git` must be a file whose first line is `gitdir: <G>`
    (`G` relative → against `root`); `G/commondir` must exist; `common = (G / commondir text).resolve()`; require
    `common.name == ".git"`; then `Worktree(root, common.parent, common)`. Any `OSError`, `UnicodeDecodeError` or
    missing piece → `None`.
  - `repo_worktrees`: a linked worktree gives its `main` and `common`; a `git_root` whose `.git` is a directory gives
    `(root, root/".git")`; else `None`. Linked roots: for each `common/"worktrees"/*/"gitdir"`, the path it holds
    (relative → against that admin dir), its `.parent`, kept when `(parent/".git").is_file()`. Sorted by `str`.

- [ ] **Step 4: Run the suite**
  - Run: `uv run pytest -q`
  - Expected: PASS.

- [ ] **Step 5: Commit**: `music-video: read git worktrees from their files`

### Task 2: The workspace in a lane

**Files:**
- Modify: `music-video/scripts/musicvideo/workspace.py` (`saved_home`, `is_workspace`, `config_path`,
  `main_counterpart`, `workspace_home`, `Workspace`, `load_workspace`, `stored_path`, `filed_path`,
  `load_private_names`)
- Test: `tests/test_mv_lanes.py`

**Interfaces:**
- Consumes: `worktrees.linked_worktree`, `workspace.folder_key`.
- Produces:
  - `workspace.LANES = ".lanes"`
  - `workspace.saved_home() -> Path | None`: the `workspace` value of `settings.json` (today's step, extracted).
  - `workspace.main_counterpart(folder: Path) -> Path | None`: `wt.main / folder.absolute().relative_to(wt.root)` for
    a folder in a linked worktree, else `None`.
  - `workspace.config_path(home: Path) -> Path`: `home/config.yaml` if it exists, else the main counterpart's if that
    exists, else `home/config.yaml`.
  - `workspace.is_workspace(folder: Path) -> bool`: `config_path(folder)` parses to a mapping with a non-empty
    `artist`, and `folder/"specs"` is a directory. Never raises.
  - `Workspace` new fields, both defaulted so existing constructions keep working: `lane: str | None = None`,
    `main_home: Path | None = None` (`__post_init__` sets it to `home` when `None`, via `object.__setattr__`).
  - `Workspace.work_root -> Path`: `work_dir` | `work_dir/LANES/<lane>`.
  - `Workspace.finals_root -> Path`: `results_dir` | `results_dir/LANES/<lane>`.
  - `Workspace.work_for(id) -> work_root/id`, `results_for(id) -> finals_root/id`,
    `Workspace.song_dir(id) -> results_dir/id` (always shared). `album_dir` unchanged.

- [ ] **Step 1: Write the failing tests** (§9.1 names, plus the Review Focus cases)

```python
def test_plain_folder_resolves_to_todays_paths(mv_ws, tmp_path):
    assert mv_ws.lane is None and mv_ws.main_home == mv_ws.home
    assert mv_ws.work_root == tmp_path / "My Work é"
    assert mv_ws.work_for("x") == tmp_path / "My Work é" / "x"
    assert mv_ws.results_for("x") == mv_ws.song_dir("x") == tmp_path / "My Results é" / "x"
    assert mv_ws.album_dir("a") == tmp_path / "My Results é" / "albums" / "a"

def test_main_checkout_of_a_repo_resolves_to_todays_paths(mv_ws, mv_lane):   # same asserts, .git is a directory
def test_two_worktrees_get_distinct_folders(mv_lane, monkeypatch):
    # MUSIC_VIDEO_HOME = a, then b, then main: work_for, results_for differ pairwise; song_dir and album_dir equal;
    # a.lane == load_workspace(a).lane (stable); results_for("x") == results_dir / ".lanes" / a.lane / "x"
def test_lane_key_is_readable_and_distinct_for_same_folder_name(mv_ws, tmp_path):
    # two worktrees both named "feature" under different parents → keys start "feature-", differ
def test_cwd_in_worktree_maps_the_saved_workspace(mv_lane, tmp_path, monkeypatch):
    # delenv MUSIC_VIDEO_HOME; remember_home(main); chdir(lane.a / "videos") → workspace_home().resolve() == lane.a.resolve()
    # and again with the workspace in a sub-folder "music" of the repo root: chdir(worktree / "music" / "specs") → worktree / "music"
def test_cwd_outside_a_worktree_keeps_the_saved_workspace(mv_lane, tmp_path, monkeypatch):
    # chdir into a plain folder holding a valid config.yaml + specs/ → the saved workspace; same inside a main checkout
def test_worktree_missing_the_workspace_folder_keeps_the_saved_workspace(...):
    # saved = main / "music"; worktree has no "music" folder; chdir(worktree) → saved
def test_music_video_home_still_wins(mv_lane, monkeypatch):
    # chdir(lane.a); MUSIC_VIDEO_HOME = lane.b → home is b, lane is b's key (lane-ness follows the folder)
def test_worktree_without_config_reads_the_main_config(mv_lane, monkeypatch):
    # MUSIC_VIDEO_HOME = lane.a → artist "Test Artist", billing_day 15; then write lane.a/config.yaml with another
    # artist → the lane's own wins; videos_dir resolves under lane.a
def test_relative_results_dir_in_a_lane_is_mains(mv_lane, monkeypatch):
    # main config results_dir: "results" → in lane a: results_dir == main / "results",
    # stored_path(ws, main / "results" / "x" / "s.mp3") == "results/x/s.mp3", filed_path of it is under main
def test_private_names_fall_back_to_main(mv_lane, monkeypatch):
    # main/private-names.txt "Secret Name"; lane has none → ["Secret Name"]; lane adds "Other" → both, once each
```

- [ ] **Step 2: Run them and check they fail**
  - Run: `uv run pytest tests/test_mv_lanes.py -q`
  - Expected: FAIL with `AttributeError: 'Workspace' object has no attribute 'lane'`.

- [ ] **Step 3: Implement**
  - `workspace_home()`: `MUSIC_VIDEO_HOME`; else `_mapped_home(Path.cwd(), saved_home())` if not `None`; else
    `saved_home()`; else `DEFAULT_HOME`.
  - `_mapped_home(cwd: Path, saved: Path | None) -> Path | None`, only when `linked_worktree(cwd)` is a `wt`:
    1. If `saved` is set and `saved.expanduser().resolve()` is inside `wt.main.resolve()`: `candidate = wt.root /
       rel`; return it when `is_workspace(candidate)`.
    2. Else the nearest of `cwd` and its parents up to and including `wt.root` with `is_workspace(folder)`.
    3. Else `None`.
  - `load_workspace(home)`:
    - Reads `config_path(home)`. The error when it is missing names both places: `no workspace at {home} (no
      config.yaml here or in {main counterpart})`, or today's message when not in a lane.
    - `lane = folder_key(wt.root)` and `main_home = main_counterpart(home)` when `linked_worktree(home)`, else `None`
      and `home`.
    - `videos_dir`, `work_dir` resolve relative values against `home`. `results_dir`, `downloads_dir` resolve
      against `main_home`.
  - `stored_path` and `filed_path` use `ws.main_home` where they used `ws.home` (identical in a main checkout).
  - `load_private_names`: the names of `home/private-names.txt` then, in a lane, of
    `main_home/private-names.txt`, in order, without duplicates.

- [ ] **Step 4: Run the suite**
  - Run: `uv run pytest -q`
  - Expected: PASS, the existing `test_mv_workspace.py` untouched.

- [ ] **Step 5: Commit**: `music-video: a workspace in a git worktree is a lane with its own work and finals`

### Task 3: Engine entries per lane

**Files:**
- Modify: `music-video/scripts/musicvideo/studio.py` (add `entry_dir`; `write_entry`, `VideoContext`,
  `video_context`, `linked_video`, `web_entry`, `take_lease`, `_in_use`)
- Modify: `music-video/scripts/musicvideo/cli.py` (`_prepare`)
- Test: `tests/test_mv_engine.py`, `tests/test_mv_lanes.py`

**Interfaces:**
- Consumes: `Workspace.lane`, `Workspace.results_for`.
- Produces:
  - `studio.entry_dir(rt: Path, video_id: str, lane: str | None = None) -> Path`: `rt/".entries"/video_id`, or
    `rt/".entries"/f".lane-{lane}"/video_id`.
  - `studio.write_entry(rt, video_dir, video_id, lane: str | None = None) -> Path`
  - `VideoContext.lane: str | None = None` (the last field, defaulted).
  - `studio.take_lease(rt, video_id, lane: str | None = None) -> Path`: the lease JSON gains `"lane"`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_mv_engine.py
def test_entries_are_keyed_by_lane(mv_lane, tmp_path, monkeypatch):
    # a video "night-drive" with index.tsx in main and in lane a (copied by mv_lane); ctx for each via
    # VideoContext(..., lane=ws.lane); rt = tmp_path / "rt"
    assert studio.write_entry(rt, main_dir, "night-drive") == rt / ".entries" / "night-drive" / "index.ts"
    assert studio.write_entry(rt, a_dir, "night-drive", lane=key_a) == rt / ".entries" / f".lane-{key_a}" / "night-drive" / "index.ts"
    assert studio.linked_video(rt, ctx_main).resolve() == main_dir.resolve()
    assert studio.linked_video(rt, ctx_a).resolve() == a_dir.resolve()     # main's link not re-pointed
    assert studio.linked_video(rt, ctx_main).resolve() == main_dir.resolve()

def test_a_lease_names_its_lane(tmp_path):
    lease = json.loads(studio.take_lease(tmp_path / "rt", "night-drive", lane="lane-a-1234abcd").read_text(encoding="utf-8"))
    assert lease["lane"] == "lane-a-1234abcd"
    studio.release_leases()

# tests/test_mv_lanes.py (fixture order: web_video before mv_lane, so the lane copies the video folder)
def test_web_default_out_in_a_lane_is_the_lane_folder(web_video, mv_lane, monkeypatch):
    # MUSIC_VIDEO_HOME = lane.a; timing.json + analysis.json in the lane's work_for("night-drive")/public
    # main(["web", "night-drive"]) == 0; the --out passed is results_dir/.lanes/<key>/night-drive/web, never
    # results_dir/night-drive/web; MV_WEB_ENTRY is under .entries/.lane-<key>/
def test_library_does_not_list_lane_results(mv_ws, tmp_path):
    # a file under results_dir/.lanes/k/x/final.mp4 and one under results_dir/x/final.mp4 → library.scan lists only the second
```

  Also add to `test_plain_folder_resolves_to_todays_paths`: `studio.write_entry(rt, …, "x")` is
  `rt/".entries"/"x"/"index.ts"` when `ws.lane is None`.

- [ ] **Step 2: Run them and check they fail**
  - Run: `uv run pytest tests/test_mv_engine.py tests/test_mv_lanes.py -q -k "lane or library"`
  - Expected: FAIL with `TypeError: write_entry() got an unexpected keyword argument 'lane'`.

- [ ] **Step 3: Implement**
  - `write_entry`, `linked_video` and `web_entry` build their folder with `entry_dir`. `typecheck_config` already
    follows `linked_video(...).parent`.
  - `video_context` passes `lane=ws.lane`.
  - `_in_use` appends `, worktree {lane}` after the video when the lease has one.
  - `_prepare`: `take_lease(rt, video_id, ws.lane)` and `write_entry(rt, ctx.dir, video_id, lane=ctx.lane)`.
  - No TypeScript change: `web.ts` stages beside `MV_WEB_ENTRY` (phase 1), so staging follows the entry into the
    lane's folder.

- [ ] **Step 4: Run the suite**
  - Run: `uv run pytest -q`
  - Expected: PASS.

- [ ] **Step 5: Commit**: `music-video: engine entries per lane`

### Task 4: `init`, `paths`, `clean` and `doctor` in a lane

**Files:**
- Modify: `music-video/scripts/musicvideo/workspace.py` (`init_workspace`)
- Modify: `music-video/scripts/musicvideo/cli.py` (`cmd_init`, `cmd_paths`, `cmd_clean`)
- Modify: `music-video/scripts/musicvideo/doctor.py`
- Test: `tests/test_mv_lanes.py`

**Interfaces:**
- Consumes: `linked_worktree`, `saved_home`, `config_path`, `Workspace.work_root`, `Workspace.finals_root`.
- Produces: no new names; command output below.

- [ ] **Step 1: Write the failing tests**

```python
def test_init_in_a_lane_keeps_settings(mv_lane, tmp_path, capsys, monkeypatch):
    before = (tmp_path / "settings.json").read_bytes()
    monkeypatch.delenv("MUSIC_VIDEO_HOME"); monkeypatch.chdir(mv_lane.a)
    assert main(["init"]) == 0                                   # no --artist needed: main's config counts
    assert (tmp_path / "settings.json").read_bytes() == before
    assert not (mv_lane.a / "config.yaml").exists()
    out = capsys.readouterr().out
    assert "this is a worktree of" in out and "the saved workspace stays" in out

def test_paths_in_a_lane(mv_lane, capsys, monkeypatch):
    # main: keys exactly {"video","work","public","renders","qc","results","web"} (no "lane"), values as today
    # lane a: out["lane"] == key; work/renders/qc/public under work_dir/.lanes/key; results/web under results_dir/.lanes/key

def test_clean_in_a_lane_removes_only_lane_work(mv_lane, capsys, monkeypatch):
    # work_dir/night-drive and work_dir/.lanes/<key>/night-drive both exist; clean in lane a → only the lane one gone;
    # clean in main → only work_dir/night-drive gone, .lanes untouched

def test_doctor_names_the_lane(mv_lane, capsys, monkeypatch):
    # stub doctor.shutil.which and doctor._node_major as test_doctor_seeds_a_checkouts_engine_instead_of_installing
    # in tests/test_mv_engine.py does; MUSIC_VIDEO_HOME = lane.a; run_doctor(install=False) (its return code is not asserted);
    # out has f"ok   worktree {key} of {main}: work in {work_root}, video finals in {finals_root}"
```

- [ ] **Step 2: Run them and check they fail**
  - Run: `uv run pytest tests/test_mv_lanes.py -q -k "init or paths or clean or doctor"`
  - Expected: FAIL.

- [ ] **Step 3: Implement**
  - `init_workspace`: `created = not config_path(home).is_file()`. Call `remember_home(home)` only when
    `linked_worktree(home)` is `None`.
  - `cmd_init`: the `--artist` check uses `config_path(home)`. In a lane, after today's line, print
    `this is a worktree of {wt.main}; the saved workspace stays {saved_home() or 'unset'}`.
  - `cmd_paths`: add `"lane": ws.lane` to the JSON **only when** `ws.lane` is set, as the last key.
  - `cmd_clean`: `work_root = ws.work_root.expanduser().resolve()` replaces `work_dir` in the target and parent
    check. The overlap checks are unchanged. Messages say "work folder {work_root}".
  - `doctor`: the "no workspace" check uses `config_path(workspace_home())`. In a lane, print the line from the test
    right after the workspace line.

- [ ] **Step 4: Run the suite**
  - Run: `uv run pytest -q`
  - Expected: PASS; `test_paths_command` and the `test_clean_*` tests in `test_mv_video_paths.py` are unchanged.

- [ ] **Step 5: Commit**: `music-video: init, paths, clean and doctor know the lane`

### Task 5: Song steps and the one download budget

**Files:**
- Modify: `music-video/scripts/musicvideo/workspace.py` (add `worktree_homes`)
- Modify: `music-video/scripts/musicvideo/spec.py` (add `iter_worktree_specs`)
- Modify: `music-video/scripts/musicvideo/budget.py` (`downloads_in_cycle` de-duplicates)
- Modify: `music-video/scripts/musicvideo/cli.py` (`cmd_downloaded`, `cmd_status`)
- Modify: `music-video/scripts/musicvideo/ingest.py` (`song_dir`, the ownership check)
- Test: `tests/test_mv_lanes.py`

**Interfaces:**
- Consumes: `worktrees.repo_worktrees`, `Workspace.main_home`, `Workspace.song_dir`.
- Produces:
  - `workspace.worktree_homes(ws: Workspace) -> list[Path]`: `ws.home` first, then the same workspace folder in the
    main checkout and in every other linked worktree (`root / main_home.relative_to(main root)`), keeping those with a
    `specs/` folder, without duplicates (by resolved path). Outside git, or when `main_home` is not inside the main
    root: `[ws.home]`.
  - `spec.iter_worktree_specs(ws: Workspace) -> Iterator[tuple[Path, dict]]`: `iter_specs` over each of
    `worktree_homes(ws)`.
  - `budget.downloads_in_cycle(specs, today, billing_day) -> int`: same signature. A spec that has an `id` counts
    once per `(id, downloaded_at)`; one without an `id` counts as today.

- [ ] **Step 1: Write the failing tests**

```python
def test_downloads_count_across_worktrees(mv_lane, monkeypatch, capsys):
    # one spec downloaded in main, another in lane a, another in lane b (downloaded_at = now, distinct ids);
    # the same spec with the same downloaded_at in lane a and lane b (merged into both) → counts once
    # main(["status"]) from main, a and b each print "Downloads: 4 of 20"
    # main(["downloaded", "<a fifth spec in lane a>", "--take-url", "u"]) prints "recorded download 5 of 20"

def test_a_plain_workspace_counts_as_today(mv_ws, write_spec, capsys):   # no .git: same count as before

def test_a_deleted_worktree_is_skipped(mv_lane, monkeypatch, capsys):
    # shutil.rmtree(mv_lane.b) without touching main/.git/worktrees/lane-b → status from a and main exits 0

def test_ingest_in_a_lane_files_into_shared_results(mv_lane, make_mp3, monkeypatch):
    # MUSIC_VIDEO_HOME = lane.a; a downloaded spec in the lane; ingest(--file) → the MP3 is in
    # results_dir/night-drive/ (song_dir), not under .lanes; the lane spec's kept.file == the string ingest gives
    # the same spec in main (stored_path against main_home); parametrized over main's results_dir as configured
    # by mv_ws (absolute) and as "results" (relative: the song lands in main / "results" / "night-drive", and
    # kept.file == "results/night-drive/Test Artist - Night Drive.mp3")

def test_ingest_refuses_a_file_another_worktree_owns(mv_lane, make_mp3, monkeypatch):
    # lane b has spec "other" filed as the album file "Test Artist - Night Drive.mp3"; ingest of album spec
    # "night-drive" in lane a raises MVError "already belongs to spec 'other'"; the same spec id filed in main does not
```

- [ ] **Step 2: Run them and check they fail**
  - Run: `uv run pytest tests/test_mv_lanes.py -q -k "download or worktree or ingest"`
  - Expected: FAIL.

- [ ] **Step 3: Implement**
  - `cmd_downloaded` and the Downloads line of `cmd_status` feed `iter_worktree_specs(ws)` to `downloads_in_cycle`.
    The "Songs:" line of `cmd_status` keeps `iter_specs(ws)`: this worktree's own specs.
  - `ingest`: `dest_dir = ws.album_dir(album.id) if album else ws.song_dir(spec_id)`. The ownership loop runs over
    `iter_worktree_specs(ws)` and skips specs whose file stem equals `spec_path.stem` (the same song in another
    worktree).

- [ ] **Step 4: Run the suite**
  - Run: `uv run pytest -q`
  - Expected: PASS; `test_mv_budget.py` and `test_mv_ingest.py` unchanged.

- [ ] **Step 5: Commit**: `music-video: songs stay shared and one budget counts every worktree`

### Task 6: Release 0.8.0

**Files:**
- Modify: `music-video/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
  `music-video/scripts/musicvideo/__init__.py` (0.8.0)
- Modify: `music-video/CHANGELOG.md`, `music-video/README.md` (folders table), `music-video/skills/make/SKILL.md`
  ("Where a video lives")

- [ ] **Step 1:** Bump the three versions and run `uv run pytest tests/test_mv_packaging.py -q`. Expected: PASS.
- [ ] **Step 2:** Write the CHANGELOG entry `## 0.8.0`:
  - In a git worktree of the project folder, music-video works on that worktree's specs and video code. Its working
    files go to `work/.lanes/<worktree>/`, its video finals to `<results>/.lanes/<worktree>/` (hidden from the
    library), and its engine entries are its own.
  - Songs and albums are filed into the shared results folder. The download budget counts every worktree.
  - `init` in a worktree no longer re-points the saved workspace.
  - No change for a project folder that is not a git worktree.
- [ ] **Step 3:** README folders table:
  - The Work row adds `.lanes/<worktree>/<id>/` for a git worktree of the project.
  - The Results row adds `.lanes/<worktree>/<id>/`: that worktree's video finals, hidden from the library.
- [ ] **Step 4:** In `skills/make/SKILL.md`, after the `paths` paragraph, add one paragraph: "In a git worktree of the
  project, `paths` prints that worktree's own folders (and a `lane` key). The song stays in the main results folder.
  Song downloads still count against the one budget." Run `uv run pytest tests/test_mv_skills.py -q`. Expected: PASS.
- [ ] **Step 5:** Run `uv run pytest -q`, then on the Mac `uv run pytest -m studio -q`. Expected: PASS.
- [ ] **Step 6: Commit**: `music-video 0.8.0: project lanes for git worktrees (#14 phase 2)`

---

## Decisions taken while planning

Each was open in the design or arose from the code. "If wrong" names the cost.

1. **Version 0.8.0, not 0.7.0.** The design predates 0.7.0–0.7.3 (the sections page). Lanes change where a worktree
   writes, so a minor bump. *If wrong:* a number in three files.
2. **A new module `worktrees.py`** holds the git file reading. `workspace.py` stays about settings and config, and
   phase 3's `lanes` command will reuse `repo_worktrees`. *If wrong:* one more small file.
3. **Not a lane:** a `.git` file without `commondir` (submodules, a `--separate-git-dir` main checkout), and a
   worktree whose common git dir is not named `.git` (worktrees of a bare repo). These have no main working tree to
   map the saved workspace into, so they keep today's paths. *If wrong:* such users share folders between sessions
   exactly as today. Supporting them later means a lane without a main counterpart.
4. **Mapping needs a workspace at the target.** The saved workspace is mapped into the worktree only when the
   mapped folder `is_workspace`. Otherwise the nearest-workspace search runs, and then no mapping. With no saved
   setting, only the search applies. *If wrong:* a session in a worktree whose branch lacks the workspace folder
   works on the main checkout's files, as it does today, and never fails.
5. **Shared things resolve against the main checkout.** In a lane, a relative `results_dir` or `downloads_dir`, and
   `stored_path`/`filed_path`, resolve against `main_home`. `videos_dir` and `work_dir` resolve against the lane, as
   the design says. This follows from §4.3's "songs are shared" and "`kept.file` stays valid after merge".
   *If wrong:* someone wanting per-lane songs through a relative `results_dir` does not get them. The design rules
   that out anyway.
6. **`private-names.txt` is the union** of the lane's file and the main checkout's. The design does not cover it,
   but the file is usually gitignored, so a lane would otherwise validate against no names at all. *If wrong:* a
   name deleted on a branch is still checked until the branch merges.
7. **`paths` prints `"lane"` only in a lane.** §5 says `null` in a main checkout, but the hard constraint (§1, "the
   same output") and §9.1 ("main checkout output unchanged") win. *If wrong:* a consumer must use
   `.get("lane")`. The `make` skill reads named keys only.
8. **De-duplication lives in `downloads_in_cycle`**, by `(id, downloaded_at)`. A spec without an `id` is counted as
   today, so existing callers and tests behave the same. *If wrong:* none in one folder, where ids are unique by
   file name.
9. **`status` splits the two lines.** "Downloads" counts every worktree (one budget). "Songs: by status" stays the
   current worktree's specs, which is what that branch has. *If wrong:* a cosmetic difference in one line.
10. **The `ingest` ownership check spans worktrees.** The design does not say so, but with a shared album folder, two
    lanes filing different specs under the same artist and title would otherwise overwrite each other's tagged MP3.
    *If wrong:* a refusal that names the other spec, which is the collision the check already exists for.
11. **Leases record the lane** (§4.7 lists it, and phase 1 left it out). The "in use" message names the worktree.
    *If wrong:* one extra JSON field.
12. **`init` in a lane counts the main checkout's `config.yaml`.** It prints "using existing" and needs no `--artist`.
    It never writes a `config.yaml` into the lane unless neither exists. *If wrong:* a user who wanted a separate
    config per worktree writes one by hand. It then wins, as the design says.
13. **No new port, seeding, pruning or `lanes` code** (phase 3, §8). This includes the `sections` page's port 8645,
    which came after the design and has the same busy-port behaviour as `edit-timing`. *If wrong:* two lanes running
    `sections` at once get "port busy: pass --port" until phase 3.
14. **Paths are compared resolved** for "is the saved workspace inside the main tree". Case is not normalised
    (§10 item 9: low risk). *If wrong:* on a case-insensitive disk, a saved path typed with different case does not
    map, and the session keeps today's behaviour.
15. **plugins#19 is not folded in.** None of its eight items is needed by lanes.

## Questions for the maintainer

None block execution. One to confirm when reviewing:

- Decision 6 makes a lane's private-name check the union of the lane's and the main checkout's
  `private-names.txt`. If you keep that file committed rather than gitignored, the union changes nothing. If you
  would rather a lane use only its own file, say so before Task 2.
