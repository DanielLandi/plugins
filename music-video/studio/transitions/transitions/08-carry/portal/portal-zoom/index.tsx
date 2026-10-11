import React from 'react';
import { AbsoluteFill, useVideoConfig } from 'remotion';
import { defineTransition, ease, mix, paramDefaults, seg } from '../../../../src/core';
import meta from './transition.json';

type P = { x: number; y: number; radius: number; ring: string };

/**
 * 0–0.3: a round portal pops open in A, showing B inside (smaller, for parallax).
 * 0.3–1: the camera flies into it: A scales up around the portal centre by Z, the portal grows by Z,
 * and B inside settles to full size, so at the end B fills the frame untransformed.
 */
const useZoom = (progress: number, p: P) => {
  const { width: W, height: H } = useVideoConfig();
  const cx = p.x * W;
  const cy = p.y * H;
  const r0 = p.radius * H;
  const far = Math.max(Math.hypot(cx, cy), Math.hypot(W - cx, cy), Math.hypot(cx, H - cy), Math.hypot(W - cx, H - cy));
  const open = ease.outBack(seg(progress, 0, 0.3));
  const q = ease.inCubic(seg(progress, 0.3, 1));
  const Z = mix(1, (far * 1.08) / r0, q);
  return { cx, cy, r: r0 * Math.max(0, open) * Z, Z, q };
};

export default defineTransition<P>({
  defaults: paramDefaults<P>(meta),
  Exiting: ({ progress, children, params }) => {
    const { cx, cy, Z } = useZoom(progress, params);
    return <AbsoluteFill style={{ transform: `scale(${Z})`, transformOrigin: `${cx}px ${cy}px` }}>{children}</AbsoluteFill>;
  },
  Entering: ({ progress, children, params }) => {
    const { cx, cy, r, Z, q } = useZoom(progress, params);
    if (r <= 0) return null;
    const rim = Math.max(0, 14 * Z * (1 - q));
    return (
      <AbsoluteFill>
        <AbsoluteFill style={{ clipPath: `circle(${r}px at ${cx}px ${cy}px)` }}>
          <AbsoluteFill style={{ transform: `scale(${mix(0.55, 1, q)})`, transformOrigin: `${cx}px ${cy}px` }}>{children}</AbsoluteFill>
        </AbsoluteFill>
        {rim > 0.5 ? (
          <div style={{ position: 'absolute', left: cx - r, top: cy - r, width: r * 2, height: r * 2, borderRadius: '50%', boxSizing: 'border-box', border: `${rim}px solid ${params.ring}`, boxShadow: `0 0 ${rim * 3}px rgba(0,0,0,0.35)` }} />
        ) : null}
      </AbsoluteFill>
    );
  },
});
