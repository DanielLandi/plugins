import { describe, expect, it } from 'vitest';
import { cameraAt, type CameraKey } from './camera';

const keys: CameraKey[] = [
  { t: 1, pos: [0, 0, 0], look: [0, 0, -1] },
  { t: 2, pos: [10, 0, 0], look: [10, 0, -1] },
  { t: 3, pos: [10, 10, 0], look: [10, 10, -1], fov: 30 },
  { t: 4, pos: [50, 0, 0], look: [50, 0, -1], ease: 'cut' },
];

describe('cameraAt', () => {
  it('holds the first and last keys outside the range', () => {
    expect(cameraAt(keys, 0).pos.toArray()).toEqual([0, 0, 0]);
    expect(cameraAt(keys, 9).pos.toArray()).toEqual([50, 0, 0]);
  });

  it('passes exactly through every key', () => {
    for (const k of keys.slice(0, 3)) {
      const p = cameraAt(keys, k.t).pos.toArray();
      p.forEach((v, i) => expect(v).toBeCloseTo(k.pos[i], 6));
    }
  });

  it('eases in and out: slow at the ends of a segment, fast in the middle', () => {
    const x = (t: number) => cameraAt(keys, t).pos.x;
    expect(x(1.1) - x(1)).toBeLessThan(x(1.55) - x(1.45));
  });

  it('interpolates fov from the default', () => {
    expect(cameraAt(keys, 2.5, 50).fov).toBeCloseTo(40, 6);
  });

  it('a cut key jumps at its time instead of moving', () => {
    expect(cameraAt(keys, 3.99).pos.toArray()).toEqual([10, 10, 0]);
    expect(cameraAt(keys, 4).pos.toArray()).toEqual([50, 0, 0]);
  });

  it('is a pure function of time', () => {
    expect(cameraAt(keys, 1.37).pos.toArray()).toEqual(cameraAt(keys, 1.37).pos.toArray());
  });
});
