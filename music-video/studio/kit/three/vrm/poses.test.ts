import { describe, expect, it } from 'vitest';
import { addPose, mirrorPose, mixPose, poseTrack, type Pose } from './motion';
import { breath, fingers, poses, walkCycle } from './poses';

describe('pose math', () => {
  const a: Pose = { spine: [0.2, 0, 0], leftUpperArm: [0, 0, -1] };
  const b: Pose = { spine: [0, 0.4, 0], head: [0.1, 0, 0] };
  it('mixPose blends and treats a missing bone as rest', () => {
    expect(mixPose(a, b, 0.5)).toEqual({ spine: [0.1, 0.2, 0], leftUpperArm: [0, 0, -0.5], head: [0.05, 0, 0] });
    expect(mixPose(a, b, 0)).toEqual({ ...a, head: [0, 0, 0] });
  });
  it('addPose adds a layer with a weight', () => {
    expect(addPose(a, b, 2)).toEqual({ spine: [0.2, 0.8, 0], leftUpperArm: [0, 0, -1], head: [0.2, 0, 0] });
  });
  it('mirrorPose swaps sides, negates y and z, and undoes itself', () => {
    const m = mirrorPose({ leftUpperArm: [0.1, 0.2, -1], spine: [0.3, 0.1, 0.05] });
    expect(m).toEqual({ rightUpperArm: [0.1, -0.2, 1], spine: [0.3, -0.1, -0.05] });
    const p = poses.high5R;
    expect(mirrorPose(mirrorPose(p))).toEqual(p);
  });
  it('poseTrack holds the ends and lands on each key', () => {
    const keys: [number, Pose][] = [[1, a], [2, b]];
    expect(poseTrack(0, keys)).toEqual(a);
    expect(poseTrack(2, keys)).toEqual(mixPose(a, b, 1));
    expect(poseTrack(5, keys)).toEqual(b);
  });
});

describe('the pose library', () => {
  it('left poses mirror the right ones', () => {
    expect(poses.waveL).toEqual(mirrorPose(poses.waveR));
    expect(poses.fistBumpL).toEqual(mirrorPose(poses.fistBumpR));
    expect(poses.guardL).toEqual(mirrorPose(poses.guardR));
  });
  it('fingers curls one side or both', () => {
    const left = fingers(1, 'left');
    expect(Object.keys(left).every((k) => k.startsWith('left'))).toBe(true);
    expect(Object.keys(fingers(1)).some((k) => k.startsWith('right'))).toBe(true);
    expect(fingers(0, 'right').rightIndexProximal).toEqual([0, 0, 0]);
  });
  it('layers are periodic functions of time', () => {
    expect(breath(1 / 0.28).chest![0]).toBeCloseTo(breath(0).chest![0]);
    expect(walkCycle(0.25).leftUpperLeg![0]).toBeCloseTo(-walkCycle(0.75).leftUpperLeg![0]);
  });
});
