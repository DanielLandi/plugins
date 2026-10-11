import type React from 'react';
import type { SongData, SongProps } from './types';

/**
 * What a video exports (as `web`, from its `web.tsx`) to be drawn live on a web page by `music-video web`:
 * the component the page plays (it receives `data`), its frame rate, and its length in frames (or a function of
 * the song data). `words`, when given, are the only sung words the page keeps: no other lyrics ship.
 */
export type WebEntry = {
  Component: React.FC<SongProps>;
  fps: number;
  frames: number | ((data: SongData) => number);
  words?: readonly string[];
};

export const webFrames = (entry: WebEntry, data: SongData) =>
  Math.max(1, Math.round(typeof entry.frames === 'function' ? entry.frames(data) : entry.frames));
