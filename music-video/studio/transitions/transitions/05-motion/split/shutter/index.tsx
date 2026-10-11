import React from 'react';
import { AbsoluteFill, useVideoConfig } from 'remotion';
import { clipStyle, defineTransition, ease, mix, paramDefaults, rectPath } from '../../../../src/core';
import meta from './transition.json';

type P = { orientation: 'vertical' | 'horizontal'; scaleIn: number };

/** A splits into two halves that slide apart like doors; B settles from a slight zoom behind them. */
export default defineTransition<P>({
  defaults: paramDefaults<P>(meta),
  exitingOnTop: true,
  Exiting: ({ progress, children, params: { orientation } }) => {
    const { width: W, height: H } = useVideoConfig();
    if (progress >= 1) return null;
    const q = ease.inOutQuint(progress) * 51;
    const vert = orientation === 'vertical';
    const halves: [string, string][] = vert
      ? [[rectPath(0, 0, W / 2 + 0.5, H), `translateX(${-q}%)`], [rectPath(W / 2, 0, W / 2, H), `translateX(${q}%)`]]
      : [[rectPath(0, 0, W, H / 2 + 0.5), `translateY(${-q}%)`], [rectPath(0, H / 2, W, H / 2), `translateY(${q}%)`]];
    return (
      <AbsoluteFill>
        {halves.map(([clip, move], i) => (
          <AbsoluteFill key={i} style={{ transform: move }}>
            <AbsoluteFill style={clipStyle(clip)}>{children}</AbsoluteFill>
          </AbsoluteFill>
        ))}
      </AbsoluteFill>
    );
  },
  Entering: ({ progress, children, params }) => (
    <AbsoluteFill style={{ transform: `scale(${mix(1 + params.scaleIn, 1, ease.outCubic(progress))})` }}>{children}</AbsoluteFill>
  ),
});
