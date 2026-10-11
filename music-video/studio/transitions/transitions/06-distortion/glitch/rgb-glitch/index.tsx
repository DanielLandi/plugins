import React from 'react';
import { AbsoluteFill } from 'remotion';
import { Defs, defineTransition, paramDefaults, rand, useSvgId } from '../../../../src/core';
import meta from './transition.json';

type P = { strength: number; seed: number };

/**
 * Per frame: horizontal noise bands shift rows sideways (displacement map), then the red and blue
 * channels are pulled apart. Strength follows a jittery envelope that peaks at the swap, and around
 * the swap the picture flickers between A and B for a few random frames.
 */
const envelope = (p: number) => Math.pow(Math.sin(Math.PI * p), 1.5);
const frameOf = (p: number, d: number) => Math.round(p * d);
const showB = (p: number, d: number, seed: number) => {
  const flicker = p > 0.3 && p < 0.7 && rand(seed, 'flick', frameOf(p, d)) < 0.4;
  return (p >= 0.5) !== flicker;
};

const Glitched: React.FC<{ progress: number; duration: number; params: P; children: React.ReactNode }> = ({ progress, duration, params, children }) => {
  const id = useSvgId('glitch');
  const f = frameOf(progress, duration);
  const k = params.strength * envelope(progress) * (0.4 + 0.9 * rand(params.seed, 'amp', f));
  if (k < 0.02) return <AbsoluteFill>{children}</AbsoluteFill>;
  const shift = 26 * k;
  return (
    <AbsoluteFill>
      <Defs>
        <filter id={id} x="-5%" y="-5%" width="110%" height="110%" colorInterpolationFilters="sRGB">
          <feTurbulence type="fractalNoise" baseFrequency={`0 ${0.008 + 0.03 * rand(params.seed, 'bf', f)}`} numOctaves={1} seed={params.seed * 97 + f} result="noise" />
          <feComponentTransfer in="noise" result="bands">
            <feFuncR type="discrete" tableValues="0.5 0.5 0.15 0.5 0.85 0.5 0.5 0.3" />
            <feFuncG type="discrete" tableValues="0.5" />
          </feComponentTransfer>
          <feDisplacementMap in="SourceGraphic" in2="bands" scale={220 * k} xChannelSelector="R" yChannelSelector="G" result="d" />
          <feColorMatrix in="d" type="matrix" values="1 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 1 0" result="r" />
          <feOffset in="r" dx={shift} dy={0} result="r2" />
          <feColorMatrix in="d" type="matrix" values="0 0 0 0 0  0 1 0 0 0  0 0 0 0 0  0 0 0 1 0" result="g" />
          <feColorMatrix in="d" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 1 0 0  0 0 0 1 0" result="b" />
          <feOffset in="b" dx={-shift} dy={0} result="b2" />
          <feBlend in="r2" in2="g" mode="screen" result="rg" />
          <feBlend in="rg" in2="b2" mode="screen" />
        </filter>
      </Defs>
      <AbsoluteFill style={{ filter: `url(#${id})` }}>{children}</AbsoluteFill>
    </AbsoluteFill>
  );
};

export default defineTransition<P>({
  defaults: paramDefaults<P>(meta),
  Exiting: ({ progress, children, params, durationInFrames }) =>
    showB(progress, durationInFrames, params.seed) ? null : <Glitched progress={progress} duration={durationInFrames} params={params}>{children}</Glitched>,
  Entering: ({ progress, children, params, durationInFrames }) =>
    showB(progress, durationInFrames, params.seed) ? <Glitched progress={progress} duration={durationInFrames} params={params}>{children}</Glitched> : null,
});
