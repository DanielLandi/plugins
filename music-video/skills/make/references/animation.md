> Adapted from `animation-principles` in Imaginative-Prompting/claude-video-skills (MIT, © 2026 Imaginative
> Prompting); see the plugin's `THIRD_PARTY_NOTICES.md`.

# Animation principles

Read before any scene code, with `studio.md`. Anything that moves follows it: characters, props, type, effects. The
camera has its own rules on top of these. Characters with a style of their own (a cartoon, a liquid, a realistic
person) can get their own notes in the video's `LOOK.md`.

## 1. Every frame is a pure function of time

Remotion renders frames out of order, in parallel tabs, and a render chunk (or a motion-blur sub-frame) can start
anywhere. A frame can never depend on the frame rendered before it.

- **Physical state is re-simulated, not remembered.** Springs, lag and follow-through are re-run from t = 0 on a
  fixed step (1/120 s works), or baked once per scene into an array and sampled. Remotion's `spring()` is already a
  function of the frame.
- **Noise is seeded.** Never `Math.random()` at render time: `random('seed')` from `remotion`, or noise keyed on
  song time.
- **Timing lives in one place:** the song clock (`useSongTime()`, in seconds) and the scene's own constants, never
  a shader's hidden clock.
- **Speed is a parameter.** Every action takes one `speed` number that scales all its phases, so it can be retimed
  after a note without being rebuilt.

```ts
// Follow-through that is still a pure function of time: re-simulate from t = 0 on a fixed step,
// then a partial step to t itself, so motion-blur sub-frames move smoothly.
// (Bake the whole steps to an array once per scene if it gets slow.)
function springAt(t: number, target: (t: number) => number, k = 120, c = 14, dt = 1 / 120) {
  let x = target(0), v = 0;
  const step = (s: number, h: number) => {
    v += (k * (target(s) - x) - c * v) * h;
    x += v * h;
  };
  const n = Math.floor(t / dt);
  for (let i = 0; i < n; i++) step(i * dt, dt);
  step(n * dt, t - n * dt);
  return x;
}
```

## 2. The grammar of a move

Every deliberate move is **hold → anticipation → action → overshoot → settle**.

| Phase | What it does | A cartoon or elastic character | A realistic person (toned down) |
|---|---|---|---|
| Hold | the pose reads | 6–8 frames or more on any key pose | longer: 10–15 frames or more |
| Anticipation | the opposite way first, scaled to the move | ~0.2 s, ease-out | 0.25–0.5 s; often a breath in |
| Action | the move itself | ~0.15 s, a sharp ease-out (a snap) | 0.25–0.6 s; minimum-jerk for reaches |
| Overshoot | past the mark | a few cm, ~30% squash | 5% or less, in rotation, not position |
| Settle | back to rest | ~0.45 s damped spring, no jolt at the start | 0.5–0.9 s, heavier damping |

- **Nothing alive moves linearly.** Linear motion is for machines doing machine things (a conveyor, a progress bar).
- **Eases match the physics.** Something pushed starts fast (ease-out). Something falling or giving up starts slow
  and speeds up (ease-in). An impact is never eased into a stop (section 6).
- **Settles start with no jolt:** a damped curve with zero slope where it starts, or a real spring stepped from rest.

```ts
// 0 → 1 with a damped overshoot and zero slope at u = 0, so the settle never jolts as it begins.
const settle = (u: number, k = 6, w = 14) =>
  1 - Math.exp(-k * u) * (Math.cos(w * u) + (k / w) * Math.sin(w * u));
```

## 3. Arcs, overlap, follow-through

- **Moves travel on arcs,** not straight lines. Dashes lift.
- **A body moves as a chain, not a block.** The root leads, then the spine, then the head and limbs, each a few
  frames later.
- **Loose parts lag and follow through** on springs: hair, a hat's cuff, a hoodie's strings, fingers, cloth.
- **Momentum carries across segments.** A path's velocity is continuous where segments meet. No stop-go between
  waypoints unless the stop is the point.
- **Turns rotate the aim** (slerp), never lerp a look-at point toward a far target.

## 4. Every action moves the material it acts on

Moving a whole object along a path while its contents stay rigid looks fake. A ball of yarn that changes direction
in the air trails its loose strands; it doesn't move as one solid lump.

- **Show cause, propagation and consequence.** A force acts somewhere, travels through connected material, and
  leaves follow-through. A local hit doesn't make every part react at once and identically.
- **Travel changes the body.** Acceleration leaves loose material trailing, a turn carries it outward, braking lets
  it overtake, gather and recoil.
- **Internal actions are forces too:** a pulse, a gesture or a shape change pulls on neighbouring material.
- **Carry the result forward.** Keep displaced state and momentum into the next action. Don't reset the material
  after every hit.
- **Idle wobble isn't a reaction.** Decorative sine waves and noise don't stand in for a response driven by the
  actual movement. Change the stimulus's direction or strength and the deformation must change with it.
- **Material-specific:** rigid, elastic, liquid and particle bodies respond differently. Unaffected objects can
  stay still. The rule is causal response, not everything wobbling.
- **Something driven by the music reacts to the music:** its main accent lands on the beat (anticipation may come
  before), not a slow animation that starts on the beat and peaks late. How hard it reacts follows the video's
  **jolts** answer (`LOOK.md`, `look.ts`): with no jolts (the default), beat reactions are eased (a nod, a sway, a
  glow, a breath); a kick or a shake on the drum hits only when the answer is yes.

## 5. Alive is never static

- **Breathing:** a slow rise and fall of the chest and shoulders, with the head riding it. About 4–5 s a breath at
  rest, faster after effort, held in anticipation, let out in release.
- **Per-limb idle:** each limb drifts on its own low-amplitude noise (1–2° for a person), out of phase with the
  others. Fingers relax and curl. Weight shifts every few seconds when standing.
- **Attention:** something is always looking at something, with the eyes, or with the head and the body's lean.
- **Check it over time,** not from one still: a 6 s loop of a character at rest must look alive.

## 6. Weight, gravity, impacts

- **Gravity accelerates.** A fall is ease-in or a real ballistic arc, never a slow even slide downward. Falling
  letters split apart and drop fast.
- **An impact has a contact frame.** Speed is highest at contact, then compression (a squash, or a person's joints
  giving), a damped rebound, and a settle.
- **The first part to land stops first;** the parts behind it land after, in order (forearms, then the head).
- **Weight shows in timing.** Heavy things start slow and stop hard. Light things react fast and float a beat.
- **What it touches reacts:** a chair rolls back, keys go down under fingers, a cushion gives, a car's body leans
  out of a turn and dips its nose when it brakes.

## 7. Nothing pops in

- **Every entrance animates** over 6–12 frames (anticipation, an eased action, overshoot, settle), letter by letter
  for type where it fits. Nothing goes from absent to whole in one frame.
- **An entrance starts on its cue, never before.** Something keyed to a sung word starts on the word's start in
  `timing.json` (with `onsets: true`, its first sound) and becomes readable as it animates in. A breath or wind-up
  before the cue can drive anticipation that isn't readable yet.
- **Hiding isn't the same as absent.** Something waiting edge-on and flipping round in the last half frame is still
  a pop, and an unlit sign's dark letters still read before they light. Things exist from their cue.
- **Grow out, never through.** Letters or buildings that push out of a wall or rise out of the street are drawn only
  once their nearest face is clear of the surface (about 3 cm close up, about 0.4 m at city distances). Scaling a
  depth up from 0 while visible z-fights and flickers.
- **Exits leave the frame or animate out.** Anything that vanishes between two frames is a pop until you've shown
  it leaving the frame's edge.

## 8. Smears and motion blur

- **Cartoon things smear:** on a fast frame, stretch the shape back along its real path over the last ~0.07 s,
  tapered and fading, gated by speed so slow moves never smear.
- **Realistic people don't smear;** their fast moves get motion blur.
- **The camera and fast objects get real motion blur** in finals: the `blur` command (step 7.5 of the make skill),
  a 180° shutter from several samples per frame.

## 9. Contacts

- **Every moving part's sweep is clear** of the props round it, on every frame. Probe it, don't eyeball it.
- **Hands land on what they work:** real keys, the mouse, the desk. Planted feet don't slide.
- **Nothing passes through** a desk, a body or a screen unless the design says so.
- **Things written or placed in the world stay fixed** to what they're on.

## Failure modes

- **Approving motion from stills.** Pops, stops and strobing only show in consecutive frames.
- **Every-Nth-frame sheets** (the `qc` overview sheet included) hide strobing and one-frame pops.
- **Relaying "no pops" from a scene agent** without looking at the frames yourself.
- **Decorative noise in place of a reaction,** or a reaction to the beat too weak to see at the delivered camera
  distance.
- **A rework that drops the point:** new notes add to the existing beats; they don't replace them.

## Verify

1. `typecheck <id>`, and stills at the scene's start, middle and peak.
2. Probe the camera's framing and image speed (`shot-design.md`).
3. Render a clip of the section, `mux` and `qc` it.
4. Read `qc`'s pop and flicker lines: each flagged frame is either a designed snap or a bug. Look at every one.
5. Step through consecutive frames (the sections page steps frame by frame) around every flag, contact, entrance,
   impact and repeat.
6. Full-resolution stills of contacts, hands, eyes and type.
7. Watch it at 1× as a loop.
8. For a reaction, compare with the stimulus turned off: the difference must be the response, not idle motion.
