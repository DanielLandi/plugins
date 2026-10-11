import React from 'react';
import { AbsoluteFill } from 'remotion';
import { pulse, useBeat, useSongTime } from '@mv/kit';

export const Verse: React.FC = () => {
  const beat = useBeat();
  const t = useSongTime();
  const k = beat ? pulse(beat.phase) : 0;
  return (
    <AbsoluteFill style={{ background: '#13294b' }}>
      <div style={{ position: 'absolute', left: `${42 + 3 * Math.sin(t)}%`, top: '30%', width: '16%', aspectRatio: '1',
        borderRadius: '50%', background: '#f5c542', transform: `scale(${1 + 0.2 * k})` }} />
    </AbsoluteFill>
  );
};
