import React from 'react';
import { AbsoluteFill, useVideoConfig } from 'remotion';
import { defineTransition, ease, mix, paramDefaults, seg } from '../../../../src/core';
import meta from './transition.json';

type P = { color: string; shape: 'square' | 'circle'; turns: number; roll: number; counterClockwise: boolean; blur: number };

const PEAK = 0.55; // the shape covers the frame here

/** Scale a W×H frame needs, rotated by `deg`, to still cover the screen. */
const coverScale = (deg: number, W: number, H: number) => {
  const a = (Math.abs(deg) % 180) * (Math.PI / 180);
  return Math.max(Math.abs(Math.cos(a)) + (W / H) * Math.abs(Math.sin(a)), Math.abs(Math.cos(a)) + (H / W) * Math.abs(Math.sin(a)));
};

/**
 * The incoming colour arrives as a shape: it spins in at the centre and grows (accelerating) until it
 * covers the frame at PEAK, while the camera rolls the old scene along with it. The new scene, whose
 * background is that colour, then spins into place over it.
 */
export default defineTransition<P>({
  defaults: paramDefaults<P>(meta),
  Exiting: ({ progress, children, params: p }) => {
    const { width: W, height: H } = useVideoConfig();
    if (progress >= 0.75) return <AbsoluteFill style={{ background: p.color }} />;
    const dir = p.counterClockwise ? -1 : 1;
    const q = ease.inCubic(seg(progress, 0, PEAK));
    const roll = dir * p.roll * q;
    const diag = Math.hypot(W, H);
    const size = mix(0, diag * 1.02, ease.inQuint(seg(progress, 0.05, PEAK)) * 0.97 + 0.03 * ease.outBack(seg(progress, 0, 0.25)));
    const spin = dir * p.turns * 360 * ease.inOutCubic(seg(progress, 0, PEAK));
    return (
      <AbsoluteFill>
        <AbsoluteFill style={{ transform: `rotate(${roll}deg) scale(${coverScale(roll, W, H) * (1 + 0.1 * q)})`, filter: `blur(${p.blur * q * 0.5}px)` }}>{children}</AbsoluteFill>
        <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
          <div style={{ width: size, height: size, background: p.color, borderRadius: p.shape === 'circle' ? '50%' : size * 0.08, transform: `rotate(${spin}deg)`, filter: `blur(${p.blur * Math.sin(Math.PI * seg(progress, 0, PEAK)) * 0.3}px)` }} />
        </AbsoluteFill>
      </AbsoluteFill>
    );
  },
  Entering: ({ progress, children, params: p }) => {
    const { width: W, height: H } = useVideoConfig();
    if (progress < PEAK) return null;
    const dir = p.counterClockwise ? -1 : 1;
    const q = ease.outCubic(seg(progress, PEAK, 1));
    const angle = -dir * p.roll * 1.5 * (1 - q);
    return (
      <AbsoluteFill style={{ opacity: seg(progress, PEAK, PEAK + 0.1), transform: `rotate(${angle}deg) scale(${coverScale(angle, W, H) * mix(1.15, 1, q)})`, filter: `blur(${p.blur * (1 - q)}px)` }}>
        {children}
      </AbsoluteFill>
    );
  },
});
