import React from 'react';
import { AbsoluteFill, useVideoConfig } from 'remotion';
import { Defs, defineTransition, ease, paramDefaults, Pass, seg, useSvgId } from '../../../../src/core';
import meta from './transition.json';

type P = { from: string; to: string; color: string; panel: string };

/**
 * Gooey text morph: both words are blurred in proportion to how "absent" they are, then a sharp
 * alpha threshold turns the overlapping blur into one liquid shape. A band behind the word opens
 * and closes; scene B crossfades in behind it.
 */
export default defineTransition<P>({
  defaults: paramDefaults<P>(meta),
  Exiting: Pass,
  Entering: ({ progress, children, params: { from, to, color, panel } }) => {
    const { height: H } = useVideoConfig();
    const id = useSvgId('goo');
    const band = ease.outCubic(seg(progress, 0, 0.18)) * (1 - ease.inCubic(seg(progress, 0.82, 1)));
    const f = ease.inOutCubic(seg(progress, 0.3, 0.7));
    const blurOf = (v: number) => (v >= 1 ? 0 : Math.min(8 / Math.max(v, 1e-3) - 8, 80));
    const fontSize = H * 0.16;
    const word = (text: string, v: number) => (
      <div style={{ position: 'absolute', width: '100%', textAlign: 'center', fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700, fontSize, letterSpacing: -fontSize * 0.03, color, filter: `blur(${blurOf(v)}px)`, opacity: Math.pow(v, 0.4) }}>
        {text}
      </div>
    );
    return (
      <AbsoluteFill>
        <AbsoluteFill style={{ opacity: ease.inOutCubic(seg(progress, 0.35, 0.65)) }}>{children}</AbsoluteFill>
        <Defs>
          <filter id={id}>
            <feColorMatrix type="matrix" values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 255 -140" />
          </filter>
        </Defs>
        <AbsoluteFill style={{ justifyContent: 'center' }}>
          <div style={{ height: H * 0.3, background: panel, transform: `scaleY(${band})` }} />
        </AbsoluteFill>
        <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center', filter: `url(#${id})`, opacity: band }}>
          <div style={{ position: 'relative', width: '100%', height: fontSize * 1.2, display: 'flex', alignItems: 'center' }}>
            {word(from, 1 - f)}
            {word(to, f)}
          </div>
        </AbsoluteFill>
      </AbsoluteFill>
    );
  },
});
