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
 * Tangents for a monotone cubic Hermite curve through (ts, vs) (Fritsch–Carlson, with Fritsch–Butland's weighted
 * harmonic mean): the curve passes every key and never overshoots one, so a camera never runs backwards between two
 * keys on any axis. A held value (two equal keys) gets a zero tangent, so the hold is still and the move after it
 * starts from rest. (Centripetal Catmull-Rom looped where keys were dense or held: a visible backward jolt.)
 */
const monotoneTangents = (ts: readonly number[], vs: readonly number[]): number[] => {
  const n = vs.length;
  const d = ts.slice(0, -1).map((t, j) => (vs[j + 1] - vs[j]) / Math.max(ts[j + 1] - t, 1e-9));
  const m = new Array<number>(n);
  m[0] = d[0];
  m[n - 1] = d[n - 2];
  for (let j = 1; j < n - 1; j++) {
    const [d0, d1] = [d[j - 1], d[j]];
    if (d0 * d1 <= 0) {
      m[j] = 0;
      continue;
    }
    const [h0, h1] = [ts[j] - ts[j - 1], ts[j + 1] - ts[j]];
    m[j] = (3 * (h0 + h1)) / ((2 * h1 + h0) / d0 + (h1 + 2 * h0) / d1);
  }
  // The end tangents may not exceed three times their secant (or point against it), or the end span overshoots.
  for (const [j, dj] of [[0, d[0]], [n - 1, d[n - 2]]] as const) {
    if (m[j] * dj <= 0) m[j] = 0;
    else if (Math.abs(m[j]) > 3 * Math.abs(dj)) m[j] = 3 * dj;
  }
  return m;
};

/** One axis of the monotone curve, at the eased position x (0..1) of the span from key i to key i + 1. */
const hermite = (ts: readonly number[], vs: readonly number[], m: readonly number[], i: number, x: number) => {
  const h = ts[i + 1] - ts[i];
  const [x2, x3] = [x * x, x * x * x];
  return (2 * x3 - 3 * x2 + 1) * vs[i] + (x3 - 2 * x2 + x) * h * m[i] + (-2 * x3 + 3 * x2) * vs[i + 1] + (x3 - x2) * h * m[i + 1];
};

/**
 * The camera at song time t. Positions follow a monotone cubic curve through the keys (on the song clock), so a path
 * of keys reads as one continuous move that never runs backwards between keys; time between keys is eased per
 * segment.
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
  const ts = span.map((key) => key.t);
  const along = (pick: (key: CameraKey) => Vec3) => {
    if (span.length < 3) return new THREE.Vector3(...pick(a)).lerp(new THREE.Vector3(...pick(b)), x);
    const axis = (c: 0 | 1 | 2) => {
      const vs = span.map((key) => pick(key)[c]);
      return hermite(ts, vs, monotoneTangents(ts, vs), local, x);
    };
    return new THREE.Vector3(axis(0), axis(1), axis(2));
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
