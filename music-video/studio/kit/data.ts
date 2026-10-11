import { staticFile, type CalculateMetadataFunction } from 'remotion';
import type { Analysis, SongData, SongProps, Timing } from './types';

export const FPS = 30;

const fetchJson = async <T,>(name: string): Promise<T> => {
  const res = await fetch(staticFile(name));
  if (!res.ok) throw new Error(`${name} is missing from this video's public folder: run music-video analyze first`);
  return (await res.json()) as T;
};

/** An instrumental has no words: no timing.json, so it gets empty timing over the song's length. */
export const emptyTiming = (duration: number): Timing => ({ version: 1, duration, words: [], lines: [], sections: [] });

export const loadSongData = async (): Promise<SongData> => {
  const analysis = await fetchJson<Analysis>('analysis.json');
  const res = await fetch(staticFile('timing.json'));
  const timing = res.ok ? ((await res.json()) as Timing) : emptyTiming(analysis.duration);
  return { timing, analysis };
};

/**
 * calculateMetadata for a song composition: loads the data once and sizes the composition to the song or a range.
 * `subframes` (a prop) multiplies the frame rate, for motion blur.
 */
export const songMetadata =
  <P extends SongProps>(range?: { from: number; to: number }): CalculateMetadataFunction<P> =>
  async ({ props }) => {
    const data = props.data ?? (await loadSongData());
    const seconds = range ? range.to - range.from : data.analysis.duration;
    // Scenes read time in seconds (frame / fps), so a higher rate renders the same motion in finer steps.
    const fps = FPS * Math.max(1, Math.round(props.subframes ?? 1));
    return { durationInFrames: Math.max(1, Math.ceil(seconds * fps)), fps, props: { ...props, data } };
  };
