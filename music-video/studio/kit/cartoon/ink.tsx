// The cartoon engine's renderer: every outline is a variable-width brush stroke from perfect-freehand (MIT), and the
// points are re-jittered with a seed that changes every few frames, so the lines boil like hand-redrawn cels.
// Adapted from the cartoon research round's brush-ink rig.
import getStroke from 'perfect-freehand';
import React from 'react';
import { INK, jitter, smooth, type P } from './draw';
import { noise1 } from './motion';
import type { Shape } from './rig';

/** A perfect-freehand outline polygon → a smooth closed SVG path (quadratic curves through the midpoints). */
export const strokePath = (outline: number[][]): string => {
  if (outline.length < 3) return '';
  let d = `M ${outline[0][0].toFixed(1)} ${outline[0][1].toFixed(1)} Q`;
  for (let i = 0; i < outline.length; i++) {
    const [x0, y0] = outline[i];
    const [x1, y1] = outline[(i + 1) % outline.length];
    d += ` ${x0.toFixed(1)} ${y0.toFixed(1)} ${((x0 + x1) / 2).toFixed(1)} ${((y0 + y1) / 2).toFixed(1)}`;
  }
  return d + ' Z';
};

/** A polyline resampled to about `step` px between points (perfect-freehand wants dense input). */
const resample = (pts: readonly P[], step: number, closed: boolean): P[] => {
  const src = closed ? [...pts, pts[0]] : pts;
  const out: P[] = [src[0]];
  let carry = 0;
  for (let i = 1; i < src.length; i++) {
    const [ax, ay] = src[i - 1], [bx, by] = src[i];
    const L = Math.hypot(bx - ax, by - ay);
    if (L === 0) continue;
    let d = step - carry;
    while (d <= L) {
      out.push([ax + ((bx - ax) * d) / L, ay + ((by - ay) * d) / L]);
      d += step;
    }
    carry = L - (d - step);
  }
  if (!closed) out.push(src[src.length - 1]);
  return out;
};

/** A closed ring smoothed with a Catmull-Rom spline, `per` samples per segment. */
const splineRing = (pts: readonly P[], per = 4): P[] => {
  const n = pts.length, out: P[] = [];
  for (let i = 0; i < n; i++) {
    const p0 = pts[(i - 1 + n) % n], p1 = pts[i], p2 = pts[(i + 1) % n], p3 = pts[(i + 2) % n];
    for (let s = 0; s < per; s++) {
      const t = s / per, t2 = t * t, t3 = t2 * t;
      const c = (k: 0 | 1) => 0.5 * (2 * p1[k] + (-p0[k] + p2[k]) * t + (2 * p0[k] - 5 * p1[k] + 4 * p2[k] - p3[k]) * t2
        + (-p0[k] + 3 * p1[k] - 3 * p2[k] + p3[k]) * t3);
      out.push([c(0), c(1)]);
    }
  }
  return out;
};

/** Few-point lines (brows, closed-eye arcs) → a smooth curve: a quadratic through the middle point. */
const densify = (pts: readonly P[]): P[] => {
  if (pts.length >= 4) return pts.slice();
  if (pts.length === 2) return [pts[0], [(pts[0][0] + pts[1][0]) / 2, (pts[0][1] + pts[1][1]) / 2], pts[1]];
  const [a, b, c] = pts;
  const cx = 2 * b[0] - (a[0] + c[0]) / 2, cy = 2 * b[1] - (a[1] + c[1]) / 2;
  return Array.from({ length: 13 }, (_, i): P => {
    const t = i / 12, u = 1 - t;
    return [u * u * a[0] + 2 * u * t * cx + t * t * c[0], u * u * a[1] + 2 * u * t * cy + t * t * c[1]];
  });
};

/**
 * A brush stroke along points, as a filled SVG path: `size` is the brush width in px, pressure wanders with the seed.
 * Use it for set pieces (a railing, a skyline) so they are inked like the characters.
 */
export const inkPath = (pts: readonly P[], seed: number, size: number, closed: boolean, thinning = 0.55, taper = 0): string => {
  const dense = resample(closed ? splineRing(pts) : densify(pts), 6, closed);
  const withP = dense.map(([x, y], i) => [x, y, 0.55 + 0.4 * noise1(i * 0.09, seed)]);
  if (closed && withP.length > 1) withP.push(withP[0], withP[1]);
  return strokePath(getStroke(withP, {
    size, thinning, smoothing: 0.6, streamline: 0.2, simulatePressure: false, last: true,
    start: { cap: true, taper }, end: { cap: true, taper },
  }));
};

const hose = (pts: P[], size: number) =>
  strokePath(getStroke(resample(pts, 5, false), { size, thinning: 0, smoothing: 0.7, streamline: 0.1, simulatePressure: false, last: true }));

/** The rig's shapes drawn in brush ink. `seed` boils the lines (change it every few frames); `boil` is how far, in px. */
export const InkShapes: React.FC<{ shapes: Shape[]; seed: number; boil?: number; ink?: string }> = ({ shapes, seed, boil = 1.3, ink = INK }) => (
  <g>
    {shapes.map((s, i) => {
      const sd = seed * 31 + i * 7;
      if (s.k === 'dot') return <circle key={i} cx={s.x} cy={s.y} r={s.r} fill={s.fill} />;
      if (s.k === 'blob') {
        const pts = jitter(s.pts, sd, s.layer ? 0 : boil * 0.6);
        return (
          <g key={i}>
            {s.fill !== 'none' && <path d={smooth(pts)} fill={s.fill} opacity={s.layer === 'hi' ? 0.8 : 1} />}
            {s.ink ? <path d={inkPath(jitter(s.pts, sd + 1, boil), sd, s.ink, true)} fill={ink} /> : null}
          </g>
        );
      }
      if (s.k === 'limb') {
        const pts = jitter(s.pts, sd, boil * 0.5);
        return (
          <g key={i}>
            <path d={hose(pts, s.w + s.ink * 2)} fill={ink} />
            <path d={hose(pts, s.w)} fill={s.fill} />
          </g>
        );
      }
      return <path key={i} d={inkPath(jitter(densify(s.pts), sd, boil * 0.6), sd, s.w, false, 0.6, 30)} fill={s.color ?? ink} />;
    })}
  </g>
);
