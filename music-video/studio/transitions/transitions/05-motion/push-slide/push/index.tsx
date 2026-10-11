import React from 'react';
import { AbsoluteFill } from 'remotion';
import { defineTransition, ease, paramDefaults } from '../../../../src/core';
import meta from './transition.json';

type Dir = 'left' | 'right' | 'up' | 'down';
type P = { direction: Dir; curve: 'cubic' | 'quint' | 'expo' };

export const AXIS: Record<Dir, [number, number]> = { left: [-1, 0], right: [1, 0], up: [0, -1], down: [0, 1] };
const CURVE = { cubic: ease.inOutCubic, quint: ease.inOutQuint, expo: ease.inOutExpo };
const shift = (dir: Dir, k: number) => `translate(${AXIS[dir][0] * k * 100}%, ${AXIS[dir][1] * k * 100}%)`;

/** Both scenes travel together: A leaves in `direction`, B follows it in from the opposite side. */
export default defineTransition<P>({
  defaults: paramDefaults<P>(meta),
  Exiting: ({ progress, children, params }) => (
    <AbsoluteFill style={{ transform: shift(params.direction, CURVE[params.curve](progress)) }}>{children}</AbsoluteFill>
  ),
  Entering: ({ progress, children, params }) => (
    <AbsoluteFill style={{ transform: shift(params.direction, CURVE[params.curve](progress) - 1) }}>{children}</AbsoluteFill>
  ),
});
