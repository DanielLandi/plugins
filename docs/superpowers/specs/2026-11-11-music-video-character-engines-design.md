# music-video character engines (anime with three-vrm first)

Issue: plugins#26. Status: design, 2026-11-11. The user skipped the design questions ("skip the questions"); the
calls below marked *(builder's call)* are the coordinator's defaults.

## Why

The anime proof of concept (two characters drawn as SVG from scratch) was "promising but crude": too many geometric
figures. A research round tested libraries for more natural character animation and picked **@pixiv/three-vrm**
(MIT) with the four **VRoid β AvatarSample_1–4** characters (CC0) as the first library; **Inochi2D** (BSD-2) is the
second look for painted 2D, later; Rive is out. A cartoon round is running now and will add its own pick later.

The user's standing direction: *models keep improving; a library that helps today may be beaten tomorrow by the
model writing everything itself.* So the plugin must not bet on one library. It offers **several ways to animate
characters, side by side**, and gives the user a cheap, repeatable way to **watch** whether the model alone has
overtaken the libraries.

## Goals

1. **Character engines** as a named, per-video choice. The first set:
   - `raw`: the model writes the characters and their motion from scratch in scene code (SVG, canvas or three.js),
     as today. Always available; needs nothing installed.
   - `vrm`: 3D anime characters through three-vrm (MToon cel shading, spring-bone hair and cloth, expressions,
     look-at), in a new kit module.
   - Later engines (`inochi2d`, the cartoon pick) plug into the same choice without changing the skill's flow.
2. **The look step offers the engines** (make skill step 5) whenever the concept has characters: each look direction
   names its engine, so the style-frame sheet compares engines as well as styles. The chosen engine is recorded in
   `LOOK.md` (a **Characters:** line), `look.ts` (`characterEngine`) and `video.yaml` (`characters:`), like `jolts`.
3. **A bake-off**: the same short brief (one shot, two characters, ≈10 s on a song window) built once per engine and
   kept as variants of one scene on the review page (`version … --scene bakeoff --variant <engine>`), so the user
   compares them side by side with the existing compare/wipe/flip tools. Usable inside any video (at the look step)
   and on its own.
4. **Model watch**: a fixed benchmark brief ships with the plugin (the anime duel: rooftop meet, reaction close-ups,
   a clash on the hit, a fist bump; original characters). A `bakeoff` record in the workspace (`bakeoffs.md` next to
   `config.yaml`, one line per run: date, model id, engines, the user's verdict) lets a later session see when the
   last run was and with which model. When the session's model differs from the last recorded run's, the make skill
   offers (once, never blocking) to re-run the benchmark. That is the monitoring: verdicts over time, per model.
5. **three-vrm in the kit** (`studio/kit/three/vrm.tsx` and friends), from the research code: loader that holds the
   render until ready, deterministic spring bones (replayed from frame 0 at a fixed dt, as proven in research), poses
   in normalized bone space, a pose/keyframe track API, expressions and look-at, and a two-character template scene.

## Non-goals

- AI image or video generation. The plugin's hard rule stands ("no image or video generation"); the user owns that
  rule. If they lift it later, a generative engine would be one more entry in the same choice.
- Inochi2D and cartoon engines in this release (their slot exists; their code comes later).
- Motion capture or BVH retargeting (100STYLE, CC BY) — a later phase.
- Character creation tools; users bring CC0/OFL VRM files or use the four samples.

## Anti-goals

- An engine that makes `raw` worse or harder to pick. `raw` stays first-class and is always in a bake-off.
- Non-deterministic frames (a seeked frame must match a sequential render; research measured PSNR 81.7 dB).
- Avatars in the plugin repo (decided: no).
- Any recreation of an existing show's characters or look.

## Decided by the user

- three-vrm first; Inochi2D later as the painted-2D look; Rive out.
- Avatars: **downloaded by `doctor` into the install folder, with pinned checksums** (not bundled, not per video).
- Many options, monitored over time (this design's goals 1–4).

## Constraints

- Public repo, MIT/CC0 only for code and assets; credit in `THIRD_PARTY_NOTICES.md` (three-vrm MIT notice) and the
  avatars' CC0 source in the install folder and in each video's `SOURCES.md` when used.
- The engine already ships `three`, `@react-three/fiber` and `@remotion/three`; add `@pixiv/three-vrm` (research used
  3.5.5; pin it in `studio/package.json` / lock) and a `.vrm` → `asset/resource` rule in `webpack-override.ts`.
- Avatars: find stable, unauthenticated download URLs for VRoid β AvatarSample_1–4 (VRoid Hub / pixiv's official
  pages) and verify the CC0 terms again; pin sha256. Skip A/B/C (not CC0). *If no stable unauthenticated URL exists,
  fall back to: `doctor` prints where to get them and a `vrm add <file>` command copies a user-downloaded file into
  the install folder after checking its checksum — and say so in the report.* The avatars are optional: `doctor`
  must not fail or block when they are missing; only a `vrm` video needs them, and its first render says how to get
  them.
- Scenes reach the avatars through the engine's public folder like other installed assets (the builder picks the
  mechanism; it must work in a project worktree lane, 0.9.0).
- Windows and macOS: Python with `encoding="utf-8"`, argument lists for subprocesses; skills call only the plugin CLI.
- Teachers / other users who never use characters see no change beyond an optional download offer.

## What's left to the builder

- Module layout inside `kit/three/` and the exact pose/track API (reuse `motion.ts` ideas: `track`, `ramp`, eases,
  seeded rng; reuse the kit's `releaseWhenDrawn` and Stage/camera).
- How `bakeoff` is driven: a CLI command (`bakeoff <id> --engines raw,vrm`) that scaffolds the bake-off scene files
  per engine from the benchmark brief, or skill text only that uses `new-video`/`version --variant`. Prefer the
  smallest thing that makes the comparison one command away for the user. *(builder's call)*
- The benchmark brief's wording (a references file, e.g. `references/bakeoff.md`) and the template scene's content.
- Tests: kit unit tests (vitest) for pose/track math and spring determinism (two renders of the same frame, seeked vs
  sequential, match); a studio test that renders a still of the template VRM scene when the avatars are installed
  (skip cleanly otherwise); Python tests for `doctor`'s download (checksums, offline, partial file), the
  `characters:` setting, `bakeoffs.md` records, and the skill text (tests/test_mv_skills.py rules).

## Done means

A user making a music video with characters is offered `raw` and `vrm` at the look step, can run a bake-off that
puts both on the review page as variants of one scene, and the workspace remembers each bake-off's model and
verdict so the next model can be checked against it.
