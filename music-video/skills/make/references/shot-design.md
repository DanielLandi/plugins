> Adapted from `shot-design` in Imaginative-Prompting/claude-video-skills (MIT, © 2026 Imaginative Prompting);
> see the plugin's `THIRD_PARTY_NOTICES.md`.

# Shot design

Read before keying any camera move (`<CameraRig keys>` in 3D, or a 2D scene's pan and zoom) or composing a frame
the camera lands on, and when reviewing a draft's camera. Moves start and land on the song map (`analysis.json`:
beats, downbeats, `drums`; `timing.json`: words); how things move is in `animation.md`. It doesn't cover lens
effects or the grade (`look.md`).

## Your first attempt will be bland: don't ship it

These are the defaults a first pass falls into. Each one was sent back in the films this was learned on.

- **The observer shot:** eye level, 2–4 m away, a mid lens (35–50° vertical), the subject centred, nothing near the
  lens and nothing far behind.
- **One axis at one speed:** a straight push or pull. Nothing turns, nothing passes the lens.
- **Waypoint-and-stop:** arrive, hold, move to the next. Or push to a second waypoint in the same place, then pull
  to a third.
- **The stick camera:** a fixed offset from a moving subject, so it sits in the centre the whole shot.
- **Looking down:** a high camera tipped 35–45° onto a few people.
- **The same size all section:** every frame a medium shot.
- **Nudges:** moves under ~0.3 m or ~10° that read as indecision.
- **The slow creeping zoom:** a constant slow push-in during every hold. Hold the framing instead: a slow drift
  with a direction, or, only when the video's jolts answer is yes (`LOOK.md`, `look.ts`), a slight shake on the
  beat.
- **Softened words:** the user says "at the edge" and you put it a third of the way in; "close-up" and you frame a
  medium.

## Procedure

1. **List the section's beats** with their sung word starts (`timing.json`) and drum hits (`analysis.json`
   `drums`).
2. **Write a shot card per move** (`shot-card.md`). Start with one sentence: "From [start frame], [move] so we
   [reveal / follow / feel] [what], landing on [end frame] on [word or beat]." If the only verb is "show", the move
   has no reason. The sentence goes into the section's `STORYBOARD.md` entry.
3. **Write a spec for every waypoint**, meaning any frame a move lands on or passes its key moment through
   (Framing below). Put the user's framing words in literally, using the table below.
4. **Contrast pass:** put the section's waypoints in a table (size, height, side of the subject, lens, the subject's
   place in frame). Fix any two neighbours that are alike before building anything.
5. **Key the moves** by the rules below.
6. **Probe before rendering** (Verify).
7. **Look:** stills at every waypoint, full size, each judged as a photograph; then a clip, stepped frame by frame
   on the sections page, and watched at speed with the song.
8. **Report** what each move is for and how each waypoint meets its spec, in the user's words where they gave them.

## Moves

- **Something big changes.** Across a move, at least one of these changes a lot: shot size (the subject's height in
  frame ×2 or more), angle (an orbit of 45°+ round the subject, or 1 m+ of height relative to it), or what we know
  (a reveal). A move that ends near the frame it started on is wasted.
- **Two axes, one leading:** push + rise, pull + rise, orbit + push, truck + pan, dolly + tilt. Never a pure zoom,
  or a pure pan from a fixed spot.
- **Parallax, always.** Keep something 0.5–3 m from the lens moving through the frame (a shoulder, heads, a railing,
  a wall edge) and something far behind (a skyline, lights). At least one object per move crosses 20%+ of the frame.
- **Lens by intention:** wide (60°+ vertical) close to the action for energy; long (25° or less) from farther back
  for compression and intimacy. Avoid a mid lens at mid distance. Never zoom the lens (`fov`) to make something
  bigger: move the camera, or bring the object to the camera. (Portrait frames are narrower: check the 9:16 framing
  at every waypoint too; `studio.md` has the sizes.)
- **Height with meaning:** low for power and scale, level for connection, high for pattern and isolation. Default to
  near level, no more than ~20–25° down, with the horizon in frame. A steep top-down is a short, deliberate beat.
- **Let the subject travel through the frame.** It enters, crosses, leaves and comes back. It spends under ~60% of a
  move in the middle third.
- **Reveal structure:** start tight or blocked and open up, or start wide and push into the one thing that matters.
  Put the reveal on the beat.
- **Speed is musical:** a move starts and lands on beats, speeds up into accents, and slows (never stops) through
  held notes. One speed curve per move: one rise, one fall, no lurch. Not every hit needs a move: a camera that
  snaps to everything is as bad as one that never lands.
- **Never dead:** a hold is a slow drift with a direction, or a held framing that breathes; with jolts (the video's
  answer is yes), a held framing can take a slight shake on the beat. Dead-still holds are for one or two emphasis
  beats per section.
- **Overlap the moves:** the next move eases in under the last one, never stop-start. The direction of travel turns
  gradually (~10° a frame at most while moving).
- **Monotone and decisive:** each parameter of a move (heading, distance, height, aim) changes one way. No swinging
  past a framing and back, and no camera anticipation or overshoot. Turn look directions (slerp); never lerp a
  look-at point.
- **Following shots move continuously:** a camera following something never drops to zero speed between moves.
- **The shot comes first.** Overlay subtitles (`LyricLayer`) are placed into the shot afterwards: nothing about an
  overlay word may move, hold, slow, aim or shorten the camera. A word drawn into the world (a sign, `<Text3D>`) is
  a subject like any other, and a move can land on it (`studio.md`).
- **Balance the film:** quiet stretches and energetic ones, a spread of shot sizes, mostly near level. A draft that
  never settled was sent back, and so was the next one, which snapped to everything. The measured balance of three
  finished films is in `shot-balance.md`.
- **Jolts are the video's choice.** With the jolts answer yes, the camera can kick on the kick drum (a small push
  toward the subject and a quick roll-and-nudge, dying within about a fifth of a second, on top of the keyed move;
  softer on a held framing that has to be read). With no (the default), the camera never kicks or shakes on the
  beat; the music drives where moves start and land instead.

## Scene changes

Our scene changes are the transition board (`cuts.ts`, `storyboard.md`): every cut has a carrier, a reason and a
transition from the catalogue, and the screen never goes blank. These rules choose the carrier and the transition
when the camera is the carrier, and govern cuts inside a scene.

- **One continuous camera inside a scene by default.** A sequence described as a list of views ("over the right
  shoulder, then the left, then the TV") is one move travelling between them, not cuts.
- **A shot change inside a scene is a fast continuous move:** a whip, an arc or a pull-out, with motion blur in the
  final (`blur`).
- **A world change pushes into a shape.** Push in on a shape in the first world (a circle, a window, the moon, a
  letter's counter). The next world appears inside it while the push continues, and the shape grows past the
  frame's edges, so we arrive still moving. On the board, that is a cut whose carrier is the camera and the shape,
  with `iris` or `portal-zoom` from the catalogue fitted to it; a plain dissolve reads as an editing shortcut.
- **Going through an object** (a screen, a phone, a wall): travel through real geometry along a real path, and show
  the new place the moment the camera is inside. Never cover the swap with a white flash, a fade or a frame filled
  by a flat icon.
- **A hard cut (`ease: 'cut'` on a camera key, or a cut with no transition) only when the user asks for one, or
  once the camera has pushed into something until it fills the frame.** Never jump cut inside a busy frame. At a
  cut behind a full-frame push, nothing in frame may change: the subject and its background exist in both worlds,
  every character keeps its pose, facing and gaze, and the two frames either side of the cut match. Put the cut
  before a whip starts, not inside it. A designed hard cut inside a scene is passed to `qc` as `--cut <song s>`,
  so its hard-cut scan accepts it.

## Framing (waypoints)

Write one line per item for every waypoint: the beat it serves; the subject and its size; its place (which third,
which side); the angle (height, how far down or up, which side of the subject); the lens; foreground, midground
and background; what's at the edges.

- **Sizes, measured:** ECU, the detail fills 60%+ of the width. CU, the head is ⅓–½ of the height. MCU, chest up.
  MS, waist up. WS, the whole body at ⅓–½ of the height. EWS, the subject under ~10% of the height. Consecutive
  waypoints differ by at least one size, or by 45°+ of angle.
- **Place:** eyes on the upper-third line; the subject on a vertical third, facing or moving into the bigger space
  (lead room of a third of the frame or more). Centre only for deliberate symmetry.
- **Three layers:** at least two of foreground, subject and background; ideally all three. The foreground is soft
  and partly cropped by the edge, and can frame the subject.
- **Lines lead to the subject:** roads, railings, rows of people, walls, light beams. Diagonals over horizontals.
- **Balanced:** weigh the 3×3 grid and make the negative space deliberate. The opening frame and every landing are
  judged as still photographs.
- **Clean edges:** nothing important within 5% of an edge unless it's crossing in or out; no tangents; people
  cropped between joints, not at them. Characters stay whole in both 16:9 and 9:16 (`checks.md`, framing).
- **Separation:** the subject reads against what's behind it by value or colour. Look for merges (a dark head
  against a dark area).
- **Level horizon:** roll 0 unless it's a flying move banking into a turn.
- **One-glance story:** at 360 px wide, the frame says the idea without any words. If it doesn't, the frame is
  wrong.

**The user's words, as numbers:**

| They say | You build |
|---|---|
| "at the edge" | the subject at 0.9 of the frame width or more |
| "close-up" | the head ⅓–½ of the frame's height |
| "ECU" | the detail 60%+ of the frame's width, never just "closer" |
| "framed by A and B" | the subject in the notch between A and B in screen space, with small gaps (measure them) |
| "wide angle" | ~60°+ vertical, close to the action |
| "in frame" | seen: rays from the lens reach 50%+ of the subject, not just its centre |

## Failure modes

- **Approving camera work from a few stills.** Quick 3–8-frame contact sheets passed a flying object stopping in
  mid-air, a snap onto the subject and a 687°/s whip. Step every frame of the changed shot.
- **Answering the user's read of the picture with a metric.** A number that disagrees with what they see is a
  broken metric until frames prove otherwise.
- **Re-staging approved shots while fixing one.** A camera round changes only the frames the note names. Before
  rendering, compare every approved beat against the last approved version at the same song times (the review
  page lines them up).
- **Sparse keys on an orbit** stall where a coordinate turns round. Key along a computed path (every couple of
  frames), or interpolate in angle.
- **A spline key edit leaks into its neighbours' timing.** Pin the neighbours' rates and diff the old path against
  the new.
- **The subject lost in its surroundings:** never let a crowd or prop share the subject's colour around it.

## Verify

Run these over the whole scene, not just the changed shot, every round:

- **Smoothness, from the camera function per frame:** turn rate 90°/s or less; turn change 250°/s² or less; speed
  change 12 m/s² or less (4 for slow moves); travel direction 300°/s or less; no reversal in any parameter. Faster
  only on a deliberate whip, with blur. At large scales, measure pace (speed ÷ view depth): 4/s or less, changing
  12/s² or less.
- **Image speed:** project points at the subject's distance into the next frame. Keep it under ~120 px a frame at
  1080p, except designed whips.
- **Size and place** of the subject at each waypoint, against its spec.
- **Seen:** 50%+ of the subject reached by rays from the lens on every frame it should be in.
- **Clearances:** no pass nearer the lens than ~0.3 m unless designed, and the camera's path clear of the set.
- **Balance:** the section's still share, landings and sizes against `shot-balance.md`.
- **The render:** `qc`'s hard-cut and jitter scans (a camera that wanders and comes back) pass, or each flag is
  a designed cut (`--cut`) or, with jolts, a designed kick.

A turn-rate probe can be a few lines over any pure camera function (a scratch file next to the scene, run once):

```ts
// Flag frames where the camera turns faster than 90°/s (30 fps). cameraAt(f) returns { quaternion }.
for (let f = start; f < end; f++) {
  const degPerSec = THREE.MathUtils.radToDeg(cameraAt(f).quaternion.angleTo(cameraAt(f + 1).quaternion)) * 30;
  if (degPerSec > 90) console.log(`f${f}: turning ${degPerSec.toFixed(0)}°/s`);
}
```
