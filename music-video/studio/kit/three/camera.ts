import { useThree } from '@react-three/fiber';
import type React from 'react';
import * as THREE from 'three';
import { useSongTime } from '../SongContext';

export type Vec3 = [number, number, number];

/**
 * One camera key on the song's clock. Between two keys the camera moves with `ease` (the arriving key's):
 * 'inOut' lands and holds (the default), 'out' arrives fast and settles, 'in' leaves slowly and hits,
 * 'linear' is for mechanical moves only, 'cut' jumps at the key's time.
 */
export type CameraKey = { t: number; pos: Vec3; look: Vec3; fov?: number; roll?: number; ease?: Ease };
export type Ease = 'inOut' | 'out' | 'in' | 'linear' | 'cut';

const EASES: Record<Exclude<Ease, 'cut'>, (x: number) => number> = {
  inOut: (x) => (x < 0.5 ? 4 * x * x * x : 1 - (-2 * x + 2) ** 3 / 2),
  out: (x) => 1 - (1 - x) ** 3,
  in: (x) => x * x * x,
  linear: (x) => x,
};

export type CameraState = { pos: THREE.Vector3; look: THREE.Vector3; fov: number; roll: number };

/**
 * The camera at song time t. Positions follow a centripetal Catmull-Rom curve through the keys, so a path of keys
 * reads as one continuous move; time between keys is eased per segment.
 */
export const cameraAt = (keys: readonly CameraKey[], t: number, defaultFov = 50): CameraState => {
  if (keys.length === 0) throw new Error('cameraAt needs at least one key');
  const k = [...keys].sort((a, b) => a.t - b.t);
  const fovOf = (key: CameraKey) => key.fov ?? defaultFov;
  if (t <= k[0].t || k.length === 1) {
    return { pos: new THREE.Vector3(...k[0].pos), look: new THREE.Vector3(...k[0].look), fov: fovOf(k[0]), roll: k[0].roll ?? 0 };
  }
  const last = k[k.length - 1];
  if (t >= last.t) {
    return { pos: new THREE.Vector3(...last.pos), look: new THREE.Vector3(...last.look), fov: fovOf(last), roll: last.roll ?? 0 };
  }
  let i = 0;
  while (k[i + 1].t <= t) i++;
  const a = k[i];
  const b = k[i + 1];
  const ease = b.ease ?? 'inOut';
  if (ease === 'cut') {
    return { pos: new THREE.Vector3(...a.pos), look: new THREE.Vector3(...a.look), fov: fovOf(a), roll: a.roll ?? 0 };
  }
  const x = EASES[ease]((t - a.t) / (b.t - a.t));
  // A cut starts a new curve: points across a cut must not bend this segment.
  const segStart = (() => {
    let s = i;
    while (s > 0 && (k[s].ease ?? 'inOut') !== 'cut') s--;
    return s;
  })();
  const segEnd = (() => {
    let e = i + 1;
    while (e < k.length - 1 && (k[e + 1].ease ?? 'inOut') !== 'cut') e++;
    return e;
  })();
  const span = k.slice(segStart, segEnd + 1);
  const local = i - segStart;
  const along = (pick: (key: CameraKey) => Vec3) => {
    if (span.length < 3) return new THREE.Vector3(...pick(a)).lerp(new THREE.Vector3(...pick(b)), x);
    const curve = new THREE.CatmullRomCurve3(span.map((key) => new THREE.Vector3(...pick(key))), false, 'centripetal');
    // Map (segment, x) onto the curve's parameter: Catmull-Rom passes key j at u = j / (n - 1).
    return curve.getPoint((local + x) / (span.length - 1));
  };
  return {
    pos: along((key) => key.pos),
    look: along((key) => key.look),
    fov: fovOf(a) + (fovOf(b) - fovOf(a)) * x,
    roll: (a.roll ?? 0) + ((b.roll ?? 0) - (a.roll ?? 0)) * x,
  };
};

/** Drives the stage's camera from keys on the song's clock. `shake` adds a small seeded tremble (world units). */
export const CameraRig: React.FC<{ keys: readonly CameraKey[]; fov?: number; shake?: (t: number) => Vec3 }> = ({
  keys,
  fov = 50,
  shake,
}) => {
  const camera = useThree((s) => s.camera) as THREE.PerspectiveCamera;
  const t = useSongTime();
  // The default fov is a constant, never camera.fov: a frame must not depend on the frame rendered before it.
  const c = cameraAt(keys, t, fov);
  if (shake) c.pos.add(new THREE.Vector3(...shake(t)));
  camera.position.copy(c.pos);
  camera.up.set(0, 1, 0);
  camera.lookAt(c.look);
  if (c.roll) camera.rotateZ(c.roll);
  if (camera.fov !== c.fov) {
    camera.fov = c.fov;
    camera.updateProjectionMatrix();
  }
  return null;
};
