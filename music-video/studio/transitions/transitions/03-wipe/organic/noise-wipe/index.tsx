import React from 'react';
import { AbsoluteFill, useVideoConfig } from 'remotion';
import { clipStyle, defineTransition, ease, fbm1, paramDefaults, Pass, polyPath, type Pt } from '../../../../src/core';
import meta from './transition.json';

type P = { direction: 'left' | 'right' | 'up' | 'down'; roughness: number; seed: number };

/** A ragged edge (fractal noise along the edge, drifting as it moves) sweeps across the frame. */
export default defineTransition<P>({
  defaults: paramDefaults<P>(meta),
  Exiting: Pass,
  Entering: ({ progress, children, params: { direction, roughness, seed } }) => {
    const { width: W, height: H } = useVideoConfig();
    if (progress >= 1) return <AbsoluteFill>{children}</AbsoluteFill>;
    const horiz = direction === 'left' || direction === 'right';
    const along = horiz ? W : H; // the axis the edge travels
    const across = horiz ? H : W;
    const amp = roughness * along;
    const pos = ease.inOutCubic(progress) * (along + 2 * amp) - amp;
    const N = 140;
    const edge: Pt[] = [];
    for (let k = 0; k <= N; k++) {
      const c = (k / N) * across;
      const v = pos + fbm1((k / N) * 5 + progress * 1.5, seed) * amp;
      edge.push(horiz ? [v, c] : [c, v]);
    }
    // Region already covered: from the starting side to the edge. "left" travels left→right.
    let pts: Pt[] = horiz ? [[0, H], [0, 0], ...edge] : [[W, 0], [0, 0], ...edge];
    if (direction === 'right') pts = pts.map(([x, y]) => [W - x, y]);
    if (direction === 'up') pts = pts.map(([x, y]) => [x, H - y]);
    return <AbsoluteFill style={clipStyle(polyPath(pts))}>{children}</AbsoluteFill>;
  },
});
