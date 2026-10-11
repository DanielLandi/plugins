import React, { createContext, useContext } from 'react';
import { useCurrentFrame, useVideoConfig } from 'remotion';
import { beatAt, energyAt, sectionAt } from './time';
import type { SongData } from './types';

const SongContext = createContext<SongData | null>(null);

export const SongProvider: React.FC<{ data: SongData; children: React.ReactNode }> = ({ data, children }) => (
  <SongContext.Provider value={data}>{children}</SongContext.Provider>
);

export const useSongData = (): SongData => {
  const data = useContext(SongContext);
  if (!data) throw new Error('useSongData() must be used inside <SongProvider>');
  return data;
};

/** Seconds into the song. Inside a scene, <Series> and <Excerpt> keep this equal to song time. */
export const useSongTime = (): number => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return frame / fps;
};

export const useBeat = () => {
  const { analysis } = useSongData();
  return beatAt(analysis.beats, analysis.downbeats, useSongTime());
};

export const useSection = () => sectionAt(useSongData().analysis.sections, useSongTime());

export const useEnergy = () => {
  const { analysis } = useSongData();
  return energyAt(analysis.energy, analysis.fps, useSongTime());
};
