// A small pose library for VRM humanoids, in normalized bone space (see motion.ts), adapted from the three-vrm
// research round. Hand-keyed starting points: mix them, layer breathing and sway on top, and adjust per shot.
// Signs: leftUpperArm z < 0 lowers the arm; leftLowerArm y < 0 bends the elbow forward; spine x > 0 leans forward;
// upperLeg x < 0 lifts the leg forward; lowerLeg x > 0 bends the knee. Right-side bones take the opposite y and z.
import { mirrorPose, type Pose } from './motion';

const relax: Pose = {
  leftUpperArm: [0, 0, -1.22], rightUpperArm: [0, 0, 1.22],
  leftLowerArm: [0, -0.25, 0], rightLowerArm: [0, 0.25, 0],
  leftHand: [0, 0, -0.1], rightHand: [0, 0, 0.1],
  leftUpperLeg: [0, 0, -0.03], rightUpperLeg: [0, 0, 0.03],
};
const waveR: Pose = {
  ...relax,
  rightUpperArm: [0, 0.35, 0.15], rightLowerArm: [0, 0.2, -1.7], rightHand: [0, 0, 0],
  spine: [0, 0, -0.05], head: [0, 0, 0.08],
};
const high5R: Pose = {
  ...relax,
  rightUpperArm: [0, 1.15, -0.8], rightLowerArm: [0, 0.3, -0.15], rightHand: [0, 0, -0.35],
  spine: [0.06, 0.12, 0], chest: [0.04, 0.1, 0], head: [-0.1, 0, 0],
};
const windupR: Pose = {
  ...relax,
  rightUpperArm: [0, -0.2, -0.85], rightLowerArm: [0, 0.2, -0.9], rightHand: [0, 0, 0.3],
  spine: [-0.08, -0.25, 0], chest: [-0.05, -0.15, 0],
};
const guardR: Pose = {
  leftUpperArm: [0, -0.9, -1.05], rightUpperArm: [0, 0.9, 1.05],
  leftLowerArm: [0, -2.1, 0], rightLowerArm: [0, 2.0, 0],
  spine: [0.12, 0.15, 0], chest: [0.06, 0.15, 0], head: [-0.1, -0.25, 0],
  leftUpperLeg: [-0.35, 0, -0.12], leftLowerLeg: [0.45, 0, 0],
  rightUpperLeg: [0.2, 0, 0.12], rightLowerLeg: [0.25, 0, 0],
  hips: [0, -0.15, 0],
};
const punchR: Pose = {
  ...guardR,
  rightUpperArm: [0, 1.25, 0.15], rightLowerArm: [0, 0.05, 0], rightShoulder: [0, 0.15, 0],
  spine: [0.2, -0.35, 0], chest: [0.1, -0.3, 0], head: [-0.15, 0.4, 0],
};
/** Right fist out at chest height, elbow a little bent: meets a partner's fistBumpL. */
const fistBumpR: Pose = {
  ...relax,
  rightUpperArm: [0, 1.35, -0.05], rightLowerArm: [0, 0.25, 0], rightHand: [0, 0, 0],
  rightShoulder: [0, 0.1, 0], spine: [0.05, 0.1, 0], chest: [0.03, 0.08, 0], head: [-0.05, 0, 0],
};

export const poses = {
  relax,
  /** Hands clasped behind the back, a little lean back: waiting, daydreaming. */
  handsBehind: {
    leftUpperArm: [0.35, 0.45, -1.15], rightUpperArm: [0.35, -0.45, 1.15],
    leftLowerArm: [0, 0.9, 0], rightLowerArm: [0, -0.9, 0],
    spine: [-0.05, 0, 0], chest: [-0.05, 0, 0],
  } as Pose,
  waveR, waveL: mirrorPose(waveR),
  high5R, high5L: mirrorPose(high5R),
  windupR, windupL: mirrorPose(windupR),
  /** Surprised: arms in, shoulders up, lean back. */
  startle: {
    leftUpperArm: [0, -0.6, -1.0], rightUpperArm: [0, 0.6, 1.0],
    leftLowerArm: [0, -1.9, 0], rightLowerArm: [0, 1.9, 0],
    leftShoulder: [0, 0, 0.12], rightShoulder: [0, 0, -0.12],
    spine: [-0.12, 0, 0], chest: [-0.06, 0, 0], neck: [-0.05, 0, 0], head: [-0.08, 0, 0],
  } as Pose,
  /** Fighting stance, fists up. */
  guardR, guardL: mirrorPose(guardR),
  punchR, punchL: mirrorPose(punchR),
  fistBumpR, fistBumpL: mirrorPose(fistBumpR),
  /** Running lean with the arms swept back (legs come from walkCycle). */
  dash: {
    leftUpperArm: [0.5, 0.9, -1.1], rightUpperArm: [0.5, -0.9, 1.1],
    leftLowerArm: [0, 0.3, 0], rightLowerArm: [0, -0.3, 0],
    spine: [0.4, 0, 0], chest: [0.15, 0, 0], neck: [-0.2, 0, 0], head: [-0.2, 0, 0],
  } as Pose,
  laugh: {
    ...relax,
    leftUpperArm: [0, -0.3, -1.1], rightUpperArm: [0, 0.3, 1.1],
    leftLowerArm: [0, -1.4, 0], rightLowerArm: [0, 1.4, 0],
    spine: [-0.1, 0, 0], chest: [-0.08, 0, 0], head: [-0.15, 0, 0],
  } as Pose,
};

// ---- layers: add them on top of a pose with addPose ----

/** Breathing: chest and shoulders rise and fall `rate` times a second. */
export const breath = (t: number, rate = 0.28, amt = 1): Pose => {
  const s = Math.sin(t * Math.PI * 2 * rate) * amt;
  return {
    spine: [0.012 * s, 0, 0], chest: [-0.025 * s, 0, 0], neck: [-0.01 * s, 0, 0],
    leftShoulder: [0, 0, -0.025 * s], rightShoulder: [0, 0, 0.025 * s],
    leftUpperArm: [0, 0, 0.02 * s], rightUpperArm: [0, 0, -0.02 * s],
  };
};

/** Weight shifting while standing; a different seed per character keeps two from swaying in step. */
export const sway = (t: number, amt = 1, seed = 0): Pose => {
  const a = Math.sin(t * 0.9 + seed) * amt, b = Math.sin(t * 0.55 + seed * 2.1) * amt;
  return {
    hips: [0, 0.02 * b, 0.025 * a], spine: [0, 0, -0.02 * a],
    head: [0.02 * b, 0.04 * b, 0.025 * a],
    leftUpperLeg: [0, 0, -0.02 * a], rightUpperLeg: [0, 0, -0.02 * a],
  };
};

/** A walk or run cycle; `phase` counts steps of both feet (one cycle = 1). Move the character with its pos. */
export const walkCycle = (phase: number, amt = 1, stride = 1): Pose => {
  const s = Math.sin(phase * Math.PI * 2) * amt, c = Math.cos(phase * Math.PI * 2);
  const kneeL = (Math.max(0, -c) * 1.4 + 0.15) * amt, kneeR = (Math.max(0, c) * 1.4 + 0.15) * amt;
  return {
    leftUpperLeg: [-0.7 * s * stride, 0, 0], rightUpperLeg: [0.7 * s * stride, 0, 0],
    leftLowerLeg: [kneeL, 0, 0], rightLowerLeg: [kneeR, 0, 0],
    leftFoot: [0.2 * s, 0, 0], rightFoot: [-0.2 * s, 0, 0],
    hips: [0, 0.12 * s, 0], spine: [0, -0.1 * s, 0],
    leftUpperArm: [0.6 * s, 0, 0], rightUpperArm: [-0.6 * s, 0, 0],
  };
};

const FINGERS = ['Index', 'Middle', 'Ring', 'Little'];

/** Finger curl: 0 flat, about 0.35 relaxed, about 1.4 a fist. */
export const fingers = (curl: number, side: 'left' | 'right' | 'both' = 'both'): Pose => {
  const out: Pose = {};
  for (const sd of side === 'both' ? ['left', 'right'] : [side]) {
    const sg = sd === 'left' ? -1 : 1;
    FINGERS.forEach((f, i) => {
      const c = curl * (1 + i * 0.08);
      out[`${sd}${f}Proximal`] = [0, 0, sg * c];
      out[`${sd}${f}Intermediate`] = [0, 0, sg * c * 1.1];
      out[`${sd}${f}Distal`] = [0, 0, sg * c * 0.8];
    });
    out[`${sd}ThumbProximal`] = [0, -sg * curl * 0.4, 0];
    out[`${sd}ThumbDistal`] = [0, -sg * curl * 0.5, 0];
  }
  return out;
};
