import type { TimingLine } from './types';

// Same rules as music-video preview, so the timing preview matches the video.
export const LEAD_S = 0.6;
export const TAIL_S = 0.4;

export type ScheduledLine = { line: TimingLine; from: number; to: number };

export const scheduleLines = (lines: readonly TimingLine[]): ScheduledLine[] => {
  const out: ScheduledLine[] = [];
  let prevTo = 0;
  lines.forEach((line, n) => {
    const from = Math.max(line.start - LEAD_S, prevTo);
    let to = line.end + TAIL_S;
    const next = lines[n + 1];
    if (next) to = Math.min(to, Math.max(line.end, next.start - LEAD_S));
    to = Math.max(to, from + 0.1);
    out.push({ line, from, to });
    prevTo = to;
  });
  return out;
};

export const lineAt = (schedule: readonly ScheduledLine[], t: number) =>
  schedule.find((s) => s.from <= t && t < s.to) ?? null;

export const wordProgress = (word: { start: number; end: number }, t: number) =>
  t <= word.start ? 0 : t >= word.end ? 1 : (t - word.start) / (word.end - word.start);
