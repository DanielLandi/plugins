import React from 'react';
import { AbsoluteFill, Composition, OffthreadVideo, staticFile, useVideoConfig, type CalculateMetadataFunction } from 'remotion';
import { linearTiming, TransitionSeries } from '@remotion/transitions';
import { clamp, defineTransition, ease, mix, seg, toPresentation, type Params } from '../transitions/src/core';
import { transitionPresentation } from './transitions';

/* A reel: finished clips chained by joins (`music-video reel`). Each join is its own short render: the last
 * `frames` of clip A and the first `frames` of clip B through one transition, so adding a clip to a reel renders
 * only its two joins. The default transition is `passage`, below; any id of the transition library also works. */

/* ------------------------------------------------------------------ passage ------------------------------------ */

export type PassageParams = {
  /** the point the opening grows from, as fractions of the frame (where A is heading: its vanishing point, or the
   * exit of the tunnel or doorway it is riding into) */
  x: number;
  y: number;
  /** the opening's height when it first appears, as a fraction of the frame's height */
  size: number;
  /** width / height of the opening (its top corners are round, its bottom is flat, like a tunnel mouth) */
  aspect: number;
  /** B starts at 1 - depth of its size and settles to its own size long before the opening reaches the rider, so
   * she is in the same place on both sides of the edge (the clips' chase cameras frame her alike) */
  depth: number;
  /** the rim of the passage: its colour, and how dark A gets as the camera comes into it (0..1) */
  rim: string;
  dim: number;
  /** extra brightness of B when the opening first appears (the glare of an exit), settling to none */
  glare: number;
  /** where B is heading in its first frames (its vanishing point, fractions of the frame): B starts shifted so this
   * point sits in the opening (the opening shows the road ahead, not B's sky) and eases back to its own place long
   * before the opening reaches the rider */
  bx: number;
  by: number;
  /** optional: where the opening is as the join runs, [q, x, y] keys (q = join progress 0..1), for an exit that
   * moves across the frame (a turn into a doorway); x, y above are then ignored */
  track?: [number, number, number][];
};

export const PASSAGE_DEFAULTS: PassageParams = { x: 0.5, y: 0.42, size: 0.07, aspect: 1.15, depth: 0.12, rim: '#07080a', dim: 0.35, glare: 0.06, bx: 0.5, by: 0.45 };

type Box = { cx: number; cy: number; hw: number; hh: number; r: number };

/** The opening at scale s: half-width, half-height and the radius of its round top corners, centred on (cx, cy). */
const box = (cx: number, cy: number, H: number, p: PassageParams, s: number): Box => {
  const hh = (p.size * H * s) / 2;
  const hw = hh * p.aspect;
  return { cx, cy, hw, hh, r: Math.min(hw, hh) * 0.9 };
};

/** Is the point inside the opening? (the round top corners count; the bottom is square) */
export const insideOpening = (b: Box, x: number, y: number) => {
  const dx = Math.abs(x - b.cx), dy = y - b.cy;
  if (dx > b.hw || dy > b.hh || dy < -b.hh) return false;
  const top = -b.hh + b.r, side = b.hw - b.r;
  if (dy < top && dx > side) return Math.hypot(dx - side, dy - top) <= b.r;
  return true;
};

/** The scale at which the opening covers the whole frame (every corner, with a margin). */
export const coverScale = (W: number, H: number, p: PassageParams) => {
  const cx = p.x * W, cy = p.y * H;
  const pts: [number, number][] = [[-2, -2], [W + 2, -2], [-2, H + 2], [W + 2, H + 2], [cx, -2], [-2, cy], [W + 2, cy]];
  let lo = 1, hi = 2;
  while (!pts.every(([x, y]) => insideOpening(box(cx, cy, H, p, hi), x, y))) hi *= 2;
  for (let i = 0; i < 40; i++) {
    const m = (lo + hi) / 2;
    if (pts.every(([x, y]) => insideOpening(box(cx, cy, H, p, m), x, y))) hi = m;
    else lo = m;
  }
  return hi * 1.02;
};

/** The opening's scale at progress q, as the camera rides towards it: its apparent size goes as 1 / distance, so it
 * grows slowly at first and fills the frame fast at the end, as a real tunnel exit does. The distance runs as
 * q^warp (the camera gathers speed), so the edge sweeps over the rider in a few frames at the very end. */
export const approachScale = (q: number, full: number, warp = 1.6) => {
  const d = 1 - (1 - 1 / full) * Math.pow(clamp(q), warp);
  return 1 / d;
};

const f = (n: number) => n.toFixed(2);
const openingPath = (b: Box) => {
  const { cx, cy, hw, hh, r } = b;
  const L = cx - hw, R = cx + hw, T = cy - hh, B = cy + hh;
  return `M${f(L)} ${f(B)}L${f(L)} ${f(T + r)}A${f(r)} ${f(r)} 0 0 1 ${f(L + r)} ${f(T)}L${f(R - r)} ${f(T)}A${f(r)} ${f(r)} 0 0 1 ${f(R)} ${f(T + r)}L${f(R)} ${f(B)}Z`;
};

/** A join's frames run at progress 0, 1/D … (D-1)/D: stretch it so its last frame is fully B (the clip after the
 * join starts on the next frame, so nothing pops at the splice). */
export const joinProgress = (progress: number, frames: number) => clamp(progress * frames / Math.max(1, frames - 1));

/** The opening's centre at progress q: (x, y), or the track's keys eased between (C1, so it never jerks). */
export const trackAt = (p: PassageParams, q: number): [number, number] => {
  const k = p.track;
  if (!k || k.length === 0) return [p.x, p.y];
  if (q <= k[0][0]) return [k[0][1], k[0][2]];
  for (let i = 1; i < k.length; i++) {
    if (q <= k[i][0]) {
      const u = (q - k[i - 1][0]) / Math.max(1e-6, k[i][0] - k[i - 1][0]);
      const e = u * u * (3 - 2 * u);
      return [mix(k[i - 1][1], k[i][1], e), mix(k[i - 1][2], k[i][2], e)];
    }
  }
  const last = k[k.length - 1];
  return [last[1], last[2]];
};

const usePassage = (progress: number, params: PassageParams) => {
  const { width: W, height: H } = useVideoConfig();
  const base = { ...PASSAGE_DEFAULTS, ...params };
  const [ex, ey] = trackAt(base, 1);
  const [x, y] = trackAt(base, progress);
  const p = { ...base, x, y };
  const full = coverScale(W, H, { ...base, x: ex, y: ey });
  // it grows out of a point (the exit comes into view) rather than appearing at its first size
  // with a track, the opening comes into view at its first key (the exit may be round a corner before that)
  const q = seg(progress, base.track?.[0]?.[0] ?? 0, 1);
  const s = approachScale(q, full) * ease.outCubic(seg(q, 0, 0.2));
  return { p, W, H, b: box(p.x * W, p.y * H, H, p, s), s, full };
};

/**
 * passage (Carry › Portal family, after portal-zoom): the camera rides through a passage. An opening shaped like a
 * tunnel mouth appears where A is heading and grows as the camera comes up to it, at the rate a real exit does
 * (1 / distance), with B already playing inside it, far and a little bright, settling to its own size and exposure
 * as the opening fills the frame. A darkens towards the rim as the passage closes round the camera. B is visible
 * from the first frame of the join: there is never a blank or a flat sheet before the new scene.
 */
export const passage = defineTransition<PassageParams>({
  defaults: PASSAGE_DEFAULTS,
  Exiting: ({ progress: raw, children, params, durationInFrames }) => {
    const progress = joinProgress(raw, durationInFrames);
    const { p, W, H, b } = usePassage(progress, params);
    const dim = p.dim * ease.inOutCubic(clamp(progress / 0.85));
    const rimW = Math.max(b.hh, H * 0.08) * 0.9;
    return (
      <AbsoluteFill>
        <AbsoluteFill style={{ filter: `brightness(${f(1 - dim)})` }}>{children}</AbsoluteFill>
        <svg width={W} height={H} style={{ position: 'absolute', inset: 0 }}>
          <defs>
            <filter id="passage-soft" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation={f(rimW * 0.35)} />
            </filter>
          </defs>
          <path d={openingPath(b)} fill="none" stroke={p.rim} strokeWidth={f(rimW)} strokeOpacity={f(0.85 * Math.min(1, progress * 6))} filter="url(#passage-soft)" />
        </svg>
      </AbsoluteFill>
    );
  },
  Entering: ({ progress: raw, children, params, durationInFrames }) => {
    const progress = joinProgress(raw, durationInFrames);
    const { p, W, H, b } = usePassage(progress, params);
    const settle = ease.outCubic(clamp(progress / 0.6));
    const scale = mix(1 - p.depth, 1, settle);
    const shift = 1 - ease.inCubic(clamp(progress / 0.92));
    const dx = (b.cx - p.bx * W) * shift, dy = (b.cy - p.by * H) * shift;
    const glare = p.glare * (1 - ease.inOutCubic(clamp(progress / 0.9)));
    // the shadow of the passage's lip on the inside of the edge: where the edge sweeps over the rider she is dark on
    // both sides of it; gone by the last frame, so B ends clean
    const lip = Math.min(H * 0.12, b.hh * 0.3);
    const lipOpacity = 0.75 * seg(b.hh / H, 0.22, 0.36) * (1 - ease.inOutCubic(seg(progress, 0.94, 1)));
    return (
      <AbsoluteFill style={{ clipPath: `path('${openingPath(b)}')` }}>
        <AbsoluteFill style={{ transform: `translate(${f(dx)}px, ${f(dy)}px) scale(${scale})`, transformOrigin: `${f(b.cx - dx)}px ${f(b.cy - dy)}px`, filter: glare > 0.001 ? `brightness(${f(1 + glare)})` : undefined }}>
          {children}
        </AbsoluteFill>
        {lipOpacity > 0.002 ? (
          <svg width={W} height={H} style={{ position: 'absolute', inset: 0 }}>
            <defs>
              <filter id="passage-lip" x="-50%" y="-50%" width="200%" height="200%">
                <feGaussianBlur stdDeviation={f(lip * 0.45)} />
              </filter>
            </defs>
            <path d={openingPath(b)} fill="none" stroke={p.rim} strokeWidth={f(lip * 2)} strokeOpacity={f(lipOpacity)} filter="url(#passage-lip)" />
          </svg>
        ) : null}
      </AbsoluteFill>
    );
  },
});

/* ------------------------------------------------------------------ the join composition ----------------------- */

export type JoinProps = {
  /** clips in the public folder (paths for staticFile) */
  a: string;
  b: string;
  /** A's first frame used (its last `frames` frames), and the join's length in frames */
  aFrom: number;
  frames: number;
  /** a transition id from the library, or 'passage' (the default) */
  transition?: string;
  params?: Params;
};

const presentationFor = (id: string | undefined, params: Params | undefined) =>
  !id || id === 'passage' ? toPresentation(passage, (params ?? {}) as Partial<PassageParams>) : transitionPresentation(id, params ?? {});

export const Join: React.FC<JoinProps> = ({ a, b, aFrom, frames, transition, params }) => (
  <AbsoluteFill style={{ background: '#000' }}>
    <TransitionSeries>
      <TransitionSeries.Sequence durationInFrames={frames}>
        <OffthreadVideo src={staticFile(a)} trimBefore={aFrom} muted />
      </TransitionSeries.Sequence>
      <TransitionSeries.Transition presentation={presentationFor(transition, params)} timing={linearTiming({ durationInFrames: frames })} />
      <TransitionSeries.Sequence durationInFrames={frames}>
        <OffthreadVideo src={staticFile(b)} muted />
      </TransitionSeries.Sequence>
    </TransitionSeries>
  </AbsoluteFill>
);

const joinMetadata: CalculateMetadataFunction<JoinProps> = ({ props }) => ({ durationInFrames: Math.max(1, props.frames) });

/** Register the join in a video's index.tsx: `<JoinComposition id="<video>-join" />`. `music-video reel` renders it
 * with the clips and frames of each join as input props. */
export const JoinComposition: React.FC<{ id: string; width?: number; height?: number; fps?: number }> = ({ id, width = 1920, height = 1080, fps = 30 }) => (
  <Composition id={id} component={Join} width={width} height={height} fps={fps} durationInFrames={1}
    defaultProps={{ a: '', b: '', aFrom: 0, frames: 1 } as JoinProps} calculateMetadata={joinMetadata} />
);
