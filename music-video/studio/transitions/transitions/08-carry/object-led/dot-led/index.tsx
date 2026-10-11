import React from 'react';
import { AbsoluteFill, useVideoConfig } from 'remotion';
import { defineTransition, ease, mix, paramDefaults, Pass, seg } from '../../../../src/core';
import meta from './transition.json';

type P = { color: string; size: number; toX: number; toY: number };

/**
 * 0–0.6: a dot bounces in from the left (three bounces, landing exactly on the target).
 * 0.6–1: scene B opens as a circle from the dot; the dot's colour becomes a thinning rim.
 */
export default defineTransition<P>({
  defaults: paramDefaults<P>(meta),
  Exiting: Pass,
  Entering: ({ progress, children, params: { color, size, toX, toY } }) => {
    const { width: W, height: H } = useVideoConfig();
    const r0 = (size * H) / 2;
    const tx = toX * W;
    const ty = toY * H;
    const t = seg(progress, 0, 0.6);
    const x = mix(-r0 * 2, tx, ease.outCubic(t));
    const y = ty - Math.abs(Math.sin(Math.PI * 3 * t)) * Math.pow(1 - t, 1.4) * H * 0.45;
    // Squash a little on each impact.
    const impact = 1 - Math.abs(Math.sin(Math.PI * 3 * t));
    const squash = t < 1 ? 1 + 0.25 * Math.pow(impact, 8) * (1 - t) : 1;
    const far = Math.max(Math.hypot(tx, ty), Math.hypot(W - tx, ty), Math.hypot(tx, H - ty), Math.hypot(W - tx, H - ty));
    const q = ease.inOutCubic(seg(progress, 0.6, 1));
    const r = mix(r0, far + 4, q);
    const rim = r0 * 0.6 * (1 - q);
    return (
      <AbsoluteFill>
        {q > 0 ? (
          <>
            <div style={{ position: 'absolute', left: tx - r - rim, top: ty - r - rim, width: (r + rim) * 2, height: (r + rim) * 2, borderRadius: '50%', background: color }} />
            <AbsoluteFill style={{ clipPath: `circle(${r}px at ${tx}px ${ty}px)` }}>{children}</AbsoluteFill>
          </>
        ) : (
          <div style={{ position: 'absolute', left: x - r0 * squash, top: y - r0 / squash, width: r0 * 2 * squash, height: (r0 * 2) / squash, borderRadius: '50%', background: color }} />
        )}
      </AbsoluteFill>
    );
  },
});
