import React from 'react';
import { AbsoluteFill } from 'remotion';
import { pulse, useBeat, useSongTime } from '@mv/kit';

export const Chorus: React.FC = () => {
  const beat = useBeat();
  const t = useSongTime();
  const k = beat ? pulse(beat.phase) : 0;
  return (
    <AbsoluteFill style={{ background: '#5b1a3a' }}>
      <div style={{ position: 'absolute', left: '40%', top: '25%', width: '20%', aspectRatio: '1', border: '12px solid #f5c542',
        transform: `rotate(${t * 40}deg) scale(${1 + 0.15 * k})` }} />
    </AbsoluteFill>
  );
};
