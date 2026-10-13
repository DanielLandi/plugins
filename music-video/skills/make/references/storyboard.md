# Storyboard and transition board (step 6)

## STORYBOARD.md — one entry per section of `analysis.json`
- **Time:** start–end (m:ss), the section id (`chorus-2`).
- **Scene:** what we see, drawn from that section's lyric images; how it relates to the last scene.
- **On the beat:** what moves on beats, what on downbeats.
- **Big moments:** which `hits` get a visual event, and what it is.
- **Lyrics:** overlay, or how the words appear in the scene.
- Last entry: **Vertical cut** — the 30–60 s excerpt (start on a bar line, hook in the first frame) and how the
  layout recomposes for 9:16. It ends on a finished thought (a line's end, an image that resolves), never in the
  middle of a move; where the 16:9 camera moves on after that, a portrait-only camera key holds the last framing to
  the end.

## scenes.ts
One `SceneEntry` per section, in order, `from` = the section start (snap to the nearest downbeat when it is within
0.15 s). Components in `scenes/<section-id>.tsx`; until written, use `Placeholder`.

## cuts.ts — the transition board
For every pair of neighbouring scenes, one `CutSpec`:
- **carrier:** an element already on screen that makes the change (a light, a line, a shape, the camera). No carrier, no cut.
- **why:** what the cut means: continuity, a turn, a section break, a reveal, a rise, a breath.
- **landsOn:** the downbeat or word it is centred on (`layoutSeries` centres the cut on the scene boundary).
- **transition:** an id from `${CLAUDE_PLUGIN_ROOT}/studio/transitions/catalog.json` (read `TAXONOMY.md` next to it
  for the families), with `params` (most take `color`: use the incoming scene's background).
- **frames:** inside the transition's `duration.min`–`max`; snap cuts are short, breaths long; a beat is 30 × 60 / tempo frames.

Rules:
- The screen never goes blank: no dips to a flat colour, no flash to white. Library transitions that cover the frame
  are allowed only when the cover is made of the scenes' own elements.
- 2–4 transition families per video, used consistently: the same kind of cut means the same kind of change. Bigger
  moves only at section breaks.
- The board (`uv run "${CLAUDE_PLUGIN_ROOT}/scripts/music-video.py" board <id>`) must pass; read every `cut-NN.png`
  panel in `<renders>/board/` (outgoing frame, 35%, 65%, incoming frame). If the carrier does not read in the
  in-betweens, change the choice, not the frame.
