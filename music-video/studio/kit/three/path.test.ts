import * as THREE from 'three';
import { describe, expect, it } from 'vitest';
import type { Vec3 } from './camera';
import { makePath, pathQuaternion, ride } from './path';

const dist = (a: Vec3, b: Vec3) => Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
const angle = (a: Vec3, b: Vec3) => Math.acos(Math.min(1, a[0] * b[0] + a[1] * b[1] + a[2] * b[2]));

// A winding downhill road: uneven spacing, turns both ways, a dip.
const ROAD: Vec3[] = [[0, 10, 0], [4, 9.5, 18], [-6, 8, 35], [-2, 7.2, 47], [12, 5, 60], [15, 4.5, 82], [8, 2, 100]];

describe('makePath', () => {
  const road = makePath(ROAD);

  it('starts and ends on the first and last points and passes through every point', () => {
    expect(dist(road.at(0).pos, ROAD[0])).toBeLessThan(1e-9);
    expect(dist(road.at(road.length).pos, ROAD[ROAD.length - 1])).toBeLessThan(1e-6);
    for (const p of ROAD) {
      let best = Infinity;
      for (let s = 0; s <= road.length; s += 0.01) best = Math.min(best, dist(road.at(s).pos, p));
      expect(best).toBeLessThan(0.01);
    }
  });

  it('is parametrised by arc length: equal steps in s are equal steps along the curve', () => {
    const n = 2000;
    const step = road.length / n;
    for (let i = 0; i < n; i++) {
      const d = dist(road.at(i * step).pos, road.at((i + 1) * step).pos);
      expect(Math.abs(d - step) / step).toBeLessThan(1e-3); // a chord is a hair shorter than its arc
    }
    // ...and the length is the curve's real length (a fine polyline of it).
    let poly = 0;
    for (let i = 0; i < 20000; i++) poly += dist(road.at((i * road.length) / 20000).pos, road.at(((i + 1) * road.length) / 20000).pos);
    expect(Math.abs(poly - road.length)).toBeLessThan(1e-3);
  });

  it('has a unit tangent along the motion, continuous through every point, and continuous curvature (no lean twitch)', () => {
    const eps = 1e-3;
    for (let s = 0.5; s < road.length - 0.5; s += 0.37) {
      const p = road.at(s);
      expect(Math.hypot(...p.tangent)).toBeCloseTo(1, 9);
      const ahead = road.at(s + eps).pos;
      const dir: Vec3 = [(ahead[0] - p.pos[0]) / eps, (ahead[1] - p.pos[1]) / eps, (ahead[2] - p.pos[2]) / eps];
      expect(angle(p.tangent, dir)).toBeLessThan(1e-3);
    }
    // Through the control points (where a Catmull-Rom curve's curvature jumps), tangent and curvature stay continuous.
    for (const s of road.knots.slice(1, -1)) {
      const a = road.at(s - eps), b = road.at(s + eps);
      expect(angle(a.tangent, b.tangent)).toBeLessThan(1e-3);
      expect(Math.abs(a.curvature - b.curvature)).toBeLessThan(1e-3);
    }
  });

  it('clamps an open path at its ends', () => {
    expect(road.at(-5).pos).toEqual(road.at(0).pos);
    expect(road.at(road.length + 5).pos).toEqual(road.at(road.length).pos);
  });

  it('gives yaw (0 = +z, the kit’s convention) and pitch (+ climbing)', () => {
    const flat = makePath([[0, 0, 0], [0, 0, 10]]);
    expect(flat.at(5).yaw).toBeCloseTo(0, 9);
    expect(flat.at(5).pitch).toBeCloseTo(0, 9);
    const east = makePath([[0, 0, 0], [10, 10, 0]]);
    expect(east.at(3).yaw).toBeCloseTo(Math.PI / 2, 9);
    expect(east.at(3).pitch).toBeCloseTo(Math.PI / 4, 9);
  });
});

describe('a closed path round a circle', () => {
  const R = 20;
  const ring: Vec3[] = Array.from({ length: 32 }, (_, i) => {
    const a = (i / 32) * Math.PI * 2;
    return [R * Math.sin(a), 0, R * Math.cos(a)];
  });
  const loop = makePath(ring, { closed: true });

  it('is as long as the circle and wraps round', () => {
    expect(loop.length).toBeCloseTo(2 * Math.PI * R, 1);
    expect(dist(loop.at(loop.length + 3).pos, loop.at(3).pos)).toBeLessThan(1e-6);
    expect(dist(loop.at(-3).pos, loop.at(loop.length - 3).pos)).toBeLessThan(1e-6);
    expect(angle(loop.at(loop.length - 1e-4).tangent, loop.at(1e-4).tangent)).toBeLessThan(1e-3);
  });

  it('turning left (yaw increasing) has positive curvature 1/R, and banks into the turn like a rider', () => {
    for (let s = 0; s < loop.length; s += 5) {
      expect(loop.at(s).curvature).toBeCloseTo(1 / R, 3);
      // tan(bank) = v²κ/g: 10 m/s on a 20 m radius leans about 27°.
      expect(loop.bank(s, 10)).toBeCloseTo(Math.atan(100 / (R * 9.81)), 2);
    }
    const right = makePath([...ring].reverse(), { closed: true });
    expect(right.at(10).curvature).toBeCloseTo(-1 / R, 3);
    expect(right.bank(10, 10)).toBeLessThan(0);
    // A soft limit: never past max, and close to the raw lean when the raw lean is small.
    expect(Math.abs(loop.bank(10, 30, { max: 0.5 }))).toBeLessThan(0.5);
    expect(loop.bank(10, 3, { max: 0.5 })).toBeCloseTo(loop.bank(10, 3), 2);
  });

  it('smooths the bank over a window, and a straight has none', () => {
    const line = makePath([[0, 0, 0], [0, 0, 50]]);
    expect(line.bank(20, 15)).toBe(0);
    expect(loop.bank(10, 10, { window: 3 })).toBeCloseTo(loop.bank(10, 10), 2);
  });
});

describe('ride', () => {
  const road = makePath(ROAD);
  it('moves at the given speed from a start time, and stops at the end of an open path', () => {
    expect(ride(road, 2, 5, { start: 2 }).s).toBe(0);
    expect(ride(road, 4, 5, { start: 2 }).s).toBeCloseTo(10, 9);
    expect(ride(road, 4, 5, { start: 2, s0: 7 }).s).toBeCloseTo(17, 9);
    expect(ride(road, 400, 5).s).toBe(road.length);
    const r = ride(road, 3, 8);
    expect(r.bank).toBe(road.bank(r.s, 8));
  });
  it('is a pure function of time (any frame alone equals the same frame in sequence)', () => {
    expect(ride(road, 3.7, 6)).toEqual(ride(road, 3.7, 6));
  });
});

describe('pathQuaternion', () => {
  it('turns something modelled facing +z to face along the path, nose up a slope, leaning into the turn', () => {
    const climb = makePath([[0, 0, 0], [10, 10, 0]]);
    const p = climb.at(4);
    const fwd = new THREE.Vector3(0, 0, 1).applyQuaternion(pathQuaternion(p));
    expect(fwd.distanceTo(new THREE.Vector3(...p.tangent))).toBeLessThan(1e-9);
    // Bank > 0 leans left: the model's up tips towards its own left (+x, the kit's convention).
    const flat = makePath([[0, 0, 0], [0, 0, 10]]).at(5);
    const up = new THREE.Vector3(0, 1, 0).applyQuaternion(pathQuaternion(flat, 0.3));
    expect(up.x).toBeCloseTo(Math.sin(0.3), 9);
    expect(up.y).toBeCloseTo(Math.cos(0.3), 9);
  });
});
