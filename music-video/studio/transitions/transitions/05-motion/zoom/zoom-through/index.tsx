import React from 'react';
import { AbsoluteFill, useVideoConfig } from 'remotion';
import { defineTransition, ease, mix, paramDefaults, seg } from '../../../../src/core';
import meta from './transition.json';

type P = { color: string; x: number; y: number; amount: number; blur: number };

const PEAK = 0.55;

/**
 * A circle in the incoming colour pops open at (x, y). The camera rushes toward it (the old scene
 * scales up around that point) while the circle grows faster, so it fills the frame by PEAK.
 * The new scene, on that colour, lands with a short settle.
 */
export default defineTransition<P>({
  defaults: paramDefaults<P>(meta),
  Exiting: ({ progress, children, params: p }) => {
    const { width: W, height: H } = useVideoConfig();
    if (progress >= 0.75) return <AbsoluteFill style={{ background: p.color }} />;
    const cx = p.x * W;
    const cy = p.y * H;
    const far = Math.max(Math.hypot(cx, cy), Math.hypot(W - cx, cy), Math.hypot(cx, H - cy), Math.hypot(W - cx, H - cy));
    const q = ease.inCubic(seg(progress, 0, PEAK));
    const Z = mix(1, p.amount, q);
    const pop = ease.outBack(seg(progress, 0, 0.22));
    const r = Math.max(0, H * 0.06 * pop + (far * 1.02 - H * 0.06) * ease.inQuint(seg(progress, 0.12, PEAK)));
    return (
      <AbsoluteFill>
        <AbsoluteFill style={{ transform: `scale(${Z})`, transformOrigin: `${cx}px ${cy}px`, filter: `blur(${p.blur * q}px)` }}>{children}</AbsoluteFill>
        <div style={{ position: 'absolute', left: cx - r, top: cy - r, width: r * 2, height: r * 2, borderRadius: '50%', background: p.color }} />
      </AbsoluteFill>
    );
  },
  Entering: ({ progress, children, params: p }) => {
    if (progress < PEAK) return null;
    const q = ease.outCubic(seg(progress, PEAK, 1));
    return (
      <AbsoluteFill style={{ opacity: seg(progress, PEAK, PEAK + 0.12), transform: `scale(${mix(0.86, 1, q)})`, filter: `blur(${p.blur * 0.6 * (1 - q)}px)` }}>
        {children}
      </AbsoluteFill>
    );
  },
});
