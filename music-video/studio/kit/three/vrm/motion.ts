// Pure, deterministic motion for characters: every value is a function of time in seconds (adapted from the
// three-vrm research round). Names avoid the kit's own `clamp`, `pulse` (beats) and kit/three's `Ease` and `hash`.
import { clamp } from '../../time';

export type EaseFn = (t: number) => number;

export const eases = {
  linear: (t: number) => t,
  inOut: (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2),
  out: (t: number) => 1 - Math.pow(1 - t, 3),
  in: (t: number) => t * t * t,
  /** Overshoots a little, then settles: a pose that lands with weight. */
  outBack: (t: number) => {
    const c1 = 1.70158, c3 = c1 + 1;
    return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2);
  },
  outElastic: (t: number) =>
    t <= 0 ? 0 : t >= 1 ? 1 : Math.pow(2, -10 * t) * Math.sin((t * 10 - 0.75) * ((2 * Math.PI) / 3)) + 1,
  sine: (t: number) => -(Math.cos(Math.PI * t) - 1) / 2,
  /** Smootherstep (a quintic): flat speed and acceleration at both ends and no jump in acceleration anywhere. Use it
   * for continuous motion driven by acceleration (a lean, a bank, a drifting camera): inOut's acceleration jumps
   * from +12 to -12 at its midpoint, which a lean shows as a twitch. */
  smooth: (t: number) => t * t * t * (t * (6 * t - 15) + 10),
} satisfies Record<string, EaseFn>;

const lerp = (a: number, b: number, k: number) => a + (b - a) * k;

/** 0 → 1 between a and b, eased; clamped outside. */
export const ramp = (t: number, a: number, b: number, e: EaseFn = eases.inOut) => e(clamp((t - a) / (b - a)));

/** 0 before a, up to 1 by b, held to c, back to 0 by d. */
export const swell = (t: number, a: number, b: number, c: number, d: number, e: EaseFn = eases.inOut) =>
  t < c ? ramp(t, a, b, e) : 1 - ramp(t, c, d, e);

/** A keyframed number: [time, value, the ease into this key (inOut when left out)]. */
export type Key = [number, number, EaseFn?];

export const track = (t: number, keys: readonly Key[]): number => {
  if (t <= keys[0][0]) return keys[0][1];
  for (let i = 1; i < keys.length; i++) {
    const [t1, v1, e] = keys[i];
    if (t <= t1) {
      const [t0, v0] = keys[i - 1];
      return t1 === t0 ? v1 : lerp(v0, v1, (e ?? eases.inOut)((t - t0) / (t1 - t0)));
    }
  }
  return keys[keys.length - 1][1];
};

/** A seeded random stream (mulberry32): the same seed gives the same numbers on every render. */
export const seeded = (seed: number) => {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
};

// ---- poses: humanoid bone name → Euler [x, y, z] in radians, in three-vrm's normalized bone space ----
// Normalized space: T-pose, facing +z, the character's left is +x. A missing bone is at rest.
export type Euler3 = [number, number, number];
export type Pose = { [bone: string]: Euler3 };

const ZERO: Euler3 = [0, 0, 0];

export const mixPose = (a: Pose, b: Pose, w: number): Pose => {
  const out: Pose = {};
  for (const k of new Set([...Object.keys(a), ...Object.keys(b)])) {
    const pa = a[k] ?? ZERO, pb = b[k] ?? ZERO;
    out[k] = [lerp(pa[0], pb[0], w), lerp(pa[1], pb[1], w), lerp(pa[2], pb[2], w)];
  }
  return out;
};

/** A layer on top of a pose (breathing, a wave, a head turn), scaled by w. */
export const addPose = (a: Pose, b: Pose, w = 1): Pose => {
  const out: Pose = { ...a };
  for (const k of Object.keys(b)) {
    const pa = a[k] ?? ZERO, pb = b[k];
    out[k] = [pa[0] + pb[0] * w, pa[1] + pb[1] * w, pa[2] + pb[2] * w];
  }
  return out;
};

/** Keyframed poses: [time, pose, the ease into this key]. */
export type PoseKey = [number, Pose, EaseFn?];

export const poseTrack = (t: number, keys: readonly PoseKey[]): Pose => {
  if (t <= keys[0][0]) return keys[0][1];
  for (let i = 1; i < keys.length; i++) {
    const [t1, p1, e] = keys[i];
    if (t <= t1) {
      const [t0, p0] = keys[i - 1];
      return mixPose(p0, p1, t1 === t0 ? 1 : (e ?? eases.inOut)((t - t0) / (t1 - t0)));
    }
  }
  return keys[keys.length - 1][1];
};

/** The same pose on the other side (left ↔ right): x stays, y and z turn the other way. */
export const mirrorPose = (p: Pose): Pose => {
  const out: Pose = {};
  for (const [k, [x, y, z]] of Object.entries(p)) {
    const m = k.startsWith('left') ? `right${k.slice(4)}` : k.startsWith('right') ? `left${k.slice(5)}` : k;
    out[m] = [x, 0 - y, 0 - z];
  }
  return out;
};
