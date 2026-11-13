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

describe('review fixes (#34)', () => {
  const pts = (s: Shape) => (s.k === 'dot' ? [[s.x, s.y] as [number, number]] : s.pts);

  it('a smear trails behind the character by default, whichever way it faces', () => {
    // > 0: the body reaches further right of x than left of it (the trail is on the right)
    const trail = (face: 1 | -1, smearDir?: 1 | -1) => {
      const shapes = buildCharacter(cast.bean, { x: 600, ground: 900, face, smear: 1, ...(smearDir ? { smearDir } : {}) });
      const outline = shapes.find((s) => s.k === 'blob' && s.fill === 'none'); // the body's ink outline
      const xs = pts(outline!).map((p) => p[0]);
      return Math.max(...xs) - 600 - (600 - Math.min(...xs));
    };
    expect(trail(1)).toBeLessThan(-100); // faces right: trails left
    expect(trail(-1)).toBeGreaterThan(100); // faces left: trails right
    // smearDir is the way it moves on screen: the trail goes the other way, whichever way it faces
    expect(trail(1, -1)).toBeGreaterThan(100);
    expect(trail(-1, 1)).toBeLessThan(-100);
  });

  it('a reach lands on its scene point with spin, either facing, at any scale', () => {
    for (const face of [1, -1] as const) for (const spin of [0, 0.8, -2]) {
      const world: [number, number] = [1100, 620];
      const shapes = buildCharacter(cast.bean, { x: 700, ground: 900, face, spin, scale: 0.7, sy: 1.2, armF: { world } });
      const hose = pts(shapes[3]); // the front arm's hose (the back arm is shapes 0–2)
      const hand = hose[hose.length - 1];
      expect(hand[0]).toBeCloseTo(world[0], 1);
      expect(hand[1]).toBeCloseTo(world[1], 1);
    }
  });
});
