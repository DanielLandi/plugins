import React from 'react';
import { AbsoluteFill, useVideoConfig } from 'remotion';
import { defineTransition, ease, mix, paramDefaults, seg } from '../../../../src/core';
import meta from './transition.json';

type P = { x: number; y: number; corner: number };

/**
 * A rounded window grows from (x, y) to the full frame (its corners easing square at the end).
 * The new scene inside settles from a slight zoom; the old scene recedes a touch behind it.
 */
export default defineTransition<P>({
  defaults: paramDefaults<P>(meta),
  Exiting: ({ progress, children }) => (
    <AbsoluteFill style={{ transform: `scale(${mix(1, 0.94, ease.inOutCubic(progress))})`, filter: `brightness(${mix(1, 0.75, progress)})` }}>{children}</AbsoluteFill>
  ),
  Entering: ({ progress, children, params: { x, y, corner } }) => {
    const { width: W, height: H } = useVideoConfig();
    const e = ease.inOutQuint(progress);
    const startW = W * 0.12;
    const startH = H * 0.12;
    const w = mix(startW, W, e);
    const h = mix(startH, H, e);
    // Centre travels from (x, y) to the frame centre so the window ends exactly on the frame.
    const cx = mix(x * W, W / 2, e);
    const cy = mix(y * H, H / 2, e);
    const r = corner * H * (1 - ease.inCubic(seg(progress, 0.6, 1)));
    const inset = `inset(${cy - h / 2}px ${W - (cx + w / 2)}px ${H - (cy + h / 2)}px ${cx - w / 2}px round ${r}px)`;
    return (
      <AbsoluteFill style={{ clipPath: progress >= 1 ? undefined : inset }}>
        <AbsoluteFill style={{ transform: `scale(${mix(1.15, 1, ease.outCubic(progress))})` }}>{children}</AbsoluteFill>
      </AbsoluteFill>
    );
  },
});
