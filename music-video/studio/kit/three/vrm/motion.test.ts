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

describe('eases.smooth (continuous motion)', () => {
  const h = 1e-4;
  const d1 = (e: (t: number) => number, t: number) => (e(t + h) - e(t - h)) / (2 * h);
  const d2 = (e: (t: number) => number, t: number) => (e(t + h) - 2 * e(t) + e(t - h)) / (h * h);
  // One-sided second derivatives just left and right of x (a jump in acceleration shows as a gap between them).
  const left2 = (e: (t: number) => number, x: number) => d2(e, x - 3 * h);
  const right2 = (e: (t: number) => number, x: number) => d2(e, x + 3 * h);

  it('has no jump in acceleration at its midpoint, unlike inOut', () => {
    expect(Math.abs(left2(eases.smooth, 0.5) - right2(eases.smooth, 0.5))).toBeLessThan(0.1);
    // The cubic in-out jumps from +12 to -12 there (kept as it is: existing videos depend on it).
    expect(Math.abs(left2(eases.inOut, 0.5) - right2(eases.inOut, 0.5))).toBeGreaterThan(20);
  });
  it('starts and ends flat: no speed and no acceleration at 0 and 1', () => {
    for (const x of [0, 1]) {
      const inside = x === 0 ? 2 * h : 1 - 2 * h;
      expect(Math.abs(d1(eases.smooth, inside))).toBeLessThan(1e-3);
      expect(Math.abs(d2(eases.smooth, inside))).toBeLessThan(1e-1);
    }
    expect(eases.smooth(0)).toBe(0);
    expect(eases.smooth(1)).toBe(1);
    expect(eases.smooth(0.5)).toBeCloseTo(0.5, 12);
  });
  it('is smooth everywhere inside (no kink in acceleration)', () => {
    for (let x = 0.05; x < 0.96; x += 0.05) {
      expect(Math.abs(left2(eases.smooth, x) - right2(eases.smooth, x))).toBeLessThan(0.1);
    }
  });
  it('leaves the existing eases exactly as they were', () => {
    expect(eases.inOut(0.3)).toBe(4 * 0.3 * 0.3 * 0.3);
    expect(eases.inOut(0.7)).toBe(1 - Math.pow(-2 * 0.7 + 2, 3) / 2);
    expect(eases.sine(0.3)).toBe(-(Math.cos(Math.PI * 0.3) - 1) / 2);
    expect(track(1.5, [[1, 0], [2, 10]])).toBe(10 * eases.inOut(0.5));
  });
});
