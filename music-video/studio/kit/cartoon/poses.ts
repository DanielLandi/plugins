// Poses for the cartoon rig, keyed like the vrm engine's: presets are layers (a pose without x, ground and face),
// `poseTrack` keys them over time, `mixPose` blends two, `addPose` puts a layer on top (breath, a wave, a bounce).
import type { P } from './draw';
import { eases, lerp, type EaseFn } from './motion';
import type { Arm, Mouth, MouthKey, Pose } from './rig';

/** A pose without its place: what presets, keys and layers carry. */
export type PoseLayer = Partial<Omit<Pose, 'x' | 'ground' | 'face'>>;

// Numbers and what they are when left out (the rig's defaults).
const ONE = ['scale', 'sx', 'sy', 'eyeScale', 'eyeOpen', 'mouthScale', 'legSquash'] as const;
const ZERO = ['lift', 'lean', 'bend', 'spin', 'look', 'eyesClosed', 'brow', 'swirl', 'walk', 'walkPhase', 'hatLift',
  'hatSpin', 'sprout', 'smear'] as const;
type NumKey = (typeof ONE)[number] | (typeof ZERO)[number] | 'stride';
const NUMS: [NumKey, number][] = [...ONE.map((k): [NumKey, number] => [k, 1]), ...ZERO.map((k): [NumKey, number] => [k, 0]), ['stride', 70]];
const ARM_NUMS: [keyof Arm & ('sag' | 'wiggle' | 'wigglePhase' | 'open'), number][] = [['sag', 0.35], ['wiggle', 0], ['wigglePhase', 0], ['open', 0]];
/** The rig's hanging arms, as offsets from each shoulder. */
const HANG: Record<'armF' | 'armB', P> = { armF: [30, 90], armB: [-30, 90] };

const lerpP = (a: P, b: P, w: number): P => [lerp(a[0], b[0], w), lerp(a[1], b[1], w)];
const one = (m: Mouth): MouthKey => (typeof m === 'string' ? m : m[2] < 0.5 ? m[0] : m[1]);

const mixArm = (side: 'armF' | 'armB', a: Arm | undefined, b: Arm | undefined, w: number): Arm | undefined => {
  if (!a && !b) return undefined;
  const A: Arm = a ?? { hand: HANG[side] }, Bm: Arm = b ?? { hand: HANG[side] };
  const out: Arm = {};
  for (const [k, d] of ARM_NUMS) if (A[k] !== undefined || Bm[k] !== undefined) out[k] = lerp(A[k] ?? d, Bm[k] ?? d, w);
  // Shoulder-space hands mix as points; a world point is reached by `reach`, so a key from a hanging hand to a
  // world point (a reach, a handshake) blends smoothly in the rig, where the shoulder is known.
  const rA = A.world ? A.reach ?? 1 : 0, rB = Bm.world ? Bm.reach ?? 1 : 0;
  if (A.hand || Bm.hand || !A.world || !Bm.world) out.hand = lerpP(A.hand ?? HANG[side], Bm.hand ?? HANG[side], w);
  if (A.world && Bm.world) out.world = lerpP(A.world, Bm.world, w);
  else if (A.world || Bm.world) out.world = (A.world ?? Bm.world) as P;
  if (out.world && (rA !== 1 || rB !== 1 || !A.world || !Bm.world)) out.reach = lerp(rA, rB, w);
  const front = w < 0.5 ? A.front : Bm.front;
  if (front !== undefined) out.front = front;
  return out;
};

/** Two poses blended (w = 0 is a, 1 is b): numbers and hands in between, mouths morphed, on/off fields half way. */
export const mixPose = <T extends PoseLayer>(a: T, b: T, w: number): T => {
  const out: PoseLayer = {};
  for (const [k, d] of NUMS) if (a[k] !== undefined || b[k] !== undefined) out[k] = lerp(a[k] ?? d, b[k] ?? d, w);
  if (a.pupil || b.pupil) out.pupil = lerpP(a.pupil ?? [0, 0], b.pupil ?? [0, 0], w);
  if (a.feet && b.feet) out.feet = [lerpP(a.feet[0], b.feet[0], w), lerpP(a.feet[1], b.feet[1], w)];
  else if (a.feet || b.feet) out.feet = w < 0.5 ? a.feet : b.feet;
  for (const side of ['armF', 'armB'] as const) {
    const arm = mixArm(side, a[side], b[side], w);
    if (arm) out[side] = arm;
  }
  if (a.mouth !== undefined || b.mouth !== undefined) {
    const ma = a.mouth ?? 'smile', mb = b.mouth ?? 'smile';
    const ka = one(ma), kb = one(mb);
    out.mouth = w <= 0 ? ma : w >= 1 ? mb : ka === kb ? ka : [ka, kb, w];
  }
  const dir = w < 0.5 ? a.smearDir ?? b.smearDir : b.smearDir ?? a.smearDir;
  if (dir !== undefined) out.smearDir = dir;
  // Whole poses (with a place) mix their place too: x and ground in between, the facing half way.
  const pa = a as Partial<Pose>, pb = b as Partial<Pose>, place: Partial<Pose> = {};
  if (pa.x !== undefined && pb.x !== undefined) place.x = lerp(pa.x, pb.x, w);
  if (pa.ground !== undefined && pb.ground !== undefined) place.ground = lerp(pa.ground, pb.ground, w);
  if (pa.face !== undefined || pb.face !== undefined) place.face = w < 0.5 ? pa.face ?? pb.face : pb.face ?? pa.face;
  return { ...a, ...b, ...out, ...place } as T;
};

/** A layer added on top of a pose, scaled by w: its numbers, hand and pupil offsets add; its stride, mouth and switches win. */
export const addPose = <T extends PoseLayer>(a: T, b: PoseLayer, w = 1): T => {
  const out: PoseLayer = { ...a };
  for (const [k, d] of NUMS) if (b[k] !== undefined) out[k] = k === 'stride' ? b[k] : (a[k] ?? d) + (b[k] as number) * w;
  if (b.pupil) out.pupil = [(a.pupil?.[0] ?? 0) + b.pupil[0] * w, (a.pupil?.[1] ?? 0) + b.pupil[1] * w];
  for (const side of ['armF', 'armB'] as const) {
    const lb = b[side];
    if (!lb) continue;
    const base: Arm = { ...(a[side] ?? { hand: HANG[side] }) };
    for (const [k, d] of ARM_NUMS) if (lb[k] !== undefined) base[k] = (base[k] ?? d) + (lb[k] as number) * w;
    if (lb.hand) {
      const off = lb.hand;
      if (base.world && !base.hand) base.world = [base.world[0] + off[0] * w, base.world[1] + off[1] * w];
      else base.hand = [(base.hand ?? HANG[side])[0] + off[0] * w, (base.hand ?? HANG[side])[1] + off[1] * w];
    }
    if (lb.world) { // a world point in a layer is reached toward, by w (never added to a hand)
      const from = base.world ? base.reach ?? 1 : 0;
      base.world = lb.world;
      base.reach = lerp(from, lb.reach ?? 1, w);
    }
    if (lb.front !== undefined) base.front = lb.front;
    out[side] = base;
  }
  if (b.mouth !== undefined && w >= 0.5) out.mouth = b.mouth;
  if (b.feet) out.feet = b.feet;
  if (b.smearDir !== undefined) out.smearDir = b.smearDir;
  return out as T;
};

/** Keyed poses: [time, pose, the ease into this key (inOut when left out)]. */
export type PoseKey = readonly [number, PoseLayer, EaseFn?];

export const poseTrack = (t: number, keys: readonly PoseKey[]): PoseLayer => {
  if (t <= keys[0][0]) return keys[0][1];
  for (let i = 1; i < keys.length; i++) {
    const [t1, p1, e] = keys[i];
    if (t <= t1) {
      const [t0, p0] = keys[i - 1];
      return mixPose(p0, p1, t1 === t0 ? 1 : (e ?? eases.inOut)((t - t0) / (t1 - t0)));
    }
  }
  return keys[keys.length - 1][1];
};

/** Breathing: a slow squash and stretch (add with addPose). `phase` keeps two characters from breathing together. */
export const breath = (t: number, phase = 0): PoseLayer => ({ sy: 0.025 * Math.sin(t * 4.4 + phase) });

/**
 * Walking at screen position x: the feet cycle with the distance travelled, so they never slide (one stride per
 * half cycle). `face` is the way the character walks; `amount` fades the walk in and out; pass the pose's `scale`.
 */
export const walk = (x: number, face: 1 | -1, amount = 1, stride = 70, scale = 1): PoseLayer =>
  ({ walk: amount, walkPhase: (x * face) / (2 * stride * scale), stride });

/**
 * Presets (character space: the front arm `armF` is on the side the character faces; hands are offsets from each
 * shoulder, y down). Layer motion on top: a wave's back-and-forth, a laugh's bounce.
 */
export const poses = {
  rest: { armF: { hand: [26, 80], sag: 0.3 }, armB: { hand: [-26, 80], sag: 0.3 } },
  wave: { armF: { hand: [50, -150], sag: 0.25, open: 1 }, armB: { hand: [-26, 80], sag: 0.3 }, brow: 0.6, mouth: 'grin' },
  /** The double take: stretched tall, eyes popped, jaw dropped, hat up. */
  take: { sy: 1.4, sx: 0.82, eyeScale: 1.85, brow: 1.4, mouth: 'shout', hatLift: 70,
    armF: { hand: [70, -90], sag: -0.4, open: 1 }, armB: { hand: [-80, -80], sag: 0.4, open: 1 } },
  startle: { sy: 1.12, eyeScale: 1.35, brow: 1, mouth: 'o', armF: { hand: [60, -100], sag: -0.3, open: 1 },
    armB: { hand: [-60, -90], sag: 0.3, open: 1 } },
  /** A playful fighting stance: crouched, brows crossed, fists up. */
  guard: { sy: 0.9, lean: 0.12, legSquash: 0.85, brow: -0.8, mouth: 'grin', feet: [[-60, 0], [62, 0]],
    armF: { hand: [80, -20], sag: -0.3 }, armB: { hand: [50, -40], sag: 0.2 } },
  /** Anticipation before a strike: wound back, squashed, eyes narrowed. */
  windup: { sy: 0.86, lean: -0.18, legSquash: 0.8, brow: -1, mouth: 'flat', eyeOpen: 0.6, feet: [[-60, 0], [62, 0]],
    armF: { hand: [-50, -10], sag: 0.4 }, armB: { hand: [40, -40], sag: 0.2 } },
  /** The strike: stretched forward, the front fist far out. */
  punch: { sy: 1.05, lean: 0.22, brow: -0.6, mouth: 'shout', feet: [[-70, 0], [70, 0]],
    armF: { hand: [190, -30], sag: 0, front: true }, armB: { hand: [-40, 10], sag: 0.4 } },
  cheer: { sy: 1.08, eyesClosed: 1, mouth: 'laugh', armF: { hand: [40, -170], open: 1, sag: 0.2 },
    armB: { hand: [-40, -170], open: 1, sag: 0.2 } },
  laugh: { eyesClosed: 1, mouth: 'laugh', lean: -0.08, armF: { hand: [30, 20], sag: 0.5 }, armB: { hand: [-30, 20], sag: 0.5 } },
  shrug: { brow: 0.8, mouth: 'flat', armF: { hand: [60, -40], open: 1, sag: -0.4 }, armB: { hand: [-60, -40], open: 1, sag: -0.4 } },
  /** Gazing out at something far away, content. */
  lookOut: { look: 0.3, pupil: [0.2, -0.7], brow: 0.3, mouth: 'smile', armF: { hand: [26, 80], sag: 0.3 },
    armB: { hand: [-26, 80], sag: 0.3 } },
} satisfies Record<string, PoseLayer>;
