import React from 'react';
import { AbsoluteFill, useVideoConfig } from 'remotion';
import { bridged, ease, mix, paramDefaults, seg } from '../../../../src/core';
import meta from './transition.json';

type P = { text: string; color: string; textColor: string; hold: number };

/**
 * Phase in: a badge pops in with a spin (overshoot), then swells to cover the frame.
 * Phase out: the cover shrinks back to the badge, which pops away. The word stays readable throughout.
 */
export default bridged<P>(paramDefaults<P>(meta), ({ phase, progress, params: { text, color, textColor } }) => {
  const { width: W, height: H } = useVideoConfig();
  const badge = H * 0.24;
  const cover = Math.hypot(W, H) / 2 + 4;
  let r: number;
  let spin: number;
  if (phase === 'in') {
    const pop = ease.outBack(seg(progress, 0, 0.45));
    const grow = ease.inCubic(seg(progress, 0.45, 1));
    r = mix(badge * pop, cover, grow);
    spin = mix(-200, 0, ease.outCubic(seg(progress, 0, 0.6)));
  } else {
    const shrink = ease.outCubic(seg(progress, 0, 0.55));
    const away = ease.inBack(seg(progress, 0.55, 1));
    r = mix(cover, badge, shrink) * (1 - away);
    spin = mix(0, 200, ease.inCubic(seg(progress, 0.4, 1)));
  }
  const fontSize = Math.min(badge * 0.62, (badge * 3.2) / Math.max(1, text.length));
  return (
    <AbsoluteFill>
      <svg width={W} height={H}>
        <circle cx={W / 2} cy={H / 2} r={Math.max(0, r)} fill={color} />
      </svg>
      <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center', transform: `rotate(${spin}deg) scale(${Math.min(1, r / badge)})` }}>
        <div style={{ color: textColor, fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700, fontSize, letterSpacing: -fontSize * 0.02 }}>{text}</div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
});
