import { describe, expect, it } from 'vitest';
import { addPose, breath, mixPose, poseTrack, poses, walk, type PoseLayer } from './poses';
import { eases } from './motion';
import { cast } from './cast';
import { buildCharacter } from './rig';

describe('cartoon poses', () => {
  it('mixes numbers and hands, and switches discrete fields half way', () => {
    const a: PoseLayer = { sy: 1, armF: { hand: [0, 0] }, mouth: 'smile' };
    const b: PoseLayer = { sy: 2, armF: { hand: [100, -50], front: true }, mouth: 'shout' };
    expect(mixPose(a, b, 0)).toEqual(a);
    expect(mixPose(a, b, 1)).toEqual(b);
    const mid = mixPose(a, b, 0.5);
    expect(mid.sy).toBe(1.5);
    expect(mid.armF?.hand).toEqual([50, -25]);
    expect(mid.mouth).toEqual(['smile', 'shout', 0.5]);
    expect(mixPose(a, b, 0.4).armF?.front).toBeFalsy();
    expect(mixPose(a, b, 0.6).armF?.front).toBe(true);
  });

  it('mixing a body-space hand with a world-space hand stays finite', () => {
    const m = mixPose({ armF: { hand: [10, 20] } }, { armF: { world: [900, 600] } }, 0.5);
    const p = m.armF?.hand ?? m.armF?.world;
    expect(p && p.every(Number.isFinite)).toBe(true);
  });

  it('keys poses over time, landing exactly on each key', () => {
    const keys = [[0, poses.rest], [1, poses.guard, eases.outBack], [2, poses.cheer]] as const;
    expect(poseTrack(-1, keys)).toEqual(poses.rest);
    expect(poseTrack(1, keys)).toEqual(mixPose(poses.rest, poses.guard, 1));
    expect(poseTrack(5, keys)).toEqual(poses.cheer);
    expect(poseTrack(1.5, keys)).toEqual(poseTrack(1.5, keys));
  });

  it('adds layers on top', () => {
    const p = addPose({ sy: 1, lean: 0.1, armB: { hand: [5, 5] } }, { sy: 0.1, armB: { hand: [1, -1] } }, 2);
    expect(p.sy).toBeCloseTo(1.2);
    expect(p.lean).toBe(0.1);
    expect(p.armB?.hand).toEqual([7, 3]);
    expect(breath(1.3).sy).not.toBe(1);
    expect(walk(1, 1).walk).toBe(1);
    expect(addPose({ stride: 90 }, walk(0, 1, 1, 62)).stride).toBe(62); // a stride is set, not added
  });

  it('every preset is a plain layer (no position)', () => {
    for (const p of Object.values(poses)) {
      expect('x' in p || 'ground' in p || 'face' in p).toBe(false);
    }
  });
});

describe('review fixes', () => {
  it('a keyed reach from a hanging hand to a world point moves the hand a little per step, never a jump', () => {
    const at = (w: number) => {
      const p = mixPose({ armF: { hand: [30, 90] } }, { armF: { world: [1400, 500] } }, w);
      const shapes = buildCharacter(cast.bean, { ...p, x: 600, ground: 900, face: 1 });
      return shapes[5].k === 'blob' ? shapes[5].pts[0] : [0, 0]; // the front mitten's palm
    };
    for (let w = 0; w < 1; w += 0.05) {
      const [a, b] = [at(w), at(w + 0.05)];
      expect(Math.hypot(b[0] - a[0], b[1] - a[1])).toBeLessThan(60);
    }
  });

  it('a layer with a world point blends the reach toward it instead of adding it to the hand', () => {
    const p = addPose<PoseLayer>({ armF: { hand: [30, 90] } }, { armF: { world: [900, 600] } }, 0.5);
    expect(p.armF?.world).toEqual([900, 600]);
    expect(p.armF?.reach).toBe(0.5);
    expect(p.armF?.hand).toEqual([30, 90]);
  });

  it('the planted foot stays put while walking at any scale', () => {
    for (const scale of [1, 0.5]) {
      const foot = (x: number) => {
        const shapes = buildCharacter(cast.plum, { ...walk(x, 1, 1, 70, scale), x, ground: 900, face: 1, scale });
        const leg = shapes[6];
        return leg.k === 'limb' ? leg.pts[leg.pts.length - 1][0] : NaN;
      };
      expect(foot(10)).toBeCloseTo(foot(0), 3);
    }
  });
});
