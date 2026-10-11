import React from 'react';
import { AbsoluteFill, useVideoConfig } from 'remotion';
import { defineTransition, ease, mix, paramDefaults, seg } from '../../../../src/core';
import meta from './transition.json';

type P = { background: string; size: number };

/**
 * k = 0: the full frame. k = 1: a circle of diameter size×H in the centre, the picture shrunk inside it.
 * A goes 0→1, the picture inside crossfades to B, then B goes 1→0.
 */
const Morphing: React.FC<{ k: number; size: number; children: React.ReactNode }> = ({ k, size, children }) => {
  const { width: W, height: H } = useVideoConfig();
  const D = size * H;
  const w = mix(W, D, k);
  const h = mix(H, D, k);
  const r = mix(0, D / 2, Math.pow(k, 0.6));
  const s = mix(1, (D * 1.15) / H, k);
  return (
    <AbsoluteFill style={{ clipPath: `inset(${(H - h) / 2}px ${(W - w) / 2}px round ${r}px)` }}>
      <AbsoluteFill style={{ transform: `scale(${s})` }}>{children}</AbsoluteFill>
    </AbsoluteFill>
  );
};

export default defineTransition<P>({
  defaults: paramDefaults<P>(meta),
  Exiting: ({ progress, children, params }) => (
    <AbsoluteFill style={{ background: params.background }}>
      {progress < 0.6 ? <Morphing k={ease.inOutCubic(seg(progress, 0, 0.45))} size={params.size}>{children}</Morphing> : null}
    </AbsoluteFill>
  ),
  Entering: ({ progress, children, params }) =>
    progress < 0.4 ? null : (
      <AbsoluteFill style={{ opacity: ease.inOutCubic(seg(progress, 0.4, 0.6)) }}>
        <Morphing k={1 - ease.inOutCubic(seg(progress, 0.55, 1))} size={params.size}>{children}</Morphing>
      </AbsoluteFill>
    ),
});
