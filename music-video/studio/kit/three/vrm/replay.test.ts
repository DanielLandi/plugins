import { describe, expect, it } from 'vitest';
import { replayTo, type Replayable, type ReplayState } from './replay';

/** A damped spring chasing a driven target: its position depends on its whole history, like hair on a head. */
const spring = () => {
  let target = 0, x = 0, v = 0, steps = 0;
  const r: Replayable<number> & { x: () => number; steps: () => number } = {
    apply: (s) => { target = s; },
    step: (dt) => { const a = 80 * (target - x) - 6 * v; v += a * dt; x += v * dt; steps++; },
    reset: () => { x = 0; v = 0; },
    x: () => x,
    steps: () => steps,
  };
  return r;
};
const drive = (t: number) => Math.sin(t * 3) + (t > 1 ? 1 : 0);

describe('replayTo', () => {
  it('a seeked frame equals the same frame reached one by one', () => {
    const seek = spring(), seq = spring();
    const ms: ReplayState = { frame: -1 }, mq: ReplayState = { frame: -1 };
    replayTo(seek, ms, drive, 40, 30);
    for (let f = 0; f <= 40; f++) replayTo(seq, mq, drive, f, 30);
    expect(seek.x()).toBe(seq.x());
    expect(seek.x()).not.toBe(0);
  });
  it('going back replays from rest', () => {
    const r = spring(), fresh = spring();
    const m: ReplayState = { frame: -1 };
    replayTo(r, m, drive, 40, 30);
    replayTo(r, m, drive, 10, 30);
    replayTo(fresh, { frame: -1 }, drive, 10, 30);
    expect(r.x()).toBe(fresh.x());
    expect(m.frame).toBe(10);
  });
  it('the same frame twice does not step again', () => {
    const r = spring();
    const m: ReplayState = { frame: -1 };
    replayTo(r, m, drive, 5, 30);
    const n = r.steps();
    replayTo(r, m, drive, 5, 30);
    expect(r.steps()).toBe(n);
  });
  it('the next frame costs sub steps only', () => {
    const r = spring();
    const m: ReplayState = { frame: -1 };
    replayTo(r, m, drive, 5, 30, 4);
    const n = r.steps();
    replayTo(r, m, drive, 6, 30, 4);
    expect(r.steps() - n).toBe(4);
  });
});
