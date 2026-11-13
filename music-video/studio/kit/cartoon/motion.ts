// Pure, deterministic motion for cartoon characters: every value is a function of time in seconds. The keyframe
// helpers are the vrm engine's own (one way to key motion in both), plus cartoon timing: hops with squash and
// stretch, springs that overshoot, wobbles that die out, a lagging follower for hats and sprouts, and line boil.
import { clamp } from '../time';
import { eases, ramp, seeded, swell, track, type EaseFn, type Key } from '../three/vrm/motion';

export { eases, ramp, seeded, swell, track, type EaseFn, type Key };

export const lerp = (a: number, b: number, k: number) => a + (b - a) * k;

/**
 * A lagging follower of a signal: a damped spring chasing sig(t), replayed at a fixed step from `from` (the scene's
 * start) on every call, so any frame renders the same alone or in sequence. It starts at rest on sig(from).
 */
export const follow = (
  sig: (t: number) => number, t: number,
  { from = 0, freq = 3, zeta = 0.22, dt = 1 / 120 }: { from?: number; freq?: number; zeta?: number; dt?: number } = {},
): number => {
  const w = 2 * Math.PI * freq;
  let x = sig(from), v = 0;
  const n = Math.max(0, Math.round((t - from) / dt));
  for (let i = 1; i <= n; i++) {
    const a = w * w * (sig(from + i * dt) - x) - 2 * zeta * w * v;
    v += a * dt;
    x += v * dt;
  }
  return x;
};

/** A jump arc: 0 outside [t0, t1], a parabola peaking at h in between. */
export const hop = (t: number, t0: number, t1: number, h: number) => {
  if (t <= t0 || t >= t1) return 0;
  const u = (t - t0) / (t1 - t0);
  return 4 * h * u * (1 - u);
};

/** sy for a hop: an anticipation squash before t0, a stretch on take-off, a squash on landing at t1, springing back. */
export const hopSquash = (t: number, t0: number, t1: number, amt = 1): number => {
  let sy = 1;
  if (t > t0 - 0.16 && t <= t0) sy -= 0.22 * amt * Math.sin(((t - (t0 - 0.16)) / 0.16) * Math.PI * 0.5);
  if (t > t0 && t < t1) {
    const u = (t - t0) / (t1 - t0);
    sy += 0.28 * amt * (1 - u * 2) * (u < 0.5 ? 1 : 0.6);
  }
  if (t >= t1) {
    const x = t - t1;
    sy -= 0.3 * amt * Math.exp(-7 * x) * Math.cos(2 * Math.PI * 3.2 * x);
  }
  return sy;
};

/** sx that keeps the body's area about the same for a given sy (squash wide, stretch thin). */
export const vol = (sy: number) => Math.pow(1 / Math.sqrt(Math.max(0.2, sy)), 1.6);

/** A damped spring's answer to a step at t0: 0 before, overshoots, settles at 1. */
export const springStep = (t: number, t0: number, freq = 3.2, damp = 4.5) => {
  const x = t - t0;
  if (x <= 0) return 0;
  return 1 - Math.exp(-damp * x) * Math.cos(2 * Math.PI * freq * x);
};

/** A wobble after an event at t0: 0 before, then a ±1 oscillation that dies out. */
export const wobble = (t: number, t0: number, freq = 4, damp = 5) => {
  const x = t - t0;
  if (x <= 0) return 0;
  return Math.exp(-damp * x) * Math.sin(2 * Math.PI * freq * x);
};

/** A hash of a number into [0, 1). */
export const hash = (n: number) => {
  const s = Math.sin(n * 127.1 + 311.7) * 43758.5453;
  return s - Math.floor(s);
};

/** Smooth 1D value noise in [-1, 1]. */
export const noise1 = (x: number, seed = 0) => {
  const i = Math.floor(x), f = x - i;
  const a = hash(i + seed * 57.3) * 2 - 1, b = hash(i + 1 + seed * 57.3) * 2 - 1;
  const u = f * f * (3 - 2 * f);
  return a + (b - a) * u;
};

/** The line-boil seed: it changes every `hold` frames (drawn on twos by default), like redrawn cels. */
/**
 * The output frame (at `base` fps) a rendered frame belongs to. In a sharp render it is the frame itself; in a `blur`
 * render (fps = base × sub-frames) every sub-frame inside a frame's shutter maps to that frame, so frame-keyed
 * drawing (the boil, effects) holds still within one blurred frame instead of ghosting (#35).
 */
export const outputFrame = (frame: number, fps: number, base = 30) => Math.round((frame * base) / fps);

export const boilSeed = (frame: number, hold = 2, base = 1) => base * 1000 + Math.floor(frame / hold);

export { clamp };
