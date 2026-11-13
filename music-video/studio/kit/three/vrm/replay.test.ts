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
  it('a later frame continues from an earlier one instead of replaying (render tabs skip frames)', () => {
    const r = spring(), fresh = spring();
    const m: ReplayState = { frame: -1 };
    replayTo(r, m, drive, 10, 30, 4);
    const n = r.steps();
    replayTo(r, m, drive, 40, 30, 4);
    expect(r.steps() - n).toBe(30 * 4);
    replayTo(fresh, { frame: -1 }, drive, 40, 30, 4);
    expect(r.x()).toBe(fresh.x());
  });
  it('the pose clock is the song clock, also when the physics starts between two frames', () => {
    // An <Avatar from={from}> replays from frame start = round(from * fps): its last pose for song frame `frame`
    // must be drive(frame / fps), the kit's useSongTime, exactly (not from + (frame - start) / fps).
    for (const fps of [24, 30, 60]) {
      for (const from of [0, 1.37, 12.51, 61.016]) {
        const start = Math.round(from * fps);
        for (const frame of [start, start + 1, start + 7, start + 300]) {
          const times: number[] = [];
          replayTo(spring(), { frame: -1 }, (t) => { times.push(t); return drive(t); }, frame - start, fps, 4, 1, start);
          expect(times[times.length - 1]).toBe(frame / fps);
          expect(times[0]).toBe(start / fps); // it settles in the pose of its first frame
        }
      }
    }
  });
  it('a replay that starts later steps the same physics, only shifted in song time', () => {
    const late = spring(), seq = spring();
    const m: ReplayState = { frame: -1 };
    replayTo(late, { frame: -1 }, (t) => drive(t - 2), 40, 30, 4, 1, 60);
    for (let f = 0; f <= 40; f++) replayTo(seq, m, (t) => drive(t - 2), f, 30, 4, 1, 60);
    expect(late.x()).toBe(seq.x());
  });
});
