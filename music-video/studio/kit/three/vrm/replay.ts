// Deterministic physics for any frame: spring bones (hair, skirts, ribbons) depend on their whole history, so a
// frame rendered on its own (a still, a seek, one of several render tabs) replays the history from frame 0 at a
// fixed time step, and a sequential render steps one frame on. Both give the same numbers. (The research round
// measured a seeked frame against a sequential render at PSNR 81.7 dB.)

/** Something that can be posed, stepped and put back at rest: a VRM's spring bones, or a test spring. */
export type Replayable<S> = {
  /** Pose it for this moment (bones, position, gravity on the springs…). */
  apply(state: S): void;
  /** Advance its physics by dt seconds. */
  step(dt: number): void;
  /** Back to rest: no velocity, no history. */
  reset(): void;
};

/** Which frame the thing was last brought to (-1: never). Keep one per instance. */
export type ReplayState = { frame: number };

/**
 * The time drive() sees at step s (1..sub) of replay frame f, for a replay whose frame 0 is frame `origin` of the
 * song: (origin + f - 1 + s / sub) / fps, counted in whole sub-steps so that the last step of a frame is exactly
 * (origin + f) / fps, the kit's clock (useSongTime = frame / fps) at that frame.
 */
export const replayTime = (origin: number, f: number, s: number, sub: number, fps: number): number =>
  ((origin + f - 1) * sub + s) / (fps * sub);

/**
 * Bring `r` to `frame` (counted from `origin`, the song frame where its physics starts): from rest it first settles
 * for `settle` seconds under drive at the origin (hair falls into place), then steps every frame up to this one, `sub`
 * steps per frame, with drive given song time (replayTime). A later frame continues from where it was (render tabs
 * take every few frames); an earlier one replays from rest.
 */
export const replayTo = <S,>(r: Replayable<S>, mem: ReplayState, drive: (t: number) => S, frame: number, fps: number,
  sub = 4, settle = 1, origin = 0): void => {
  if (frame === mem.frame) return;
  const dt = 1 / fps / sub;
  const stepFrame = (f: number) => {
    for (let s = 1; s <= sub; s++) {
      r.apply(drive(replayTime(origin, f, s, sub, fps)));
      r.step(dt);
    }
  };
  let f = mem.frame + 1;
  if (mem.frame < 0 || frame < mem.frame) {
    const still = drive(replayTime(origin, 0, sub, sub, fps));
    r.apply(still);
    r.reset();
    for (let i = 0; i < Math.round(settle * fps * sub); i++) {
      r.apply(still);
      r.step(dt);
    }
    f = 1;
  }
  // Onwards from where it is: the same steps a full replay would take, so the result is the same either way.
  for (; f <= frame; f++) stepFrame(f);
  mem.frame = frame;
};
