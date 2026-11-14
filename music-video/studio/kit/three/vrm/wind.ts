// Air on hair and cloth: a character moving through still air feels a headwind. The drag comes from the character's
// own velocity, taken from drive() itself at t ± a few milliseconds (song time, the same clock the spring replay
// steps on), never from wall time or the previous frame, so any frame still renders the same alone or in sequence.
import * as THREE from 'three';
import type { Vec3 } from '../camera';

type Moving = { pos: Vec3; yaw: number; hips?: Vec3; wind?: Vec3 };

export type AirOptions = {
  /** Headwind per m/s of the character's own speed, against its motion (0.1: a push of 1 at 10 m/s, which streams
   * the samples' hair; their hair springs have no gravity of their own). 0 is off. */
  airDrag?: number;
  /** A constant wind (world units, like AvatarState.wind), added to whatever drive() returns. */
  wind?: Vec3;
};

const H = 1 / 240;
const Y = new THREE.Vector3(0, 1, 0);
const hipsAt = (s: Moving) => {
  const p = new THREE.Vector3(...s.pos);
  if (s.hips) p.add(new THREE.Vector3(...s.hips).applyAxisAngle(Y, s.yaw));
  return p;
};

/** The character's world velocity at t (its hips: feet position plus the hips offset), m/s. */
export const airVelocity = <A extends unknown[]>(drive: (t: number, ...rest: A) => Moving, t: number, ...rest: A): Vec3 =>
  hipsAt(drive(t + H, ...rest)).sub(hipsAt(drive(t - H, ...rest))).divideScalar(2 * H).toArray() as Vec3;

/** drive() with its wind plus the constant wind plus the headwind of its own motion. Unchanged when both are off. */
export const withAirDrag = <S extends Moving, A extends unknown[]>(drive: (t: number, ...rest: A) => S, o: AirOptions) => {
  const k = o.airDrag ?? 0;
  const c = o.wind ?? [0, 0, 0];
  if (k === 0 && c[0] === 0 && c[1] === 0 && c[2] === 0) return drive;
  return (t: number, ...rest: A): S => {
    const s = drive(t, ...rest);
    const w = s.wind ?? [0, 0, 0];
    const v = k === 0 ? [0, 0, 0] : airVelocity(drive, t, ...rest);
    return { ...s, wind: [w[0] + c[0] - k * v[0], w[1] + c[1] - k * v[1], w[2] + c[2] - k * v[2]] };
  };
};
