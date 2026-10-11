import React from 'react';
import { AbsoluteFill } from 'remotion';
import { pulse, SafeArea, useBeat, useSection } from '@mv/kit';
import { palette } from '../look';

/** Stands in until the storyboard's scenes exist: the section name and a dot on every beat. */
export const Placeholder: React.FC = () => {
  const beat = useBeat();
  const section = useSection();
  const k = beat ? pulse(beat.phase) : 0;
  return (
    <AbsoluteFill style={{ background: palette.background }}>
      <SafeArea style={{ color: palette.neutral2, fontFamily: 'Helvetica, Arial, sans-serif', fontSize: 48 }}>
        {section?.section.name}
      </SafeArea>
      <div style={{ position: 'absolute', right: '6%', top: '8%', width: 40, height: 40, borderRadius: 20,
        background: beat?.isDownbeat ? palette.accent : palette.neutral, opacity: 0.2 + 0.8 * k }} />
    </AbsoluteFill>
  );
};
