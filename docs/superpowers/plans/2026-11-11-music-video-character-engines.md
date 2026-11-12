# music-video character engines (raw + vrm, bake-off, model watch) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A video with characters picks a character engine at the look step (`raw` or `vrm`), a one-command bake-off
puts every engine's take on the same brief side by side on the review page, and a `bakeoffs.md` record lets the next
model be checked against the last one.

**Architecture:** Python gains `avatars.py` (pinned downloads of the four CC0 VRoid β samples into the install
folder, never failing `doctor`), `characters.py` (the engine registry and the `characters:` setting) and `bakeoff.py`
(scaffold a bake-off into a video, record and read `bakeoffs.md`). The engine gains `@pixiv/three-vrm` 3.5.5, a `.vrm`
asset rule and an `@mv/avatars` alias to the install folder, and a `kit/three/vrm/` module adapted from the research
(motion and pose math, a deterministic spring-bone replay, the `<Avatar>` component). Bake-off starters live in
`studio/bakeoff/<engine>.tsx`; the template's `index.tsx` registers `<id>-bakeoff-<engine>` compositions from a
generated `bakeoff.ts`; versions use the existing `version --scene bakeoff --variant <engine>`.

**Tech Stack:** Python 3.11+ (stdlib `urllib`, `zipfile`, `hashlib`; pytest), TypeScript + React + three.js 0.186 +
@react-three/fiber + @remotion/three 4.0.534, @pixiv/three-vrm 3.5.5, vitest.

**Spec:** `docs/superpowers/specs/2026-11-11-music-video-character-engines-design.md`

## Global Constraints

- Public repo: MIT/CC0 only; no avatars in the repo; nothing from the private research repo except our own adapted
  code; no song names, lyrics or personal data; the benchmark brief is original wording; `tests/test_mv_privacy.py`
  (with `MV_PUBLISH=1`) passes.
- Windows and macOS: `encoding="utf-8"` on every text read/write; subprocesses as argument lists; skills call only
  `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" <command>` (rules in `tests/test_mv_skills.py`).
- `@pixiv/three-vrm` pinned to exactly `3.5.5` in `studio/package.json` and the lock.
- `doctor` never fails or blocks because of avatars (missing, offline, bad checksum): its exit code is unchanged.
- Avatars live in `install_dir() / "avatars"`; downloads are checked against pinned sha256 before they are kept.
- Character engines: exactly `raw` and `vrm` now; `raw` always first and always in a bake-off.
- Anti-goal: frames are deterministic (a seeked frame matches a sequential render).
- No version bump; CHANGELOG gets only a section headed `## Unreleased (draft, not bumped)`.
- Stay out of the lanes code (`workspace.py` lane logic, `paths.py`, `worktrees.py`): another branch edits it.
- Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Gates: `uv run pytest -q`; `uv run pytest -m studio -q`; engine `npm test` (folder printed by `doctor`).

## Rulings (builder's calls; the ledger repeats them with cost if wrong)

1. Avatar source: OpenGameArt's CC0 mirror zips (no official unauthenticated URL exists; VRoid Hub needs a login).
   Pin the zip's and the extracted `.vrm`'s sha256. `avatars add <file>` accepts a `.vrm` or zip whose sha256 matches.
2. Command name `avatars` (`status | install | add FILE`), not `vrm add`: later engines bring their own models.
3. Scenes reach avatars as `import url from '@mv/avatars/vroid-sample-1.vrm'` (webpack alias to `MV_AVATARS`, set by
   `tool_env`); a render of a video whose code imports a missing avatar stops before bundling with the install line.
4. Bake-off: one command `bakeoff new <id> [--song S] [--engines raw,vrm] [--from SEC]` scaffolds starters and the
   generated `bakeoff.ts`; the model writes each engine's take from `references/bakeoff.md`; renders go through the
   usual render/mux/qc/`version --variant`. `bakeoff record` and `bakeoff last` keep and read `bakeoffs.md`.
5. `bakeoffs.md` lives in `ws.home` (next to the workspace's `config.yaml`), a Markdown table, one row per run; a
   declined offer is a row too (engines `-`, verdict `declined`) so the same model is never offered twice.
6. Default bake-off window: 10 s, placed so the song's strongest `analysis.hits` moment falls 6 s in (clamped to the
   song); `--from` overrides.
7. `characters:` / `characterEngine` default `null` (no characters); values `raw` | `vrm`.
8. `doctor` downloads the avatars by default (the user's decision) unless `--no-install` or `--no-avatars`.

## Review Focus

1. **Offline or flaky network during `doctor`** — a note line, exit code unchanged, no half file left as an avatar.
   Test in Task 1 (`test_doctor_offline_keeps_exit_code`).
2. **A truncated or tampered avatar already in the install folder** (an old interrupted copy, a hand-copied file) —
   `status` reports it bad and `install` replaces it. Test in Task 1 (`test_bad_file_is_replaced`).
3. **A video that imports an avatar that is not installed** — the render stops with one line naming
   `music-video avatars install`, not a webpack stack trace. Test in Task 2 (`test_render_stops_when_avatar_missing`).
4. **A song shorter than the 10 s window, or with no hits** — the window clamps inside the song and never goes
   negative. Test in Task 6 (`test_window_short_song_and_no_hits`).
5. **Re-running `bakeoff new` on a video that already has a bake-off** — written scene files are never overwritten;
   only missing engines are added. Test in Task 6 (`test_scaffold_keeps_written_scenes`).

---

### Task 1: Avatars: pinned download, add, status, doctor

**Files:**
- Create: `music-video/scripts/musicvideo/avatars.py`
- Modify: `music-video/scripts/musicvideo/doctor.py`, `music-video/scripts/musicvideo/cli.py`
- Test: `tests/test_mv_avatars.py`

**Interfaces:**
- Produces: `@dataclass(frozen=True) Avatar(key: str, file: str, name: str, zip_url: str, zip_sha256: str,
  member: str, sha256: str, size: int, page: str)`; `AVATARS: tuple[Avatar, ...]` (keys `vroid-sample-1..4`, files
  `vroid-sample-N.vrm`); `avatar_dir() -> Path`; `state(a: Avatar, folder: Path | None = None) -> str` (`ok` |
  `missing` | `bad`); `install(fetch: Fetch = fetch_url, avatars=AVATARS) -> list[str]` (message lines; raises
  `MVError` only on per-file failure when called by the CLI); `add(file: Path, avatars=AVATARS) -> Avatar`;
  `doctor_lines(install: bool, fetch: Fetch = fetch_url) -> list[str]` (never raises); `Fetch = Callable[[str, Path],
  None]` (download a URL to a path).
- Pinned values (OpenGameArt node 170868, "Author: VRoid Project", CC0):
  1: `avatarsample_d_0.zip` 311a383b…3167 → `AvatarSample_D.vrm` 16851352 B, 9adf1b44…f9b7;
  2: `avatarsample_e.zip` 3b6808e2…b6b1 → `AvatarSample_E.vrm` 17936516 B, aea824cc…7911;
  3: `avatarsample_f.zip` e187569e…ebd1 → `AvatarSample_F.vrm` 14198800 B, d8eff1ed…21bb;
  4: `avatarsample_g.zip` 3dc643aa…1b34 → `AvatarSample_G.vrm` 15321932 B, ad5750ce…57c0 (full hashes in the ledger).

- [ ] **Step 1: Write the failing tests** (a fake `Fetch` copies bytes from a dict; test avatars built from tiny fake
  zips with real hashes):
  `test_install_downloads_checks_and_writes_sources` (file at `avatar_dir()/<file>`, `state == "ok"`,
  `avatar_dir()/SOURCES.md` names CC0 and the page; no `*.part` left);
  `test_zip_checksum_mismatch_keeps_nothing` (`state == "missing"`, no `.part`, message names the file);
  `test_bad_file_is_replaced` (truncated file → `bad` → install → `ok`);
  `test_add_accepts_a_matching_vrm_or_zip_and_refuses_others` (`MVError` "not one of");
  `test_doctor_offline_keeps_exit_code` (fetch raises `URLError`; `run_doctor` result unchanged and a `note` line
  says `music-video avatars install`); `test_doctor_no_install_only_reports`;
  `test_pinned_avatars_are_the_four_samples` (4 entries, 64-hex hashes, https URLs on opengameart.org).
- [ ] **Step 2: Run** `uv run pytest tests/test_mv_avatars.py -q` — FAIL (no module).
- [ ] **Step 3: Implement `avatars.py`**: stream to `<dir>/.<file>.part` then `os.replace`; verify zip sha256, extract
  `member` with `zipfile`, verify `.vrm` sha256 and size; `state` checks size then sha256 (cached in
  `.verified.json` by size+mtime_ns). `fetch_url` uses `urllib.request` with a 60 s timeout and a generic User-Agent.
  In `doctor.py` call `doctor_lines(install and not no_avatars)` after the engine step (wrapped so nothing raises).
  CLI: `avatars [status|install|add] [file]`; doctor gets `--no-avatars`.
- [ ] **Step 4: Run** the tests — PASS; then `uv run pytest -q`.
- [ ] **Step 5: Commit** `music-video: avatars command and doctor download of the CC0 VRoid samples (#26)`.

### Task 2: Engine plumbing: three-vrm, .vrm assets, @mv/avatars, render-time check

**Files:**
- Modify: `music-video/studio/package.json`, `package-lock.json`, `webpack-override.ts`, `types/assets.d.ts`,
  `tools/board.ts`, `tools/web.ts`, `music-video/scripts/musicvideo/studio.py`, `music-video/scripts/musicvideo/cli.py`
  (`_prepare`), `music-video/THIRD_PARTY_NOTICES.md`
- Test: `tests/test_mv_avatars.py`, `tests/test_mv_studio.py`, `tests/test_mv_repo_files.py`

**Interfaces:**
- Consumes: `avatars.AVATARS`, `avatars.avatar_dir()`.
- Produces: `avatars.imported(video_dir: Path) -> set[str]` (files named by `@mv/avatars/<file>` in `*.ts`/`*.tsx`);
  `avatars.check_video(video_dir: Path) -> None` (raises `MVError` naming the missing files and
  `music-video avatars install`); `tool_env` adds `MV_AVATARS`; `typecheck_config` maps `@mv/avatars/*`.

- [ ] **Step 1: Failing tests**: `test_render_stops_when_avatar_missing` (video file importing
  `'@mv/avatars/vroid-sample-1.vrm'` → `check_video` raises with `avatars install`; with the file present it passes;
  imports of user files like `./hero.vrm` are ignored); `test_tool_env` asserts `env["MV_AVATARS"] ==
  str(avatar_dir())`; `test_engine_pins_three_vrm` (`dependencies["@pixiv/three-vrm"] == "3.5.5"`, lock has
  `node_modules/@pixiv/three-vrm` version 3.5.5, `webpack-override.ts` has `vrm` and `@mv/avatars`); notices test
  requires `three-vrm`.
- [ ] **Step 2: Run** — FAIL.
- [ ] **Step 3: Implement**: dependency + lock (`npm install @pixiv/three-vrm@3.5.5 --save-exact` in a scratch copy of
  `studio/`, copy back `package.json` and `package-lock.json`); webpack rule `/\.(glb|gltf|vrm)$/` and alias
  `'@mv/avatars': process.env.MV_AVATARS ?? path.join(studio, 'avatars')`; `declare module '*.vrm'`; board/web Node
  hooks stub `.vrm` and resolve `@mv/avatars/*` to a stub; vite `assetsInclude` gains `**/*.vrm` and the alias;
  `_prepare` calls `avatars.check_video(ctx.dir)` (render, still, stills, blur, board, studio, web); notices add
  three-vrm (MIT, © pixiv Inc.) and the avatars' CC0 source (downloaded, not shipped).
- [ ] **Step 4: Run** the tests — PASS; `uv run pytest -q`.
- [ ] **Step 5: Commit** `music-video: three-vrm in the engine, .vrm assets and @mv/avatars (#26)`.

### Task 3: Kit motion and poses (`kit/three/vrm/motion.ts`, `poses.ts`)

**Files:**
- Create: `music-video/studio/kit/three/vrm/motion.ts`, `poses.ts`, `motion.test.ts`, `poses.test.ts`
- Modify: `music-video/studio/vitest.config.ts` (include `kit/**/*.test.ts` already covers it; check)

**Interfaces:**
- Produces (exported from `@mv/kit/three`; names chosen not to collide with `@mv/kit`'s `clamp`, `pulse` or
  `kit/three`'s `Ease`, `hash`): `EaseFn = (t: number) => number`; `eases: Record<'linear'|'inOut'|'in'|'out'|
  'outBack'|'outElastic'|'sine', EaseFn>`; `ramp(t, a, b, e?)`; `swell(t, a, b, c, d, e?)` (0→1→0);
  `Key = [number, number, EaseFn?]`, `track(t, keys)`; `seeded(seed) => () => number` (mulberry32);
  `Euler3`, `Pose = Partial<Record<string, Euler3>>`, `mixPose(a, b, w)`, `addPose(a, b, w?)`,
  `PoseKey = [number, Pose, EaseFn?]`, `poseTrack(t, keys)`, `mirrorPose(p)`; `poses` (relax, handsBehind, waveR,
  waveL, high5R, high5L, windupR, windupL, startle, guardR, guardL, punchR, punchL, dash, laugh, fistBumpR,
  fistBumpL); layers `breath(t, rate?, amt?)`, `sway(t, amt?, seed?)`, `walkCycle(phase, amt?, stride?)`,
  `fingers(curl, side?)`.
- [ ] **Step 1: Failing tests**: `track` holds before the first key and after the last, hits each key value, uses the
  key's ease; `ramp` 0 at a, 1 at b; `swell` 0/1/1/0 at a/b/c/d; `seeded(7)` gives the same 5 numbers twice and
  all in [0,1); `mixPose(a,b,0.5)` averages and fills missing bones with 0; `mirrorPose` swaps `leftX`↔`rightX`,
  negates y and z, and `mirrorPose(mirrorPose(p))` equals `p`; `poses.waveL` equals `mirrorPose(poses.waveR)`;
  `fingers(1,'left')` has only left bones.
- [ ] **Step 2: Run** `npx vitest run kit/three/vrm` in the engine — FAIL.
- [ ] **Step 3: Implement** (adapted from the research `motion.ts`/`poses.ts`; add `fistBumpR`: right arm forward at
  shoulder height, fist).
- [ ] **Step 4: Run** — PASS. **Step 5: Commit** `music-video: kit pose and keyframe math for characters (#26)`.

### Task 4: Deterministic spring replay and `<Avatar>`

**Files:**
- Create: `music-video/studio/kit/three/vrm/replay.ts`, `replay.test.ts`, `Avatar.tsx`, `index.ts`
- Modify: `music-video/studio/kit/three/index.ts`

**Interfaces:**
- Produces: `Replayable<S> = { apply(state: S): void; step(dt: number): void; reset(): void }`;
  `ReplayState = { frame: number }`; `replayTo<S>(r: Replayable<S>, mem: ReplayState, drive: (t: number) => S,
  frame: number, fps: number, sub = 4, settle = 1) -> void` (from rest: settle `settle` s under `drive(0)`, then frames
  1..frame, `sub` steps each at dt = 1/fps/sub; only `frame === mem.frame + 1` continues); `AvatarState = { pos: Vec3;
  yaw: number; pose: Pose; hips?: Vec3; expr?: Record<string, number>; lookAt?: Vec3 | null; wind?: Vec3 }`;
  `Drive = (t: number) => AvatarState`; `<Avatar url drive outline? silhouette? />`; `faceYaw(from: Vec3, to: Vec3)`.
- [ ] **Step 1: Failing tests** (a fake damped spring as `Replayable`): seeking frame 40 directly equals stepping
  0..40 one by one (exact `toBe`); going back to 10 after 40 equals a fresh replay to 10; same frame twice does not
  step again.
- [ ] **Step 2: Run** — FAIL. **Step 3: Implement** `replay.ts`; `Avatar.tsx` from research `vrm.tsx` (loader with
  `VRMLoaderPlugin`, `removeUnnecessaryVertices`, `combineSkeletons`, `rotateVRM0`; VRM 0.x mirror of x/z; expressions
  reset then set; look-at target; wind on spring gravity) using `replayTo` and the kit's `releaseWhenDrawn`; a failed
  load cancels the render with `avatar <url> did not load: run music-video avatars install`.
- [ ] **Step 4: Run** vitest and `npm run typecheck` — PASS. **Step 5: Commit**
  `music-video: deterministic spring replay and the Avatar component (#26)`.

### Task 5: The character engine setting and the template's bake-off wiring

**Files:**
- Create: `music-video/scripts/musicvideo/characters.py`, `music-video/studio/template/bakeoff.ts`
- Modify: `music-video/studio/kit/types.ts`, `music-video/studio/template/look.ts`, `video.yaml`, `LOOK.md`,
  `index.tsx`
- Test: `tests/test_mv_characters.py`

**Interfaces:**
- Produces: Python `ENGINES = ("raw", "vrm")`, `characters_setting(ws, video_id) -> str | None` (missing file/key or
  null → None; unknown → `MVError` listing the engines); TS `CharacterEngine = 'raw' | 'vrm'`,
  `BakeoffEntry = { engine: CharacterEngine; Component: React.FC }`; template `bakeoff.ts` exports
  `bakeoff: { from: number; to: number; entries: BakeoffEntry[] }` (empty); `index.tsx` registers
  `${ID}-bakeoff-${engine}` (1920×1080, `songMetadata<Props>(bakeoff)`, `<Excerpt from={bakeoff.from}>`, song audio,
  no lyrics).
- [ ] **Step 1: Failing tests**: template defaults (`characterEngine: CharacterEngine | null = null`,
  `characters: null` in video.yaml, `**Characters:** none` in LOOK.md); `characters_setting` cases; the TS union in
  `kit/types.ts` lists exactly `ENGINES`; template `index.tsx` imports `./bakeoff` and names `-bakeoff-`.
- [ ] **Step 2–4:** FAIL → implement → PASS. **Step 5: Commit**
  `music-video: characters setting and the template's bake-off compositions (#26)`.

### Task 6: `bakeoff` command: scaffold, record, last

**Files:**
- Create: `music-video/scripts/musicvideo/bakeoff.py`, `music-video/studio/bakeoff/raw.tsx`,
  `music-video/studio/bakeoff/vrm.tsx`
- Modify: `music-video/scripts/musicvideo/cli.py`
- Test: `tests/test_mv_bakeoff.py`

**Interfaces:**
- Consumes: `characters.ENGINES`, `studio.new_video`, `studio.PLUGIN_STUDIO`.
- Produces: `WINDOW = 10.0`; `default_window(analysis: dict, length=WINDOW) -> tuple[float, float]`;
  `scaffold(ws, video_id, engines: list[str] | None = None, start: float | None = None, song: str | None = None)
  -> dict(video, dir, engines, added, window, wired)`; `record(ws, video_id, model, verdict, engines=None,
  declined=False, today=None) -> dict`; `records(ws) -> list[dict]`; `watch(ws, model) -> dict(last, offer, reason)`;
  `BAKEOFFS = "bakeoffs.md"`. CLI `bakeoff {new,record,last} [id] [--song] [--engines] [--from] [--model]
  [--verdict] [--declined]`.
- Starters: `bakeoff/raw.tsx` exports `Bakeoff` (an empty stage with the brief's beats as a comment; the model draws
  everything); `bakeoff/vrm.tsx` exports `Bakeoff` (the two-character template scene: two samples on a rooftop at
  dusk, a meet, a turn to each other, a fist bump on the window's hit at 6 s, expressions and look-at).
- [ ] **Step 1: Failing tests**: `test_window_on_the_strongest_hit`, `test_window_short_song_and_no_hits`;
  `test_scaffold_new_video_borrows_a_song` (`--song` writes `song:` into the new video's `video.yaml`);
  `test_scaffold_writes_starters_and_bakeoff_ts` (raw first, generated `bakeoff.ts` imports `./bakeoff/raw` and
  `./bakeoff/vrm` with the window, vrm adds a SOURCES.md row, unknown engine → `MVError`);
  `test_scaffold_keeps_written_scenes`; `test_scaffold_says_how_to_wire_an_old_index`;
  `test_record_and_last` (table with header, `|` in a verdict escaped, `watch` offers for a new model, not for the
  same model, not after a declined row for that model, offers when there is no record).
- [ ] **Step 2–4:** FAIL → implement → PASS (`uv run pytest -q`).
- [ ] **Step 5: Commit** `music-video: bakeoff command and the raw and vrm starters (#26)`.

### Task 7: Skill, references and docs

**Files:**
- Create: `music-video/skills/make/references/bakeoff.md`
- Modify: `music-video/skills/make/SKILL.md` (step 5), `references/look.md` (Characters line), `references/studio.md`
  (vrm section), `music-video/README.md`, `SERVICES.md`, `music-video/CHANGELOG.md` (draft section)
- Test: `tests/test_mv_characters.py`

- [ ] **Step 1: Failing tests**: step 5 names `raw`, `vrm`, `Characters:`, `characterEngine`, `characters:`,
  `bakeoff new`, `bakeoff last` and says the offer is once and never blocks; `references/bakeoff.md` has the brief
  (rooftop, reaction close-ups, clash on the hit, fist bump, original characters), the `version … --variant`
  line and `bakeoff record`; `studio.md` names `@mv/avatars` and `avatars install`; SERVICES.md names OpenGameArt.
- [ ] **Step 2–4:** FAIL → write → PASS (full suite, including `test_mv_skills.py`).
- [ ] **Step 5: Commit** `music-video: the look step offers character engines; bake-off and model watch (#26)`.

### Task 8: Engine gate, real render and determinism check

**Files:**
- Create: `tests/test_mv_vrm_e2e.py` (`pytestmark = pytest.mark.studio`)

- [ ] **Step 1:** `uv run music-video/scripts/music-video.py doctor` from the worktree (installs this checkout's
  engine and the avatars); `npm test` in the printed engine folder — PASS.
- [ ] **Step 2: Studio tests**: `test_vrm_bakeoff_renders_two_characters` (skip unless all avatars `ok`; new video,
  fixture song, `bakeoff new --from 0`, `still <id> <id>-bakeoff-vrm out.png --frame=60`, size > 50 kB);
  `test_seeked_frame_matches_sequential` (render frames 0–45 as a PNG sequence at concurrency 1 and a still at 45;
  PSNR ≥ 60 dB with numpy/Pillow). Run `uv run pytest -m studio -q` — PASS.
- [ ] **Step 3:** Render a still with two characters into the scratchpad and look at it; fix the starter until it
  reads (both characters visible, lit, on the ground, facing each other).
- [ ] **Step 4: Commit** `music-video: studio tests for the vrm bake-off render (#26)`.

### Task 9: Close

- [ ] `MV_PUBLISH=1 uv run pytest -q tests/test_mv_privacy.py` with a temporary copy of the denylist (deleted after).
- [ ] Final whole-branch review by a fresh opus reviewer; one fix pass; `git fetch && git merge origin/main`; full
  gates again; `git push`.
