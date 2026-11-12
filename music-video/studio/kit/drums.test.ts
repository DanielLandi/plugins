import { describe, expect, it } from 'vitest';
import { jolt, joltAt, lastHit } from './drums';
import type { DrumHit } from './types';

const hits: DrumHit[] = [
  { t: 1, kind: 'kick', strength: 1 },
  { t: 1.5, kind: 'snare', strength: 0.8 },
  { t: 2, kind: 'kick', strength: 0.5 },
];

describe('lastHit', () => {
  it('finds the latest hit of a kind at or before t', () => {
    expect(lastHit(hits, 0.5)).toBeNull();
    expect(lastHit(hits, 1.7, ['kick'])).toMatchObject({ t: 1, since: expect.closeTo(0.7, 6) });
    expect(lastHit(hits, 1.7)).toMatchObject({ t: 1.5, kind: 'snare' });
    expect(lastHit(hits, 2, ['kick'])!.strength).toBe(0.5);
  });
});

describe('jolt', () => {
  it('starts at rest, wiggles, and is gone within half a second', () => {
    expect(jolt(0)).toBe(0);
    expect(Math.abs(jolt(0.03))).toBeGreaterThan(0.3);
    expect(Math.abs(jolt(0.25))).toBeLessThan(0.1);
    expect(jolt(0.6)).toBe(0);
    expect(jolt(-0.1)).toBe(0);
  });
});

describe('joltAt', () => {
  it('is zero unless the video jolts', () => {
    expect(joltAt(false, hits, 1.03)).toBe(0);
    expect(Math.abs(joltAt(true, hits, 1.03))).toBeGreaterThan(0.3);
  });
  it('scales by the hit strength and is zero with no drums measured', () => {
    expect(Math.abs(joltAt(true, hits, 2.03))).toBeCloseTo(Math.abs(jolt(0.03)) * 0.5, 6);
    expect(joltAt(true, undefined, 1.03)).toBe(0);
  });
});
