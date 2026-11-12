import { useSongData, useSongTime } from './SongContext';
import type { DrumHit, DrumKind } from './types';

// Drum hits measured by `music-video analyze` (analysis.json `drums`): data, never motion of their own. A scene keys
// a jolt to them only when the video's jolts answer is yes (look.ts `jolts`, asked at step 5); with no jolts (the
// default), nothing kicks or shakes on the beat.

/** The latest hit (of the given kinds) at or before t, with the seconds since it; null before the first. */
export const lastHit = (hits: readonly DrumHit[], t: number, kinds?: readonly DrumKind[]) => {
  for (let i = hits.length - 1; i >= 0; i--) {
    const h = hits[i];
    if (h.t <= t && (!kinds || kinds.includes(h.kind))) return { ...h, since: t - h.t };
  }
  return null;
};

/** A small jolt after a hit, s seconds ago: two quick wiggles from rest, gone within about a fifth of a second. */
export const jolt = (s: number) => (s <= 0 || s > 0.5 ? 0 : Math.exp(-11 * s) * Math.sin(52 * s));

/**
 * The jolt at song time t, scaled by the hit's strength, or 0 when the video does not jolt (`enabled` is look.ts
 * `jolts`) or no drums were measured. Offset the camera by a few thousandths of its distance to the subject along
 * its right and up axes, and roll it a few thousandths of a radian, times this; softer on a framing to be read.
 */
export const joltAt = (enabled: boolean, hits: readonly DrumHit[] | undefined, t: number,
  kinds: readonly DrumKind[] = ['kick']) => {
  if (!enabled || !hits) return 0;
  const h = lastHit(hits, t, kinds);
  return h ? jolt(h.since) * h.strength : 0;
};

/** joltAt on the song clock: `useJolt(jolts)` with `jolts` from the video's look.ts. */
export const useJolt = (enabled: boolean, kinds: readonly DrumKind[] = ['kick']) =>
  joltAt(enabled, useSongData().analysis.drums?.hits, useSongTime(), kinds);
