# music-video `cartoon` character engine (brush-ink rubber-hose rig) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A third character engine, `cartoon`, next to `raw` and `vrm`: hand-inked 2D rubber-hose characters whose
faces act, offered at the look step and in the bake-off, with a working two-character starter scene.

**Architecture:** A new kit module `studio/kit/cartoon/` (imported as `@mv/kit/cartoon`, not re-exported from
`kit/index.ts`), adapted from the cartoon research round's brush-ink rig: a pure rig (`Character` + `Pose` → shapes in
screen space), a brush renderer (perfect-freehand strokes that boil on twos), Flubber mouth and smear morphs, pose
presets with `poseTrack`/`mixPose`/`addPose`, the same `track`/`ramp`/`swell`/`eases`/`seeded` helpers as
`kit/three/vrm` (re-exported from it), a deterministic spring follower, effects, and two original characters. Python
adds `cartoon` to the engine registry; `bakeoff new` copies `studio/bakeoff/cartoon.tsx`.

**Tech Stack:** TypeScript + React 19 + Remotion 4.0.534 (plain SVG), perfect-freehand 1.2.3 (MIT), flubber 0.4.2
(MIT), vitest; Python 3.11 + pytest.

**Spec:** issue plugins#33 (the decision) on top of
`docs/superpowers/specs/2026-11-11-music-video-character-engines-design.md` (#26: engines, bake-off, model watch).

## Global Constraints

- Public repo: MIT/CC0 only; nothing from the private research repo except our own adapted code; no song names,
  lyrics or personal data; characters are original (never a recreation of an existing show's characters or look);
  `MV_PUBLISH=1 uv run pytest -q tests/test_mv_privacy.py` passes.
- `perfect-freehand` `1.2.3` and `flubber` `0.4.2` pinned exactly in `studio/package.json`; lock regenerated with
  `npm install --ignore-scripts --package-lock-only`; MIT notices (and flubber's dependencies' licences) in
  `THIRD_PARTY_NOTICES.md`.
- Engines: `ENGINES == ("raw", "vrm", "cartoon")`; `raw` first and always in a bake-off; `CharacterEngine` in
  `kit/types.ts` lists the same.
- Deterministic: a seeked frame equals the same frame in a sequential render (exact pixels for this SVG engine).
- Skills call only `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" <command>`; Python reads/writes with
  `encoding="utf-8"`.
- No version bump; CHANGELOG lines go under the existing `## Unreleased (draft, not bumped)`.
- Do not touch the `music-video-character-engines` branch; work on `music-video-cartoon-engine` only.
- Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Gates: `uv run pytest -q`; `uv run pytest -m studio -q`; engine `npm test`; privacy with `MV_PUBLISH=1`.

## Rulings (builder's calls)

1. The bake-off starter `studio/bakeoff/cartoon.tsx` is also the two-character template scene (as `bakeoff/vrm.tsx`
   is for vrm): one file to keep working, copied by `bakeoff new`, pointed to from `studio.md`.
2. Motion helpers (`eases`, `ramp`, `swell`, `track`, `seeded`, `Key`, `EaseFn`) are re-exported from
   `kit/three/vrm/motion.ts` (a pure file, no three.js import), so both engines key motion the same way.
3. The research pair is kept as the cast, renamed by look: `cast.bean` (tall tangerine bean in a striped beanie) and
   `cast.plum` (round plum with a springy sprout). A video defines its own `Character` data for its own cast.
4. The spring follower replays from the scene's start (`from`, like `<Avatar from>`), not from song time 0, so a late
   scene does not simulate minutes of song every frame.
5. Coordinates are the composition's pixels (1920×1080 for a bake-off); `Pose.scale` scales a character about its
   feet; close-ups are camera moves (`zoomAt`), which scale the ink too, as a redrawn close-up would.
6. Shake follows the video's jolts answer: the starter imports `jolts` from `../look` and shakes on the hit only
   when it is true.
7. `bakeoff new` with no `--engines` writes all three takes (raw, vrm, cartoon).

## Review Focus

1. A scene far into the song (`from` = 180 s): the follower must cost the same as at 0 s and match a sequential
   render. Test: `follow` with `from` gives the same value whether reached by a fresh call or after earlier frames.
2. `mixPose` between a hand given in body space and one given in world space must not jump to garbage (NaN). Test:
   `mixPose` of `{armF:{hand}}` and `{armF:{world}}` yields finite points.
3. Mouth morphs between every pair of mouth keys at k = 0.5 produce finite rings (Flubber on uneven point counts).
4. A pose with every field left out (`{x, ground, face}`) renders a whole character (no NaN in any path).
5. The vertical cut (1080×1920) and an unknown engine name in `video.yaml` (`characters: toon`) name the choices
   (`raw, vrm, cartoon`).

---

### Task 1: kit/cartoon math (rig, motion, poses) with vitest

**Files:**
- Create: `music-video/studio/kit/cartoon/{draw.ts,motion.ts,rig.ts,poses.ts,cast.ts,index.ts}` and
  `music-video/studio/types/flubber.d.ts`
- Test: `music-video/studio/kit/cartoon/{rig.test.ts,motion.test.ts,poses.test.ts}`

**Interfaces (Produces):**
- `type P = [number, number]`; `smooth(pts, closed?, tension?)`, `jitter(pts, seed, amp)`, `ellipsePts`, `cubicPts`,
  `starPts`, `INK`.
- `follow(sig: (t) => number, t, opts?: { from?: number; freq?: number; zeta?: number; dt?: number }): number`;
  `springStep`, `wobble`, `hop`, `hopSquash`, `vol`, `noise1`, `boilSeed(frame, hold?, base?)`, plus the re-exports.
- `type Character`, `type Arm`, `type MouthKey`, `type Pose`, `type Shape`; `buildCharacter(c: Character, p: Pose):
  Shape[]`; `mouthPts(a, b, k): P[]`; `MOUTH_KEYS`.
- `type PoseLayer = Partial<Omit<Pose, 'x' | 'ground' | 'face'>>`; `poses` presets (rest, wave, take, guard, windup,
  punch, cheer, laugh, shrug, lookOut); `mixPose(a, b, w)`, `addPose(a, b, w?)`, `poseTrack(t, keys)`,
  `breath(t, phase?)`, `walk(t, speed, stride?)`.
- `cast.bean`, `cast.plum`.

- [ ] Write the tests: same pose → identical shapes (deep equal) twice and after building other frames in between;
  `follow(sig, 3, {from: 2})` equals itself after a loop of earlier calls, and is ≈ sig at rest; review-focus 2–4;
  `poseTrack` hits each key exactly at its time; mixPose(a, b, 0) = a, (…, 1) = b; `vol(1) == 1`.
- [ ] Run `npx vitest run kit/cartoon` in the engine: FAIL (missing modules).
- [ ] Implement, adapting the research rig under `strict` TypeScript; Flubber caches keyed by shape pair (a WeakMap
  on the `Character` for smears).
- [ ] Run: PASS. Commit.

### Task 2: brush renderer, effects, `<Cartoon>` and the frame-equality unit test

**Files:**
- Create: `music-video/studio/kit/cartoon/{ink.tsx,fx.tsx,Cartoon.tsx}`
- Test: `music-video/studio/kit/cartoon/ink.test.ts` (react-dom/server `renderToStaticMarkup`)

**Interfaces:** `InkShapes({ shapes, seed, boil? })`; `Cartoon({ character, pose, seed?, hold?, boil? })` (boils
every `hold` = 2 frames from `useCurrentFrame`); `inkPath(pts, seed, closed?)`; fx: `Shadow`, `ImpactBurst`,
`DustPuffs`, `TakeLines`, `SpeedLines`, `Emote`, `Flash`, `StarRing`, `shake(t, t0, amp?)`,
`zoomAt(z, fx, fy, shx?, shy?, w?, h?)`.

- [ ] Test: markup of frame N built alone equals markup after building frames 0..N-1; markup has no `NaN`; two seeds
  differ (lines boil).
- [ ] Implement; run vitest PASS; `npm run typecheck` clean. Commit.

### Task 3: the engine in the registry, the starter scene, references and docs

**Files:**
- Modify: `scripts/musicvideo/characters.py` (ENGINES), `studio/kit/types.ts`, `studio/template/{look.ts,LOOK.md}`,
  `skills/make/SKILL.md` (step 5), `skills/make/references/{look.md,studio.md,bakeoff.md}`, `README.md`,
  `CHANGELOG.md`, `THIRD_PARTY_NOTICES.md`, `scripts/musicvideo/cli.py` (help text if it lists engines)
- Create: `studio/bakeoff/cartoon.tsx`
- Test: `tests/test_mv_characters.py`, `tests/test_mv_bakeoff.py`, `tests/test_mv_skills.py`

- [ ] Tests: `ENGINES == ("raw", "vrm", "cartoon")`; an unknown engine names `raw, vrm, cartoon`; `bakeoff new`
  default writes `raw.tsx`, `vrm.tsx`, `cartoon.tsx` and `import { Bakeoff as Cartoon } from './bakeoff/cartoon';`;
  `--engines cartoon` writes no vrm and no avatar credit; studio.md names `@mv/kit/cartoon`, `<Cartoon`, `poseTrack`,
  `bakeoff/cartoon.tsx`; test_mv_skills: every engine in `ENGINES` is named in backticks in the look step,
  `bakeoff.md` and `studio.md`.
- [ ] Run: FAIL. Implement. Starter follows the brief (rooftop at dusk, reaction close-ups, square-up, clash on the
  hit, fist bump) with the vrm starter's `beat()` mapping so the clash lands on `hit`.
- [ ] Run `uv run pytest -q`: PASS. Commit.

### Task 4: studio test and the real render

**Files:**
- Create: `tests/test_mv_cartoon_e2e.py` (`pytest.mark.studio`)

- [ ] Test: `bakeoff new cartoon-check --engines cartoon --from 0` on the fixture song; `typecheck`; a still at frame
  45 is not flat (std > 20); a `--sequence` render of frames 0–45 ends on a frame pixel-identical to the still.
- [ ] Run `uv run pytest -m studio -q`: PASS. Engine `npm test`: PASS.
- [ ] Render the cartoon take over a real song window in a scratch workspace; `qc` it; read the frame sheet; fix
  broken frames. Commit.

### Task 5: review and fix pass

- [ ] A fresh reviewer (opus) reads the branch diff against `origin/music-video-character-engines`; one fix pass;
  gates again; push the branch.
