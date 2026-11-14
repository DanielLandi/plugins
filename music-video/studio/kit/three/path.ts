// Paths to ride: a smooth 3D curve through points, measured by distance along it (arc length), with the tangent,
// the turn and the lean a rider or a vehicle takes at speed. Pure functions: any frame computes the same alone or in
// sequence.
//
// The curve is a cubic spline through the points (chord-length knots), C2 continuous: its curvature has no jump at
// the points, so a lean that follows it does not twitch there (a Catmull-Rom curve's does: issue #36).
import * as THREE from 'three';
import type { Vec3 } from './camera';

export type PathPoint = {
  /** Distance along the path, metres (clamped to it, or wrapped round a closed one). */
  s: number;
  pos: Vec3;
  /** Unit direction of travel. */
  tangent: Vec3;
  /** Heading about y (0 = +z, the kit's convention; faceYaw's sense): an <Avatar>'s yaw to face along the path. */
  yaw: number;
  /** Climb angle, radians (+ uphill). */
  pitch: number;
  /** Signed turn per metre (1 / radius) seen from above: + turning left (yaw increasing), - turning right. */
  curvature: number;
};

export type BankOptions = {
  /** Gravity, m/s² (9.81). */
  g?: number;
  /** A soft limit (radians): the lean eases towards it and never passes it. */
  max?: number;
  /** Average the turn over ±window metres (a rider's reaction time, about speed × 0.25 s). */
  window?: number;
};

export type Path = {
  /** Total length, metres. */
  length: number;
  closed: boolean;
  /** The distance along the path of each of its points. */
  knots: number[];
  at(s: number): PathPoint;
  /**
   * The lean (radians) that balances the turn at s at this speed (m/s): tan(bank) = v²·curvature / g. + leans left
   * (into a left turn). A bike, a skater, a plane; pathQuaternion(at(s), bank) applies it to a vehicle.
   */
  bank(s: number, speed: number, opts?: BankOptions): number;
};

// ---- the spline: per axis, second derivatives M at the knots ----

/** Second derivatives of a natural (open) or periodic (closed) cubic spline through ys at knots us. */
const spline2nd = (us: number[], ys: number[], closed: boolean): number[] => {
  const n = ys.length;
  const h = (i: number) => us[i + 1] - us[i];
  if (!closed) {
    // Natural ends (M = 0), Thomas algorithm on the interior.
    const M = new Array<number>(n).fill(0);
    if (n < 3) return M;
    const m = n - 2;
    const a = new Array<number>(m), b = new Array<number>(m), c = new Array<number>(m), d = new Array<number>(m);
    for (let k = 0; k < m; k++) {
      const i = k + 1;
      a[k] = h(i - 1);
      b[k] = 2 * (h(i - 1) + h(i));
      c[k] = h(i);
      d[k] = 6 * ((ys[i + 1] - ys[i]) / h(i) - (ys[i] - ys[i - 1]) / h(i - 1));
    }
    for (let k = 1; k < m; k++) {
      const w = a[k] / b[k - 1];
      b[k] -= w * c[k - 1];
      d[k] -= w * d[k - 1];
    }
    M[m] = d[m - 1] / b[m - 1];
    for (let k = m - 2; k >= 0; k--) M[k + 1] = (d[k] - c[k] * M[k + 2]) / b[k];
    return M;
  }
  // Periodic: n points, n segments (the last back to the first; us has n + 1 knots). A cyclic tridiagonal system,
  // solved with Sherman-Morrison on top of the Thomas algorithm.
  const hp = (i: number) => h(((i % n) + n) % n);
  const y = (i: number) => ys[((i % n) + n) % n];
  const a = new Array<number>(n), b = new Array<number>(n), c = new Array<number>(n), d = new Array<number>(n);
  for (let i = 0; i < n; i++) {
    a[i] = hp(i - 1);
    b[i] = 2 * (hp(i - 1) + hp(i));
    c[i] = hp(i);
    d[i] = 6 * ((y(i + 1) - y(i)) / hp(i) - (y(i) - y(i - 1)) / hp(i - 1));
  }
  const thomas = (bb: number[], rhs: number[]) => {
    const cp = new Array<number>(n), dp = new Array<number>(n), x = new Array<number>(n);
    cp[0] = c[0] / bb[0];
    dp[0] = rhs[0] / bb[0];
    for (let i = 1; i < n; i++) {
      const den = bb[i] - a[i] * cp[i - 1];
      cp[i] = c[i] / den;
      dp[i] = (rhs[i] - a[i] * dp[i - 1]) / den;
    }
    x[n - 1] = dp[n - 1];
    for (let i = n - 2; i >= 0; i--) x[i] = dp[i] - cp[i] * x[i + 1];
    return x;
  };
  const gamma = -b[0];
  const bb = b.slice();
  bb[0] -= gamma;
  bb[n - 1] -= (c[n - 1] * a[0]) / gamma;
  const u = new Array<number>(n).fill(0);
  u[0] = gamma;
  u[n - 1] = c[n - 1];
  const x = thomas(bb, d);
  const z = thomas(bb, u);
  const k = (x[0] + (a[0] * x[n - 1]) / gamma) / (1 + z[0] + (a[0] * z[n - 1]) / gamma);
  return x.map((v, i) => v - k * z[i]);
};

// 5-point Gauss-Legendre on [0, 1].
const GL_X = [0.0469100770306680, 0.2307653449471585, 0.5, 0.7692346550528415, 0.9530899229693320];
const GL_W = [0.1184634425280945, 0.2393143352496832, 0.2844444444444444, 0.2393143352496832, 0.1184634425280945];
const SUB = 16; // arc-length table entries per segment

/**
 * A smooth path through `points` (metres), parametrised by distance along it. `closed` joins the last point back to
 * the first (leave the first point out of the end, or repeat it: both work).
 */
export const makePath = (points: readonly Vec3[], opts: { closed?: boolean } = {}): Path => {
  const closed = opts.closed ?? false;
  const pts: Vec3[] = [];
  for (const p of points) {
    const q = pts[pts.length - 1];
    if (!q || Math.hypot(p[0] - q[0], p[1] - q[1], p[2] - q[2]) > 1e-9) pts.push([p[0], p[1], p[2]]);
  }
  if (closed && pts.length > 1) {
    const [f, l] = [pts[0], pts[pts.length - 1]];
    if (Math.hypot(f[0] - l[0], f[1] - l[1], f[2] - l[2]) < 1e-9) pts.pop();
  }
  if (pts.length < (closed ? 3 : 2)) throw new Error(`a ${closed ? 'closed' : 'open'} path needs at least ${closed ? 3 : 2} distinct points`);
  const n = pts.length;
  const segs = closed ? n : n - 1;
  const P = (i: number) => pts[i % n];
  const us = [0];
  for (let i = 0; i < segs; i++) {
    const [p, q] = [P(i), P(i + 1)];
    us.push(us[i] + Math.hypot(q[0] - p[0], q[1] - p[1], q[2] - p[2]));
  }
  const M = [0, 1, 2].map((ax) => spline2nd(us, pts.map((p) => p[ax]), closed));
  const Mi = (ax: number, i: number) => M[ax][i % n];

  /** Position, first and second derivative (per u) on segment i at local x. */
  const evalSeg = (i: number, x: number) => {
    const h = us[i + 1] - us[i];
    const pos: Vec3 = [0, 0, 0], d1: Vec3 = [0, 0, 0], d2: Vec3 = [0, 0, 0];
    for (let ax = 0; ax < 3; ax++) {
      const [y0, y1] = [P(i)[ax], P(i + 1)[ax]];
      const [m0, m1] = [Mi(ax, i), Mi(ax, i + 1)];
      const b = (y1 - y0) / h - (h * (2 * m0 + m1)) / 6;
      const c = m0 / 2;
      const d = (m1 - m0) / (6 * h);
      pos[ax] = y0 + x * (b + x * (c + x * d));
      d1[ax] = b + x * (2 * c + 3 * d * x);
      d2[ax] = 2 * c + 6 * d * x;
    }
    return { pos, d1, d2 };
  };
  const speed = (i: number, x: number) => Math.hypot(...evalSeg(i, x).d1);
  /** Arc length along segment i from local x0 to x1 (Gauss-Legendre: exact enough for a cubic's speed). */
  const arc = (i: number, x0: number, x1: number) => {
    let sum = 0;
    for (let k = 0; k < 5; k++) sum += GL_W[k] * speed(i, x0 + (x1 - x0) * GL_X[k]);
    return sum * (x1 - x0);
  };

  // Table: SUB entries per segment, (segment, local x, s).
  const tSeg: number[] = [], tX: number[] = [], tS: number[] = [];
  let acc = 0;
  for (let i = 0; i < segs; i++) {
    const h = us[i + 1] - us[i];
    for (let k = 0; k < SUB; k++) {
      const x0 = (k / SUB) * h;
      tSeg.push(i);
      tX.push(x0);
      tS.push(acc);
      acc += arc(i, x0, ((k + 1) / SUB) * h);
    }
  }
  const length = acc;
  const knots = Array.from({ length: segs + 1 }, (_, i) => (i < segs ? tS[i * SUB] : length));

  const locate = (s: number): { i: number; x: number; s: number } => {
    let lo = 0, hi = tS.length - 1;
    while (lo < hi) {
      const mid = (lo + hi + 1) >> 1;
      if (tS[mid] <= s) lo = mid;
      else hi = mid - 1;
    }
    const i = tSeg[lo];
    const h = us[i + 1] - us[i];
    const xEnd = lo + 1 < tS.length && tSeg[lo + 1] === i ? tX[lo + 1] : h;
    const sEnd = lo + 1 < tS.length ? tS[lo + 1] : length;
    // Linear guess inside the entry, then Newton on the exact arc length.
    let x = tX[lo] + ((s - tS[lo]) / Math.max(sEnd - tS[lo], 1e-12)) * (xEnd - tX[lo]);
    for (let it = 0; it < 4; it++) {
      const err = tS[lo] + arc(i, tX[lo], x) - s;
      x = Math.min(xEnd, Math.max(tX[lo], x - err / Math.max(speed(i, x), 1e-12)));
    }
    return { i, x, s };
  };

  const wrap = (s: number) => (closed ? ((s % length) + length) % length : Math.min(length, Math.max(0, s)));

  const at = (sIn: number): PathPoint => {
    const s = wrap(sIn);
    const { i, x } = locate(s);
    const { pos, d1, d2 } = evalSeg(i, x);
    const v = Math.hypot(...d1);
    const tangent: Vec3 = [d1[0] / v, d1[1] / v, d1[2] / v];
    const hz = d1[0] * d1[0] + d1[2] * d1[2];
    // d(yaw)/du with yaw = atan2(x', z'), per metre of travel.
    const curvature = hz > 1e-12 ? (d1[2] * d2[0] - d1[0] * d2[2]) / hz / v : 0;
    return {
      s, pos, tangent, curvature,
      yaw: Math.atan2(tangent[0], tangent[2]),
      pitch: Math.asin(Math.max(-1, Math.min(1, tangent[1]))),
    };
  };

  const bank = (s: number, v: number, o: BankOptions = {}) => {
    const g = o.g ?? 9.81;
    let k = at(s).curvature;
    if (o.window && o.window > 0) {
      // Nine samples across ±window, weighted by a smooth (Hann) bump: a moving average with no edges.
      let sum = 0, wsum = 0;
      for (let j = -4; j <= 4; j++) {
        const w = 1 + Math.cos((j / 5) * Math.PI);
        sum += w * at(s + (j / 4) * o.window).curvature;
        wsum += w;
      }
      k = sum / wsum;
    }
    const raw = Math.atan((v * v * k) / g);
    return o.max ? o.max * Math.tanh(raw / o.max) : raw;
  };

  return { length, closed, knots, at, bank };
};

/**
 * Where a rider is at time t (seconds, song time) going `speed` m/s along the path from `start` (song seconds,
 * default 0) and distance `s0`, with the bank for that speed. For a changing speed, compute the distance yourself
 * (e.g. `track` over [time, metres] keys, eased with eases.smooth) and use path.at(s) and path.bank(s, v).
 */
export const ride = (path: Path, t: number, speed: number, opts: { start?: number; s0?: number } & BankOptions = {}) => {
  const { start = 0, s0 = 0, ...bankOpts } = opts;
  const p = path.at(s0 + speed * Math.max(0, t - start));
  return { ...p, bank: path.bank(p.s, speed, bankOpts) };
};

/**
 * The rotation that carries something modelled facing +z (the kit's convention; a car's nose, a board's nose)
 * along the path at p: heading, nose up or down the slope, then `bank` (radians, + leans left) about its own length.
 */
export const pathQuaternion = (p: PathPoint, bank = 0): THREE.Quaternion =>
  new THREE.Quaternion().setFromEuler(new THREE.Euler(-p.pitch, p.yaw, -bank, 'YXZ'));
