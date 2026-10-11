import React from 'react';
import { AbsoluteFill } from 'remotion';
import { defineTransition, ease, paramDefaults, Pass } from '../../../../src/core';
import meta from './transition.json';

type P = { curve: 'linear' | 'smooth' };

export default defineTransition<P>({
  defaults: paramDefaults<P>(meta),
  Exiting: Pass,
  Entering: ({ progress, children, params }) => (
    <AbsoluteFill style={{ opacity: params.curve === 'smooth' ? ease.inOutCubic(progress) : progress }}>{children}</AbsoluteFill>
  ),
});
