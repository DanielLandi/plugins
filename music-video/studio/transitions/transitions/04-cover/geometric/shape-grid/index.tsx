import React from 'react';
import { AbsoluteFill, useVideoConfig } from 'remotion';
import { bridged, circlePath, ease, paramDefaults, polyPath, rand, rectPath, seg } from '../../../../src/core';
import meta from './transition.json';

type P = { color: string; shape: 'square' | 'circle' | 'diamond'; columns: number; from: 'top-left' | 'center' | 'left' | 'top' | 'random'; hold: number };

/** Cells grow in a wave (phase in), then shrink in the same wave order (phase out). */
export default bridged<P>(paramDefaults<P>(meta), ({ phase, progress, params: { color, shape, columns, from } }) => {
  const { width: W, height: H } = useVideoConfig();
  const cell = W / columns;
  const rows = Math.ceil(H / cell);
  const maxD = Math.hypot(W / 2, H / 2);
  let d = '';
  for (let j = 0; j < rows; j++) {
    for (let i = 0; i < columns; i++) {
      const cx = (i + 0.5) * cell;
      const cy = (j + 0.5) * cell;
      const order =
        from === 'center' ? Math.hypot(cx - W / 2, cy - H / 2) / maxD
        : from === 'left' ? cx / W
        : from === 'top' ? cy / H
        : from === 'random' ? rand(7, i, j)
        : (cx + cy) / (W + H);
      const q = ease.inOutCubic(seg(progress, order * 0.5, order * 0.5 + 0.5));
      const k = phase === 'in' ? q : 1 - q;
      if (k <= 0) continue;
      if (shape === 'circle') d += circlePath(cx, cy, cell * 0.72 * k);
      else if (shape === 'diamond') {
        const r = cell * 1.01 * k;
        d += polyPath([[cx, cy - r], [cx + r, cy], [cx, cy + r], [cx - r, cy]]);
      } else {
        const s = (cell + 1) * k;
        d += rectPath(cx - s / 2, cy - s / 2, s, s);
      }
    }
  }
  return (
    <AbsoluteFill>
      <svg width={W} height={H}>
        <path d={d} fill={color} />
      </svg>
    </AbsoluteFill>
  );
});
