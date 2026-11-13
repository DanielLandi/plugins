// The rubber-hose rig of the cartoon engine (adapted from the cartoon research round). Pure geometry: a character
// (data) and a pose (numbers) → a list of shapes in the composition's pixels. ink.tsx draws them as brush strokes.
// Character space: facing +x, feet at (0, 0), y up is negative; `face: -1` mirrors it.
import { interpolate as flubber } from 'flubber';
import { add, cubicPts, ellipsePts, rot, type P } from './draw';
import { clamp, lerp } from './motion';

export type Shape =
  | { k: 'blob'; pts: P[]; fill: string; ink?: number; layer?: 'shade' | 'hi' }
  | { k: 'limb'; pts: P[]; w: number; fill: string; ink: number }
  | { k: 'line'; pts: P[]; w: number; color?: string }
  | { k: 'dot'; x: number; y: number; r: number; fill: string };

/** A character is data: colours and proportions (px at scale 1), an optional hat or sprout on top. */
export type Character = {
  fill: string; shade: string; hi: string; limb: string; shoe: string;
  /** Body half-width and half-height; `pear` widens the bottom. */
  rx: number; ry: number; pear: number;
  legLen: number; hipW: number; limbW: number; handR: number;
  eyeRx: number; eyeRy: number; eyeGap: number; eyeY: number; cheek?: string;
  hat?: { fill: string; band: string; pom: string };
  sprout?: { stem: string; leaf: string };
};

/**
 * An arm: `hand` is the mitten's offset from the shoulder (character space, before `face`), `world` a point in the
 * composition the hand reaches (a stretchy reach, a handshake, a fist bump); with both, `reach` (0..1, default 1)
 * blends the hand from `hand` toward `world`. `sag` bends the hose, `wiggle` sends a travelling wave along it,
 * `open` spreads the mitten, `front` draws the arm over the body.
 */
export type Arm = { hand?: P; world?: P; reach?: number; sag?: number; front?: boolean; wiggle?: number; wigglePhase?: number; open?: number };

export const MOUTH_KEYS = ['smile', 'grin', 'laugh', 'o', 'shout', 'flat', 'frown', 'wavy'] as const;
export type MouthKey = (typeof MOUTH_KEYS)[number];
/** One mouth, or a morph between two: [from, to, 0..1]. */
export type Mouth = MouthKey | [MouthKey, MouthKey, number];

/**
 * Everything a character does in one frame. Only x, ground and face are required. Squash and stretch (`sx`, `sy`)
 * scale the body about the hips; `lean` tilts it, `bend` curves it, `spin` turns the whole character, `lift` raises
 * it off the ground. Face: `look` (-1..1) turns the face, `pupil` moves the pupils, `eyeScale` pops the eyes,
 * `eyeOpen`/`eyesClosed` (closed > 0.5 draws happy arcs), `brow` (-1 cross … 1.5 raised), `swirl` dizzy eyes,
 * `mouth`, `mouthScale`. Legs: `walk` (0..1 how much), `walkPhase` (cycles), `stride` (px), `feet` (both feet in
 * character space), `legSquash`. On top: `hatLift`, `hatSpin`, `sprout` (an angle). `smear` (0..1) morphs the body
 * into a teardrop trailing behind the character (the way it faces), or behind `smearDir` (the way it moves on screen,
 * 1 right, -1 left) when set. `scale` sizes the whole character about its feet; 0 (or less) draws nothing.
 */
export type Pose = {
  x: number; ground: number; face: 1 | -1;
  scale?: number; lift?: number; lean?: number; bend?: number; sx?: number; sy?: number; spin?: number;
  look?: number; pupil?: P; eyeScale?: number; eyeOpen?: number; eyesClosed?: number; brow?: number; swirl?: number;
  mouth?: Mouth; mouthScale?: number;
  armF?: Arm; armB?: Arm;
  walk?: number; walkPhase?: number; stride?: number; feet?: [P, P]; legSquash?: number;
  hatLift?: number; hatSpin?: number; sprout?: number;
  smear?: number; smearDir?: 1 | -1;
};

// ---- mouths (face-local, centred at 0, 0), morphed by Flubber

const ring = (f: (a: number) => P, n = 28): P[] => Array.from({ length: n }, (_, i) => f((i / n) * Math.PI * 2));
const MOUTHS: Record<MouthKey, P[]> = {
  smile: [[-40, -4], [-20, 8], [0, 12], [20, 8], [40, -4], [42, -8], [20, 14], [0, 18], [-20, 14], [-42, -8]],
  grin: [[-46, -10], [46, -10], [40, 10], [24, 26], [0, 32], [-24, 26], [-40, 10]],
  laugh: [[-50, -14], [50, -14], [44, 16], [26, 40], [0, 48], [-26, 40], [-44, 16]],
  o: ring((a) => [Math.cos(a) * 20, Math.sin(a) * 28 + 6]),
  shout: ring((a) => [Math.cos(a) * 36, Math.sin(a) * 44 + 10]),
  flat: [[-30, -3], [30, -3], [30, 3], [-30, 3]],
  frown: [[-34, 10], [-16, 0], [0, -3], [16, 0], [34, 10], [32, 14], [16, 5], [0, 3], [-16, 5], [-32, 14]],
  wavy: [[-36, 2], [-24, -6], [-12, 2], [0, -6], [12, 2], [24, -6], [36, 2], [36, 8], [24, 0], [12, 8], [0, 0],
    [-12, 8], [-24, 0], [-36, 8]],
};
const OPEN: Record<MouthKey, boolean> = { smile: false, grin: true, laugh: true, o: true, shout: true, flat: false, frown: false, wavy: false };

type Morph = (k: number) => P[];
const morph = (a: P[], b: P[], seg: number): Morph => flubber(a, b, { string: false, maxSegmentLength: seg }) as unknown as Morph;
const mouthCache = new Map<string, Morph>();

/** A mouth outline between two shapes (k = 0 is a, 1 is b). Flubber matches the rings and blends them. */
export const mouthPts = (a: MouthKey, b: MouthKey, k: number): P[] => {
  if (a === b || k <= 0) return MOUTHS[a];
  if (k >= 1) return MOUTHS[b];
  const key = `${a}>${b}`;
  let f = mouthCache.get(key);
  if (!f) mouthCache.set(key, (f = morph(MOUTHS[a], MOUTHS[b], 3)));
  return f(k);
};

const smearCache = new WeakMap<Character, Map<number, Morph>>();
/** The body outline morphed toward a long teardrop trailing behind (dir is the trailing side's sign). */
const smearPts = (c: Character, body: P[], back: 1 | -1, k: number): P[] => {
  let byDir = smearCache.get(c);
  if (!byDir) smearCache.set(c, (byDir = new Map()));
  let f = byDir.get(back);
  if (!f) {
    const tear: P[] = Array.from({ length: 40 }, (_, i) => {
      const a = (i / 40) * Math.PI * 2;
      const cx = Math.cos(a), sn = Math.sin(a);
      const trailing = cx * back > 0 ? 1 : 0;
      return [cx * c.rx * (1 + trailing * 2.6) * 1.05, sn * c.ry * (1 - trailing * 0.45 * Math.abs(cx))];
    });
    byDir.set(back, (f = morph(body, tear, 8)));
  }
  return f(k);
};

// ---- the rig

const walkFoot = (u: number, stride: number, liftH: number): P => {
  u = ((u % 1) + 1) % 1;
  if (u < 0.5) return [lerp(stride / 2, -stride / 2, u / 0.5), 0];
  const v = (u - 0.5) / 0.5;
  const e = v * v * (3 - 2 * v);
  return [lerp(-stride / 2, stride / 2, e), Math.sin(Math.PI * v) * liftH];
};

const mouthOf = (m: Mouth | undefined): [MouthKey, MouthKey, number] =>
  m === undefined ? ['smile', 'smile', 0] : typeof m === 'string' ? [m, m, 0] : m;

/** The character in this pose, as shapes in draw order (back arm, legs, body, face, top, front arm). */
export const buildCharacter = (c: Character, p: Pose): Shape[] => {
  const S = p.scale ?? 1;
  if (!(S > 0)) return []; // scaled to nothing (dividing by it would put NaN in every path)
  const sx = p.sx ?? 1, sy = p.sy ?? 1, lean = p.lean ?? 0, bend = p.bend ?? 0, face = p.face;
  const lift = p.lift ?? 0;
  const stride = p.stride ?? 70;
  const walk = p.walk ?? 0;
  const phase = p.walkPhase ?? 0;
  const bob = walk * 10 * (0.5 - 0.5 * Math.cos(4 * Math.PI * phase)); // up at the passing pose
  const legK = p.legSquash ?? 1;
  const hipsY = -(c.legLen * legK) - lift / S - bob;
  const bodyH = c.ry * 2 * sy;
  const bodyCy = hipsY - c.ry * sy + 6;
  const spin = p.spin ?? 0;

  // character space → composition pixels (spin about the body's centre, mirror, scale about the feet)
  const toScreen = ([x, y]: P): P => {
    if (spin) {
      const dx = x, dy = y - bodyCy;
      x = dx * Math.cos(spin) - dy * Math.sin(spin);
      y = bodyCy + dx * Math.sin(spin) + dy * Math.cos(spin);
    }
    return [p.x + x * face * S, p.ground + y * S];
  };
  // composition pixels → character space (toScreen undone: unscale, unmirror, unspin), for points the hands reach
  const fromScreen = ([sx0, sy0]: P): P => {
    const x = ((sx0 - p.x) * face) / S, y = (sy0 - p.ground) / S;
    if (!spin) return [x, y];
    const dy = y - bodyCy;
    return [x * Math.cos(spin) + dy * Math.sin(spin), bodyCy - x * Math.sin(spin) + dy * Math.cos(spin)];
  };
  // a point fixed to the body (relative to its centre, unsquashed) → character space, with squash, lean and bend
  const bodyLocal = ([bx, by]: P): P => {
    let x = bx * sx, y = by * sy + bodyCy;
    const h = clamp((hipsY - y) / Math.max(1, bodyH), 0, 1.6); // 0 at the hips, 1 at the top
    x += -Math.sin(lean) * (hipsY - y) + bend * h * h;
    y = hipsY - (hipsY - y) * Math.cos(lean);
    return [x, y];
  };
  const B = (pt: P): P => toScreen(bodyLocal(pt));

  // body outline: a pear, wider at the bottom
  const bodyRel: P[] = Array.from({ length: 40 }, (_, i) => {
    const a = (i / 40) * Math.PI * 2;
    const s = Math.sin(a); // +1 at the bottom
    return [Math.cos(a) * c.rx * (1 + c.pear * s), s * c.ry];
  });
  let body = bodyRel.map(B);

  // legs: noodles from the hips to the feet, and shoes
  const legs: Shape[] = [];
  for (const side of [-1, 1] as const) {
    let foot: P;
    if (p.feet) foot = side < 0 ? p.feet[0] : p.feet[1];
    else {
      const wf = walkFoot(phase + (side > 0 ? 0.5 : 0), stride, 26);
      foot = [lerp(side * c.hipW * 1.1, wf[0] + side * c.hipW * 0.75, walk), -wf[1] * walk - (lift / S) * 0.9];
    }
    const hip = bodyLocal([side * c.hipW, c.ry * 0.78]);
    const knee = 18 * (1 - clamp((hip[1] - foot[1]) / -c.legLen - 0.6, 0, 1)) + 6;
    const pts = cubicPts(hip, [hip[0] + knee, lerp(hip[1], foot[1], 0.35)], [foot[0] + knee * 0.6, lerp(hip[1], foot[1], 0.7)], foot, 14).map(toScreen);
    legs.push({ k: 'limb', pts, w: c.limbW * S, fill: c.limb, ink: 6 * S });
    const shoe = ellipsePts(foot[0] + 12, foot[1] - 15, 34, 17, 16).map(([x, y]): P => [x, Math.min(y, foot[1] + 1)]);
    legs.push({ k: 'blob', pts: shoe.map(toScreen), fill: c.shoe, ink: 6 * S });
  }

  // arms: hoses from the shoulder to a mitten
  const arm = (side: -1 | 1, a: Arm | undefined): Shape[] => {
    const sh = bodyLocal([side * c.rx * 0.82, -c.ry * 0.05]);
    const body: P = a?.hand ? [sh[0] + a.hand[0], sh[1] + a.hand[1]] : [sh[0] + side * 30, sh[1] + 90];
    const k = a?.reach ?? 1;
    const target = a?.world ? fromScreen(a.world) : body;
    const hand: P = [lerp(body[0], target[0], k), lerp(body[1], target[1], k)];
    const dx = hand[0] - sh[0], dy = hand[1] - sh[1];
    const len = Math.hypot(dx, dy) || 1;
    const nx = -dy / len, ny = dx / len;
    const sag = (a?.sag ?? 0.35) * len * 0.35 * side;
    let pts = cubicPts(sh, [sh[0] + dx * 0.33 + nx * sag, sh[1] + dy * 0.33 + ny * sag],
      [sh[0] + dx * 0.66 + nx * sag, sh[1] + dy * 0.66 + ny * sag], hand, Math.max(12, Math.round(len / 14)));
    const wig = a?.wiggle ?? 0;
    if (wig) {
      const n = pts.length - 1;
      pts = pts.map(([x, y], i): P => {
        const s = i / n;
        const w = wig * Math.sin(s * Math.PI) * Math.sin(s * Math.PI * 3 - (a?.wigglePhase ?? 0));
        return [x + nx * w, y + ny * w];
      });
    }
    const sp = pts.map(toScreen);
    const hs = toScreen(hand);
    const ang = Math.atan2(sp[sp.length - 1][1] - sp[sp.length - 2][1], sp[sp.length - 1][0] - sp[sp.length - 2][0]);
    const r = c.handR * S;
    const open = a?.open ?? 0;
    // a mitten: palm and thumb, along the forearm
    const palm = ellipsePts(0, 0, r * (1 + 0.15 * open), r * 0.85, 14).map(([x, y]) => rot([x + r * 0.5, y], ang, hs));
    const thumb = ellipsePts(r * 0.2, -r * 0.75 * side * face, r * 0.42, r * 0.3, 10).map((q) => rot(q, ang - 0.5 * side * face, hs));
    return [
      { k: 'limb', pts: sp, w: c.limbW * S, fill: c.limb, ink: 6 * S },
      { k: 'blob', pts: thumb, fill: c.fill, ink: 5 * S },
      { k: 'blob', pts: palm, fill: c.fill, ink: 6 * S },
    ];
  };
  const armB = arm(-1, p.armB), armF = arm(1, p.armF);

  // smear: the body morphs into a teardrop trailing behind (behind its back, or opposite smearDir on screen)
  const smear = p.smear ?? 0;
  if (smear > 0.01) body = smearPts(c, bodyRel, (-(p.smearDir ?? face) * face) as 1 | -1, Math.min(1, smear)).map(B);

  // face
  const look = (p.look ?? 0) * c.rx * 0.32;
  const eyeC = (side: -1 | 1): P => [look + side * c.eyeGap, -c.ry * c.eyeY];
  const faceShapes: Shape[] = [];
  const es = p.eyeScale ?? 1;
  const closed = p.eyesClosed ?? 0;
  const open = clamp((p.eyeOpen ?? 1) * (1 - closed), 0.04, 1);
  for (const side of [-1, 1] as const) {
    const [ex, ey] = eyeC(side);
    const w = c.eyeRx * es * (side * (p.look ?? 0) > 0 ? 1.04 : 0.96);
    const h = c.eyeRy * es;
    if (closed > 0.5) {
      // happy closed eyes: upturned arcs
      faceShapes.push({ k: 'line', pts: ([[ex - w * 0.8, ey + 4], [ex, ey - h * 0.45], [ex + w * 0.8, ey + 4]] as P[]).map(B), w: 9 * S });
      continue;
    }
    faceShapes.push({ k: 'blob', pts: ellipsePts(ex, ey, w, h * open, 18).map(B), fill: '#ffffff', ink: 6 * S });
    if (open > 0.25) {
      const swirl = p.swirl ?? 0;
      if (swirl > 0) {
        const sw: P[] = Array.from({ length: 30 }, (_, i) => {
          const a = i * 0.6 + swirl * 8 * side;
          const rr = (i / 30) * w * 0.75;
          return B([ex + Math.cos(a) * rr, ey + Math.sin(a) * rr * open]);
        });
        faceShapes.push({ k: 'line', pts: sw, w: 5 * S });
      } else {
        const pu = p.pupil ?? [0, 0];
        const [px, py] = B([ex + pu[0] * w * 0.45 + (p.look ?? 0) * w * 0.25, ey + pu[1] * h * 0.4 * open + h * 0.12]);
        const pr = c.eyeRx * 0.42 * Math.sqrt(es) * Math.min(1, open + 0.3) * S;
        faceShapes.push({ k: 'dot', x: px, y: py, r: pr, fill: '#1d1414' });
        faceShapes.push({ k: 'dot', x: px - pr * 0.35 * face, y: py - pr * 0.4, r: pr * 0.32, fill: '#ffffff' });
      }
    }
    const br = p.brow ?? 0;
    const by = ey - h - 12 - br * 22;
    const tilt = br < 0 ? -br * 10 * side : 0;
    faceShapes.push({ k: 'line', pts: ([[ex - w * 0.7, by + tilt], [ex, by - 6 - br * 4], [ex + w * 0.7, by - tilt]] as P[]).map(B), w: 8 * S });
  }
  if (c.cheek) for (const side of [-1, 1] as const) {
    const [ex, ey] = eyeC(side);
    faceShapes.unshift({ k: 'blob', pts: ellipsePts(ex + side * c.eyeRx * 0.7, ey + c.eyeRy + 22, 20, 11, 10).map(B), fill: c.cheek, layer: 'hi' });
  }
  const [ma, mb, mk] = mouthOf(p.mouth);
  const ms = p.mouthScale ?? 1;
  const mcy = -c.ry * c.eyeY + c.eyeRy * es + 46;
  const mouthLocal = mouthPts(ma, mb, mk).map(([x, y]): P => [look * 1.15 + x * ms, mcy + y * ms]);
  const openNow = mk < 0.5 ? OPEN[ma] : OPEN[mb];
  faceShapes.push({ k: 'blob', pts: mouthLocal.map(B), fill: openNow ? '#7a2231' : '#2a1d1a', ink: (openNow ? 5 : 2) * S });
  if (openNow) {
    const ys = mouthLocal.map((q) => q[1]);
    const bottom = Math.max(...ys), top = Math.min(...ys);
    if (bottom - top > 18) {
      faceShapes.push({ k: 'blob', pts: ellipsePts(look * 1.15 + 6, bottom - (bottom - top) * 0.22, 16 * ms, (bottom - top) * 0.18, 10).map(B), fill: '#ff7d8e' });
    }
  }

  // hat or sprout
  const top: Shape[] = [];
  if (c.hat) {
    const hc: P = [0, -c.ry * 0.86 - (p.hatLift ?? 0)];
    const hs = p.hatSpin ?? 0;
    const place = (q: P) => B(add(rot(q, hs), hc));
    const cap: P[] = Array.from({ length: 22 }, (_, i) => {
      const a = Math.PI + (i / 21) * Math.PI;
      return [Math.cos(a) * c.rx * 0.78, Math.sin(a) * c.ry * 0.42];
    });
    const capPts = [...cap, [c.rx * 0.8, 6] as P, [-c.rx * 0.8, 6] as P].map(place);
    const band = ([[-c.rx * 0.86, -8], [c.rx * 0.86, -8], [c.rx * 0.88, 14], [-c.rx * 0.88, 14]] as P[]).map(place);
    const pom = ellipsePts(0, -c.ry * 0.42 - 16, 22, 20, 12).map(place);
    top.push({ k: 'blob', pts: capPts, fill: c.hat.fill, ink: 6 * S }, { k: 'blob', pts: band, fill: c.hat.band, ink: 6 * S },
      { k: 'blob', pts: pom, fill: c.hat.pom, ink: 6 * S });
  }
  if (c.sprout) {
    const ang = p.sprout ?? 0;
    const base: P = [0, -c.ry * 0.97];
    const tip: P = [base[0] + Math.sin(ang) * 70, base[1] - Math.cos(ang) * 70];
    const mid: P = [base[0] + Math.sin(ang * 0.4) * 38, base[1] - Math.cos(ang * 0.4) * 38];
    top.push({ k: 'line', pts: [base, mid, tip].map(B), w: 9 * S, color: c.sprout.stem });
    const leaf = (sgn: 1 | -1, a: number) => ([[0, 0], [22, -18], [52, -10], [64, 4], [40, 14], [16, 10]] as P[])
      .map(([x, y]) => B(add(rot([x * sgn, y], a), tip)));
    top.push({ k: 'blob', pts: leaf(1, ang - 0.9), fill: c.sprout.leaf, ink: 5 * S }, { k: 'blob', pts: leaf(-1, ang + 0.9), fill: c.sprout.leaf, ink: 5 * S });
  }

  // shading: the lit body shrunk toward the front-top leaves a shade crescent at the back-bottom; a highlight on top
  const lit = bodyRel.map(([x, y]): P => [x * 0.9 + c.rx * 0.075, y * 0.9 - c.ry * 0.07]);
  const hi = ellipsePts(c.rx * 0.38, -c.ry * 0.55, c.rx * 0.16, c.ry * 0.09, 12, -0.5);

  const out: Shape[] = [];
  if (p.armB?.front !== true) out.push(...armB);
  if (p.armF?.front !== true) out.push(...armF);
  out.push(...legs);
  const smearing = smear > 0.3;
  out.push({ k: 'blob', pts: body, fill: smearing ? c.fill : c.shade });
  if (!smearing) {
    out.push({ k: 'blob', pts: lit.map(B), fill: c.fill, layer: 'shade' });
    out.push({ k: 'blob', pts: hi.map(B), fill: c.hi, layer: 'hi' });
  }
  out.push({ k: 'blob', pts: body, fill: 'none', ink: 7 * S });
  out.push(...faceShapes, ...top);
  if (p.armB?.front === true) out.push(...armB);
  if (p.armF?.front === true) out.push(...armF);
  return out;
};
