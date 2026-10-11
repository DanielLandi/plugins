import React from 'react';
import { AbsoluteFill, useVideoConfig } from 'remotion';
import { clipStyle, defineTransition, ease, fbm1, mix, paramDefaults, polyPath, seg, type Pt } from '../../../../src/core';
import meta from './transition.json';

type P = { background: string; wobble: number; seed: number };

/**
 * The frame is clipped to a wobbling blob (a circle whose radius is pushed by noise around its rim,
 * the noise drifting over time). k = 0 covers the frame; k = 1 is a small blob in the centre.
 */
const Blob: React.FC<{ k: number; t: number; params: P; children: React.ReactNode }> = ({ k, t, params, children }) => {
  const { width: W, height: H } = useVideoConfig();
  const full = Math.hypot(W, H) / 2 / (1 - params.wobble);
  const R = mix(full, H * 0.22, k);
  const amp = params.wobble * Math.min(1, 0.3 + k);
  const pts: Pt[] = [];
  const N = 96;
  for (let i = 0; i < N; i++) {
    const a = (i / N) * Math.PI * 2;
    // Sample the noise around a circle so the rim joins up seamlessly.
    const n = fbm1(Math.cos(a) * 1.3 + 7 + t * 2.2, params.seed) * 0.6 + fbm1(Math.sin(a) * 1.3 + 3 - t * 1.7, params.seed + 3) * 0.6;
    const r = R * (1 + amp * n);
    pts.push([W / 2 + Math.cos(a) * r, H / 2 + Math.sin(a) * r]);
  }
  return (
    <AbsoluteFill style={clipStyle(polyPath(pts))}>
      <AbsoluteFill style={{ transform: `scale(${mix(1, 0.5, k)})` }}>{children}</AbsoluteFill>
    </AbsoluteFill>
  );
};

export default defineTransition<P>({
  defaults: paramDefaults<P>(meta),
  Exiting: ({ progress, children, params }) => (
    <AbsoluteFill style={{ background: params.background }}>
      {progress < 0.6 ? <Blob k={ease.inOutCubic(seg(progress, 0, 0.45))} t={progress} params={params}>{children}</Blob> : null}
    </AbsoluteFill>
  ),
  Entering: ({ progress, children, params }) =>
    progress < 0.4 ? null : (
      <AbsoluteFill style={{ opacity: ease.inOutCubic(seg(progress, 0.4, 0.6)) }}>
        <Blob k={1 - Math.min(1, ease.outBack(seg(progress, 0.55, 1)))} t={progress} params={params}>{children}</Blob>
      </AbsoluteFill>
    ),
});
