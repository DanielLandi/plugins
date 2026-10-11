import React from 'react';
import { AbsoluteFill } from 'remotion';
import { Defs, defineTransition, ease, paramDefaults, useSvgId } from '../../../../src/core';
import meta from './transition.json';

type Dir = 'left' | 'right' | 'up' | 'down';
type P = { direction: Dir; blur: number };

const AXIS: Record<Dir, [number, number]> = { left: [-1, 0], right: [1, 0], up: [0, -1], down: [0, 1] };

/** A push on an exponential curve with directional blur that peaks with the speed. */
const Side: React.FC<{ progress: number; offset: number; params: P; children: React.ReactNode }> = ({ progress, offset, params, children }) => {
  const id = useSvgId('whip');
  const [ax, ay] = AXIS[params.direction];
  const k = ease.inOutExpo(progress) + offset;
  // Speed of an expo in-out curve peaks in the middle; a raised sine follows it closely.
  const b = params.blur * Math.pow(Math.sin(Math.PI * progress), 4);
  const std = ax !== 0 ? `${b} 0` : `0 ${b}`;
  return (
    <AbsoluteFill style={{ transform: `translate(${ax * k * 100}%, ${ay * k * 100}%)` }}>
      <Defs>
        <filter id={id} x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation={std} edgeMode="duplicate" />
        </filter>
      </Defs>
      <AbsoluteFill style={{ filter: b > 0.5 ? `url(#${id})` : undefined }}>{children}</AbsoluteFill>
    </AbsoluteFill>
  );
};

export default defineTransition<P>({
  defaults: paramDefaults<P>(meta),
  Exiting: ({ progress, children, params }) => <Side progress={progress} offset={0} params={params}>{children}</Side>,
  Entering: ({ progress, children, params }) => <Side progress={progress} offset={-1} params={params}>{children}</Side>,
});
