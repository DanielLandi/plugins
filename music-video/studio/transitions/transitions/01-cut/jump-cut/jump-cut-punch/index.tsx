import React from 'react';
import { AbsoluteFill } from 'remotion';
import { defineTransition, paramDefaults } from '../../../../src/core';
import meta from './transition.json';

type P = { scale: number; originX: number; originY: number };

/**
 * Cut to scene B punched in, then (when the transition ends) cut to B's normal framing.
 * The transition's length is how long the punch-in holds.
 */
export default defineTransition<P>({
  defaults: paramDefaults<P>(meta),
  Exiting: () => null,
  Entering: ({ children, params }) => (
    <AbsoluteFill style={{ transform: `scale(${params.scale})`, transformOrigin: `${params.originX * 100}% ${params.originY * 100}%` }}>
      {children}
    </AbsoluteFill>
  ),
});
