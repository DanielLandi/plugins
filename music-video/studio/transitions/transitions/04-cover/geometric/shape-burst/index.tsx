import React from 'react';
import { AbsoluteFill, useVideoConfig } from 'remotion';
import { bridged, ease, paramDefaults, seg, useSvgId } from '../../../../src/core';
import meta from './transition.json';

type P = { colors: string[]; x: number; y: number; hold: number };

/**
 * Phase in: circles of each colour burst out one after another; the last colour covers the frame.
 * Phase out: over that last colour, the other colours burst again in reverse order, followed by a hole showing scene B.
 */
export default bridged<P>(paramDefaults<P>(meta), ({ phase, progress, params: { colors, x, y } }) => {
  const { width: W, height: H } = useVideoConfig();
  const id = useSvgId('burst');
  const cx = x * W;
  const cy = y * H;
  const R = Math.max(Math.hypot(cx, cy), Math.hypot(W - cx, cy), Math.hypot(cx, H - cy), Math.hypot(W - cx, H - cy)) + 2;
  const n = colors.length;
  const ringR = (k: number, count: number) => {
    const start = (k / count) * 0.45;
    return R * ease.inOutCubic(seg(progress, start, start + 0.55));
  };
  if (phase === 'in') {
    return (
      <AbsoluteFill>
        <svg width={W} height={H}>
          {colors.map((c, k) => <circle key={k} cx={cx} cy={cy} r={ringR(k, n)} fill={c} />)}
        </svg>
      </AbsoluteFill>
    );
  }
  const inner = colors.slice(0, -1).reverse();
  return (
    <AbsoluteFill>
      <svg width={W} height={H}>
        <defs>
          <mask id={id} maskUnits="userSpaceOnUse" x={0} y={0} width={W} height={H}>
            <rect width={W} height={H} fill="#fff" />
            <circle cx={cx} cy={cy} r={ringR(inner.length, inner.length + 1)} fill="#000" />
          </mask>
        </defs>
        <g mask={`url(#${id})`}>
          <rect width={W} height={H} fill={colors[n - 1]} />
          {inner.map((c, k) => <circle key={k} cx={cx} cy={cy} r={ringR(k, inner.length + 1)} fill={c} />)}
        </g>
      </svg>
    </AbsoluteFill>
  );
});
