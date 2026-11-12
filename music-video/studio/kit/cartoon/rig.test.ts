import { describe, expect, it } from 'vitest';
import { cast } from './cast';
import { MOUTH_KEYS, buildCharacter, mouthPts, type Pose, type Shape } from './rig';

const finite = (shapes: Shape[]) =>
  shapes.every((s) => (s.k === 'dot' ? [s.x, s.y, s.r].every(Number.isFinite) : s.pts.every(([x, y]) => Number.isFinite(x) && Number.isFinite(y))));

const acting: Pose = {
  x: 700, ground: 900, face: 1, sy: 1.3, sx: 0.85, lean: 0.2, look: 0.6, eyeScale: 1.7, brow: 1.2,
  mouth: ['flat', 'shout', 0.4], hatLift: 60, hatSpin: 0.3, smear: 0.6, walk: 1, walkPhase: 0.3,
  armF: { world: [1200, 700], wiggle: 30, wigglePhase: 2, front: true }, armB: { hand: [-60, -80], open: 1 },
};

describe('cartoon rig', () => {
  it('builds the same shapes for the same pose, alone or after other frames', () => {
    const first = buildCharacter(cast.bean, acting);
    for (let i = 0; i < 20; i++) buildCharacter(cast.bean, { ...acting, smear: i / 20, mouth: ['o', 'laugh', i / 20] });
    expect(buildCharacter(cast.bean, acting)).toEqual(first);
  });

  it('draws a whole character from the bare minimum pose', () => {
    for (const c of [cast.bean, cast.plum]) {
      const shapes = buildCharacter(c, { x: 400, ground: 900, face: -1 });
      expect(shapes.length).toBeGreaterThan(15);
      expect(finite(shapes)).toBe(true);
    }
  });

  it('keeps every point finite while acting', () => {
    expect(finite(buildCharacter(cast.bean, acting))).toBe(true);
    expect(finite(buildCharacter(cast.plum, { ...acting, sprout: 0.8, spin: 2, eyesClosed: 1, swirl: 3 }))).toBe(true);
  });

  it('morphs between every pair of mouths', () => {
    for (const a of MOUTH_KEYS) for (const b of MOUTH_KEYS) {
      const pts = mouthPts(a, b, 0.5);
      expect(pts.length).toBeGreaterThan(3);
      expect(pts.every(([x, y]) => Number.isFinite(x) && Number.isFinite(y))).toBe(true);
    }
    expect(mouthPts('smile', 'shout', 0)).toEqual(mouthPts('smile', 'smile', 0));
  });

  it('stands on its feet: the lowest point is the ground, whatever the scale', () => {
    for (const scale of [1, 0.5]) {
      const shapes = buildCharacter(cast.plum, { x: 500, ground: 800, face: 1, scale });
      const ys = shapes.flatMap((s) => (s.k === 'dot' ? [s.y] : s.pts.map((p) => p[1])));
      expect(Math.max(...ys)).toBeGreaterThan(795);
      expect(Math.max(...ys)).toBeLessThan(805);
    }
    const tall = (scale: number) => {
      const ys = buildCharacter(cast.bean, { x: 500, ground: 800, face: 1, scale }).flatMap((s) => (s.k === 'dot' ? [s.y] : s.pts.map((p) => p[1])));
      return 800 - Math.min(...ys);
    };
    expect(tall(0.5)).toBeCloseTo(tall(1) / 2, 0);
  });

  it('faces the other way with face = -1', () => {
    const xs = (face: 1 | -1) => buildCharacter(cast.bean, { x: 500, ground: 800, face, look: 1 })
      .filter((s) => s.k === 'dot').map((s) => (s.k === 'dot' ? s.x : 0));
    const mean = (v: number[]) => v.reduce((s, x) => s + x, 0) / v.length;
    expect(mean(xs(1))).toBeGreaterThan(510);
    expect(mean(xs(-1))).toBeLessThan(490);
  });
});
