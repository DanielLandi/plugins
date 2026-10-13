import * as THREE from 'three';
import { describe, expect, it } from 'vitest';
import { arcPts, bevelBox, cardGeometry, FINISH_DEFAULTS, frameGeometry, type Profile, wavyPlane } from './finish';

// The geometry is pure three.js; the post, shadows and canvas textures need a browser and are covered by renders.

const bounds = (g: THREE.BufferGeometry) => {
  const p = g.attributes.position as THREE.BufferAttribute;
  for (let i = 0; i < p.array.length; i++) expect(Number.isFinite(p.array[i])).toBe(true);
  g.computeBoundingBox();
  return g.boundingBox!;
};
const vec3 = (v: readonly number[]) => {
  expect(v).toHaveLength(3);
  v.forEach((c) => expect(Number.isFinite(c)).toBe(true));
};

describe('FINISH_DEFAULTS', () => {
  it('has every look value, finite, with five halation rings', () => {
    for (const k of ['bloomGain', 'threshold', 'radius', 'grain', 'grainSize', 'vignette', 'contrast', 'lift', 'soft', 'fringe'] as const) {
      expect(Number.isFinite(FINISH_DEFAULTS[k])).toBe(true);
      expect(FINISH_DEFAULTS[k]).toBeGreaterThanOrEqual(0);
    }
    expect(FINISH_DEFAULTS.halation).toHaveLength(5);
    FINISH_DEFAULTS.halation.forEach(vec3);
    vec3(FINISH_DEFAULTS.warmLift);
    vec3(FINISH_DEFAULTS.coolLift);
  });

  it('is overridable by spreading', () => {
    const look = { ...FINISH_DEFAULTS, grain: 0.08 };
    expect(look.grain).toBe(0.08);
    expect(look.vignette).toBe(FINISH_DEFAULTS.vignette);
  });
});

describe('cardGeometry', () => {
  it('keeps the card\'s size and lifts only toward the viewer, most at the chosen corner', () => {
    const [w, h, lift, thick] = [0.15, 0.1, 0.05, 0.0035];
    for (const corner of [-1, 1] as const) {
      const b = bounds(cardGeometry(w, h, corner, lift, thick));
      expect(b.min.x).toBeCloseTo(-w / 2, 6);
      expect(b.max.x).toBeCloseTo(w / 2, 6);
      expect(b.min.y).toBeCloseTo(-h / 2, 6);
      expect(b.max.y).toBeCloseTo(h / 2, 6);
      expect(b.min.z).toBeCloseTo(-thick / 2, 6);
      expect(b.max.z).toBeGreaterThan(lift * 0.9);
      expect(b.max.z).toBeLessThan(thick / 2 + lift + 0.007);
      // the highest point is at the lifted lower corner
      const p = cardGeometry(w, h, corner, lift, thick).attributes.position as THREE.BufferAttribute;
      let top = 0;
      for (let i = 1; i < p.count; i++) if (p.getZ(i) > p.getZ(top)) top = i;
      expect(Math.sign(p.getX(top))).toBe(corner);
      expect(p.getY(top)).toBeCloseTo(-h / 2, 6);
    }
  });

  it('is cached', () => {
    expect(cardGeometry(0.1, 0.1, 1)).toBe(cardGeometry(0.1, 0.1, 1));
  });
});

describe('wavyPlane', () => {
  it('stays within its size and amplitude', () => {
    const [w, h, amp] = [0.4, 0.6, 0.003];
    const b = bounds(wavyPlane(w, h, amp, 2));
    expect(b.min.x).toBeCloseTo(-w / 2, 6);
    expect(b.max.x).toBeCloseTo(w / 2, 6);
    expect(b.min.y).toBeCloseTo(-h / 2, 6);
    expect(b.max.y).toBeCloseTo(h / 2, 6);
    expect(b.min.z).toBeGreaterThanOrEqual(-amp - 1e-9);
    expect(b.max.z).toBeLessThanOrEqual(amp + 1e-9);
    expect(b.max.z - b.min.z).toBeGreaterThan(amp * 0.5);
  });
});

describe('bevelBox', () => {
  it('rounds a box to its exact size', () => {
    const g = bevelBox([0.4, 0.2, 0.1])!;
    expect(g).not.toBeNull();
    const b = bounds(g);
    expect(b.max.x - b.min.x).toBeCloseTo(0.4, 5);
    expect(b.max.y - b.min.y).toBeCloseTo(0.2, 5);
    expect(b.max.z - b.min.z).toBeCloseTo(0.1, 5);
    expect(bevelBox([0.4, 0.2, 0.1])).toBe(g);
  });

  it('leaves boxes too thin to round to a plain box', () => {
    expect(bevelBox([1, 1, 0.005])).toBeNull();
  });
});

describe('frameGeometry', () => {
  const profile: Profile = [
    [0, 0, 0.6],
    ...arcPts(0.02, 0.01, 0.01, Math.PI, Math.PI / 2, 4, (k) => 0.7 + 0.3 * k),
    [0.05, 0.015, 1],
    [0.06, 0.005, 0.5],
  ];

  it('arcPts runs along its arc, ends included', () => {
    const a = arcPts(0, 0, 1, 0, Math.PI / 2, 4, (k) => k);
    expect(a).toHaveLength(5);
    expect(a[0][0]).toBeCloseTo(1, 9);
    expect(a[4][1]).toBeCloseTo(1, 9);
    a.forEach(([u, z]) => expect(Math.hypot(u, z)).toBeCloseTo(1, 9));
    expect(a.map((p) => p[2])).toEqual([0, 0.25, 0.5, 0.75, 1]);
  });

  it('sweeps the profile round the outer rectangle, mitred, with colours and uvs', () => {
    const [W, H] = [1.2, 0.8];
    const g = frameGeometry('test-frame', W, H, profile);
    const b = bounds(g);
    expect(b.min.x).toBeCloseTo(-W / 2, 6);
    expect(b.max.x).toBeCloseTo(W / 2, 6);
    expect(b.min.y).toBeCloseTo(-H / 2, 6);
    expect(b.max.y).toBeCloseTo(H / 2, 6);
    expect(b.min.z).toBeCloseTo(0, 6);
    expect(b.max.z).toBeCloseTo(Math.max(...profile.map((p) => p[1])), 6);
    // four lengths, two vertices per profile point, two triangles per profile step
    expect(g.attributes.position.count).toBe(4 * 2 * profile.length);
    expect(g.index!.count).toBe(4 * 6 * (profile.length - 1));
    expect(g.attributes.color.count).toBe(g.attributes.position.count);
    expect(g.attributes.uv.count).toBe(g.attributes.position.count);
    // nothing inside the frame's opening
    const p = g.attributes.position as THREE.BufferAttribute;
    const inset = profile[profile.length - 1][0];
    for (let i = 0; i < p.count; i++) {
      const inside = Math.abs(p.getX(i)) < W / 2 - inset - 1e-6 && Math.abs(p.getY(i)) < H / 2 - inset - 1e-6;
      expect(inside).toBe(false);
    }
    expect(frameGeometry('test-frame', W, H, profile)).toBe(g);
  });
});
