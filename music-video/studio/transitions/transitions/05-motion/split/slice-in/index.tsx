import React from 'react';
import { AbsoluteFill, useVideoConfig } from 'remotion';
import { clipStyle, defineTransition, ease, paramDefaults, Pass, rectPath, seg } from '../../../../src/core';
import meta from './transition.json';

type P = { slices: number; stagger: number; from: 'bottom' | 'top' | 'alternate' };

/** B arrives as vertical slices (copies of B clipped to each column) sliding into place one after another. */
export default defineTransition<P>({
  defaults: paramDefaults<P>(meta),
  Exiting: Pass,
  Entering: ({ progress, children, params: { slices, stagger, from } }) => {
    const { width: W } = useVideoConfig();
    if (progress >= 1) return <AbsoluteFill>{children}</AbsoluteFill>;
    const size = W / slices;
    return (
      <AbsoluteFill>
        {Array.from({ length: slices }, (_, i) => {
          const start = (i / Math.max(1, slices - 1)) * stagger;
          const q = ease.inOutQuint(seg(progress, start, start + 1 - stagger));
          const sign = from === 'top' ? -1 : from === 'alternate' && i % 2 ? -1 : 1;
          return (
            <AbsoluteFill key={i} style={{ transform: `translateY(${sign * (1 - q) * 101}%)` }}>
              <AbsoluteFill style={clipStyle(rectPath(i * size, 0, size + 0.5, 99999))}>{children}</AbsoluteFill>
            </AbsoluteFill>
          );
        })}
      </AbsoluteFill>
    );
  },
});
