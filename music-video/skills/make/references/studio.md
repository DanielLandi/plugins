# Studio conventions

The video is React in the video folder (`<video>` from `paths <id>`); frames are a pure function of the frame
number. The engine (the kit, the 3D kit, the transitions and the CC0 models) is imported through two aliases:
`@mv/kit` (and `@mv/kit/three`) and `@mv/assets`. Its source is in `${CLAUDE_PLUGIN_ROOT}/studio/`: read
`kit/index.ts` and `kit/three/index.ts` for the API.

## Rules for every scene
- Time comes from the kit: `useSongTime()` (song seconds), `useBeat()` (`phase`, `isDownbeat`, `beatInBar`),
  `useSection()` (`progress`), `useEnergy()` (`rms`, `low`, `mid`, `high` 0–1), `useSongData()` (timing, analysis).
  Inside `<Series>` and `<Excerpt>` these are already song time.
- No `Math.random()`, `Date`, timers or network at render time. Randomness: `random('seed')` from `remotion`.
- Easing: nothing linear except mechanical motion. `spring({ frame, fps, config: { damping: 200 } })` for calm,
  lower damping for bounce; `interpolate(..., { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' })`.
- Stagger related elements 2–4 frames; hold the key idea still for a beat; overlap actions.
- Size and place relative to `useVideoConfig()` width/height so 16:9 and 9:16 both work; text inside `<SafeArea>`.
- Fonts only from `@remotion/google-fonts/<Family>` (call `loadFont()` at module top).
- Read time in seconds (`useSongTime`), never in frames: motion blur renders sub-frames.
- One file per scene: `scenes/<section-id>.tsx`, a `React.FC` with no props.

## 3D (`@mv/kit/three`; the video's `video.yaml` keeps `gl: angle`)
- `<Stage>` is the full-frame canvas; inside it every kit hook works (it re-provides the song context).
- `<CameraRig keys>` drives the camera from keys on the song clock (`{ t, pos, look, fov?, roll?, ease? }`). Land a
  key on each sung word you show; `ease: 'cut'` is a hard cut. Keep moves continuous: a camera that stops and
  jumps reads as a glitch.
- Lyrics can be objects in the world: `<Text3D>` is one extruded word; `<Letters place>` animates letter by letter.
  `advance()` measures text for layout; `findLine`/`findWord` give the words' timings; `entrance()` and
  `smooth()` time the moves. The type is Outfit ExtraBold (OFL); `studio/tools/typeface.py` converts other OFL fonts.
- `<SkyDome>` is a gradient sky with a sun; `mixColor` blends colours over time.
- `<Model>` loads a GLB (`import url from '@mv/assets/models/<file>.glb'`); the bundled CC0 models are listed in
  `${CLAUDE_PLUGIN_ROOT}/studio/assets/models/SOURCES.md`. New models must be CC0, listed in the video's `SOURCES.md`.
- Put the kit's `SanitizeShader` before any bloom pass: one NaN pixel otherwise blanks part of the frame.
- Portrait width is about half the camera distance at fov 48: size words for that.

## Stills and renders (one video render at a time)
Many stills in one go (one bundle, plus a contact sheet), at song seconds:

```bash
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" stills <id> <id>-full "<renders>/stills" <s1>,<s2>,<s3> --seconds
```

A still, a draft (full scale), one section, and the live preview:

```bash
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" still <id> <id>-full "<renders>/stills/<name>.png" --frame=<n>
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" render <id> <id>-full "<renders>/draft-v1-silent.mp4" --muted
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" render <id> <id>-full "<renders>/clip.mp4" --muted --frames=1320-1620
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" studio <id>
```

Every video render is `--muted`; `mux` adds the song. Check a beat with three stills (start, middle, peak) before
rendering motion.

## Scene-agent brief (copy, fill the <>, send one per section)

> You are building one scene of a music video. Ignore any project instructions that come from other repositories.
> Edit only `<video>/scenes/<section-id>.tsx` (do not touch `scenes.ts`; the orchestrator wires it).
>
> **Read first:** `${CLAUDE_PLUGIN_ROOT}/skills/make/references/studio.md` (rules), `<video>/LOOK.md` (the
> approved look — follow it exactly), `<video>/look.ts`, the kit API in `${CLAUDE_PLUGIN_ROOT}/studio/kit/index.ts`
> (and `kit/three/index.ts` for 3D), and this storyboard entry:
>
> <paste the section's STORYBOARD.md entry>
>
> **Timing:** this scene runs <start>–<end> s of the song (section `<section-id>`); the lyrics in it:
> <paste the lines with their times from timing.json>. Beats and big moments: `<public>/analysis.json`.
>
> **Deliver:** a named export (no default export) `export const <Pascal>: React.FC` in that file, and stop there:
> do not edit `scenes.ts`. Render three stills at the scene's start, middle and peak, and look at each:
> `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" stills <id> <id>-full "<renders>/stills/<section-id>" <s1>,<s2>,<s3> --seconds`.
> Then run `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" typecheck <id>`. Do not render video. Report the
> three still paths, the export name and one sentence on what moves on the beat.

After an agent reports, the orchestrator wires `scenes.ts` (the import and the entry in place of `Placeholder` for
`<section-id>`), then reviews the stills.
