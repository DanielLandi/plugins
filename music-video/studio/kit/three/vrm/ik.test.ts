import * as THREE from 'three';
import { describe, expect, it } from 'vitest';
import type { Vec3 } from '../camera';
import { boneQuaternion, jointAt, limbIK, measureRig, withIK, type HumanRig, type IKState } from './ik';

// A made-up humanoid in the kit's convention (T-pose, facing +z, its left is +x), with slightly bent rest limbs like
// a real model's. Offsets are each bone's joint relative to its parent's joint; the hips' is from the feet.
const half: Record<string, { parent: string; offset: Vec3 }> = {
  UpperLeg: { parent: 'hips', offset: [0.08, -0.05, 0.005] },
  LowerLeg: { parent: 'UpperLeg', offset: [-0.02, -0.4, -0.01] },
  Foot: { parent: 'LowerLeg', offset: [-0.01, -0.42, -0.02] },
  Shoulder: { parent: 'chest', offset: [0.05, 0.2, -0.01] },
  UpperArm: { parent: 'Shoulder', offset: [0.1, 0, 0] },
  LowerArm: { parent: 'UpperArm', offset: [0.25, 0, -0.005] },
  Hand: { parent: 'LowerArm', offset: [0.22, 0, 0] },
};
const RIG: HumanRig = {
  hips: { parent: null, offset: [0, 0.95, 0] },
  spine: { parent: 'hips', offset: [0, 0.1, 0] },
  chest: { parent: 'spine', offset: [0, 0.15, 0.01] },
};
for (const [name, b] of Object.entries(half)) {
  const side = (s: string, p: string) => (p === 'hips' || p === 'chest' ? p : `${s}${p}`);
  RIG[`left${name}`] = { parent: side('left', b.parent), offset: b.offset };
  RIG[`right${name}`] = { parent: side('right', b.parent), offset: [-b.offset[0], b.offset[1], b.offset[2]] };
}

const V = (v: Vec3) => new THREE.Vector3(...v);
const len = (a: Vec3, b: Vec3) => V(a).distanceTo(V(b));
const yawQ = (yaw: number) => new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), yaw);
/** A point given in the character's own frame (x its left, z its front), in the world. */
const world = (s: IKState, local: Vec3): Vec3 => V(local).applyQuaternion(yawQ(s.yaw)).add(V(s.pos)).toArray() as Vec3;
const dirWorld = (s: IKState, local: Vec3): Vec3 => V(local).applyQuaternion(yawQ(s.yaw)).toArray() as Vec3;

// Somewhere on a slope, turned, with the hips dropped and twisted and the spine bent: IK must see all of it.
const STATE: IKState = {
  pos: [1.5, 0.4, -2],
  yaw: 0.7,
  hips: [0.02, -0.12, 0.05],
  pose: { hips: [0.1, 0.3, -0.05], spine: [0.2, -0.1, 0.05], chest: [0.1, 0.15, 0] },
};

describe('jointAt (forward kinematics)', () => {
  it('puts a T-pose joint at its rest place, moved and turned with the character', () => {
    const rest: IKState = { pos: [2, 0, 3], yaw: Math.PI / 2, pose: {} };
    // The left foot at rest: hips + upper leg + lower leg + foot offsets, the character turned to face +x.
    const local: Vec3 = [0.08 - 0.02 - 0.01, 0.95 - 0.05 - 0.4 - 0.42, 0.005 - 0.01 - 0.02];
    expect(len(jointAt(RIG, rest, 'leftFoot'), world(rest, local))).toBeLessThan(1e-9);
  });
});

describe('limbIK', () => {
  for (const side of ['left', 'right'] as const) {
    it(`plants the ${side} foot on its target, keeps the bone lengths and points the knee at the pole`, () => {
      const sg = side === 'left' ? 1 : -1;
      const target = world(STATE, [0.15 * sg, 0.12, 0.25]);
      const pole = dirWorld(STATE, [0.2 * sg, 0, 1]);
      const pose = { ...STATE.pose, ...limbIK(RIG, STATE, `${side}Leg`, { target, pole }) };
      const s = { ...STATE, pose };
      const hip = jointAt(RIG, s, `${side}UpperLeg`), knee = jointAt(RIG, s, `${side}LowerLeg`), foot = jointAt(RIG, s, `${side}Foot`);
      expect(len(foot, target)).toBeLessThan(1e-6);
      expect(len(hip, knee)).toBeCloseTo(V(RIG[`${side}LowerLeg`].offset).length(), 9);
      expect(len(knee, foot)).toBeCloseTo(V(RIG[`${side}Foot`].offset).length(), 9);
      // The knee sits off the hip→foot line on the pole's side.
      const mid = V(hip).lerp(V(foot), 0.5);
      expect(V(knee).sub(mid).dot(V(pole))).toBeGreaterThan(0.02);
      // The knee is a hinge that bends the natural way (lowerLeg x > 0).
      const [kx, ky, kz] = pose[`${side}LowerLeg`];
      expect(kx).toBeGreaterThan(0.2);
      expect(Math.abs(ky) + Math.abs(kz)).toBeLessThan(1e-9);
    });

    it(`reaches the ${side} hand to a target past a bent spine, the elbow towards the pole`, () => {
      const sg = side === 'left' ? 1 : -1;
      const target = world(STATE, [0.35 * sg, 1.25, 0.3]);
      const pole = dirWorld(STATE, [0.3 * sg, -1, -0.4]);
      const pose = { ...STATE.pose, ...limbIK(RIG, STATE, `${side}Arm`, { target, pole }) };
      const s = { ...STATE, pose };
      const sh = jointAt(RIG, s, `${side}UpperArm`), el = jointAt(RIG, s, `${side}LowerArm`), hand = jointAt(RIG, s, `${side}Hand`);
      expect(len(hand, target)).toBeLessThan(1e-6);
      expect(len(sh, el)).toBeCloseTo(V(RIG[`${side}LowerArm`].offset).length(), 9);
      expect(V(el).sub(V(sh).lerp(V(hand), 0.5)).dot(V(pole))).toBeGreaterThan(0.02);
      // The elbow is a hinge bending the forearm forward: leftLowerArm y < 0, rightLowerArm y > 0.
      const [ex, ey, ez] = pose[`${side}LowerArm`];
      expect(ey * sg).toBeLessThan(-0.2);
      expect(Math.abs(ex) + Math.abs(ez)).toBeLessThan(1e-9);
    });
  }

  it('stretches straight towards a target out of reach (never past the limb’s length)', () => {
    const target = world(STATE, [0.6, -0.5, 0.9]);
    const pose = { ...STATE.pose, ...limbIK(RIG, STATE, 'leftLeg', { target, pole: dirWorld(STATE, [0, 0, 1]) }) };
    const s = { ...STATE, pose };
    const hip = V(jointAt(RIG, s, 'leftUpperLeg')), foot = V(jointAt(RIG, s, 'leftFoot'));
    const reach = V(RIG.leftLowerLeg.offset).length() + V(RIG.leftFoot.offset).length();
    expect(hip.distanceTo(foot)).toBeLessThanOrEqual(reach + 1e-9);
    expect(hip.distanceTo(foot)).toBeGreaterThan(reach * 0.99);
    const toward = V(target).sub(hip).normalize();
    expect(foot.clone().sub(hip).normalize().dot(toward)).toBeGreaterThan(0.9999);
  });

  it('sets the foot’s turn in the character’s frame when asked (flat on the ground, facing forward)', () => {
    const target = world(STATE, [0.12, 0.1, 0.2]);
    const pose = { ...STATE.pose, ...limbIK(RIG, STATE, 'leftLeg', { target, pole: dirWorld(STATE, [0, 0, 1]), end: [0, 0, 0] }) };
    const q = boneQuaternion(RIG, { ...STATE, pose }, 'leftFoot');
    expect(q.angleTo(yawQ(STATE.yaw))).toBeLessThan(1e-6);
    const tilted = { ...STATE.pose, ...limbIK(RIG, STATE, 'leftLeg', { target, pole: dirWorld(STATE, [0, 0, 1]), end: [0.2, 0.3, 0] }) };
    const want = yawQ(STATE.yaw).multiply(new THREE.Quaternion().setFromEuler(new THREE.Euler(0.2, 0.3, 0, 'XYZ')));
    expect(boneQuaternion(RIG, { ...STATE, pose: tilted }, 'leftFoot').angleTo(want)).toBeLessThan(1e-6);
  });

  it('withIK solves several limbs into a new state and leaves the given one alone', () => {
    const before = JSON.stringify(STATE);
    const goals = {
      leftLeg: { target: world(STATE, [0.15, 0.1, 0.2]), pole: dirWorld(STATE, [0, 0, 1]) },
      rightArm: { target: world(STATE, [-0.3, 1.2, 0.35]), pole: dirWorld(STATE, [0, -1, -0.5]) },
    };
    const out = withIK(RIG, STATE, goals);
    expect(JSON.stringify(STATE)).toBe(before);
    expect(len(jointAt(RIG, out, 'leftFoot'), goals.leftLeg.target)).toBeLessThan(1e-6);
    expect(len(jointAt(RIG, out, 'rightHand'), goals.rightArm.target)).toBeLessThan(1e-6);
    expect(out.pos).toEqual(STATE.pos);
  });

  it('is a pure function: the same input gives the same pose', () => {
    const g = { target: world(STATE, [0.15, 0.12, 0.25]), pole: dirWorld(STATE, [0, 0, 1]) };
    expect(limbIK(RIG, STATE, 'leftLeg', g)).toEqual(limbIK(RIG, STATE, 'leftLeg', g));
  });
});

describe('measureRig', () => {
  /** A stand-in for a loaded VRM: normalized bone nodes under a root, with three-vrm's API. */
  const fake = (metaVersion: '0' | '1') => {
    const root = new THREE.Object3D();
    const nodes: Record<string, THREE.Object3D> = {};
    const mirror = (v: Vec3): Vec3 => (metaVersion === '0' ? [-v[0], v[1], -v[2]] : v);
    for (const [name, b] of Object.entries(RIG)) {
      const n = new THREE.Object3D();
      n.position.set(...mirror(b.offset));
      nodes[name] = n;
    }
    for (const [name, b] of Object.entries(RIG)) (b.parent ? nodes[b.parent] : root).add(nodes[name]);
    // A method that needs its `this`, like three-vrm's.
    const humanoid = {
      nodes,
      humanBones: Object.fromEntries(Object.keys(RIG).map((k) => [k, {}])),
      getNormalizedBoneNode(this: { nodes: typeof nodes }, n: string) { return this.nodes[n] ?? null; },
    };
    return { meta: { metaVersion }, humanoid };
  };
  it('reads each bone’s parent and rest offset (VRM 1.0)', () => {
    const r = measureRig(fake('1'));
    expect(r.leftFoot.parent).toBe('leftLowerLeg');
    expect(r.hips.parent).toBeNull();
    expect(r.leftFoot.offset).toEqual(RIG.leftFoot.offset);
  });
  it('turns a VRM 0.x model’s rest into the kit’s convention (its left is +x)', () => {
    const r = measureRig(fake('0'));
    expect(r.leftUpperLeg.offset[0]).toBeCloseTo(0.08, 12);
    expect(r.leftUpperLeg.offset[2]).toBeCloseTo(0.005, 12);
  });
  it('skips a bone the model does not have, parenting its child to the next one up', () => {
    const f = fake('1');
    delete (f.humanoid.humanBones as Record<string, object>).chest;
    const r = measureRig(f);
    expect(r.chest).toBeUndefined();
    expect(r.leftShoulder.parent).toBe('spine');
    // The skipped bone's offset is folded in, so the joint stays where it was.
    expect(r.leftShoulder.offset[1]).toBeCloseTo(0.15 + 0.2, 12);
  });
});
