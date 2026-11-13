// Path helpers for the cartoon engine: smooth curves through points, hand-drawn jitter and simple point sets.
// Adapted from the cartoon research round's brush-ink rig.
import { seeded } from './motion';

/** A point in the composition's pixels. */
export type P = [number, number];

/** The ink colour: a warm near-black, like brush ink on paper. */
export const INK = '#2a1d1a';

/** A Catmull-Rom spline through points as an SVG path (closed or open). */
export const smooth = (pts: readonly P[], closed = true, tension = 1): string => {
  const n = pts.length;
  if (n < 2) return '';
  const at = (i: number) => (closed ? pts[(i + n) % n] : pts[Math.max(0, Math.min(n - 1, i))]);
  let d = `M ${pts[0][0].toFixed(1)} ${pts[0][1].toFixed(1)}`;
  const last = closed ? n : n - 1;
  const k = tension / 6;
  for (let i = 0; i < last; i++) {
    const p0 = at(i - 1), p1 = at(i), p2 = at(i + 1), p3 = at(i + 2);
    const c1: P = [p1[0] + (p2[0] - p0[0]) * k, p1[1] + (p2[1] - p0[1]) * k];
    const c2: P = [p2[0] - (p3[0] - p1[0]) * k, p2[1] - (p3[1] - p1[1]) * k];
    d += ` C ${c1[0].toFixed(1)} ${c1[1].toFixed(1)} ${c2[0].toFixed(1)} ${c2[1].toFixed(1)} ${p2[0].toFixed(1)} ${p2[1].toFixed(1)}`;
  }
  return closed ? d + ' Z' : d;
};

/** Each point moved by a seeded random offset of up to `amp` px: the redrawn-by-hand shimmer ("boil"). */
export const jitter = (pts: readonly P[], seed: number, amp: number): P[] => {
  if (amp === 0) return pts.slice();
  const r = seeded(seed);
  return pts.map(([x, y]) => [x + (r() * 2 - 1) * amp, y + (r() * 2 - 1) * amp]);
};

/** n points on an ellipse, starting at angle `rot`. */
export const ellipsePts = (cx: number, cy: number, rx: number, ry: number, n = 16, rot = 0): P[] =>
  Array.from({ length: n }, (_, i) => {
    const a = (i / n) * Math.PI * 2 + rot;
    return [cx + Math.cos(a) * rx, cy + Math.sin(a) * ry];
  });

/** A star polygon (five points by default). */
export const starPts = (cx: number, cy: number, r: number, inner = 0.45, rot = -Math.PI / 2, n = 5): P[] =>
  Array.from({ length: n * 2 }, (_, i) => {
    const a = rot + (i * Math.PI) / n;
    const rr = i % 2 ? r * inner : r;
    return [cx + Math.cos(a) * rr, cy + Math.sin(a) * rr];
  });

/** A cubic Bézier sampled into n + 1 points. */
export const cubicPts = (p0: P, p1: P, p2: P, p3: P, n = 24): P[] =>
  Array.from({ length: n + 1 }, (_, i) => {
    const t = i / n, u = 1 - t;
    const a = u * u * u, b = 3 * u * u * t, c = 3 * u * t * t, d = t * t * t;
    return [a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]];
  });

export const add = (a: P, b: P): P => [a[0] + b[0], a[1] + b[1]];
/** `q` turned by angle a about the point o. */
export const rot = ([x, y]: P, a: number, o: P = [0, 0]): P =>
  [o[0] + x * Math.cos(a) - y * Math.sin(a), o[1] + x * Math.sin(a) + y * Math.cos(a)];
