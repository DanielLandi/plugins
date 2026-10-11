import React from 'react';
import { AbsoluteFill, useVideoConfig } from 'remotion';
import { defineTransition, ease, paramDefaults, Pass } from '../../../../src/core';
import meta from './transition.json';

type P = { streak: number };

/**
 * A seam sweeps right → left. Right of the seam the new scene sits normally, except for a band just
 * ahead of it where B's leading column of pixels is stretched across the band (scaleX of a 1px strip),
 * so B arrives as long streaks of its own colours. The band is widest mid-sweep and gone at the ends.
 */
export default defineTransition<P>({
  defaults: paramDefaults<P>(meta),
  Exiting: Pass,
  Entering: ({ progress, children, params }) => {
    const { width: W } = useVideoConfig();
    if (progress >= 1) return <AbsoluteFill>{children}</AbsoluteFill>;
    const e = ease.inOutCubic(progress);
    const band = params.streak * W * Math.sin(Math.PI * progress);
    const seam = W * (1 - e); // left edge of everything B covers
    const col = Math.min(W - 1, seam + band); // B's column that gets stretched
    return (
      <AbsoluteFill>
        <AbsoluteFill style={{ clipPath: `inset(0 0 0 ${col}px)` }}>{children}</AbsoluteFill>
        {band > 1 ? (
          <AbsoluteFill style={{ transform: `scaleX(${band + 1})`, transformOrigin: `${col + 1}px 50%` }}>
            <AbsoluteFill style={{ clipPath: `inset(0 ${W - col - 1}px 0 ${col}px)` }}>{children}</AbsoluteFill>
          </AbsoluteFill>
        ) : null}
      </AbsoluteFill>
    );
  },
});
