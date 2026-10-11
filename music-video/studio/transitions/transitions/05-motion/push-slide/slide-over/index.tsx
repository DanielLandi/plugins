import React from 'react';
import { AbsoluteFill } from 'remotion';
import { defineTransition, ease, paramDefaults } from '../../../../src/core';
import meta from './transition.json';

type Dir = 'left' | 'right' | 'up' | 'down';
type P = { direction: Dir; dim: number; drift: number };

const AXIS: Record<Dir, [number, number]> = { left: [-1, 0], right: [1, 0], up: [0, -1], down: [0, 1] };
const shift = (dir: Dir, k: number) => `translate(${AXIS[dir][0] * k * 100}%, ${AXIS[dir][1] * k * 100}%)`;

/** B travels in `direction` over A with a shadow on its leading edge; A drifts a little way and dims. */
export default defineTransition<P>({
  defaults: paramDefaults<P>(meta),
  Exiting: ({ progress, children, params }) => {
    const e = ease.inOutQuint(progress);
    return (
      <AbsoluteFill style={{ background: '#000' }}>
        <AbsoluteFill style={{ transform: shift(params.direction, e * params.drift), opacity: 1 - params.dim * e }}>{children}</AbsoluteFill>
      </AbsoluteFill>
    );
  },
  Entering: ({ progress, children, params }) => {
    const e = ease.inOutQuint(progress);
    const [ax, ay] = AXIS[params.direction];
    return (
      <AbsoluteFill style={{ transform: shift(params.direction, e - 1), boxShadow: `${-ax * 30}px ${-ay * 30}px 80px rgba(0,0,0,${0.45 * (1 - e)})` }}>
        {children}
      </AbsoluteFill>
    );
  },
});
