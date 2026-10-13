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

  it('never runs backwards between keys: a held aim, then a move, dense keys', () => {
    // The aim holds still for a second (keys every 0.1 s), then moves on; the position drifts, then moves fast.
    const dense: CameraKey[] = [];
    for (let i = 0; i <= 40; i++) {
      const t = i * 0.1;
      const lookX = t < 1 ? 0 : (t - 1) ** 2;
      const posX = t < 2 ? t * 0.05 : 0.1 + (t - 2) * 3;
      dense.push({ t, pos: [posX, 0, 5], look: [lookX, 0, 0], ease: 'linear' });
    }
    let [prevPos, prevLook] = [-Infinity, -Infinity];
    for (let t = 0; t <= 4; t += 1 / 240) {
      const c = cameraAt(dense, t);
      expect(c.pos.x).toBeGreaterThanOrEqual(prevPos - 1e-9);
      expect(c.look.x).toBeGreaterThanOrEqual(prevLook - 1e-9);
      if (t < 1) expect(c.look.x).toBeCloseTo(0, 9); // the hold is still
      [prevPos, prevLook] = [c.pos.x, c.look.x];
    }
  });

  it('bends smoothly through a corner without overshooting either axis', () => {
    const corner: CameraKey[] = [
      { t: 0, pos: [0, 0, 0], look: [0, 0, -1], ease: 'linear' },
      { t: 1, pos: [4, 0, 0], look: [0, 0, -1], ease: 'linear' },
      { t: 2, pos: [4, 4, 0], look: [0, 0, -1], ease: 'linear' },
    ];
    for (let t = 0; t <= 2; t += 0.01) {
      const p = cameraAt(corner, t).pos;
      expect(p.x).toBeGreaterThanOrEqual(-1e-9);
      expect(p.x).toBeLessThanOrEqual(4 + 1e-9);
      expect(p.y).toBeGreaterThanOrEqual(-1e-9);
    }
  });
});
