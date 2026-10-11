import { describe, expect, it } from 'vitest';
import { lineAt, scheduleLines, wordProgress } from './lyrics';
import type { TimingLine } from './types';

const line = (i: number, start: number, end: number, words: [number, number]): TimingLine => ({
  i, text: `line ${i}`, section: 0, backing: false, start, end, words,
});
const lines = [line(0, 1, 2, [0, 1]), line(1, 2.2, 3, [2, 3]), line(2, 6, 7, [4, 4])];

describe('scheduleLines', () => {
  const schedule = scheduleLines(lines);
  it('never overlaps and keeps every word of a line on screen', () => {
    for (let i = 0; i + 1 < schedule.length; i++) expect(schedule[i].to).toBeLessThanOrEqual(schedule[i + 1].from);
    schedule.forEach((s) => {
      expect(s.from).toBeLessThanOrEqual(s.line.start);
      expect(s.to).toBeGreaterThanOrEqual(s.line.end);
    });
  });
  it('covers every word once when subtitles are on', () => {
    const covered = schedule.flatMap((s) => {
      const [a, b] = s.line.words;
      return Array.from({ length: b - a + 1 }, (_, k) => a + k);
    });
    expect(covered).toEqual([0, 1, 2, 3, 4]);
  });
  it('lineAt finds the line on screen', () => {
    expect(lineAt(schedule, 1.5)!.line.i).toBe(0);
    expect(lineAt(schedule, 4.5)).toBeNull();
  });
});

// Parity with tests/test_video_preview.py::test_line_spans_tight_lines_clamp_and_chain (and the 0.1 s floor case):
// the draft preview (Python) and the studio (TypeScript) must show each line over the same span.
describe('scheduleLines parity with line_spans', () => {
  it('gives the exact spans of the Python tight-lines test', () => {
    const spans = scheduleLines(lines).map((s) => [s.from, s.to]);
    const expected = [[0.4, 2.0], [2.0, 3.4], [5.4, 7.4]];
    spans.forEach(([from, to], k) => {
      expect(from).toBeCloseTo(expected[k][0], 6);
      expect(to).toBeCloseTo(expected[k][1], 6);
    });
  });
  it('keeps the 0.1 s floor for a zero-length line', () => {
    const tight = [line(0, 1, 2, [0, 0]), line(1, 2.05, 2.05, [1, 1]), line(2, 2.3, 3, [2, 2])];
    const [from, to] = scheduleLines(tight).map((s) => [s.from, s.to])[1];
    expect(from).toBeCloseTo(2.0, 6);
    expect(to).toBeCloseTo(2.1, 6);
  });
});

describe('wordProgress', () => {
  it('sweeps 0 → 1 across the word', () => {
    const w = { start: 1, end: 2 };
    expect(wordProgress(w, 0.5)).toBe(0);
    expect(wordProgress(w, 1.25)).toBeCloseTo(0.25);
    expect(wordProgress(w, 3)).toBe(1);
  });
});
