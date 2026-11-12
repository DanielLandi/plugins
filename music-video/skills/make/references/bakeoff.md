# The character bake-off

The same short brief, built once with each character engine, compared side by side on the review page. It answers
two questions: which engine suits this video (at the look step), and whether the model writing everything itself
(`raw`) has caught up with the libraries (the model watch, run on its own).

## Engines

- **`raw`**: you write the characters and every move from scratch in scene code (SVG, canvas or three.js through
  `@mv/kit/three`), with no character library. Always in a bake-off: it is the measure of the model itself.
- **`vrm`**: 3D anime characters through three-vrm: `<Avatar>`, poses and keyframes from `@mv/kit/three`, cel
  shading with outlines, hair and cloth that follow through on their own, expressions and eyes that follow a
  target (`references/studio.md`, "Characters"). The four CC0 sample characters come from
  `music-video avatars install`; a user's own CC0 or OFL `.vrm` goes in the video's folder.

## The benchmark brief (fixed: the model watch compares runs only while it stays the same)

One scene, 10 s of the song, two original characters (the samples, or ones drawn from scratch for `raw`; never a
recreation of an existing show's characters or look). The window puts the song's strongest hit 6 s in; near the
song's start or end, or with `--from`, it lands elsewhere: `bakeoff new` prints where, and each take gets it as
`hit` (seconds into the window). The times below are for a hit at 6 s: move them with it.

1. **0–2.5 s, the rooftop.** Late light over a city roof. The first character waits at the railing, looking out,
   weight shifting, hair moving in the breeze. The second arrives across the roof and stops short.
2. **2.5–4.5 s, reaction close-ups.** Cut or push in on each face in turn: the first turns, surprised, then
   recognises the other and grins; the second answers with a small wave or a nod. Eyes find each other.
3. **4.5–6 s, the square-up.** Both drop into a playful fighting stance, a beat of mock rivalry, anticipation
   building into the hit.
4. **6 s, the clash on the hit.** On the hit they strike at the same moment: the fists meet between them with an
   impact (a flash, a burst of wind through hair and clothes, a camera jolt only if the video's jolts answer is yes).
5. **6–10 s, the fist bump.** The clash turns into a fist bump and a laugh; they hold it, then relax, side by
   side, looking out over the roof again.

Judge each take on: do the characters read as alive (weight, breath, follow-through), does contact land (the fists
really meet, on the hit), do faces carry the reactions, does it sit on the music, and does it look like one film.

## Running it

1. Start it in the video (at the look step) or in a new video that borrows a song (the model watch):

   ```bash
   uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" bakeoff new <id> --engines raw,vrm
   uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" bakeoff new bakeoff-<yyyy-mm-dd> --song <song id>
   ```

   It writes a starter per engine in `<video>/bakeoff/<engine>.tsx` (raw: an empty stage; vrm: a working
   two-character scene to rework), and `bakeoff.ts` with the window (`--from <seconds>` moves it); takes you already
   wrote are kept. It prints the commands below with the real paths, and asks for `avatars install` when the vrm
   take needs the samples.
2. Write each take from the brief, one engine at a time, with the same care as a real scene (`studio.md`,
   `animation.md`, `shot-design.md`). Each take gets `from`, `to` and `hit`: its `t = 0` is the window's start
   (`useSongTime() - from`), the clash lands at `t = hit`, and a vrm `<Avatar>` gets `from={from}`. Do not let one take borrow from another: each shows what its engine does.
3. Render, add the song, check and keep each take as a variant of the scene `bakeoff`:

   ```bash
   uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" render <id> <id>-bakeoff-<engine> "<renders>/bakeoff-<engine>-silent.mp4" --muted
   uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" mux "<renders>/bakeoff-<engine>-silent.mp4" --spec <song> --out "<renders>/bakeoff-<engine>.mp4" --excerpt <from>-<to>
   uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" qc "<renders>/bakeoff-<engine>.mp4" --spec <song> --excerpt <from>-<to>
   uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" version <id> "<renders>/bakeoff-<engine>.mp4" --scene bakeoff --variant <engine> --excerpt <from>-<to>
   ```

4. Open the review page (`review <id> --open`) and show the takes side by side, raw first; the compare, wipe and
   flip tools play them in sync. Say in one line per take what you see, then ask the user which works and why.
5. Record the run with the user's verdict in their words, and the model that wrote the takes (your model id):

   ```bash
   uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" bakeoff record <id> --model <model id> --verdict "<what the user said>"
   ```

   Inside a video, write the winner into the look (`characterEngine`, `characters:`, the **Characters:** line),
   then clear the takes (deleting `bakeoff/` by hand would leave `bakeoff.ts` importing files that are gone, and
   the video would no longer build). The kept versions stay on the review page:

   ```bash
   uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" bakeoff clear <id>
   ```

## The model watch

Models keep improving: a library that helps today may be beaten by the model writing everything itself. Each
recorded run says which model wrote the takes, so verdicts line up over time, per model:

```bash
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" bakeoff last --model <model id>
```

It prints the last run and whether to offer the benchmark to this model. Offer it once, in one line, never as a
gate. When the user says no, record that, so this model is not asked again:

```bash
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" bakeoff record --model <model id> --declined
```
