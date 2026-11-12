# music-video — several sessions at once (worktrees)

**Date:** 2026-11-01 · **Status:** draft design, awaiting review · **Issue:** #14
**Scope:** `music-video` only (`scripts/musicvideo/workspace.py`, `studio.py`, `cli.py`, `doctor.py`, `ingest.py`,
`budget.py`, `video/timing_editor.py`, `studio/tools/web.ts`, `studio/web/main.tsx`, the `make` skill, README,
CHANGELOG). `lesson-videos` has its own `project.py` and shares no code with these modules: it is not touched.

## 1. Purpose

Let several music-video sessions run at the same time, each in its own git worktree of the **project folder**
(specs, albums, video code) and/or of the **plugin checkout**, without one session silently working on, overwriting
or deleting another's files.

**Hard constraint:** a user with one project folder and the installed plugin (the normal case, and everyone who is
not developing the plugin) sees **no change**: the same project, work, results and engine paths, byte for byte, the
same commands, the same output.

**Success:**

- Two worktrees of one project, rendering the same video id at once, get distinct work, results, web and engine
  entry folders, and neither run changes the other's files.
- A plugin branch checkout and the installed plugin render at once without overwriting each other's engine.
- Different videos in one checkout keep rendering in parallel, as today.
- A project folder that is not a linked git worktree, run by the installed plugin, resolves to today's paths
  (asserted by tests, §9).

## 2. Today: every path that touches the shared state

Read on `main` at 0.6.6. Three pieces of state live once per machine.

### 2.1 Which project folder is used

`workspace.workspace_home()`: `MUSIC_VIDEO_HOME`, else `workspace` in `settings.json` (`settings_file()`, with the
0.2.0 copy-once migration in `_settings_to_read()`), else `~/Documents/Music Videos`. The cwd is never consulted.

Callers: `load_workspace()` (every command), `cli.cmd_init` (default `--path`), `doctor.run_doctor` (the "no
workspace" message). `init_workspace()` always calls `remember_home(home)`, which **overwrites** the saved pointer.

A session started in a worktree of the project therefore reads and writes the main checkout's specs and video code.

### 2.2 The engine folder

`studio.runtime_dir()` is `install_dir()/engine` (`MV_INSTALL_DIR` overrides `install_dir()`).

- `sync_runtime()` copies `PLUGIN_STUDIO` (the `studio/` folder of whichever plugin copy is running) into it, by size
  and mtime, and deletes files the last sync copied that this source lacks (`.synced.json`). Two plugin copies
  (a branch checkout and the installed version, or two installed versions across an update) overwrite and prune
  each other, including mid-render.
- `ensure_ready()` = `sync_runtime()` + `is_installed()` (lock hash stamp `.installed-lock`). If the two copies have
  different `package-lock.json`, each one's sync makes the other "not installed", and `doctor` (`install()` →
  `npm ci`) **deletes `node_modules` under a running render**.
- `migrate_old_runtime()` (0.1.0 → 0.2.0 move) and `doctor` print `runtime_dir()`.
- `.entries/<video-id>/` holds `index.ts` (`write_entry`), `web.ts` (`web_entry`), `tsconfig.json`
  (`typecheck_config`) and the `src` link to the video folder (`linked_video`, a junction on Windows). Keyed by video
  id only: two project worktrees with the same video id re-point one link back and forth.
- `tool_env()` passes `MV_STUDIO`, `MV_ENTRY`, `MV_VIDEO_DIR` (the link), `MV_PUBLIC`, `MV_WORK`; `_prepare()` in
  `cli.py` is the single path every engine command (`studio`, `render`, `still`, `stills`, `blur`, `board`, `web`,
  `typecheck`) goes through.
- **Pre-existing race, independent of worktrees:** `studio/tools/web.ts` stages the song data in
  `<engine>/web/.data/score.json`, which `studio/web/main.tsx` imports by that fixed path. Two `web` builds of
  *different* videos at once already race on it today.
- Shared, and assumed safe: Remotion's webpack cache (`node_modules/.cache`) is already shared by parallel renders of
  different videos today (§10, item 5); the
  alignment worker's uv cache and model weights (`install_dir()/uv`, `models/`) are read-mostly and guarded by their
  own tools' file locks.

An installed engine (packages plus Remotion's headless browser) is about 1.7 GB, as `doctor` says; its
`node_modules` holds about 24k files before the browser is added. One full copy per checkout is the main cost to avoid.

### 2.3 Work and results folders

`Workspace.work_for(id)` = `work_dir/<id>` (default `cache_dir()/work`), `results_for(id)` = `results_dir/<id>`
(default `~/Movies/Music Videos`), `album_dir(a)` = `results_dir/albums/<a>`. Callers:

| Caller | Uses |
|---|---|
| `video/paths.video_song` (align, analyze, preview, loop, mux, qc, edit-timing) | `work_for(spec)`, `results_for(spec)` |
| `studio.video_context` | `work_for(song)/public` (a video may borrow another song's timings), `work_for(video)` |
| `studio.new_video` | creates `work_for(id)` |
| `video/review` (`version`, `review`) | `work_for(id)/review`, `work_for(id)/qc`, `work_for(song)/qc` |
| `cli.cmd_paths` | prints all of the above; the `make` skill uses only these printed paths |
| `cli.cmd_web` | `results_for(id)/web` (default `--out`), `work_for(loop song)/loop`; `check_web_out` + Vite `emptyOutDir` empty it |
| `cli.cmd_clean` | deletes `work_dir/<id>` after checking it does not overlap results, project or install |
| `ingest.ingest` | files the MP3 into `results_for(spec)` or `album_dir(album)`; `stored_path` writes it into the spec |
| `albums.write_manifest` | `album_dir(album)/manifest.json` |
| `cli.cmd_library` | serves `results_dir`; its login item (`library install`) bakes `results_dir` into a launchd plist and copies `library.py` into `install_dir()/library` |
| `cli.cmd_downloaded`, `cmd_status` | count downloads in the billing cycle over **this workspace's** specs |
| `doctor` | prints `results_dir`, `work_dir` |

Two worktrees of one video share renders, qc reports, review versions and timings, and `web` empties the other's
page. Two worktrees with unmerged song downloads each count only their own specs against one paid budget.

The library hides every name starting with `.` or `_` (`library.hidden`), so a dot-folder under `results_dir` is
never listed or served.

## 3. Terms

- **Main checkout:** a project folder that is not a *linked* git worktree: a plain folder, or the main working tree
  of a git repo (`.git` is a directory). Today's paths, unchanged.
- **Lane:** a project folder that is a linked git worktree (`.git` is a *file* holding `gitdir: …/.git/worktrees/<n>`).
  Lane-ness is a property of the folder, however it was found (cwd, `MUSIC_VIDEO_HOME`, saved setting).
- **Lane key:** `<slug>-<hash8>`: `slug` = the worktree folder's name, lowercased, reduced to `[a-z0-9-]`, at most 24
  characters; `hash8` = the first 8 hex of sha256 of `os.path.normcase(str(worktree_root.resolve()))`. Readable in a
  folder listing, stable for the life of the worktree, distinct for two worktrees with the same folder name.
- **Installed plugin:** a plugin copy with no `.git` at its plugin root or that root's parent (`PLUGIN_STUDIO.parent`, `PLUGIN_STUDIO.parents[1]`). That is the
  Claude Code plugin cache layout (`…/<marketplace>/music-video/<version>/studio`). **Dev checkout:** a plugin copy
  inside a git working tree (`<repo>/music-video/studio` with `<repo>/.git`, a directory or a file).

## 4. Design

### 4.1 Project resolution (`workspace_home`)

New order:

1. `MUSIC_VIDEO_HOME`, as today.
2. **Worktree mapping**, only when the cwd is inside a linked git worktree `W`:
   - read `W/.git` (`gitdir: <G>`), then `<G>/commondir` to get the common git dir, whose parent is the main
     working tree `M`. Pure file reads: no `git` binary, works on Windows.
   - If the saved workspace `S` (step 3's value) lies inside `M`, the home is `W / S.relative_to(M)` (the same
     sub-folder in the worktree; the common case is `S == M`).
   - Else, the nearest folder from the cwd up to `W` whose `config.yaml` (or whose main counterpart's `config.yaml`,
     §4.2) is a music-video workspace (§4.2) is the home.
   - Otherwise: no mapping.
3. `workspace` in `settings.json`, as today.
4. `DEFAULT_HOME`, as today.

The cwd is consulted **only** inside a linked worktree. A plain folder or a main checkout that happens to hold a
`config.yaml` (other tools use that name too) never overrides the saved workspace, so a user with two plain
workspaces who switches with `init --path` sees today's behaviour.

`remember_home()` is **not** called when the home is a lane: `init` in a worktree prints "this is a worktree of
`<M>`; the saved workspace stays `<S>`" instead of re-pointing every other session at the worktree.

### 4.2 Workspace config in a lane

`config.yaml` holds per-user values (billing day, budget, results folder) and may be gitignored in the user's project
repo. In a lane, `load_workspace(W')` reads `W'/config.yaml` if it exists, else the main counterpart
`M / W'.relative_to(W)` `/config.yaml`; relative `videos_dir` and `work_dir` values still resolve against the lane's
own home. A folder counts as a workspace when its `config.yaml` parses to a mapping with a non-empty `artist` and the
folder has a `specs/` directory (what `init` creates).

`Workspace` gains `lane: str | None` (the lane key; `None` in a main checkout) and `main_home: Path` (equal to `home`
in a main checkout).

### 4.3 Work and results per lane

| Path | Main checkout (unchanged) | Lane |
|---|---|---|
| `work_root` (new property; `clean` uses it) | `work_dir` | `work_dir/.lanes/<key>` |
| `work_for(id)` | `work_dir/<id>` | `work_dir/.lanes/<key>/<id>` |
| `results_for(id)` (video finals, `web/`) | `results_dir/<id>` | `results_dir/.lanes/<key>/<id>` |
| `song_dir(id)` (new; `ingest` uses it) | `results_dir/<id>` | `results_dir/<id>` (shared) |
| `album_dir(a)` | `results_dir/albums/<a>` | same (shared) |
| `results_dir` (library root, `doctor`) | as configured | same (shared) |

Reasons:

- **Work** holds renders, qc, review versions and timings, which follow the branch's own video code and
  `timing-fixes.yaml`. Under `work_dir` so a user-set `work_dir` still applies; a dot-folder so `clean <id>` in the
  main checkout (which only ever deletes `work_dir/<id>`) can never reach it.
- **Video finals** are per branch until the branch merges. Under `results_dir/.lanes/` they sit next to the real
  finals (easy to compare or promote by hand) and stay invisible to the library, which hides dot-names. `web` in a lane
  defaults to `results_dir/.lanes/<key>/<id>/web`, so `check_web_out` and Vite's `emptyOutDir` can only empty the
  lane's own page. An explicit `--out` stays the caller's choice, as today.
- **Songs and albums are shared.** A downloaded song costs a download from a paid budget and does not depend on the
  branch. `ingest` writes `song_dir(spec)`, the path the main checkout uses, so the `kept.file` that `stored_path`
  records in the spec stays valid after the branch merges and the worktree is deleted. Today `ingest` uses
  `results_for`; in a main checkout both give the same path.

**Seeding a lane's timings.** `align` runs vocal separation and transcription (minutes). The first time a lane needs
`work_for(id)` and it does not exist while the main checkout's `work_dir/<id>` does, copy (real copies, not hard
links: these files are rewritten in place) `public/`, `vocals.wav`, `transcript.json`, `aligned.json`, `beats.json`
and `loop/`, and write `.seeded-from` naming the source. `renders/`, `qc/` and `review/` are never copied. Phase 3;
until then a lane runs `align`/`analyze` itself (the error message already says so).

*As built (phase 3, `musicvideo/seed.py`):* `Workspace.work_for(id)` seeds, in a lane only, when the lane's folder is
missing and the main checkout's (its own `work_dir`, from its own `config.yaml`) holds any of those items, so every
command that needs the folder (`paths`, `align`, `analyze`, `preview`, `still`, `render`, the home) gets it; a main
checkout never seeds. `align-cache.json` is copied too, so a later `align` in the lane (after a timing fix) reuses
the copied vocals and transcript instead of separating again. The copy is made in `<lane work>/.seeding/<id>/<pid>`
under a lock (`.seeding/<id>.lock`, the `file_lock` of §4.7) and renamed into place: a second command waits and
finds the folder done; a staging folder left by a command that died is deleted by the next one. One line on stderr
says it copied (stdout stays clean for `paths`' JSON). After `clean <id>` in a lane, the next use seeds again.
§10 item 7: the seed does not compare `timing-fixes.yaml`; the copy is taken when the lane first needs the folder,
right after branching, when the fixes still agree, and a later fix in the lane runs `align`, which the copied cache
makes fast.

### 4.4 The download budget across worktrees

`downloaded` refuses a download past the budget, counting `kept.downloaded_at` over the specs it can see. With lanes,
a download recorded on an unmerged branch is invisible to the main checkout and to other lanes. `downloads_in_cycle`
is fed the specs of the main checkout **and every linked worktree** of the same repo (listed from
`<common git dir>/worktrees/*/gitdir`, file reads only), de-duplicated by `(spec id, downloaded_at)`. A project that
is not a git repo, or has no worktrees, sees exactly the set it sees today. `status` uses the same union.

### 4.5 Engine per plugin checkout

`runtime_dir()` becomes:

1. `MV_ENGINE_DIR` if set (new; tests and power users).
2. **Installed plugin** → `install_dir()/engine`, exactly as today.
3. **Dev checkout** → `install_dir()/engines/<slug>-<hash8>` from the checkout's repository root, as for lane keys.

Each dev checkout (the maintainer's main clone, each plugin worktree) syncs into its own engine with today's
incremental `sync_runtime()`, so editing kit files stays a fast copy. Two checkouts never share an engine, so a
branch can never prune or overwrite the installed plugin's engine, and the reverse.

Rejected for the installed plugin: keying it by version (each `/plugin update` would then need a new 1.7 GB engine
or a re-seed, and change the folder `doctor` prints). Two installed versions across an update still share
`engine/`; §4.7 makes that safe.

**`node_modules` for a new engine (the disk and time cost).** A new dev engine is seeded instead of installed:

- If an installed engine exists (`install_dir()/engine`, or any engine under `engines/`) whose `.installed-lock`
  equals the new engine's `lock_hash`, build the new `node_modules` as a **hard-link tree** of it: directories
  re-created, every file `os.link`ed, symlinks (`.bin` on macOS) re-created as symlinks. About 24k links: seconds,
  and near-zero extra disk. Then write `.installed-lock`.
  - Safe against a later `npm ci` in the source engine: `npm ci` removes and re-extracts files (new inodes), it
    never rewrites them in place, so the linked copy keeps the old, consistent set.
  - Excluded from the link tree, because tools write into them in place: `node_modules/.cache` (webpack),
    `node_modules/.vite`, `node_modules/.vite-temp`. The new engine starts with empty caches.
  - `os.link` works on NTFS within one volume; every engine is under `install_dir()`, so on one volume. On
    `OSError` (exotic file systems), fall back to `shutil.copytree` (full copy), and report the size.
- If no engine with the same lock exists, `ensure_ready` says "run music-video doctor" as today, and `doctor` runs
  `install()` (`npm ci` uses npm's own download cache, so mostly no network) in the new engine.

`ensure_ready()` seeds automatically (local, no network); `npm ci` stays a `doctor`-only step, as today.

**Stale engines.** Each dev engine keeps `.owner.json`: `{"checkout": <repo root>, "created": …, "last_used": …}`
(`last_used` touched by `ensure_ready` at most once an hour). `doctor` lists engines whose checkout no longer exists
or that are unused for 30 days, with their size; `music-video doctor --prune-engines` deletes those, each under its
lock (§4.7) and never one with a live lease. Nothing is deleted automatically. Because of the hard links, the space
freed is usually small; `doctor` reports apparent size and says so.

### 4.6 Entries per lane

`write_entry`, `web_entry`, `typecheck_config` and `linked_video` take the lane from the context:

- main checkout: `<engine>/.entries/<id>/…` (unchanged);
- lane: `<engine>/.entries/.lane-<key>/<id>/…`.

A video id never starts with a dot (`ID_RE`), so the two can never collide. `VideoContext` gains `lane`; `tool_env`
and `_prepare` pass it through.

### 4.7 Concurrency safety

**Engine lock.** `engine_lock(rt)`: an exclusive lock on `<engine>/.lock`, stdlib only (`fcntl.flock` on macOS and
Linux, `msvcrt.locking` on one byte on Windows), polled with a short sleep; after 2 s it prints "waiting for another
music-video command to finish updating the engine…", and gives up after 10 minutes with an `MVError`. Held for:
`sync_runtime`, seeding, `install` (`npm ci` + `remotion browser ensure`), `migrate_old_runtime`, pruning. Not held
while a render runs.

**Leases.** `_prepare()` writes `<engine>/.leases/<pid>-<random>.json` (`pid`, start time, plugin version, source
`PLUGIN_STUDIO`, video id, lane) after its sync and removes it when the command ends (a `finally` in `cli.main`). A
lease is live when its pid is running (POSIX `os.kill(pid, 0)`; Windows `OpenProcess` + `GetExitCodeProcess` through
`ctypes`, never `os.kill`, which terminates on Windows) and it is under 48 hours old; dead ones are deleted on sight.
Under the engine lock:

- A sync whose plan is **empty** (nothing to copy or delete, the normal case for parallel renders) proceeds.
- A sync that would change files proceeds unless a live lease comes from a **different source** (another plugin
  version or path), in which case it fails: "the engine is in use by music-video `<version>` (pid …, video …): wait
  for it to finish, then run again". Same source: the changed files are the developer's own edits; proceed, as today.
- `install` (`npm ci`) refuses while any live lease exists.

With engines per dev checkout, a different-source conflict only remains between two installed versions across a
plugin update, which today silently breaks the older render.

**Per-run web staging.** `web.ts` writes `score.json` to `.entries/[.lane-<key>/]<id>/web-data/` (passed as
`MV_WEB_DATA`), and the Vite build aliases `./.data/score.json` in `main.tsx` to it. This fixes the existing race
between two `web` builds of different videos.

**Ports.** `edit-timing` binds 8644; a second session gets "port busy: pass --port". In a lane, the default becomes
the first free port from 8644 upward (printed). The library stays one per machine (one port, one login item, the
shared `results_dir`). The `studio` command is assumed to move to a free port on its own (§10, item 8).

### 4.8 The `library` login item

Unchanged. It serves the shared `results_dir`; lane finals live in the hidden `.lanes/` folder. `library install`
from a lane installs the same agent with the same root; the copied `library.py` comes from whichever plugin copy ran
it, as today.

## 5. Command surface

- `paths <id>` prints the lane's folders (the `make` skill already uses only these). Adds `"lane": "<key>"` or `null`.
- `doctor` prints, in a lane, "worktree `<key>` of `<M>`: work in …, video finals in …", and lists stale engines.
- `doctor --prune-engines` (new flag).
- `lanes` (new): lists lanes with work and results sizes and whether the worktree still exists;
  `lanes --prune` deletes work folders and `.entries/.lane-<key>` of lanes whose worktree is gone;
  `--with-results` also deletes their `results_dir/.lanes/<key>` (finals: never by default).
- `clean <id>` in a lane deletes `work_root/<id>` only.
- `init` in a lane never rewrites `settings.json` (§4.1).

## 6. Migration

Nothing moves for a main checkout and the installed plugin: `engine/`, `work_dir/<id>`, `results_dir/<id>`,
`.entries/<id>` and `settings.json` keep today's paths. No data migration code.

- **Dev checkouts** (the maintainer's main clone included) get `engines/<key>/` on their next command, seeded by hard
  links from `engine/` when the lock matches. The old shared `engine/` stays the installed plugin's.
- **An existing worktree** that already rendered (into the main paths, today's behaviour) starts with empty lane
  folders; Phase 3 seeding copies timings from the main checkout.
- Versioning: one minor bump (0.7.0) in `plugin.json`, `marketplace.json` and `__init__.py`, CHANGELOG entry, README
  folders table (lanes, `engines/`), one paragraph in `skills/make/SKILL.md` ("in a git worktree of the project,
  `paths` prints that worktree's own folders; song downloads still count against the one budget").

## 7. Alternatives considered

| Alternative | Why not |
|---|---|
| Engine keyed by version + content hash of `studio/` (immutable engines) | Every kit edit in a dev checkout makes a new engine; the installed plugin would change folders on each update (a 1.7 GB re-seed, a new path printed by `doctor`). |
| Engine keyed by checkout path for every copy, the installed plugin included | Each installed version has its own cache path, so every update creates a new engine. Breaks "no change". |
| Run the engine in place in a dev checkout (`studio/node_modules`, `.entries` in the repo) | Breaks the rule that nothing is written into the plugin folder; `.entries` links would sit in the git tree. |
| One shared `node_modules` reached by a symlink or junction | `tool_env` runs Node with `--preserve-symlinks` and webpack resolves real paths: two module paths for one package risk duplicate React/three.js instances. A hard-link tree has no link semantics. |
| One global lock around every engine command | Serialises renders of different videos, which work in parallel today. |
| Lane folders keyed by branch name | Branches are renamed, contain `/`, can be detached; the worktree path is what is actually distinct. |
| Ask the user to set `work_dir`/`results_dir` per worktree in `config.yaml` | Manual, conflicts when `config.yaml` is committed, and does not cover the engine or `.entries`. |
| Use the cwd's `config.yaml` everywhere (the issue's first proposal, unconditionally) | Changes behaviour for a single-checkout user who starts Claude Code in another folder that holds a `config.yaml`. Restricted to linked worktrees. |
| Lane finals in the cache instead of under `results_dir/.lanes/` | Finals in a purgeable cache are easy to lose and hard to find; kept as an open question (§10). |

## 8. Phased implementation

1. **Engine isolation** (fixes the worst hazard: overwritten and pruned engines mid-render). `runtime_dir()` with
   `MV_ENGINE_DIR` / installed / dev keys; `.owner.json`; hard-link seeding; `engine_lock`; leases; per-run web
   staging. Tests §9.2. No change for the installed plugin beyond the lock and leases.
2. **Project lanes.** Worktree detection and mapping in `workspace_home`; config fallback; `Workspace.lane`,
   `work_root`, lane-aware `work_for`/`results_for`, `song_dir`; `.entries/.lane-<key>`; `init` guard; `paths`,
   `doctor`, `clean`; budget union. Tests §9.1. Skill paragraph, README, CHANGELOG, version bump.
3. **Comfort.** Timing seeding from the main checkout; `lanes` / `lanes --prune`; `doctor --prune-engines`; free
   port for `edit-timing` in a lane.

Each phase ships on its own branch with `uv run pytest -q` green on macOS and Windows CI, and the engine gate
(`uv run pytest -m studio -q`) on macOS, including two `web` builds of different videos at once.

## 9. Test plan

Pytest, in the style of `tests/test_mv_workspace.py` and `tests/test_mv_studio.py`: `tmp_path` trees, the autouse
`mv_isolated` fixture (`MV_SETTINGS`, `MV_CACHE_DIR`, `MV_INSTALL_DIR`), `monkeypatch` for `PLUGIN_STUDIO` and the
cwd. Worktrees are faked with files (`.git` file + `gitdir` + `commondir`), plus one test with a real
`git worktree add` when `git` is on PATH. Runs on the macOS and Windows CI matrix.

A new fixture `mv_lane(mv_ws, tmp_path)` turns `mv_ws` into a git main checkout and returns two linked worktrees.

### 9.1 `tests/test_mv_lanes.py`

- `test_plain_folder_resolves_to_todays_paths`: no `.git`; `work_for`, `results_for`, `song_dir`, `album_dir`,
  `work_root`, `runtime_dir()` (installed layout) and the entry path equal today's literal paths; `lane is None`.
- `test_main_checkout_of_a_repo_resolves_to_todays_paths`: same with a `.git` directory.
- `test_two_worktrees_get_distinct_folders`: both lanes differ from each other and from main for work, results and
  entries; keys are stable across two `load_workspace()` calls.
- `test_lane_key_is_readable_and_distinct_for_same_folder_name`.
- `test_cwd_in_worktree_maps_the_saved_workspace`: settings point at main; `monkeypatch.chdir` into a sub-folder
  of a worktree → `workspace_home()` is the worktree; also with the workspace in a sub-folder of the repo.
- `test_cwd_outside_a_worktree_keeps_the_saved_workspace`: cwd in an unrelated folder with a valid `config.yaml`
  → the saved workspace (no change for single-checkout users).
- `test_music_video_home_still_wins`.
- `test_worktree_without_config_reads_the_main_config`.
- `test_init_in_a_lane_keeps_settings`: `settings.json` byte-identical after `init` in a lane.
- `test_ingest_in_a_lane_files_into_shared_results`: the MP3 lands in `results_dir/<id>`; the spec's `kept.file`
  is the main-checkout path.
- `test_downloads_count_across_worktrees`: one download in main, one in each lane → `downloaded` sees 3; the same
  spec merged into two worktrees counts once; a non-git workspace counts as today.
- `test_clean_in_a_lane_removes_only_lane_work`.
- `test_paths_in_a_lane`: JSON paths, `lane` key; main checkout output unchanged.
- `test_web_default_out_in_a_lane_is_the_lane_folder`: `cmd_web` (with `ensure_ready` and `run_node` monkeypatched,
  as in `tests/test_mv_web.py`) passes the lane folder and never main's `web/`.
- `test_library_does_not_list_lane_results`: `library.scan(results_dir)` ignores `.lanes/`.

### 9.2 `tests/test_mv_engine.py`

- `test_installed_plugin_uses_todays_engine`: `PLUGIN_STUDIO` in a tree without `.git` → `install/engine`.
- `test_two_plugin_checkouts_get_distinct_engines`: two `<repo>/music-video/studio` trees with `.git` → two
  `engines/<key>` folders, neither equal to `engine`.
- `test_engine_dir_env_overrides`.
- `test_entries_are_keyed_by_lane`: `.entries/<id>` in main, `.entries/.lane-<key>/<id>` in a lane; `linked_video`
  links of two lanes point at their own folders.
- `test_seed_hard_links_modules_when_locks_match`: same `st_ino` for a linked file; `.cache`, `.vite` absent;
  `.installed-lock` written; `ensure_ready()` passes without `doctor`.
- `test_seed_falls_back_to_doctor_when_locks_differ`.
- `test_seeded_engine_survives_a_reinstall_of_its_source`: delete and rewrite the source's files (as `npm ci`
  does) → the seeded engine's files are unchanged.
- `test_engine_lock_serialises_two_syncs`: a second process (`multiprocessing`) waits on the lock.
- `test_sync_from_another_source_refuses_while_leased`: a lease from a live child process with another source →
  `MVError` naming the version; the same source proceeds; an empty plan proceeds.
- `test_dead_or_old_lease_is_ignored_and_removed`.
- `test_install_refuses_while_leased` (`npm` monkeypatched).
- `test_prune_engines_removes_only_orphans`: an engine whose checkout is gone is removed; a live one and a leased
  one are kept; `install/engine` is never a candidate.
- `test_web_stage_is_per_run`: `web.ts` reads `MV_WEB_DATA` and no longer writes `web/.data` (a source check, as
  `test_mv_web.py` does for `web-out.ts`), plus, under `-m studio`, two `web` builds of different videos at once.

The existing tests (`test_mv_studio.py`, `test_mv_workspace.py`, `test_mv_video_paths.py`, `test_mv_web.py`) must
pass unchanged: they are the "no change" contract for a main checkout.

## 10. Open questions

Each was decided conservatively for this draft; the reviewer may overturn any.

**Settled 2026-11-03.**
- Item 1 is decided by the maintainer: lane finals go under `results_dir/.lanes/<key>/`.
- Item 2 is decided by the maintainer: song steps are allowed in a lane, and the budget is counted across worktrees.
- Item 3 is checked: Claude Code runs a plugin from its cache copy (`~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/`), which is in no git repo. Only the marketplace clone has a `.git`. Detection therefore looks for `.git` only at the plugin root and its parent (`PLUGIN_STUDIO.parent`, `PLUGIN_STUDIO.parents[1]`), never further up, so a home folder kept in git cannot turn the installed plugin into a dev checkout.
- Item 4 is checked: Remotion's browser lives in `node_modules/.remotion` (about 570 MB), so the hard-link seed covers it.

The other items stay as drafted.

1. **Lane finals location.** Chosen: `results_dir/.lanes/<key>/` (hidden from the library, next to the real finals).
   Alternative: under the work cache. If `results_dir` is synced to a NAS or cloud drive, lane drafts get synced too.
2. **Song steps in a lane.** Chosen: allowed, songs and albums go to the shared folders, the budget counts every
   worktree. Alternative: refuse `downloaded`/`ingest`/`album` in a lane. Two lanes editing the same album's specs
   can still write different `manifest.json` files; the last `album` run wins, as with two edits today.
3. **Installed-plugin detection** by "no `.git` at the repository root". A user who runs the plugin from a
   marketplace git clone (rather than the plugin cache) is treated as a dev checkout and gets its own seeded engine.
   Acceptable, but confirm Claude Code always runs plugins from the cache copy.
4. **Remotion's browser location.** The design assumes `remotion browser ensure` stores its browser inside
   `node_modules` (so the hard-link seed covers it). Verify on the 4.0.x line in use; if it lives elsewhere, the seed
   must run `browser ensure` too.
5. **Webpack/Vite caches.** Excluded from the seed because they are written in place. Verify that Remotion's webpack
   cache tolerates two renders at once (already the case today for different videos), and where Vite's `cacheDir`
   resolves with `root: web`.
6. **Lease refusal vs wait.** Chosen: a sync that would change an engine leased by another source fails at once with
   a message. Alternative: wait. A render can take 30 minutes, so waiting could look like a hang.
7. **Lane seeding of timings** (Phase 3) copies from the main checkout only, never from another lane, and only when
   the lane folder is missing. Should a lane whose `timing-fixes.yaml` differs from main skip the seed?
8. **Remotion Studio port.** Assumed to pick a free port when 3000 is busy; verify before relying on it.
9. **Case and path normalisation of keys.** `normcase(resolve())` is used; on macOS (case-insensitive, normcase is a
   no-op) two spellings of one path could give two keys. Low risk: Claude Code passes the same path each time.
10. **Linux.** The plugin is macOS-first and CI covers macOS and Windows; the `fcntl` path is shared with macOS, but
    hard links and leases are not separately tested on Linux.

## 11. Out of scope

- `lesson-videos` (separate code, single project, teachers on one checkout).
- Several *plain* project folders used at once without git (still `MUSIC_VIDEO_HOME` per session, as today).
- Two installed plugin versions keeping separate engines (they share `engine/`; leases keep it safe).
- Merging or promoting lane finals into the main results (by hand, or re-render after merge).
