import React from 'react';
import { AbsoluteFill, useVideoConfig } from 'remotion';
import { clipStyle, defineTransition, ease, paramDefaults, Pass, polyPath, seg, type Pt } from '../../../../src/core';
import meta from './transition.json';

type P = { count: number; angle: number; stagger: number };

/** Bands across the frame at `angle`; each opens from its leading edge, one after another. */
export default defineTransition<P>({
  defaults: paramDefaults<P>(meta),
  Exiting: Pass,
  Entering: ({ progress, children, params: { count, angle, stagger } }) => {
    const { width: W, height: H } = useVideoConfig();
    if (progress >= 1) return <AbsoluteFill>{children}</AbsoluteFill>;
    const a = (angle * Math.PI) / 180;
    const u: Pt = [Math.cos(a), Math.sin(a)]; // across the stripes
    const v: Pt = [-u[1], u[0]]; // along the stripes
    const proj = [[0, 0], [W, 0], [0, H], [W, H]].map(([x, y]) => x * u[0] + y * u[1]);
    const lo = Math.min(...proj);
    const w = (Math.max(...proj) - lo) / count;
    const L = W + H;
    let d = '';
    for (let i = 0; i < count; i++) {
      const start = (i / Math.max(1, count - 1)) * stagger;
      const open = ease.inOutQuint(seg(progress, start, start + 1 - stagger)) * (w + 1);
      if (open <= 0) continue;
      const s0 = lo + i * w;
      const s1 = s0 + open;
      const pt = (s: number, t: number): Pt => [u[0] * s + v[0] * t, u[1] * s + v[1] * t];
      d += polyPath([pt(s0, -L), pt(s1, -L), pt(s1, L), pt(s0, L)]);
    }
    return <AbsoluteFill style={clipStyle(d)}>{children}</AbsoluteFill>;
  },
});
