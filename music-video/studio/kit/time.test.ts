import { describe, expect, it } from 'vitest';
import { beatAt, bisectRight, energyAt, pulse, sectionAt } from './time';
import type { Section } from './types';

const beats = [0, 0.5, 1, 1.5, 2, 2.5];
const downbeats = [0, 2];

describe('bisectRight', () => {
  it('finds the insertion point after equal values', () => {
    expect(bisectRight(beats, -1)).toBe(0);
    expect(bisectRight(beats, 0)).toBe(1);
    expect(bisectRight(beats, 1.2)).toBe(3);
    expect(bisectRight(beats, 9)).toBe(6);
  });
});

describe('beatAt', () => {
  it('is null before the first beat', () => expect(beatAt([1, 2], [1], 0.5)).toBeNull());
  it('knows downbeats and the beat in the bar', () => {
    const b = beatAt(beats, downbeats, 2)!;
    expect(b).toMatchObject({ index: 4, isDownbeat: true, bar: 1, beatInBar: 0, phase: 0 });
    expect(beatAt(beats, downbeats, 1.5)!).toMatchObject({ isDownbeat: false, bar: 0, beatInBar: 3 });
  });
  it('gives the phase between beats and extrapolates after the last', () => {
    expect(beatAt(beats, downbeats, 0.75)!.phase).toBeCloseTo(0.5);
    const last = beatAt(beats, downbeats, 2.75)!;
    expect(last.next).toBeCloseTo(3);
    expect(last.phase).toBeCloseTo(0.5);
  });
});

describe('sectionAt', () => {
  const sections: Section[] = [
    { id: 'intro', name: 'Intro', start: 0, end: 10, sung: false },
    { id: 'verse-1', name: 'Verse 1', start: 10, end: 30, sung: true },
  ];
  it('returns the section and its progress', () => {
    expect(sectionAt(sections, 20)).toMatchObject({ index: 1, progress: 0.5 });
    expect(sectionAt(sections, 0)!.section.id).toBe('intro');
    expect(sectionAt(sections, 99)!.progress).toBe(1);
    expect(sectionAt([], 3)).toBeNull();
  });
});

describe('energyAt and pulse', () => {
  const energy = { rms: [0, 0.5, 1], low: [0, 0, 0], mid: [1, 1, 1], high: [0.2, 0.2, 0.2] };
  it('reads the frame and clamps at the ends', () => {
    expect(energyAt(energy, 30, 1 / 30).rms).toBe(0.5);
    expect(energyAt(energy, 30, -1).rms).toBe(0);
    expect(energyAt(energy, 30, 99).rms).toBe(1);
  });
  it('pulse is 1 on the beat and decays', () => {
    expect(pulse(0)).toBe(1);
    expect(pulse(0.5)).toBeLessThan(0.1);
  });
});
