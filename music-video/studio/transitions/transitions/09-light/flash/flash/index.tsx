import React from 'react';
import { AbsoluteFill } from 'remotion';
import { defineTransition, ease, paramDefaults, seg } from '../../../../src/core';
import meta from './transition.json';

type P = { color: string; bloom: number };

/**
 * The scenes overexpose toward the middle (brightness + a little glow), and a flash layer peaks to
 * fully opaque exactly at the swap. Over transparency (the overlay render) only the flash layer remains.
 */
const Lit: React.FC<{ k: number; params: P; children: React.ReactNode }> = ({ k, params, children }) => (
  <AbsoluteFill>
    <AbsoluteFill style={{ filter: k > 0.001 ? `brightness(${1 + (params.bloom - 1) * k}) blur(${k * 6}px)` : undefined }}>{children}</AbsoluteFill>
    <AbsoluteFill style={{ background: params.color, opacity: Math.pow(k, 1.6) }} />
  </AbsoluteFill>
);

export default defineTransition<P>({
  defaults: paramDefaults<P>(meta),
  Exiting: ({ progress, children, params }) => (progress >= 0.5 ? null : <Lit k={ease.inCubic(seg(progress, 0, 0.5))} params={params}>{children}</Lit>),
  Entering: ({ progress, children, params }) => (progress < 0.5 ? null : <Lit k={1 - ease.outCubic(seg(progress, 0.5, 1))} params={params}>{children}</Lit>),
});
