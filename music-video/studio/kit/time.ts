import type { Energy, Section } from './types';

export const clamp = (x: number, lo = 0, hi = 1) => Math.min(hi, Math.max(lo, x));

/** Index of the first element greater than t (xs sorted ascending). */
export const bisectRight = (xs: readonly number[], t: number): number => {
  let lo = 0;
  let hi = xs.length;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (xs[mid] <= t) lo = mid + 1;
    else hi = mid;
  }
  return lo;
};

export type BeatState = {
  index: number; time: number; next: number; phase: number; isDownbeat: boolean; bar: number; beatInBar: number;
};

const SAME = 0.02;

export const beatAt = (beats: readonly number[], downbeats: readonly number[], t: number): BeatState | null => {
  const index = bisectRight(beats, t) - 1;
  if (index < 0) return null;
  const time = beats[index];
  const step = index + 1 < beats.length ? beats[index + 1] - time : index > 0 ? time - beats[index - 1] : 0.5;
  const bar = bisectRight(downbeats, time + SAME) - 1;
  const isDownbeat = bar >= 0 && Math.abs(downbeats[bar] - time) <= SAME;
  const beatInBar = bar < 0 ? index : index - bisectRight(beats, downbeats[bar] - SAME);
  return { index, time, next: time + step, phase: clamp((t - time) / step), isDownbeat, bar, beatInBar };
};

export const sectionAt = (sections: readonly Section[], t: number) => {
  if (!sections.length) return null;
  const index = Math.max(0, bisectRight(sections.map((s) => s.start), t) - 1);
  const section = sections[index];
  return { section, index, progress: clamp((t - section.start) / Math.max(section.end - section.start, 1e-6)) };
};

export const energyAt = (energy: Energy, fps: number, t: number) => {
  const i = clamp(Math.floor(t * fps), 0, energy.rms.length - 1);
  return { rms: energy.rms[i], low: energy.low[i], mid: energy.mid[i], high: energy.high[i] };
};

/** 1 on the beat, decaying towards the next one: multiply a size or brightness by it. */
export const pulse = (phase: number, sharpness = 6) => Math.exp(-sharpness * phase);
