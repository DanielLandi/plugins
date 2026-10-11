import React from 'react';
import { AbsoluteFill } from 'remotion';
import { bridged, ease, paramDefaults, seg } from '../../../../src/core';
import meta from './transition.json';

type P = { colors: string[]; direction: 'left' | 'right' | 'up' | 'down'; stagger: number; hold: number };

const AXIS: Record<P['direction'], [number, number]> = { left: [-1, 0], right: [1, 0], up: [0, -1], down: [0, 1] };

/**
 * Full-frame panels slide in one after another (the last one ends on top and covers),
 * then slide on out the far side, the top panel first, showing scene B.
 */
export default bridged<P>(paramDefaults<P>(meta), ({ phase, progress, params: { colors, direction, stagger } }) => {
  const [ax, ay] = AXIS[direction];
  const n = colors.length;
  const dur = 1 - stagger * (n - 1);
  return (
    <AbsoluteFill style={{ overflow: 'hidden' }}>
      {colors.map((c, k) => {
        // In: panel k starts after k staggers. Out: the top panel (last) leaves first.
        const order = phase === 'in' ? k : n - 1 - k;
        const q = ease.inOutQuint(seg(progress, order * stagger, order * stagger + dur));
        // Position along the travel axis: -1 = waiting off-screen behind, 0 = covering, 1 = gone ahead.
        const pos = phase === 'in' ? q - 1 : q;
        return <AbsoluteFill key={k} style={{ background: c, transform: `translate(${pos * ax * 100}%, ${pos * ay * 100}%)` }} />;
      })}
    </AbsoluteFill>
  );
});
