import React from 'react';
import { AbsoluteFill, useVideoConfig } from 'remotion';
import { bridged, ease, paramDefaults, rand, seg, useSvgId } from '../../../../src/core';
import meta from './transition.json';

type P = { color: string; passes: number; seed: number; hold: number };

/**
 * One continuous zigzag stroke, thick enough that its passes overlap, drawn with a dash.
 * Phase in draws it; phase out erases it from its start. A turbulence displacement makes the
 * edges rough like a dry brush. A flat fill fades in at the very end so the hold is fully covered.
 */
export default bridged<P>(paramDefaults<P>(meta), ({ phase, progress, params: { color, passes, seed } }) => {
  const { width: W, height: H } = useVideoConfig();
  const id = useSvgId('brush');
  const band = H / passes;
  const width = band * 1.7;
  const over = width * 0.6;
  let d = '';
  for (let k = 0; k < passes; k++) {
    const y = (k + 0.5) * band + (rand(seed, k) - 0.5) * band * 0.3;
    const [x0, x1] = k % 2 ? [W + over, -over] : [-over, W + over];
    const tilt = (rand(seed, 't', k) - 0.5) * band * 0.5;
    d += k === 0 ? `M${x0} ${y - tilt}` : `L${x0} ${y - tilt}`;
    d += `C${(x0 * 2 + x1) / 3} ${y - tilt * 0.3} ${(x0 + x1 * 2) / 3} ${y + tilt * 0.3} ${x1} ${y + tilt}`;
  }
  const e = ease.inOutCubic(progress);
  const dash = phase === 'in' ? { strokeDasharray: `${e} 2`, strokeDashoffset: 0 } : { strokeDasharray: `${1 - e} 2`, strokeDashoffset: -e };
  const flat = phase === 'in' ? seg(progress, 0.9, 1) : 1 - seg(progress, 0, 0.1);
  return (
    <AbsoluteFill>
      <svg width={W} height={H}>
        <defs>
          <filter id={id} x="-10%" y="-10%" width="120%" height="120%">
            <feTurbulence type="fractalNoise" baseFrequency="0.003 0.06" numOctaves={3} seed={seed} result="n" />
            <feDisplacementMap in="SourceGraphic" in2="n" scale={band * 0.35} xChannelSelector="R" yChannelSelector="G" />
          </filter>
        </defs>
        <rect width={W} height={H} fill={color} opacity={flat} />
        <path d={d} pathLength={1} fill="none" stroke={color} strokeWidth={width} strokeLinecap="round" strokeLinejoin="round" filter={`url(#${id})`} style={dash} />
      </svg>
    </AbsoluteFill>
  );
});
