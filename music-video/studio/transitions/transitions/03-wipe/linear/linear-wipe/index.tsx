import React from 'react';
import { AbsoluteFill } from 'remotion';
import { defineTransition, ease, paramDefaults, Pass } from '../../../../src/core';
import meta from './transition.json';

type P = { angle: number; softness: number; mode: 'single' | 'split' };

const mask = (image: string): React.CSSProperties => ({ maskImage: image, WebkitMaskImage: image });

export default defineTransition<P>({
  defaults: paramDefaults<P>(meta),
  Exiting: Pass,
  Entering: ({ progress, children, params: { angle, softness: s, mode } }) => {
    const e = ease.inOutCubic(progress);
    let image: string;
    if (mode === 'split') {
      const h = e * (50 + s);
      image = `linear-gradient(${angle}deg, transparent ${50 - h}%, #000 ${50 - h + s}%, #000 ${50 + h - s}%, transparent ${50 + h}%)`;
    } else {
      const pos = e * (100 + s);
      image = `linear-gradient(${angle}deg, #000 ${pos - s}%, transparent ${pos}%)`;
    }
    return <AbsoluteFill style={progress >= 1 ? {} : mask(image)}>{children}</AbsoluteFill>;
  },
});
