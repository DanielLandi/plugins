import React from 'react';
import { AbsoluteFill, useVideoConfig } from 'remotion';
import { Defs, defineTransition, paramDefaults, useSvgId } from '../../../../src/core';
import meta from './transition.json';

type P = { maxBlock: number; steps: number };

/**
 * Block size climbs in steps (geometric: 1 → maxBlock) to the middle, where A swaps for B, then falls.
 * The SVG pixelate trick: sample one pixel per block (flood + tile), keep the source colour there, then dilate it over the block.
 */
const blockSize = (p: number, maxBlock: number, steps: number) => {
  const level = Math.round(Math.sin(Math.PI * Math.min(1, Math.max(0, p))) * steps);
  return Math.round(Math.pow(maxBlock, level / steps));
};

const Pixelated: React.FC<{ size: number; children: React.ReactNode }> = ({ size, children }) => {
  const id = useSvgId('pix');
  const { width: W, height: H } = useVideoConfig();
  if (size < 2) return <AbsoluteFill>{children}</AbsoluteFill>;
  const half = Math.floor(size / 2);
  return (
    <AbsoluteFill>
      <Defs>
        <filter id={id} x="0" y="0" width="100%" height="100%">
          {/* Blur first so each block takes the average colour around its sample point, not one pixel. */}
          <feGaussianBlur in="SourceGraphic" stdDeviation={size * 0.4} edgeMode="duplicate" result="avg" />
          <feFlood x={half} y={half} width={1} height={1} />
          <feComposite width={size} height={size} />
          <feTile result="grid" />
          <feComposite in="avg" in2="grid" operator="in" />
          <feMorphology operator="dilate" radius={half} />
        </filter>
      </Defs>
      {/* The last partial row/column of blocks can sample outside the frame; stretching by one block pushes that edge off-screen. */}
      <AbsoluteFill style={{ filter: `url(#${id})`, transform: `scale(${(W + size) / W}, ${(H + size) / H})`, transformOrigin: '0 0' }}>{children}</AbsoluteFill>
    </AbsoluteFill>
  );
};

export default defineTransition<P>({
  defaults: paramDefaults<P>(meta),
  Exiting: ({ progress, children, params }) =>
    progress >= 0.5 ? null : <Pixelated size={blockSize(progress, params.maxBlock, params.steps)}>{children}</Pixelated>,
  Entering: ({ progress, children, params }) =>
    progress < 0.5 ? null : <Pixelated size={blockSize(progress, params.maxBlock, params.steps)}>{children}</Pixelated>,
});
