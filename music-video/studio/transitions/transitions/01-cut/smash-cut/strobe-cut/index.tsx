import React from 'react';
import { AbsoluteFill } from 'remotion';
import { defineTransition, paramDefaults } from '../../../../src/core';
import meta from './transition.json';

type P = { flips: number };

// Swap points get closer together (sqrt spacing), so the strobe speeds up. An odd count ends on B.
const showB = (p: number, flips: number) => {
  const n = flips % 2 ? flips : flips + 1;
  let k = 0;
  for (let i = 1; i <= n; i++) if (p >= Math.sqrt(i / (n + 1))) k = i;
  return k % 2 === 1;
};

export default defineTransition<P>({
  defaults: paramDefaults<P>(meta),
  Exiting: ({ progress, children, params }) => (showB(progress, params.flips) ? null : <AbsoluteFill>{children}</AbsoluteFill>),
  Entering: ({ progress, children, params }) => (showB(progress, params.flips) ? <AbsoluteFill>{children}</AbsoluteFill> : null),
});
