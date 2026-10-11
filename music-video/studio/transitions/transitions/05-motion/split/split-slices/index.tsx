import React from 'react';
import { AbsoluteFill, useVideoConfig } from 'remotion';
import { clipStyle, defineTransition, ease, mix, paramDefaults, rectPath, seg } from '../../../../src/core';
import meta from './transition.json';

type P = { slices: number; orientation: 'horizontal' | 'vertical'; stagger: number };

/** A is cut into slices (copies of A clipped to each band) that slide off alternately; B settles behind. */
export default defineTransition<P>({
  defaults: paramDefaults<P>(meta),
  exitingOnTop: true,
  Exiting: ({ progress, children, params: { slices, orientation, stagger } }) => {
    const { width: W, height: H } = useVideoConfig();
    if (progress >= 1) return null;
    const horiz = orientation === 'horizontal';
    const size = (horiz ? H : W) / slices;
    return (
      <AbsoluteFill>
        {Array.from({ length: slices }, (_, i) => {
          const start = (i / Math.max(1, slices - 1)) * stagger;
          const q = ease.inOutQuint(seg(progress, start, start + 1 - stagger));
          const sign = i % 2 ? 1 : -1;
          const clip = horiz ? rectPath(0, i * size, W, size + 0.5) : rectPath(i * size, 0, size + 0.5, H);
          const move = horiz ? `translateX(${sign * q * 102}%)` : `translateY(${sign * q * 102}%)`;
          return (
            <AbsoluteFill key={i} style={{ transform: move }}>
              <AbsoluteFill style={clipStyle(clip)}>{children}</AbsoluteFill>
            </AbsoluteFill>
          );
        })}
      </AbsoluteFill>
    );
  },
  Entering: ({ progress, children }) => (
    <AbsoluteFill style={{ transform: `scale(${mix(1.06, 1, ease.outCubic(progress))})` }}>{children}</AbsoluteFill>
  ),
});
