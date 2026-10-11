import React from 'react';
import { AbsoluteFill, useVideoConfig } from 'remotion';
import { bridged, ease, mix, paramDefaults } from '../../../../src/core';
import meta from './transition.json';

type P = { color: string; y: number; hold: number };

const rgba = (hex: string, a: number) => {
  const n = parseInt(hex.replace('#', ''), 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${a})`;
};

/**
 * A flare travels left → right along a horizontal line: a wide, thin anamorphic streak, a round
 * bloom that grows until it whites out the frame at the swap, and two faint lens ghosts mirrored
 * through the centre. Screen-blended, so it only ever brightens.
 */
export default bridged<P>(paramDefaults<P>(meta), ({ phase, progress, params: { color, y } }) => {
  const { width: W, height: H } = useVideoConfig();
  const k = phase === 'in' ? ease.inCubic(progress) : 1 - ease.outCubic(progress);
  const fx = phase === 'in' ? mix(-0.15 * W, 0.5 * W, ease.outCubic(progress)) : mix(0.5 * W, 1.15 * W, ease.inCubic(progress));
  const fy = y * H;
  const diag = Math.hypot(W, H);
  const r = mix(H * 0.08, diag * 2.2, Math.pow(k, 2.2));
  const ghosts = [0.6, 1.25].map((m) => [W / 2 + (W / 2 - fx) * m, H / 2 + (H / 2 - fy) * m] as const);
  return (
    <AbsoluteFill style={{ mixBlendMode: 'screen' }}>
      <AbsoluteFill style={{ background: `radial-gradient(circle at ${fx}px ${fy}px, #fff 0px, #fff ${r * 0.45}px, ${rgba(color, 0.9)} ${r * 0.7}px, transparent ${r}px)`, opacity: Math.min(1, 0.35 + k) }} />
      <AbsoluteFill style={{ background: `radial-gradient(ellipse ${W * 0.75}px ${H * 0.022 + k * H * 0.05}px at ${fx}px ${fy}px, #fff 0%, ${rgba(color, 0.95)} 30%, transparent 100%)` }} />
      {ghosts.map(([gx, gy], i) => (
        <div key={i} style={{ position: 'absolute', left: gx - H * 0.05 * (i + 1), top: gy - H * 0.05 * (i + 1), width: H * 0.1 * (i + 1), height: H * 0.1 * (i + 1), borderRadius: '50%', background: rgba(color, 0.18), border: `2px solid ${rgba(color, 0.3)}`, opacity: 1 - k }} />
      ))}
    </AbsoluteFill>
  );
});
