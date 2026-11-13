import { describe, expect, it } from 'vitest';
import { eases, ramp, seeded, swell, track } from './motion';

describe('track', () => {
  const keys: [number, number][] = [[1, 10], [2, 20], [4, 0]];
  it('holds before the first key and after the last', () => {
    expect(track(0, keys)).toBe(10);
    expect(track(9, keys)).toBe(0);
  });
  it('hits every key value exactly', () => {
    expect(track(1, keys)).toBe(10);
    expect(track(2, keys)).toBe(20);
    expect(track(4, keys)).toBe(0);
  });
  it('eases into a key with that key’s ease', () => {
    expect(track(1.5, [[1, 0], [2, 10, eases.linear]])).toBeCloseTo(5);
    expect(track(1.25, [[1, 0], [2, 10, eases.in]])).toBeCloseTo(10 * 0.25 ** 3);
    expect(track(1.5, [[1, 0], [2, 10]])).toBeCloseTo(5); // inOut by default: symmetric
  });
});

describe('ramp and swell', () => {
  it('ramp is 0 at a and 1 at b, clamped outside', () => {
    expect(ramp(1, 1, 3)).toBe(0);
    expect(ramp(3, 1, 3)).toBe(1);
    expect(ramp(-5, 1, 3)).toBe(0);
    expect(ramp(9, 1, 3)).toBe(1);
  });
  it('swell rises, holds and falls', () => {
    expect(swell(0, 1, 2, 3, 4)).toBe(0);
    expect(swell(2, 1, 2, 3, 4)).toBe(1);
    expect(swell(3, 1, 2, 3, 4)).toBe(1);
    expect(swell(4, 1, 2, 3, 4)).toBe(0);
  });
  it('every ease runs from 0 to 1', () => {
    for (const e of Object.values(eases)) {
      expect(e(0)).toBeCloseTo(0);
      expect(e(1)).toBeCloseTo(1);
    }
  });
});

describe('seeded', () => {
  it('repeats for a seed and stays in [0, 1)', () => {
    const a = seeded(7), b = seeded(7);
    const xs = Array.from({ length: 5 }, a);
    expect(Array.from({ length: 5 }, b)).toEqual(xs);
    for (const x of xs) expect(x >= 0 && x < 1).toBe(true);
    expect(Array.from({ length: 5 }, seeded(8))).not.toEqual(xs);
  });
});
