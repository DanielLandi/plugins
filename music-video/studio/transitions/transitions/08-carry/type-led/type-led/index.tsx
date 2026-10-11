import React from 'react';
import { AbsoluteFill, useVideoConfig } from 'remotion';
import { defineTransition, ease, mix, paramDefaults, Pass, seg } from '../../../../src/core';
import meta from './transition.json';

type Dir = 'left' | 'right' | 'up' | 'down';
type P = { text: string; direction: Dir; color: string };

const ANGLE: Record<Dir, number> = { right: 90, left: 270, up: 0, down: 180 };
const AXIS: Record<Dir, [number, number]> = { left: [-1, 0], right: [1, 0], up: [0, -1], down: [0, 1] };

/**
 * 0–0.25: the word lands on A. 0.25–0.75: B wipes in behind it, travelling in `direction`.
 * 0.75–1: the word flies off the same way. The word is the one thing that never changes.
 */
export default defineTransition<P>({
  defaults: paramDefaults<P>(meta),
  Exiting: Pass,
  Entering: ({ progress, children, params: { text, direction, color } }) => {
    const { width: W, height: H } = useVideoConfig();
    const land = ease.outBack(seg(progress, 0, 0.25));
    const wipe = ease.inOutCubic(seg(progress, 0.25, 0.75));
    const leave = ease.inCubic(seg(progress, 0.75, 1));
    const pos = wipe * 100;
    const image = `linear-gradient(${ANGLE[direction]}deg, #000 ${pos}%, transparent ${pos}%)`;
    const fontSize = Math.min(H * 0.2, (W * 0.85) / Math.max(1, text.length * 0.6));
    const [ax, ay] = AXIS[direction];
    return (
      <AbsoluteFill>
        <AbsoluteFill style={wipe >= 1 ? {} : { maskImage: image, WebkitMaskImage: image }}>{children}</AbsoluteFill>
        <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center', transform: `translate(${ax * leave * W * 1.1}px, ${ay * leave * H * 1.2}px)` }}>
          <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700, fontSize, letterSpacing: -fontSize * 0.03, color, opacity: Math.min(1, land * 1.5), transform: `scale(${mix(1.6, 1, Math.min(1, land))})` }}>
            {text}
          </div>
        </AbsoluteFill>
      </AbsoluteFill>
    );
  },
});
