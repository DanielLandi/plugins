import React, { useCallback } from 'react';
import { AbsoluteFill } from 'remotion';
import { type BakeoffProps } from '@mv/kit';
import {
  addPose, Avatar, breath, CameraRig, eases, faceYaw, fingers, mixPose, poses, poseTrack, ramp, SkyDome, Stage,
  sway, swell, track, walkCycle, type AvatarState, type CameraKey, type Pose, type Vec3,
} from '@mv/kit/three';
import first from '@mv/avatars/vroid-sample-1.vrm';
import second from '@mv/avatars/vroid-sample-2.vrm';

// The vrm engine's starting point for the bake-off brief (the make skill's references/bakeoff.md), and the template
// for any two-character VRM scene: a rooftop at dusk, one character waiting, the other walking in, a turn to each
// other, a playful square-up and a fist bump on the hit. Every value is a function of t (seconds into the window),
// written for a hit at HIT = 6 s; `beat` below bends the window so the bump lands on the real hit. Rewrite the beats
// to the brief.
const HIT = 6;
/** Window time → choreography time: the stretch before the real hit is scaled to HIT s, after it runs as is. */
const beat = (u: number, hit: number) => (hit > 0 && u <= hit ? (u * HIT) / hit : HIT + (u - hit));
const A_AT: Vec3 = [-0.46, 0, 0];
const B_STOP = 0.46;
const bx = (t: number) => track(t, [[0, 3.2], [2.6, B_STOP, eases.out]]);
const eyes = (x: number): Vec3 => [x, 1.35, 0];
const blink = (t: number, at: number[]) => Math.max(0, ...at.map((b) => swell(t, b, b + 0.06, b + 0.08, b + 0.16)));

const driveA = (t: number): AvatarState => {
  const noticed = ramp(t, 1.6, 2.0, eases.out);
  let pose: Pose = poseTrack(t, [
    [0, poses.handsBehind],
    [1.6, poses.handsBehind],
    [2.2, poses.relax],
    [4.4, poses.relax],
    [5.0, mixPose(poses.relax, poses.guardR, 0.7), eases.outBack],
    [5.6, mixPose(poses.guardR, poses.windupR, 0.5)],
    [HIT, poses.fistBumpR, eases.in],
    [7.2, poses.fistBumpR],
    [8.0, poses.laugh],
  ]);
  pose = addPose(pose, { head: [-0.25 * (1 - noticed), 0, 0], neck: [-0.08 * (1 - noticed), 0, 0] });
  pose = addPose(addPose(pose, breath(t, 0.27)), sway(t, 1 - ramp(t, 4.4, 5) + ramp(t, 7.4, 8), 0.3));
  pose = addPose(pose, fingers(0.35 + 1.05 * ramp(t, 4.6, 5.0)));
  // The two samples differ in height: A's fist comes down a little to meet B's.
  pose = addPose(pose, { rightUpperArm: [0, 0, 0.14] }, swell(t, 5.6, HIT, 7.2, 8.0));
  return {
    pos: A_AT,
    yaw: track(t, [[0, 0.35], [1.7, 0.35], [2.3, faceYaw(A_AT, [bx(2.3), 0, 0]), eases.out], [10, faceYaw(A_AT, [B_STOP, 0, 0])]]),
    hips: [0, -0.04 * ramp(t, 4.6, 5.0) * (1 - ramp(t, 7.2, 7.8)), 0],
    pose,
    expr: { relaxed: 0.4 * (1 - noticed), Surprised: swell(t, 1.7, 1.85, 2.1, 2.5), happy: ramp(t, 2.5, 3.0) * (1 - ramp(t, 4.5, 4.8)) + ramp(t, HIT, HIT + 0.2),
      angry: 0.3 * swell(t, 4.8, 5.0, 5.7, HIT), blink: blink(t, [0.8, 3.4, 7.9]) },
    lookAt: t < 1.6 ? [0, 3.5, -4] : eyes(bx(t)),
    wind: [0.6 * swell(t, HIT, HIT + 0.05, HIT + 0.2, HIT + 0.9), 0, 0],
  };
};

const driveB = (t: number): AvatarState => {
  const walking = 1 - ramp(t, 2.2, 2.6);
  let pose: Pose = poseTrack(t, [
    [0, poses.relax],
    [2.6, poses.relax],
    [3.0, poses.waveL, eases.out],
    [3.8, poses.waveL],
    [4.4, poses.relax],
    [5.0, mixPose(poses.relax, poses.guardL, 0.7), eases.outBack],
    [5.6, mixPose(poses.guardL, poses.windupL, 0.5)],
    [HIT, poses.fistBumpL, eases.in],
    [7.2, poses.fistBumpL],
    [8.0, poses.laugh],
  ]);
  pose = addPose(pose, walkCycle(t * 0.9, walking));
  const wave = swell(t, 2.9, 3.0, 3.6, 3.8);
  pose = addPose(pose, { leftLowerArm: [0, 0, -0.3 * Math.sin(t * 13) * wave] });
  pose = addPose(addPose(pose, breath(t, 0.31)), sway(t, ramp(t, 2.6, 3.2) * (1 - ramp(t, 4.4, 5)), 1.7));
  pose = addPose(pose, fingers(0.35 + 1.05 * ramp(t, 4.6, 5.0)));
  pose = addPose(pose, { leftUpperArm: [0, 0, 0.22] }, swell(t, 5.6, HIT, 7.2, 8.0));
  const x = bx(t);
  return {
    pos: [x, 0, 0],
    yaw: faceYaw([x, 0, 0], A_AT),
    hips: [0, 0.03 * Math.abs(Math.sin(t * 0.9 * Math.PI * 2)) * walking - 0.04 * ramp(t, 4.6, 5.0) * (1 - ramp(t, 7.2, 7.8)), 0],
    pose,
    expr: { happy: ramp(t, 2.6, 3.0) * (1 - ramp(t, 4.5, 4.8)) + ramp(t, HIT, HIT + 0.2), angry: 0.3 * swell(t, 4.8, 5.0, 5.7, HIT),
      blink: blink(t, [1.2, 4.2, 8.3]) },
    lookAt: eyes(A_AT[0]),
    wind: [-0.6 * swell(t, HIT, HIT + 0.05, HIT + 0.2, HIT + 0.9), 0, 0],
  };
};

/** The camera on the window's clock (choreography seconds mapped back onto the window), as song-time keys. */
const shots = (from: number, hit: number): CameraKey[] => {
  const at = (c: number) => from + (c <= HIT ? (c * hit) / HIT : hit + (c - HIT));
  return keys.map((k) => ({ ...k, t: at(k.t) }));
};
const keys: CameraKey[] = [
  { t: 0, pos: [0.3, 1.25, 5.2], look: [0.6, 1.0, 0], fov: 30 },
  { t: 2.6, pos: [0.0, 1.3, 4.6], look: [0, 1.1, 0], fov: 30 },
  { t: 4.4, pos: [-0.2, 1.35, 3.6], look: [0, 1.15, 0], fov: 30 },
  { t: HIT - 0.15, pos: [0.25, 1.3, 2.6], look: [0, 1.2, 0], fov: 32, ease: 'in' },
  { t: HIT + 0.4, pos: [0.15, 1.3, 2.9], look: [0, 1.2, 0], fov: 32, ease: 'out' },
  { t: 10, pos: [0.0, 1.35, 3.8], look: [0, 1.1, 0], fov: 30 },
];

export const Bakeoff: React.FC<BakeoffProps> = ({ from, hit: at }) => {
  const hit = Math.max(1, at); // a hit right at the window's start still leaves the walk-in a second
  // drive() gets song time; the beats above are written in window time, for a hit at HIT.
  const a = useCallback((t: number) => driveA(beat(t - from, hit)), [from, hit]);
  const b = useCallback((t: number) => driveB(beat(t - from, hit)), [from, hit]);
  return (
    <AbsoluteFill>
      <Stage background="#2a2346" fov={30} exposure={1.05}>
        <CameraRig keys={shots(from, hit)} fov={30} />
        <SkyDome zenith="#2b2a5c" horizon="#f2a07b" ground="#3a3048" sunColor="#ffd9a8" sunDir={[-0.6, 0.08, -1]} sunSize={0.002} glow={0.5} />
        <hemisphereLight args={['#c9c4ff', '#3b2f45', 0.9]} />
        <directionalLight position={[-3, 2.2, -2]} intensity={2.2} color="#ffc596" />
        <directionalLight position={[2, 2.5, 3]} intensity={1.1} color="#b8c4ff" />
        {/* the roof and its parapet */}
        <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
          <planeGeometry args={[14, 10]} />
          <meshStandardMaterial color="#76697e" roughness={0.95} />
        </mesh>
        <mesh position={[0, 0.35, -2.2]}>
          <boxGeometry args={[14, 0.7, 0.25]} />
          <meshStandardMaterial color="#c7a79b" roughness={0.9} />
        </mesh>
        <Avatar url={first} drive={a} from={from} outline={1.4} />
        <Avatar url={second} drive={b} from={from} outline={1.4} />
      </Stage>
    </AbsoluteFill>
  );
};
