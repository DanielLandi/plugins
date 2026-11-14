// Two-bone IK for a VRM humanoid's legs and arms: put a foot or a hand on a world point, the knee or elbow towards a
// pole, and get the pose angles back (normalized bone space, the kit's convention: T-pose, facing +z, its left is
// +x). Pure functions of the rig and the state, so a drive() can call them on every frame.
//
// The rig is the model's rest skeleton: <Avatar> measures it when the model loads and passes it to drive(t, rig).
import * as THREE from 'three';
import type { Vec3 } from '../camera';
import type { Euler3, Pose } from './motion';

/** Each humanoid bone's parent bone and its joint's rest offset from the parent's joint (metres, kit convention).
 * The hips' offset is from the character's feet origin. */
export type HumanRig = Record<string, { parent: string | null; offset: Vec3 }>;

/** What IK needs from an AvatarState. */
export type IKState = { pos: Vec3; yaw: number; pose: Pose; hips?: Vec3 };

export type Limb = 'leftLeg' | 'rightLeg' | 'leftArm' | 'rightArm';

export type IKGoal = {
  /** World point for the ankle (legs) or the wrist (arms). */
  target: Vec3;
  /** World direction the knee or elbow points (a knee: the character's front; an elbow: back and down). */
  pole: Vec3;
  /** The foot's or hand's turn in the character's own frame (yaw taken out), XYZ radians: [0, 0, 0] is its T-pose
   * turn (a foot flat and facing forward). Left out, the pose's own foot or hand angles stay. */
  end?: Euler3;
};

const LIMBS: Record<Limb, { bones: [string, string, string]; hinge: Vec3 }> = {
  // Knees bend about x (lowerLeg x > 0), elbows about y (leftLowerArm y < 0 bends forward; the right one mirrored).
  leftLeg: { bones: ['leftUpperLeg', 'leftLowerLeg', 'leftFoot'], hinge: [1, 0, 0] },
  rightLeg: { bones: ['rightUpperLeg', 'rightLowerLeg', 'rightFoot'], hinge: [1, 0, 0] },
  leftArm: { bones: ['leftUpperArm', 'leftLowerArm', 'leftHand'], hinge: [0, -1, 0] },
  rightArm: { bones: ['rightUpperArm', 'rightLowerArm', 'rightHand'], hinge: [0, 1, 0] },
};

type VrmLike = {
  meta?: { metaVersion?: string } | null;
  humanoid: { humanBones: object; getNormalizedBoneNode(name: never): THREE.Object3D | null };
};

/**
 * The rest skeleton of a loaded VRM in the kit's convention (VRM 0.x models are mirrored like the kit mirrors their
 * poses). Call it before the model is posed (<Avatar> does, once).
 */
export const measureRig = (vrm: VrmLike): HumanRig => {
  const v0 = vrm.meta?.metaVersion === '0';
  const get = (name: string) => (vrm.humanoid.getNormalizedBoneNode as (n: string) => THREE.Object3D | null).call(vrm.humanoid, name);
  const byNode = new Map<THREE.Object3D, string>();
  for (const name of Object.keys(vrm.humanoid.humanBones)) {
    const n = get(name);
    if (n) byNode.set(n, name);
  }
  const rig: HumanRig = {};
  for (const [node, name] of byNode) {
    // The hips' position may already carry an offset from a pose: its rest is kept in userData by applyState.
    const own = (node.userData.mvRest as THREE.Vector3 | undefined) ?? node.position;
    const off = own.clone();
    let p = node.parent;
    while (p && !byNode.has(p)) {
      if (p.parent) off.add(p.position); // a skipped bone folds into the offset; the rig's root does not
      p = p.parent;
    }
    rig[name] = { parent: p ? byNode.get(p)! : null, offset: v0 ? [-off.x, off.y, -off.z] : [off.x, off.y, off.z] };
  }
  return rig;
};

const qEuler = (e: Euler3 | undefined) =>
  e ? new THREE.Quaternion().setFromEuler(new THREE.Euler(e[0], e[1], e[2], 'XYZ')) : new THREE.Quaternion();
const eulerOf = (q: THREE.Quaternion): Euler3 => {
  const e = new THREE.Euler().setFromQuaternion(q, 'XYZ');
  return [e.x, e.y, e.z];
};
const Y = new THREE.Vector3(0, 1, 0);

/** A bone's joint position and rotation in the world. */
const frameOf = (rig: HumanRig, s: IKState, bone: string): { p: THREE.Vector3; q: THREE.Quaternion } => {
  const chain: string[] = [];
  for (let b: string | null = bone; b; b = rig[b]?.parent ?? null) {
    if (!rig[b]) throw new Error(`the rig has no bone "${b}"`);
    chain.unshift(b);
  }
  const p = new THREE.Vector3(...s.pos);
  const q = new THREE.Quaternion().setFromAxisAngle(Y, s.yaw);
  for (const b of chain) {
    const off = new THREE.Vector3(...rig[b].offset);
    if (rig[b].parent === null && s.hips) off.add(new THREE.Vector3(...s.hips));
    p.add(off.applyQuaternion(q));
    q.multiply(qEuler(s.pose[b]));
  }
  return { p, q };
};

/** Where a bone's joint is in the world for this state (forward kinematics). */
export const jointAt = (rig: HumanRig, s: IKState, bone: string): Vec3 => frameOf(rig, s, bone).p.toArray() as Vec3;

/** A bone's rotation in the world for this state. */
export const boneQuaternion = (rig: HumanRig, s: IKState, bone: string): THREE.Quaternion => frameOf(rig, s, bone).q;

/** Orthonormal frame with x along a and y towards b (b's part across a). */
const basis = (a: THREE.Vector3, b: THREE.Vector3, fallback: THREE.Vector3) => {
  const e1 = a.clone().normalize();
  let e2 = b.clone().sub(e1.clone().multiplyScalar(b.dot(e1)));
  if (e2.lengthSq() < 1e-12) e2 = fallback.clone().sub(e1.clone().multiplyScalar(fallback.dot(e1)));
  e2.normalize();
  return new THREE.Matrix4().makeBasis(e1, e2, new THREE.Vector3().crossVectors(e1, e2));
};

/**
 * Two-bone IK for one limb: the angles of its upper bone, its lower bone (a hinge: the knee or elbow bends only the
 * natural way) and, with `end`, its foot or hand, as a Pose to merge over the state's pose. The rest of the state's
 * pose (hips, spine, shoulders) is taken as given, so solve after setting those. A target out of reach gets the limb
 * straight towards it. Bone lengths never change.
 */
export const limbIK = (rig: HumanRig, s: IKState, limb: Limb, goal: IKGoal): Pose => {
  const { bones: [upper, lower, end], hinge } = LIMBS[limb];
  for (const b of [upper, lower, end]) if (!rig[b]) throw new Error(`the rig has no bone "${b}"`);
  const parent = frameOf(rig, s, rig[upper].parent!);
  const joint = parent.p.clone().add(new THREE.Vector3(...rig[upper].offset).applyQuaternion(parent.q));
  const inv = parent.q.clone().invert();
  const t = new THREE.Vector3(...goal.target).sub(joint).applyQuaternion(inv);
  const pole = new THREE.Vector3(...goal.pole).applyQuaternion(inv);
  const u = new THREE.Vector3(...rig[lower].offset);
  const l = new THREE.Vector3(...rig[end].offset);
  const a = new THREE.Vector3(...hinge);

  // |u + R_a(b) l|² = A + B cos b + C sin b: solve for the bend b that reaches the target's distance.
  const lPar = a.clone().multiplyScalar(l.dot(a));
  const lPerp = l.clone().sub(lPar);
  const A = u.lengthSq() + l.lengthSq() + 2 * u.dot(lPar);
  const B = 2 * u.dot(lPerp);
  const C = 2 * u.dot(new THREE.Vector3().crossVectors(a, lPerp));
  const R = Math.hypot(B, C);
  const phi = Math.atan2(C, B);
  const reach = Math.sqrt(A + R);
  const d = Math.min(t.length(), reach);
  const bend = R < 1e-12 ? 0 : Math.max(0, phi + Math.acos(Math.min(1, Math.max(-1, (d * d - A) / R))));
  const knee = new THREE.Quaternion().setFromAxisAngle(a, bend);
  const e = u.clone().add(l.clone().applyQuaternion(knee));

  // Turn the bent limb so its end lies along the target and its middle joint is on the pole's side. Before the turn,
  // the knee or elbow sits towards e × hinge (in front of the hip→ankle line, behind the shoulder→wrist line).
  const side = new THREE.Vector3().crossVectors(e, a);
  const from = basis(e, side, u);
  const to = basis(t.lengthSq() > 1e-12 ? t : e, pole, side);
  const up = new THREE.Quaternion().setFromRotationMatrix(to.multiply(from.transpose()));

  // The hinge as plain angles on its own axis (an XYZ Euler of an elbow bent past 90° would read [π, π - b, π]: the
  // same turn, but it would not mix with other poses).
  const out: Pose = { [upper]: eulerOf(up), [lower]: [hinge[0] * bend, hinge[1] * bend, hinge[2] * bend] };
  if (goal.end) {
    // The end bone's rotation relative to its parent, so that its turn in the character's frame is goal.end.
    const charInv = new THREE.Quaternion().setFromAxisAngle(Y, -s.yaw);
    const lowerInChar = charInv.multiply(parent.q).multiply(up).multiply(knee);
    out[end] = eulerOf(lowerInChar.invert().multiply(qEuler(goal.end)));
  }
  return out;
};

/** The state with the given limbs solved (legs first, then arms) and merged into its pose; the input is unchanged. */
export const withIK = <S extends IKState>(rig: HumanRig, s: S, goals: Partial<Record<Limb, IKGoal>>): S => {
  let pose: Pose = { ...s.pose };
  for (const limb of ['leftLeg', 'rightLeg', 'leftArm', 'rightArm'] as const) {
    const g = goals[limb];
    if (g) pose = { ...pose, ...limbIK(rig, { ...s, pose }, limb, g) };
  }
  return { ...s, pose };
};
