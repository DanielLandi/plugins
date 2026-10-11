import React from 'react';
import { AbsoluteFill, useVideoConfig } from 'remotion';
import { defineTransition, ease, paramDefaults, Pass } from '../../../../src/core';
import meta from './transition.json';

type P = { x: number; y: number; softness: number };

export default defineTransition<P>({
  defaults: paramDefaults<P>(meta),
  Exiting: Pass,
  Entering: ({ progress, children, params: { x, y, softness } }) => {
    const { width: W, height: H } = useVideoConfig();
    const cx = x * W;
    const cy = y * H;
    const far = Math.max(Math.hypot(cx, cy), Math.hypot(W - cx, cy), Math.hypot(cx, H - cy), Math.hypot(W - cx, H - cy));
    const r = ease.inOutCubic(progress) * (far + softness);
    const image = `radial-gradient(circle at ${cx}px ${cy}px, #000 ${Math.max(0, r - softness)}px, transparent ${r + 0.5}px)`;
    return <AbsoluteFill style={progress >= 1 ? {} : { maskImage: image, WebkitMaskImage: image }}>{children}</AbsoluteFill>;
  },
});
