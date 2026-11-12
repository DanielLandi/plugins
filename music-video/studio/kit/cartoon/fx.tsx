// Cartoon effects (SVG, inside the scene's <svg>), each a pure function of time t (seconds) and the frame (for line
// boil): contact shadows, an impact burst, dust, take lines, speed lines, emotes, a white flash, dizzy stars, a
// camera shake and a push-in. Adapted from the cartoon research round.
import React from 'react';
import { AbsoluteFill } from 'remotion';
import { INK, ellipsePts, jitter, smooth, starPts, type P } from './draw';
import { clamp, eases, ramp, seeded } from './motion';

const boilAt = (frame: number, k: number) => Math.floor(frame / 3) * 13 + k * 101;

/** A soft oval contact shadow under a character; it shrinks as the character rises (`lift` px). */
export const Shadow: React.FC<{ x: number; y: number; w: number; lift?: number }> = ({ x, y, w, lift = 0 }) => {
  const k = clamp(1 - lift / 400, 0.3, 1);
  return <ellipse cx={x} cy={y} rx={w * k} ry={w * 0.16 * k} fill={INK} opacity={0.22 * k} />;
};

/** Stars circling a dazed head between t0 and t1. */
export const StarRing: React.FC<{ t: number; frame: number; t0: number; t1: number; cx: number; cy: number; rx?: number; ry?: number; n?: number }> = ({
  t, frame, t0, t1, cx, cy, rx = 120, ry = 34, n = 4,
}) => {
  if (t < t0 || t > t1) return null;
  const grow = ramp(t, t0, t0 + 0.25, eases.outBack) * (1 - ramp(t, t1 - 0.25, t1));
  const items = Array.from({ length: n }, (_, i) => {
    const a = (i / n) * Math.PI * 2 + (t - t0) * 5.2;
    const z = Math.sin(a);
    return { i, x: cx + Math.cos(a) * rx, y: cy + z * ry, s: (0.75 + 0.35 * z) * grow, z };
  }).sort((a, b) => a.z - b.z);
  return (
    <g>
      <path d={smooth(ellipsePts(cx, cy, rx, ry, 18))} fill="none" stroke="#ffffff" strokeWidth={4} strokeDasharray="10 18" opacity={0.7 * grow} />
      {items.map(({ i, x, y, s }) => (
        <path key={i} d={smooth(jitter(starPts(x, y, 28 * s, 0.46, -Math.PI / 2 + i), boilAt(frame, 40 + i), 1.2), true, 0.25)}
          fill={i % 2 ? '#ffe14d' : '#fff3a6'} stroke={INK} strokeWidth={4.5} strokeLinejoin="round" />
      ))}
    </g>
  );
};

/** An impact at t0: a jagged burst that pops for about 0.35 s, strokes radiating out. */
export const ImpactBurst: React.FC<{ t: number; t0: number; x: number; y: number; r?: number; color?: string }> = ({ t, t0, x, y, r = 150, color = '#ffd23f' }) => {
  const dt = t - t0;
  if (dt < 0 || dt > 0.6) return null;
  // a two-frame pop, a shimmer, then a steady shrink to nothing (no frame where it simply vanishes)
  const s = dt < 0.07 ? 1.25 : dt < 0.3 ? 1 + 0.05 * Math.sin(dt * 60) : (1 + 0.05 * Math.sin(0.3 * 60)) * (1 - ramp(dt, 0.3, 0.6, eases.linear));
  const rr = seeded(Math.floor(t0 * 100));
  const spikes: P[] = Array.from({ length: 22 }, (_, i) => {
    const a = (i / 22) * Math.PI * 2;
    const k = i % 2 ? 0.5 + rr() * 0.12 : 0.9 + rr() * 0.35;
    return [x + Math.cos(a) * r * k * s, y + Math.sin(a) * r * k * s];
  });
  const inner = spikes.map(([px, py]): P => [x + (px - x) * 0.55, y + (py - y) * 0.55]);
  const poly = (pts: P[]) => `M ${pts.map((p) => `${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(' L ')} Z`;
  return (
    <g>
      {s > 0.01 && <path d={poly(spikes)} fill="#ffffff" stroke={INK} strokeWidth={7 * Math.min(1, s * 3)} strokeLinejoin="round" />}
      {s > 0.01 && <path d={poly(inner)} fill={color} />}
      {Array.from({ length: 10 }, (_, i) => {
        const a = (i / 10) * Math.PI * 2 + 0.2;
        const d0 = r * (1.05 + dt * 2.2), d1 = d0 + r * 0.45 * (1 - ramp(dt, 0.2, 0.6));
        const width = Math.min(8, (d1 - d0) / 3); // a shortening stroke thins out instead of leaving a dot
        if (width < 0.3) return null;
        return <path key={i} d={`M ${x + Math.cos(a) * d0} ${y + Math.sin(a) * d0} L ${x + Math.cos(a) * d1} ${y + Math.sin(a) * d1}`}
          stroke={INK} strokeWidth={width} strokeLinecap="round" />;
      })}
    </g>
  );
};

/** Dust puffs kicked out from a landing or a skid at t0 (dir: 0 both ways, ±1 one way), fading out. */
export const DustPuffs: React.FC<{ t: number; frame: number; t0: number; x: number; y: number; n?: number; spread?: number; dir?: -1 | 0 | 1 }> = ({
  t, frame, t0, x, y, n = 6, spread = 220, dir = 0,
}) => {
  const dt = t - t0;
  if (dt < 0 || dt > 0.9) return null;
  const r = seeded(Math.floor(t0 * 37) + 3);
  return (
    <g>
      {Array.from({ length: n }, (_, i) => {
        const side = dir === 0 ? (i % 2 ? 1 : -1) : dir;
        const v = 0.5 + r() * 0.7;
        const k = eases.out(clamp(dt / 0.9));
        const px = x + side * spread * v * k, py = y - 30 * k - r() * 20 * k;
        const rad = (22 + r() * 22) * (0.5 + k) * (1 - ramp(dt, 0.55, 0.9) * 0.9);
        return <path key={i} d={smooth(jitter(ellipsePts(px, py, rad, rad * 0.8, 9), boilAt(frame, 60 + i), 1.5))}
          fill="#fff6e0" stroke={INK} strokeWidth={4} opacity={1 - ramp(dt, 0.6, 0.9)} />;
      })}
    </g>
  );
};

/** Surprise "take" lines: short strokes popping out above a head at t0, then fading. */
export const TakeLines: React.FC<{ t: number; t0: number; x: number; y: number; r?: number }> = ({ t, t0, x, y, r = 150 }) => {
  const dt = t - t0;
  if (dt < 0 || dt > 0.7) return null;
  const k = eases.outBack(clamp(dt / 0.15));
  return (
    <g opacity={1 - ramp(dt, 0.45, 0.7)}>
      {Array.from({ length: 7 }, (_, i) => {
        const a = -Math.PI / 2 + (i - 3) * 0.32;
        const d0 = r * (0.9 + 0.15 * k), d1 = d0 + 55 * k;
        return <path key={i} d={`M ${x + Math.cos(a) * d0} ${y + Math.sin(a) * d0} L ${x + Math.cos(a) * d1} ${y + Math.sin(a) * d1}`}
          stroke={INK} strokeWidth={9} strokeLinecap="round" />;
      })}
    </g>
  );
};

/** Horizontal speed lines trailing behind something moving along x (dir: the way it travels). */
export const SpeedLines: React.FC<{ amount: number; x: number; y: number; h?: number; dir?: 1 | -1; seed?: number }> = ({ amount, x, y, h = 260, dir = 1, seed = 4 }) => {
  if (amount <= 0.01) return null;
  const r = seeded(seed);
  return (
    <g opacity={clamp(amount)}>
      {Array.from({ length: 7 }, (_, i) => {
        const yy = y - h / 2 + (i + 0.5) * (h / 7) + (r() - 0.5) * 18;
        const len = (120 + r() * 200) * amount;
        const x0 = x - dir * (40 + r() * 60);
        return <path key={i} d={`M ${x0} ${yy} L ${x0 - dir * len} ${yy}`} stroke={INK} strokeWidth={6} strokeLinecap="round" />;
      })}
    </g>
  );
};

/** An emote popping above a head between t0 and t1: '!', '?', a sweat drop or a heart. */
export const Emote: React.FC<{ t: number; t0: number; t1: number; x: number; y: number; kind: '!' | '?' | 'sweat' | 'heart'; size?: number }> = ({
  t, t0, t1, x, y, kind, size = 1,
}) => {
  if (t < t0 || t > t1) return null;
  const s = size * eases.outBack(clamp((t - t0) / 0.18)) * (1 - ramp(t, t1 - 0.15, t1));
  const bob = Math.sin((t - t0) * 9) * 4;
  return (
    <g transform={`translate(${x} ${y + bob}) scale(${s})`}>
      {kind === '!' && (
        <>
          <path d="M -12 -90 L 12 -90 L 7 -20 L -7 -20 Z" fill="#ff4d3d" stroke={INK} strokeWidth={6} strokeLinejoin="round" />
          <circle cx={0} cy={4} r={11} fill="#ff4d3d" stroke={INK} strokeWidth={6} />
        </>
      )}
      {kind === '?' && (
        <path d="M -26 -60 C -26 -96 30 -100 30 -66 C 30 -44 6 -40 6 -18 L -8 -18 C -8 -46 14 -48 14 -66 C 14 -80 -10 -80 -10 -60 Z M -10 0 a 9 9 0 1 0 18 0 a 9 9 0 1 0 -18 0 Z"
          fill="#ffd23f" stroke={INK} strokeWidth={5} strokeLinejoin="round" />
      )}
      {kind === 'sweat' && <path d="M 0 -50 C 18 -20 26 -4 26 10 C 26 26 14 36 0 36 C -14 36 -26 26 -26 10 C -26 -4 -18 -20 0 -50 Z" fill="#8fd6ff" stroke={INK} strokeWidth={5} />}
      {kind === 'heart' && <path d="M 0 30 C -60 -10 -40 -60 0 -30 C 40 -60 60 -10 0 30 Z" fill="#ff5d7a" stroke={INK} strokeWidth={6} />}
    </g>
  );
};

/** A full-frame flash (an impact frame), outside the <svg>. */
export const Flash: React.FC<{ amount: number; color?: string }> = ({ amount, color = '#ffffff' }) =>
  amount > 0.01 ? <AbsoluteFill style={{ background: color, opacity: clamp(amount) }} /> : null;

/** A camera shake offset (px) after an impact at t0; use it only when the video's jolts answer is yes. */
export const shake = (t: number, t0: number, amp = 18): P => {
  const dt = t - t0;
  if (dt < 0 || dt > 0.45) return [0, 0];
  const k = amp * Math.exp(-dt * 9);
  return [Math.sin(dt * 95) * k, Math.cos(dt * 77 + 1) * k * 0.7];
};

/**
 * A CSS transform for the scene's container: a push-in that scales the frame by (1 + z) about the point (fx, fy), plus
 * a shake offset. The ink scales with it, as in a redrawn close-up. w and h are the composition's size.
 */
export const zoomAt = (z: number, fx: number, fy: number, shx = 0, shy = 0, w = 1920, h = 1080) =>
  `translate(${shx}px, ${shy}px) translate(${fx - w / 2}px, ${fy - h / 2}px) scale(${1 + z}) translate(${w / 2 - fx}px, ${h / 2 - fy}px)`;
