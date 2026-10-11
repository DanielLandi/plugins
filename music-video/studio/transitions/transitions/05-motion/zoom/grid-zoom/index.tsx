import React from 'react';
import { AbsoluteFill, useVideoConfig } from 'remotion';
import { defineTransition, ease, mix, paramDefaults, seg } from '../../../../src/core';
import meta from './transition.json';

type Dir = 'left' | 'right' | 'up' | 'down';
type P = { color: string; background: string; zoom: number; direction: Dir };

const NEXT: Record<Dir, [number, number]> = { right: [1, 0], left: [-1, 0], down: [0, 1], up: [0, -1] };

/**
 * A world of frame-sized tiles: A is tile (0,0), B is the neighbouring tile in `direction`, the rest are
 * the incoming colour. The camera pulls back (0–0.35), glides to B's tile (0.3–0.7) and dives in (0.65–1).
 * Both sides share the same camera, so A and B stay locked to their tiles.
 */
const useCamera = (progress: number, p: P) => {
  const { width: W, height: H } = useVideoConfig();
  const gap = W * 0.06;
  const [nx, ny] = NEXT[p.direction];
  const out = ease.inOutCubic(seg(progress, 0, 0.35));
  const glide = ease.inOutCubic(seg(progress, 0.3, 0.7));
  const dive = ease.inOutCubic(seg(progress, 0.65, 1));
  const s = mix(mix(1, p.zoom, out), 1, dive);
  const cx = W / 2 + glide * nx * (W + gap);
  const cy = H / 2 + glide * ny * (H + gap);
  const world: React.CSSProperties = { transform: `translate(${W / 2}px, ${H / 2}px) scale(${s}) translate(${-cx}px, ${-cy}px)`, transformOrigin: '0 0' };
  const tile = (i: number, j: number): React.CSSProperties => ({ position: 'absolute', left: i * (W + gap), top: j * (H + gap), width: W, height: H, overflow: 'hidden' });
  return { world, tile, nx, ny };
};

export default defineTransition<P>({
  defaults: paramDefaults<P>(meta),
  Exiting: ({ progress, children, params }) => {
    const { world, tile } = useCamera(progress, params);
    const tiles: [number, number][] = [];
    for (let j = -3; j <= 3; j++) for (let i = -4; i <= 4; i++) if (i || j) tiles.push([i, j]);
    return (
      <AbsoluteFill style={{ background: params.background, overflow: 'hidden' }}>
        <div style={world}>
          {tiles.map(([i, j]) => <div key={`${i},${j}`} style={{ ...tile(i, j), background: params.color }} />)}
          <div style={tile(0, 0)}>{children}</div>
        </div>
      </AbsoluteFill>
    );
  },
  Entering: ({ progress, children, params }) => {
    const { world, tile, nx, ny } = useCamera(progress, params);
    if (progress < 0.35) return null;
    return (
      <AbsoluteFill style={{ overflow: 'hidden' }}>
        <div style={world}>
          <div style={{ ...tile(nx, ny), opacity: ease.inOutCubic(seg(progress, 0.35, 0.7)) }}>{children}</div>
        </div>
      </AbsoluteFill>
    );
  },
});
