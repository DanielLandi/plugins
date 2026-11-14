import { describe, expect, it } from 'vitest';
import type { Vec3 } from '../camera';
import { replayTo, type Replayable, type ReplayState } from './replay';
import { airVelocity, withAirDrag } from './wind';

type S = { pos: Vec3; yaw: number; pose: Record<string, never>; hips?: Vec3; wind?: Vec3 };
/** Riding along +x at 5 m/s, then turning to run along +z at 5 m/s after t = 2 (a smooth corner). */
const ride = (t: number): S => {
  const x = 5 * t;
  return { pos: [x, 0, t > 2 ? 5 * (t - 2) ** 2 : 0], yaw: Math.PI / 2, pose: {}, wind: [0, 0.2, 0] };
};

describe('withAirDrag', () => {
  it('blows against the avatar’s own motion, in proportion to its speed', () => {
    const d = withAirDrag(ride, { airDrag: 0.1 });
    const w = d(1).wind!;
    expect(w[0]).toBeCloseTo(-0.5, 9); // 5 m/s along +x → 0.5 against it
    expect(w[1]).toBeCloseTo(0.2, 9); // the drive's own wind is kept
    expect(w[2]).toBeCloseTo(0, 9);
    const v = airVelocity(ride, 1);
    expect(w[0] * v[0] + w[2] * v[2]).toBeLessThan(0); // opposite the velocity
  });

  it('adds a constant wind, and a standing avatar feels only that', () => {
    const still = (t: number): S => ({ pos: [1, 0, 1], yaw: t, pose: {} });
    expect(withAirDrag(still, { airDrag: 0.3, wind: [0.4, 0, -0.1] })(3).wind).toEqual([0.4, 0, -0.1]);
  });

  it('counts the hips moving (a hop) as well as the feet', () => {
    const hop = (t: number): S => ({ pos: [0, 0, 0], yaw: 0, pose: {}, hips: [0, 2 * t, 0] });
    expect(withAirDrag(hop, { airDrag: 0.5 })(0.3).wind![1]).toBeCloseTo(-1, 9);
  });

  it('passes the rig through to the drive', () => {
    let seen: unknown = null;
    const d = withAirDrag((t: number, rig?: unknown) => { seen = rig; return ride(t); }, { airDrag: 0.1 });
    d(1, { hips: { parent: null, offset: [0, 1, 0] } });
    expect(seen).toEqual({ hips: { parent: null, offset: [0, 1, 0] } });
  });

  it('keeps the replay deterministic: a seeked frame equals the same frame reached one by one', () => {
    // A spring pushed by the wind, like hair on a head: its state depends on its whole history.
    const spring = () => {
      let f = 0, x = 0, v = 0;
      const r: Replayable<S> & { x: () => number } = {
        apply: (s) => { f = s.wind ? s.wind[0] : 0; },
        step: (dt) => { const a = f - 40 * x - 4 * v; v += a * dt; x += v * dt; },
        reset: () => { x = 0; v = 0; },
        x: () => x,
      };
      return r;
    };
    const drive = withAirDrag(ride, { airDrag: 0.1, wind: [0.05, 0, 0] });
    const seek = spring(), seq = spring();
    const ms: ReplayState = { frame: -1 }, mq: ReplayState = { frame: -1 };
    replayTo(seek, ms, drive, 90, 30);
    for (let f = 0; f <= 90; f++) replayTo(seq, mq, drive, f, 30);
    expect(seek.x()).toBe(seq.x());
    expect(seek.x()).toBeLessThan(-0.005); // the headwind has pushed it back
  });
});
