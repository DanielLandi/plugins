import React from 'react';
import { AbsoluteFill } from 'remotion';
import { Defs, defineTransition, ease, paramDefaults, seg, useSvgId } from '../../../../src/core';
import meta from './transition.json';

type P = { strength: number; scale: number; seed: number };

/** Turbulence displacement that swells to a peak at the middle; B crossfades in under the strongest ripple. */
const Warped: React.FC<{ progress: number; params: P; children: React.ReactNode; opacity?: number }> = ({ progress, params, children, opacity = 1 }) => {
  const id = useSvgId('warp');
  const k = Math.pow(Math.sin(Math.PI * progress), 1.4);
  const bf = params.scale * (1 + 0.25 * progress);
  return (
    <AbsoluteFill style={{ opacity }}>
      <Defs>
        <filter id={id} x="-10%" y="-10%" width="120%" height="120%" colorInterpolationFilters="sRGB">
          <feTurbulence type="fractalNoise" baseFrequency={`${bf} ${bf * 1.6}`} numOctaves={2} seed={params.seed} result="n" />
          <feDisplacementMap in="SourceGraphic" in2="n" scale={params.strength * k} xChannelSelector="R" yChannelSelector="G" />
        </filter>
      </Defs>
      <AbsoluteFill style={{ filter: k > 0.01 ? `url(#${id})` : undefined, transform: `scale(${1 + 0.08 * k})` }}>{children}</AbsoluteFill>
    </AbsoluteFill>
  );
};

export default defineTransition<P>({
  defaults: paramDefaults<P>(meta),
  Exiting: ({ progress, children, params }) => <Warped progress={progress} params={params}>{children}</Warped>,
  Entering: ({ progress, children, params }) => <Warped progress={progress} params={params} opacity={ease.inOutCubic(seg(progress, 0.3, 0.7))}>{children}</Warped>,
});
