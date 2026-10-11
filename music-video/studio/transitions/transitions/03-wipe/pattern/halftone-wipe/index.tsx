import React from 'react';
import { AbsoluteFill, useVideoConfig } from 'remotion';
import { circlePath, clipStyle, defineTransition, ease, paramDefaults, Pass, seg } from '../../../../src/core';
import meta from './transition.json';

type P = { columns: number; angle: number };

/** Dots grow in a wave until they touch and overlap, like a halftone screen going from white to solid. */
export default defineTransition<P>({
  defaults: paramDefaults<P>(meta),
  Exiting: Pass,
  Entering: ({ progress, children, params: { columns, angle } }) => {
    const { width: W, height: H } = useVideoConfig();
    if (progress >= 1) return <AbsoluteFill>{children}</AbsoluteFill>;
    const cell = W / columns;
    const rows = Math.ceil(H / (cell * 0.88)) + 2;
    const a = (angle * Math.PI) / 180;
    const dx = Math.cos(a);
    const dy = Math.sin(a);
    // Project the corners to normalise each dot's position along the wave direction to 0..1.
    const proj = (x: number, y: number) => x * dx + y * dy;
    const ps = [proj(0, 0), proj(W, 0), proj(0, H), proj(W, H)];
    const lo = Math.min(...ps);
    const hi = Math.max(...ps);
    const spread = 0.6;
    const rMax = cell * 0.75;
    let d = '';
    for (let j = 0; j < rows; j++) {
      for (let i = 0; i <= columns; i++) {
        const x = (i + (j % 2) * 0.5) * cell;
        const y = j * cell * 0.88;
        const t = (proj(x, y) - lo) / (hi - lo);
        const r = rMax * ease.inOutCubic(seg(progress, t * spread, t * spread + 1 - spread));
        if (r > 0.3) d += circlePath(x, y, r);
      }
    }
    return <AbsoluteFill style={clipStyle(d)}>{children}</AbsoluteFill>;
  },
});
