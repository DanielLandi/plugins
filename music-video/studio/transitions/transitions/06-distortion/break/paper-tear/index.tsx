import React, { useMemo } from 'react';
import { AbsoluteFill, useVideoConfig } from 'remotion';
import { clipStyle, defineTransition, ease, fbm1, paramDefaults, polyPath, type Pt } from '../../../../src/core';
import meta from './transition.json';

type P = { paper: string; roughness: number; seed: number };

/**
 * A ragged tear runs top to bottom. Each half is a copy of A clipped to its side, with a strip of
 * paper (the torn fibres) showing along the tear. The halves pull apart and tilt away.
 */
export default defineTransition<P>({
  defaults: paramDefaults<P>(meta),
  exitingOnTop: true,
  Exiting: ({ progress, children, params: { paper, roughness, seed } }) => {
    const { width: W, height: H } = useVideoConfig();
    const { tear, fringeL, fringeR } = useMemo(() => {
      const N = 90;
      const tear: Pt[] = [];
      const fringeL: Pt[] = [];
      const fringeR: Pt[] = [];
      for (let k = 0; k <= N; k++) {
        const y = (k / N) * H;
        const x = W / 2 + fbm1(k * 0.35, seed) * roughness * W + fbm1(k * 2.3, seed + 5) * roughness * W * 0.15;
        const f = 4 + Math.abs(fbm1(k * 1.7, seed + 9)) * 16;
        tear.push([x, y]);
        fringeL.push([x + f, y]);
        fringeR.push([x - f, y]);
      }
      return { tear, fringeL, fringeR };
    }, [W, H, roughness, seed]);
    if (progress >= 1) return null;
    const q = ease.inOutCubic(progress);
    const pieces = [
      { clip: polyPath([[0, 0], ...tear, [0, H]]), fringe: polyPath([[0, 0], ...fringeL, [0, H]]), move: `translateX(${-q * 62}%) rotate(${-q * 7}deg)`, origin: '0% 100%' },
      { clip: polyPath([[W, 0], ...tear, [W, H]]), fringe: polyPath([[W, 0], ...fringeR, [W, H]]), move: `translateX(${q * 62}%) rotate(${q * 7}deg)`, origin: '100% 100%' },
    ];
    return (
      <AbsoluteFill>
        {pieces.map((p, i) => (
          <AbsoluteFill key={i} style={{ transform: p.move, transformOrigin: p.origin, filter: q > 0 ? 'drop-shadow(0 12px 18px rgba(0,0,0,0.35))' : undefined }}>
            <AbsoluteFill style={{ ...clipStyle(p.fringe), background: paper }} />
            <AbsoluteFill style={clipStyle(p.clip)}>{children}</AbsoluteFill>
          </AbsoluteFill>
        ))}
      </AbsoluteFill>
    );
  },
  Entering: ({ children }) => <AbsoluteFill>{children}</AbsoluteFill>,
});
