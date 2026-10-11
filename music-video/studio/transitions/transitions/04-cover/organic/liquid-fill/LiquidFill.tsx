import React, { useMemo } from 'react';
import { useCurrentFrame, useVideoConfig } from 'remotion';
import { rand, Shader } from '../../../../src/core';
import { FRAG, MAX_SEEDS } from './shader';

export type LiquidOrigin = 'random' | 'center' | 'left' | 'right' | 'top' | 'bottom';

export type LiquidFillProps = {
  color?: string;
  seed?: number;
  /** Blobs across the frame height (cell density). */
  rows?: number;
  from?: LiquidOrigin;
  /** Half vein width as a fraction of frame height. */
  gap?: number;
  wobble?: number;
  /** Paint everything except the liquid, so the blobs are holes. */
  invert?: boolean;
  /** 0..1; unset = run over the parent Sequence. */
  progress?: number;
};

type Seed = [number, number, number, number];

const makeSeeds = (aspect: number, rows: number, seed: number, from: LiquidOrigin): Seed[] => {
  const cell = 1 / rows;
  const cols = Math.ceil(aspect / cell);
  const origin: Record<Exclude<LiquidOrigin, 'random'>, [number, number]> = {
    center: [aspect / 2, 0.5],
    left: [0, 0.5],
    right: [aspect, 0.5],
    top: [aspect / 2, 0],
    bottom: [aspect / 2, 1],
  };
  const maxDist = Math.hypot(aspect, 1);
  const seeds: Seed[] = [];
  // One extra ring of cells around the frame so the edges fill like the middle.
  for (let r = -1; r <= rows; r++) {
    for (let c = -1; c <= cols; c++) {
      const x = (c + 0.5 + (rand(seed, 'x', r, c) - 0.5) * 0.85) * (aspect / cols);
      const y = (r + 0.5 + (rand(seed, 'y', r, c) - 0.5) * 0.85) * cell;
      let order = rand(seed, 'b', r, c);
      if (from !== 'random') {
        const [ox, oy] = origin[from];
        order = 0.75 * (Math.hypot(x - ox, y - oy) / maxDist) + 0.25 * order;
      }
      seeds.push([x, y, order * 0.3, 1 / (0.3 + rand(seed, 's', r, c) * 0.12)]);
    }
  }
  return seeds.slice(0, MAX_SEEDS);
};

/** Liquid that grows from blobs until it covers the frame. Transparent where it hasn't reached. */
export const LiquidFill: React.FC<LiquidFillProps> = ({
  progress,
  color = '#000000',
  seed = 0,
  rows = 5,
  from = 'random',
  gap = 0.0085,
  wobble = 0.012,
  invert = false,
}) => {
  const frame = useCurrentFrame();
  const { width, height, durationInFrames } = useVideoConfig();
  const t = Math.min(1, Math.max(0, progress ?? (durationInFrames <= 1 ? 1 : frame / (durationInFrames - 1))));
  const seeds = useMemo(() => makeSeeds(width / height, rows, seed, from), [width, height, rows, seed, from]);
  const flat = useMemo(() => new Float32Array(seeds.flat()), [seeds]);
  const [r, g, b] = hex(color);
  return (
    <Shader
      frag={FRAG}
      uniforms={[
        ['1f', 'uT', t],
        ['4fv', 'uSeeds', flat],
        ['1i', 'uCount', seeds.length],
        ['1f', 'uMaxR', 1.6 / rows],
        ['1f', 'uGap', gap],
        ['1f', 'uJunction', gap * 5],
        ['1f', 'uWobble', wobble],
        ['1f', 'uSeed', seed],
        ['3f', 'uColor', [r, g, b]],
        ['1i', 'uInvert', invert ? 1 : 0],
      ]}
    />
  );
};

const hex = (h: string): [number, number, number] => {
  let s = h.replace('#', '');
  if (s.length === 3) s = s.split('').map((c) => c + c).join('');
  const n = parseInt(s, 16);
  return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255];
};
