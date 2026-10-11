import React from 'react';
import { AbsoluteFill } from 'remotion';
import { defineTransition, ease, paramDefaults, seg } from '../../../../src/core';
import meta from './transition.json';

type P = { blur: number; zoom: number };

export default defineTransition<P>({
  defaults: paramDefaults<P>(meta),
  Exiting: ({ progress, children, params }) => {
    const k = ease.inCubic(seg(progress, 0, 0.55));
    return <AbsoluteFill style={{ filter: `blur(${params.blur * k}px)`, transform: `scale(${1 + params.zoom * k})` }}>{children}</AbsoluteFill>;
  },
  Entering: ({ progress, children, params }) => {
    if (progress < 0.38) return null;
    const k = 1 - ease.outCubic(seg(progress, 0.45, 1));
    return (
      <AbsoluteFill style={{ opacity: ease.inOutCubic(seg(progress, 0.38, 0.6)), filter: `blur(${params.blur * k}px)`, transform: `scale(${1 + params.zoom * k})` }}>
        {children}
      </AbsoluteFill>
    );
  },
});
