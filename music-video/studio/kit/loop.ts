import type { CutSpec } from './series';
import type { SongData } from './types';
import { normWord } from './words';

/**
 * An endless loop over song time: `from` to `to`, with the last `fade` seconds crossfading into the picture from
 * just before `from`, so the frame after the last one is the first one again. Seconds.
 */
export type LoopSpan = { from: number; to: number; fade: number };

/**
 * Frame offsets for a loop: the main picture is a <Sequence from={mainFrom}>; the seam is a
 * <Sequence from={seamAt} durationInFrames={seamFrames}> holding a <Sequence from={seamFrom}> picture.
 */
export type LoopLayout = { frames: number; mainFrom: number; seamAt: number; seamFrames: number; seamFrom: number };

export const loopLayout = (span: LoopSpan, fps: number): LoopLayout => {
  const start = Math.round(span.from * fps);
  const end = Math.round(span.to * fps);
  const lead = Math.round((span.from - span.fade) * fps);
  const seamFrames = start - lead;
  const frames = end - start;
  if (!(seamFrames > 0)) throw new Error(`The loop fade must be positive, not ${span.fade} s`);
  if (lead < 0) throw new Error(`The loop starts at ${span.from} s: too early for a ${span.fade} s fade`);
  if (seamFrames * 2 > frames) throw new Error(`A ${frames}-frame loop is too short for a ${seamFrames}-frame seam`);
  return { frames, mainFrom: -start, seamAt: frames - seamFrames, seamFrames, seamFrom: -lead };
};

/** The song frames drawn at loop frame `f`: the main picture's, and the seam's (null outside the seam). */
export const loopSongFrames = (L: LoopLayout, f: number) => ({
  main: f - L.mainFrom,
  seam: f >= L.seamAt ? f - L.seamAt - L.seamFrom : null,
});

/** Opacity of the seam's picture on its i-th frame: rises smoothly and is fully opaque on the last one. */
export const seamOpacity = (i: number, seamFrames: number) => {
  const k = Math.min(1, Math.max(0, (i + 1) / seamFrames));
  return k * k * (3 - 2 * k);
};

/** cuts.ts counts frames at 30 fps; at another rate each cut keeps its length in seconds. */
export const scaleCuts = (cuts: readonly CutSpec[], fps: number): CutSpec[] =>
  cuts.map((c) => ({ ...c, frames: Math.max(1, Math.round((c.frames * fps) / 30)) }));

// Matched the same way scenes look words up (findWord): see words.ts.
const norm = normWord;

/**
 * The song data a silent loop draws from: no beats, downbeats or hits (the music it plays under has its own
 * tempo), and of the lyrics only the sung words scenes look up by name (findWord), with no lines, so no lyrics ship.
 */
export const loopScore = (data: SongData, words: readonly string[]): SongData => {
  const keep = new Set(words.map(norm));
  return {
    timing: { ...data.timing, words: data.timing.words.filter((w) => keep.has(norm(w.text))), lines: [], sections: [] },
    analysis: { ...data.analysis, beats: [], downbeats: [], hits: [] },
  };
};
