import React from 'react';
import { AbsoluteFill } from 'remotion';
import { defineTransition, ease, mix, paramDefaults, seg } from '../../../../src/core';
import meta from './transition.json';

type P = { fromX: number; fromY: number; toX: number; toY: number; scale: number };

const CUT = 0.35;

/** Smallest scale (about the anchor) that keeps the frame covered when the anchor sits at screen point s. */
const coverScale = (sx: number, sy: number, ax: number, ay: number) =>
  Math.max(1, sx / Math.max(ax, 1e-3), (1 - sx) / Math.max(1 - ax, 1e-3), sy / Math.max(ay, 1e-3), (1 - sy) / Math.max(1 - ay, 1e-3));

/**
 * A pushes in toward its anchor; hard cut; B starts with its anchor exactly where A's was and
 * eases back to its own framing. The eye stays on the anchor across the cut.
 */
export default defineTransition<P>({
  defaults: paramDefaults<P>(meta),
  Exiting: ({ progress, children, params: p }) => {
    if (progress >= CUT) return null;
    const s = 1 + 0.12 * p.scale * ease.inCubic(seg(progress, 0, CUT));
    return <AbsoluteFill style={{ transform: `scale(${s})`, transformOrigin: `${p.fromX * 100}% ${p.fromY * 100}%` }}>{children}</AbsoluteFill>;
  },
  Entering: ({ progress, children, params: p }) => {
    if (progress < CUT) return null;
    const q = ease.inOutCubic(seg(progress, CUT, 1));
    // Anchor of B on screen travels from A's anchor to its own place.
    const sx = mix(p.fromX, p.toX, q);
    const sy = mix(p.fromY, p.toY, q);
    const s = Math.max(mix(p.scale * 1.12, 1, q), coverScale(sx, sy, p.toX, p.toY));
    // Translate so that B's anchor lands on (sx, sy), scaling about the anchor.
    const tx = (sx - p.toX) * 100;
    const ty = (sy - p.toY) * 100;
    return (
      <AbsoluteFill style={{ transform: `translate(${tx}%, ${ty}%) scale(${s})`, transformOrigin: `${p.toX * 100}% ${p.toY * 100}%` }}>
        {children}
      </AbsoluteFill>
    );
  },
});
