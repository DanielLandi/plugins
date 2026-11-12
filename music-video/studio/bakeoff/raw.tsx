import React from 'react';
import { AbsoluteFill } from 'remotion';
import { useSongTime, type BakeoffProps } from '@mv/kit';

// The raw engine's take on the bake-off brief (the make skill's references/bakeoff.md): the characters, their motion
// and the set are written here from scratch, in SVG, canvas or three.js (`@mv/kit/three`), with no character library.
// t below is seconds into the window; the song's strongest hit lands at t = hit (6 in the default window).
export const Bakeoff: React.FC<BakeoffProps> = ({ from, hit }) => {
  const t = useSongTime() - from;
  return (
    <AbsoluteFill style={{ background: '#241b3a', color: '#d9d4ff', fontFamily: 'Helvetica, Arial, sans-serif',
      fontSize: 40, alignItems: 'center', justifyContent: 'center' }}>
      raw take: not written yet ({t.toFixed(1)} s, the hit at {hit} s)
    </AbsoluteFill>
  );
};
