import React from 'react';
import { AbsoluteFill, useVideoConfig } from 'remotion';
import { Defs, defineTransition, ease, paramDefaults, Pass, seg, useSvgId } from '../../../../src/core';
import meta from './transition.json';

type P = { text: string; focus: number; background: string };

/**
 * A background colour fades over scene A with a word cut into it that shows scene B (an SVG mask);
 * the word then zooms toward `focus` while the background fades away, so B always ends fully shown.
 */
export default defineTransition<P>({
  defaults: paramDefaults<P>(meta),
  Exiting: Pass,
  Entering: ({ progress, children, params: { text, focus, background } }) => {
    const { width: W, height: H } = useVideoConfig();
    const id = useSvgId('textmask');
    if (progress >= 1) return <AbsoluteFill>{children}</AbsoluteFill>;
    const appear = ease.outCubic(seg(progress, 0, 0.18));
    const zoom = ease.inCubic(seg(progress, 0.42, 1));
    const fontSize = Math.min(H * 0.42, (W * 0.86) / Math.max(1, text.length * 0.62));
    const textWidth = text.length * fontSize * 0.62;
    const fx = W / 2 + (focus - 0.5) * textWidth;
    const fy = H / 2;
    const scale = (0.9 + 0.1 * appear + 0.06 * seg(progress, 0.18, 0.42)) * Math.pow(60, zoom);
    // Layers, bottom to top: background over A; B in full (fades in at the end); B through the word.
    const outside = ease.inOutCubic(seg(progress, 0.72, 1));
    return (
      <AbsoluteFill>
        <Defs>
          <mask id={id} maskUnits="userSpaceOnUse" x={0} y={0} width={W} height={H}>
            <g transform={`translate(${fx} ${fy}) scale(${scale}) translate(${-fx} ${-fy})`}>
              <text x={W / 2} y={H / 2} textAnchor="middle" dominantBaseline="central" fill="#fff"
                style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700, fontSize, letterSpacing: -fontSize * 0.03 }}>
                {text}
              </text>
            </g>
          </mask>
        </Defs>
        <AbsoluteFill style={{ background, opacity: appear }} />
        <AbsoluteFill style={{ opacity: outside }}>{children}</AbsoluteFill>
        <AbsoluteFill style={{ maskImage: `url(#${id})`, WebkitMaskImage: `url(#${id})`, opacity: appear }}>{children}</AbsoluteFill>
      </AbsoluteFill>
    );
  },
});
