import React from 'react';
import { AbsoluteFill, useVideoConfig } from 'remotion';
import { defineTransition, paramDefaults, rand, seg } from '../../../../src/core';
import meta from './transition.json';

type P = { cutAt: number; strength: number; seed: number };

/** Hard cut at `cutAt`; scene B lands with a decaying shake (scaled up just enough to hide the edges). */
export default defineTransition<P>({
  defaults: paramDefaults<P>(meta),
  Exiting: ({ progress, children, params }) => (progress < params.cutAt ? <AbsoluteFill>{children}</AbsoluteFill> : null),
  Entering: ({ progress, children, params, durationInFrames }) => {
    const { width, height } = useVideoConfig();
    if (progress < params.cutAt) return null;
    const q = seg(progress, params.cutAt, 1);
    const decay = Math.pow(1 - q, 2);
    const f = Math.round(progress * durationInFrames);
    const dx = (rand(params.seed, 'x', f) * 2 - 1) * params.strength * decay;
    const dy = (rand(params.seed, 'y', f) * 2 - 1) * params.strength * decay;
    const s = 1 + (2.2 * params.strength * decay) / Math.min(width, height);
    return <AbsoluteFill style={{ transform: `translate(${dx}px, ${dy}px) scale(${s})` }}>{children}</AbsoluteFill>;
  },
});
