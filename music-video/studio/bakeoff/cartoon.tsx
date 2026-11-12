import React from 'react';
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { useSongTime, type BakeoffProps } from '@mv/kit';
import {
  addPose, breath, Cartoon, cast, clamp, DustPuffs, eases, Emote, Flash, follow, ImpactBurst, INK, inkPath, jitter,
  lerp, mixPose, poses, poseTrack, ramp, seeded, shake, Shadow, smooth, SpeedLines, springStep, swell, TakeLines, track,
  walk, wobble, zoomAt, type P, type Pose, type PoseLayer,
} from '@mv/kit/cartoon';

// The cartoon engine's starting point for the bake-off brief (the make skill's references/bakeoff.md), and the
// template for any two-character cartoon scene: a rooftop at dusk, the bean waiting at the parapet, the plum walking
// in and stopping short, a double take and a wave in close-up, a playful square-up, the fists meeting on the hit, a
// laugh, and both looking out over the city again. Every value is a function of c, the choreography time in seconds
// written for a hit at HIT = 6 s; `beat` bends the window so the clash lands on the real hit. Rewrite it to the brief.
const HIT = 6;
/** Window time → choreography time: the stretch before the real hit is scaled to HIT s, after it runs as is. */
const beat = (u: number, hit: number) => (hit > 0 && u <= hit ? (u * HIT) / hit : HIT + (u - hit));
/** The video's jolts answer (its look.ts `jolts`): the camera shakes on the clash only when it is yes. */
const jolts = false;

const G = 900;                  // the roof's walking line (feet)
const A_X = 760;                // the bean waits here
const B_STOP = 1240;            // where the plum stops short
const MEET: P = [1000, 772];    // where the fists meet on the hit (below the faces)
const blink = (c: number, at: number[]) => Math.max(0, ...at.map((b) => swell(c, b, b + 0.05, b + 0.07, b + 0.14)));

// ---- the plum's path: walks in from off screen, stops short; at the end steps up beside the bean
const bx = (c: number) => track(c, [[0, 2150], [2.3, B_STOP, eases.out], [8.5, B_STOP], [9.3, 1130]]);

/** The fist's way to the meeting point: wound back, then shot out on the hit, held through the bump, pulled home. */
const strikeArm = (c: number, from: P, home: P | null) => {
  const out = ramp(c, 5.86, HIT, eases.in);
  const back = ramp(c, 7.05, 7.45);
  if (out <= 0 || back >= 1 || !home) return null;
  const bump = 10 * wobble(c, HIT, 3, 4);
  const hit: P = [MEET[0], MEET[1] + bump];
  const at: P = c < 7.05 ? [lerp(from[0], hit[0], out), lerp(from[1], hit[1], out)] : [lerp(hit[0], home[0], back), lerp(hit[1], home[1], back)];
  return { world: at, sag: 0.08, front: true, wiggle: 18 * (1 - out) * (c < HIT ? 1 : 0) + 22 * wobble(c, HIT, 3.2, 5), wigglePhase: c * 30 };
};

const poseA = (c: number): Pose => {
  const facing: 1 | -1 = c >= 2.62 && c < 8.6 ? 1 : -1; // looks out to the left, turns to the plum, looks out again
  let p: PoseLayer = poseTrack(c, [
    [0, poses.lookOut], [2.55, poses.lookOut],
    [2.9, { sy: 0.84, eyeOpen: 0.45, brow: -0.4, mouth: 'flat', armF: { hand: [20, 60] }, armB: { hand: [-20, 60] } }, eases.out],
    [3.45, { mouth: 'grin', brow: 0.9, eyeScale: 1.15, armF: { hand: [40, 30], sag: 0.3 }, armB: { hand: [-30, 70] } }],
    [4.45, { mouth: 'grin', brow: 0.7, eyeScale: 1.1, armF: { hand: [40, 30], sag: 0.3 }, armB: { hand: [-30, 70] } }],
    [4.95, poses.guard, eases.outBack], [5.5, poses.guard],
    [5.86, poses.windup, eases.out], [HIT, poses.punch, eases.in], [7.05, poses.punch],
    [7.45, poses.laugh], [8.45, poses.laugh], [9.0, poses.lookOut], [10, poses.lookOut],
  ]);
  // the double take: a spring that overshoots (eyes pop, jaw drops, hat flies), then settles into recognition
  const take = clamp(springStep(c, 2.95, 2.6, 3.2), 0, 1.15) * (1 - ramp(c, 3.3, 3.62));
  p = mixPose(p, poses.take, take);
  p = addPose(p, breath(c, 0.4));
  p = addPose(p, { lean: 0.04 * Math.sin(c * 1.3) }, 1 - ramp(c, 2.4, 2.6) + ramp(c, 9, 9.6)); // weight shifting
  p = addPose(p, { lift: 9 * Math.abs(Math.sin(c * Math.PI * 4)) }, swell(c, 4.9, 5.0, 5.5, 5.7)); // boxer bounce
  p = addPose(p, { sy: 0.06 * Math.abs(Math.sin((c - 7.45) * Math.PI * 4)) }, swell(c, 7.45, 7.5, 8.3, 8.45)); // laughing
  p = addPose(p, { sy: 0.16 * wobble(c, HIT, 3, 5), lean: -0.18 * wobble(c, HIT, 2.4, 4.5) }); // the impact's recoil
  p = addPose(p, { eyeOpen: -0.95 * blink(c, [1.25, 4.2, 9.4]) });
  const home: P = [A_X + 90, 760];
  const arm = strikeArm(c, [A_X + 10, 730], home);
  return {
    ...p, x: A_X, ground: G, face: facing,
    look: (p.look ?? 0) + (facing > 0 ? 0.35 : 0),
    pupil: c >= 3.45 && c < 8.6 ? [0.5, 0] : p.pupil,
    hatLift: (p.hatLift ?? 0) + 34 * swell(c, HIT, HIT + 0.06, HIT + 0.25, HIT + 0.9, eases.out),
    hatSpin: 0.04 * Math.sin(c * 1.7) + 0.35 * wobble(c, 2.95, 2, 3) - 0.25 * wobble(c, HIT, 2.5, 4),
    ...(arm ? { armF: arm } : {}),
  };
};

const poseB = (c: number): Pose => {
  const x = bx(c);
  const walking = 1 - ramp(c, 2.1, 2.35) + swell(c, 8.45, 8.55, 9.15, 9.3);
  let p: PoseLayer = poseTrack(c, [
    [0, poses.rest], [2.9, poses.rest],
    [3.05, { ...poses.startle, eyeScale: 1.2, sy: 1.05 }, eases.out],
    [3.55, { ...poses.rest, mouth: 'smile' }],
    [3.75, poses.wave, eases.outBack], [4.35, poses.wave],
    [4.6, { ...poses.rest, mouth: 'grin', brow: 0.5 }],
    [5.0, poses.guard, eases.outBack], [5.5, poses.guard],
    [5.86, poses.windup, eases.out], [HIT, poses.punch, eases.in], [7.05, poses.punch],
    [7.45, poses.laugh], [8.45, poses.laugh], [8.6, poses.rest], [9.3, poses.lookOut], [10, poses.lookOut],
  ]);
  p = addPose(p, walk(x, -1, clamp(walking), 62));
  p = addPose(p, breath(c, 2.1));
  p = addPose(p, { sy: -0.14 * wobble(c, 2.3, 2.4, 4) }); // stopping short
  p = addPose(p, { armF: { hand: [34 * Math.sin(c * 16), 0] } }, swell(c, 3.7, 3.8, 4.25, 4.4)); // the wave
  p = addPose(p, { lift: 9 * Math.abs(Math.sin(c * Math.PI * 4 + 1.3)) }, swell(c, 4.95, 5.05, 5.5, 5.7));
  p = addPose(p, { lift: 14 * Math.abs(Math.sin((c - 7.45) * Math.PI * 4)) }, swell(c, 7.45, 7.5, 8.3, 8.45));
  p = addPose(p, { sy: 0.16 * wobble(c, HIT, 3.2, 5), lean: -0.18 * wobble(c, HIT, 2.6, 4.5) });
  p = addPose(p, { eyeOpen: -0.95 * blink(c, [0.7, 2.6, 8.0]) });
  // the sprout lags the walk and the hops, sways in the breeze and is blown back by the clash
  const headX = (u: number) => -bx(u), headY = (u: number) => (u > 2.2 && u < 2.5 ? 20 * wobble(u, 2.3, 2.4, 4) : 0);
  const lag = (follow(headX, c, { freq: 2.6, zeta: 0.18 }) - headX(c)) * 0.008 + (follow(headY, c, { freq: 3.2, zeta: 0.2 }) - headY(c)) * 0.01;
  const sprout = clamp(lag, -1, 1) + 0.12 * Math.sin(c * 2.1) - 0.9 * swell(c, HIT, HIT + 0.05, HIT + 0.2, HIT + 1.0, eases.out)
    + 0.4 * wobble(c, HIT + 1.0, 2.5, 3);
  const arm = strikeArm(c, [B_STOP - 10, 770], [B_STOP - 80, 800]);
  return { ...p, x, ground: G, face: -1, sprout, look: (p.look ?? 0) + (c > 3.5 && c < 8.6 ? 0.3 : 0),
    pupil: c > 3.5 && c < 8.6 ? [0.5, 0] : p.pupil, ...(arm ? { armF: arm } : {}) };
};

// ---- the set: a city roof at dusk, inked like the characters (lines boil on threes)

/** A rectangle as points every ~40 px, so the brush follows straight edges. */
const rectPts = (x: number, y: number, w: number, h: number): P[] => {
  const edge = (a: P, b: P) => {
    const n = Math.max(1, Math.round(Math.hypot(b[0] - a[0], b[1] - a[1]) / 40));
    return Array.from({ length: n }, (_, i): P => [lerp(a[0], b[0], i / n), lerp(a[1], b[1], i / n)]);
  };
  return [...edge([x, y], [x + w, y]), ...edge([x + w, y], [x + w, y + h]), ...edge([x + w, y + h], [x, y + h]), ...edge([x, y + h], [x, y])];
};
const poly = (pts: P[]) => `M ${pts.map(([x, y]) => `${x.toFixed(1)} ${y.toFixed(1)}`).join(' L ')} Z`;

const Inked: React.FC<{ pts: P[]; fill: string; seed: number; ink?: number; round?: boolean; amp?: number }> = ({ pts, fill, seed, ink = 6, round, amp = 1.1 }) => (
  <g>
    <path d={round ? smooth(jitter(pts, seed, amp)) : poly(jitter(pts, seed, amp * 0.6))} fill={fill} />
    {ink > 0 && <path d={inkPath(jitter(pts, seed + 1, amp), seed, ink, true)} fill={INK} />}
  </g>
);

const r0 = seeded(11);
const FAR = Array.from({ length: 16 }, (_, i) => ({ x: -40 + i * 128 + r0() * 30, w: 90 + r0() * 70, top: 470 + r0() * 170 }));
const NEAR = Array.from({ length: 9 }, (_, i) => ({ x: -60 + i * 235 + r0() * 50, w: 150 + r0() * 80, top: 540 + r0() * 120 }));
const LIT = Array.from({ length: 400 }, () => r0());

const Rooftop: React.FC<{ c: number; frame: number }> = ({ c, frame }) => {
  const b = (k: number) => Math.floor(frame / 3) * 17 + k * 131;
  return (
    <svg width={1920} height={1080} viewBox="0 0 1920 1080" style={{ position: 'absolute' }}>
      <defs>
        <linearGradient id="cartoon-dusk" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#2b2a5c" />
          <stop offset="0.45" stopColor="#7c4f8c" />
          <stop offset="0.72" stopColor="#f2a07b" />
          <stop offset="1" stopColor="#ffd9a8" />
        </linearGradient>
      </defs>
      <rect width={1920} height={1080} fill="url(#cartoon-dusk)" />
      <circle cx={340} cy={600} r={190} fill="#ffe2a6" opacity={0.35} />
      <Inked pts={Array.from({ length: 24 }, (_, i): P => [340 + Math.cos((i / 24) * Math.PI * 2) * 112, 600 + Math.sin((i / 24) * Math.PI * 2) * 112])}
        fill="#ffd27a" seed={b(1)} ink={5} round />
      {[[420, 250, 1.0], [1350, 190, 0.8], [1700, 330, 0.6]].map(([x0, y, s], i) => {
        const x = ((x0 + c * 9 * (i + 1)) % 2300) - 200;
        return <Inked key={i} round seed={b(2 + i)} ink={4} fill="#f6b8a0"
          pts={Array.from({ length: 20 }, (_, k): P => [x + Math.cos((k / 20) * Math.PI * 2) * 170 * s, y + Math.sin((k / 20) * Math.PI * 2) * 26 * s])} />;
      })}
      {FAR.map((f, i) => <rect key={i} x={f.x} y={f.top} width={f.w} height={800 - f.top} fill="#5a4377" />)}
      {NEAR.map((n, i) => (
        <g key={i}>
          <Inked pts={rectPts(n.x, n.top, n.w, 760 - n.top)} fill="#3b2d58" seed={b(10 + i)} ink={5} />
          {Array.from({ length: 12 }, (_, k) => {
            const col = k % 3, row = Math.floor(k / 3);
            const y = n.top + 26 + row * 46;
            return y < 730 && LIT[i * 12 + k] > 0.45
              ? <rect key={k} x={n.x + 22 + col * ((n.w - 44) / 3 + 4)} y={y} width={(n.w - 44) / 3 - 10} height={24} fill="#ffd98a" opacity={0.85} />
              : null;
          })}
        </g>
      ))}
      {/* the water tower */}
      {[1640, 1700, 1760, 1820].map((x, i) => <Inked key={i} pts={rectPts(x, 520, 12, 210)} fill="#6b4a3a" seed={b(30 + i)} ink={4} />)}
      <Inked pts={rectPts(1610, 380, 240, 160)} fill="#a8683a" seed={b(35)} ink={6} />
      <Inked pts={[[1600, 384], [1730, 300], [1860, 384]]} fill="#7b4fd6" seed={b(36)} ink={6} />
      {/* the parapet and its railing */}
      <Inked pts={rectPts(-40, 726, 2000, 84)} fill="#c7a79b" seed={b(40)} ink={6} />
      {Array.from({ length: 18 }, (_, i) => <Inked key={i} pts={rectPts(20 + i * 112, 640, 10, 88)} fill="#e7d8cf" seed={b(50 + i)} ink={4} />)}
      <Inked pts={rectPts(-40, 632, 2000, 14)} fill="#e7d8cf" seed={b(70)} ink={5} />
      {/* the roof */}
      <Inked pts={rectPts(-40, 806, 2000, 320)} fill="#76697e" seed={b(80)} ink={6} />
      {Array.from({ length: 7 }, (_, i) => (
        <path key={i} d={inkPath([[-40, 860 + i * 34 + i * i * 3], [2000, 860 + i * 34 + i * i * 3]], b(90 + i), 3, false)} fill="#5f5468" />
      ))}
      <Inked pts={rectPts(80, 760, 190, 120)} fill="#9a8fa3" seed={b(99)} ink={6} />
    </svg>
  );
};

export const Bakeoff: React.FC<BakeoffProps> = ({ from, hit: at }) => {
  const frame = useCurrentFrame();
  const hit = Math.max(1, at); // a hit right at the window's start still leaves the walk-in a second
  const c = beat(useSongTime() - from, hit);
  const a = poseA(c), b = poseB(c);
  // the camera: wide, a push-in on the bean's double take, a whip to the plum's wave, back out for the square-up
  const z = track(c, [[0, 0.04], [2.5, 0.04], [2.95, 0.55, eases.out], [3.55, 0.55], [3.85, 0.55], [4.35, 0.5],
    [4.85, 0.07], [5.8, 0.12], [HIT, 0.18, eases.in], [6.5, 0.08, eases.out], [10, 0.04]]);
  const fx = track(c, [[0, 960], [2.5, 960], [2.95, A_X, eases.out], [3.55, A_X], [3.85, B_STOP], [4.35, B_STOP], [4.85, 990], [10, 960]]);
  const fy = track(c, [[0, 600], [2.5, 600], [2.95, 520, eases.out], [3.55, 520], [3.85, 660], [4.35, 660], [4.85, 640], [10, 620]]);
  const [shx, shy] = jolts ? shake(c, HIT, 22) : [0, 0];
  const strikeA = a.armF?.world, strikeB = b.armF?.world;
  const rushing = c > 5.86 && c < HIT ? 1 : 0;
  return (
    <AbsoluteFill style={{ overflow: 'hidden', background: '#2b2a5c' }}>
      <AbsoluteFill style={{ transform: zoomAt(z, fx, fy, shx, shy) }}>
        <Rooftop c={c} frame={frame} />
        <svg width={1920} height={1080} viewBox="0 0 1920 1080" style={{ position: 'absolute' }}>
          <Shadow x={a.x} y={G} w={120} lift={a.lift} />
          <Shadow x={b.x} y={G} w={100} lift={b.lift} />
          <DustPuffs t={c} frame={frame} t0={2.3} x={B_STOP - 50} y={G - 8} n={5} dir={-1} spread={150} />
          <DustPuffs t={c} frame={frame} t0={HIT} x={MEET[0]} y={G - 8} n={8} spread={300} />
          {strikeA && <SpeedLines amount={rushing} x={strikeA[0]} y={strikeA[1]} h={80} dir={1} seed={3} />}
          {strikeB && <SpeedLines amount={rushing} x={strikeB[0]} y={strikeB[1]} h={80} dir={-1} seed={5} />}
          <Cartoon character={cast.plum} pose={b} seed={2} />
          <Cartoon character={cast.bean} pose={a} seed={1} />
          <ImpactBurst t={c} t0={HIT} x={MEET[0]} y={MEET[1]} r={150} />
          <TakeLines t={c} t0={2.96} x={A_X} y={430} r={170} />
          <Emote t={c} t0={2.98} t1={3.6} x={A_X + 170} y={330} kind="!" />
          <Emote t={c} t0={3.05} t1={3.55} x={B_STOP + 120} y={560} kind="sweat" size={0.8} />
          <Emote t={c} t0={7.7} t1={9.7} x={MEET[0] - 20} y={430} kind="heart" />
        </svg>
      </AbsoluteFill>
      <Flash amount={c >= HIT && c < HIT + 0.034 ? 0.75 : c >= HIT && c < HIT + 0.067 ? 0.3 : 0} />
    </AbsoluteFill>
  );
};
