import React from 'react';
import { AbsoluteFill, useVideoConfig } from 'remotion';
import { bridged, ease, paramDefaults, seg } from '../../../../src/core';
import meta from './transition.json';

type P = { colors: string[]; ribbons: number; angle: number; hold: number };

/**
 * In a frame rotated by `angle`, each wave is a stack of rounded ribbons that slide in from the left,
 * staggered; the last wave covers everything. Phase out: the top wave slides on out to the right.
 */
export default bridged<P>(paramDefaults<P>(meta), ({ phase, progress, params: { colors, ribbons, angle } }) => {
  const { width: W, height: H } = useVideoConfig();
  const D = Math.hypot(W, H) * 1.15; // side of the rotated square that still covers the frame
  const h = D / ribbons;
  const waves = phase === 'in' ? colors : colors.slice(-1);
  const waveDelay = phase === 'in' ? 0.22 : 0;
  const span = 1 - waveDelay * (waves.length - 1);
  return (
    <AbsoluteFill style={{ overflow: 'hidden' }}>
      <div style={{ position: 'absolute', left: (W - D) / 2, top: (H - D) / 2, width: D, height: D, transform: `rotate(${angle}deg)` }}>
        {waves.map((c, wv) =>
          Array.from({ length: ribbons }, (_, j) => {
            const start = wv * waveDelay + (j / ribbons) * span * 0.45;
            const q = ease.inOutCubic(seg(progress, start, start + span * 0.55));
            // in: from far left (-1) to covering (0). out: from covering (0) to far right (+1).
            const x = phase === 'in' ? (q - 1) * (D + h) : q * (D + h);
            return (
              <div key={`${wv}-${j}`} style={{ position: 'absolute', top: j * h - 1, left: 0, width: D + h, height: h + 2, marginLeft: -h / 2, borderRadius: h / 2, background: c, transform: `translateX(${x}px)` }} />
            );
          }),
        )}
      </div>
    </AbsoluteFill>
  );
});
