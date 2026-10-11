import React from 'react';
import { AbsoluteFill, useVideoConfig } from 'remotion';
import { defineTransition, ease, paramDefaults, Pass, seg } from '../../../../src/core';
import meta from './transition.json';

type P = { color: string; thickness: number; orientation: 'horizontal' | 'vertical' };

/**
 * 0–0.35: a line draws across the middle of A. 0.35–1: the line splits into two edges that travel
 * outward; between them is scene B, so the line itself opens the new scene and leaves the frame.
 */
export default defineTransition<P>({
  defaults: paramDefaults<P>(meta),
  Exiting: Pass,
  Entering: ({ progress, children, params: { color, thickness: t, orientation } }) => {
    const { width: W, height: H } = useVideoConfig();
    const horiz = orientation === 'horizontal';
    const span = horiz ? H : W;
    const draw = ease.inOutCubic(seg(progress, 0, 0.35));
    const open = ease.inOutCubic(seg(progress, 0.35, 1));
    const half = open * (span / 2 + t * 2);
    const c = span / 2;
    const band: React.CSSProperties = horiz
      ? { clipPath: `inset(${c - half}px 0 ${c - half}px 0)` }
      : { clipPath: `inset(0 ${c - half}px 0 ${c - half}px)` };
    const line = (pos: number, key: string) => (
      <div key={key} style={horiz
        ? { position: 'absolute', left: 0, top: pos - t / 2, width: W * (open > 0 ? 1 : draw), height: t, background: color }
        : { position: 'absolute', top: 0, left: pos - t / 2, height: H * (open > 0 ? 1 : draw), width: t, background: color }} />
    );
    return (
      <AbsoluteFill>
        {open > 0 ? <AbsoluteFill style={band}>{children}</AbsoluteFill> : null}
        {line(c - half, 'a')}
        {open > 0 ? line(c + half, 'b') : null}
      </AbsoluteFill>
    );
  },
});
