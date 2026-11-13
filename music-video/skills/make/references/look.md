# The look (step 5)

A look is a system before it is pictures. Write it, then prove it with real frames.

## LOOK.md (one section per direction while choosing; the winner only once approved)
- **Idea:** one sentence connecting the song's purpose and genre to the picture.
- **Palette:** background, 1–2 neutrals, 1 accent (hex). The accent marks the one thing to look at.
- **Type:** a display face and at most one text face, from Google Fonts (OFL, via `@remotion/google-fonts`).
  Sizes on a scale (×1.25). Lyrics ≥ 5% of frame height in 16:9, ≥ 4% of height in 9:16.
- **Grid and safe areas:** 5% title-safe in 16:9; in 9:16 keep clear of the top 14%, bottom 22%, right 12% (kit `safeRect`).
- **Shape language and texture:** rounded or sharp, flat or dimensional, line weight, grain/paper/none.
- **Finish:** the post that makes it read as film rather than a render: grain, vignette, grade, bloom. In 3D, the
  kit's film-print `FinishPost` and depth on flat things (paper with thickness, carved frames, relief on
  procedural textures; see `studio.md`). It costs almost no render time, so plan it with the look instead of
  leaving it for the end.
- **Light and materials (3D):** which real sources light each place (lamps, screens, windows, the sky), how dark the
  set stays around them, and the real textures its surfaces get (Poly Haven, CC0; `studio.md`). Only real lights
  glow; nothing else gets an emissive glow. A style is structure, not a filter: name what makes it (outlines, a
  screen-fixed halftone, hard light bands, a saturated world against a muted hero, one accent reserved for one
  thing). When a character comes from photos, take its colours and markings from them and build the form as a
  clean stylized version; never fit the sculpt to one photo's pose.
- **Motion language:** springy, smooth or mechanical; what happens on beats (kit `useBeat`, `pulse`), on downbeats,
  on big moments (`analysis.hits`), and with energy (`useEnergy`).
- **Jolts:** the answer to the jolts question (step 5): no (the default, also when unanswered) or yes, and what
  jolts (the camera kicks on the kick drum, a shake on the big hits). With no, nothing kicks or shakes on the beat:
  beat motion is eased. With yes, jolts are small and die within about a fifth of a second.
- **Characters:** none, or the engine that animates them: `raw` (drawn and moved from scratch in scene code),
  `vrm` (three-vrm anime characters) or `cartoon` (hand-inked 2D rubber-hose characters whose faces act; both in
  `studio.md` "Characters"), and the bake-off's verdict when one ran
  (`bakeoff.md`). Each direction with characters names its engine, so the sheet compares engines too.
- **Medium:** 2D (SVG/CSS/canvas), 3D (the kit's `@mv/kit/three`, see `studio.md`), or shaders. 3D and shaders need
  `gl: angle` in `video.yaml`. Worlds can mix: a realistic world and a low-poly one, a lo-fi tape for a bridge.
- **Lyrics in the world:** overlay (kit `LyricLayer`) or diegetic (words drawn into the scene). When the words are
  already in the picture, hide the overlay for those lines.

## Style frames
- A frame is a real moment, not a mood board: the opening, a verse line, the chorus peak, the ending — at real
  frame numbers (seconds × 30), with the real words.
- Build each direction as `looks/<letter>.tsx` (a full-song scene using kit hooks) and register a composition
  `<id>-look-<letter>` in `index.tsx`, 1920×1080, `calculateMetadata={songMetadata<Props>()}`, plus
  `<id>-look-<letter>-v` at 1080×1920 for the chorus frame.
- Render all of a direction's frames in one go (one bundle, plus a contact sheet), with song seconds:

  ```bash
  uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" stills <id> <id>-look-a "<renders>/frames/a" <s1>,<s2>,<s3>,<s4> --seconds
  ```

- View every still yourself before showing it.
- Show the user the directions' contact sheets (`<renders>/frames/<letter>/<id>-look-<letter>-sheet.png`) one
  after another, in the same message, so they compare them at a glance.
- If they do not look like one film side by side, the system is not done.
- After approval: write `look.ts` (palette, fonts, `lyricStyle`, `jolts`, `characterEngine`), delete the losing
  `looks/*` and their compositions.
