import React from 'react';
import { Sequence, useVideoConfig } from 'remotion';
import { FPS } from './data';

/** Plays the song's video from `from` seconds: frame 0 of the excerpt is that moment of the full video. */
export const Excerpt: React.FC<{ from: number; children: React.ReactNode }> = ({ from, children }) => {
  const { fps } = useVideoConfig();
  // Round at the base rate, then scale: a sub-frame render (fps a multiple of FPS) starts exactly where the 30 fps one does.
  const k = Math.max(1, Math.round(fps / FPS));
  return <Sequence from={-Math.round(from * FPS) * k}>{children}</Sequence>;
};
