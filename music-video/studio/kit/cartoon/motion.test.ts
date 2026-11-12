import { describe, expect, it } from 'vitest';
import { boilSeed, follow, hop, hopSquash, noise1, springStep, track, vol, wobble } from './motion';
import { track as vrmTrack } from '../three/vrm/motion';

describe('cartoon motion', () => {
  it('shares the vrm engine keyframe helpers', () => {
    expect(track).toBe(vrmTrack);
  });

  it('follow replays from the scene start, the same on its own or after earlier frames', () => {
    const sig = (t: number) => (t < 181 ? 0 : 100);
    const alone = follow(sig, 182.5, { from: 180 });
    for (let f = 0; f < 60; f++) follow(sig, 180 + f / 30, { from: 180 });
    expect(follow(sig, 182.5, { from: 180 })).toBe(alone);
    // A follower lags, overshoots and settles near its target.
    expect(follow(sig, 181.05, { from: 180 })).toBeLessThan(100);
    expect(Math.abs(follow(sig, 189, { from: 180 }) - 100)).toBeLessThan(2);
  });

  it('follow costs the same late in a song as at its start', () => {
    const sig = (t: number) => Math.sin(t);
    const t0 = performance.now();
    for (let i = 0; i < 20; i++) follow(sig, 182, { from: 180 });
    const late = performance.now() - t0;
    expect(late).toBeLessThan(200);
    expect(follow(sig, 180, { from: 180 })).toBe(sig(180)); // at the start it sits on the signal
  });

  it('hops, squashes and springs are pure functions of t', () => {
    expect(hop(0.5, 0, 1, 100)).toBe(100);
    expect(hop(1.2, 0, 1, 100)).toBe(0);
    expect(hopSquash(-1, 0, 1)).toBe(1);
    expect(hopSquash(-0.08, 0, 1)).toBeLessThan(1); // anticipation squash before take-off
    expect(springStep(0, 0)).toBe(0);
    expect(Math.abs(springStep(3, 0) - 1)).toBeLessThan(0.01);
    expect(wobble(-1, 0)).toBe(0);
    expect(vol(1)).toBe(1);
    expect(vol(1.3)).toBeLessThan(1); // stretched tall → thinner
    expect(noise1(2.3, 4)).toBe(noise1(2.3, 4));
    expect(Math.abs(noise1(2.3, 4))).toBeLessThanOrEqual(1);
  });

  it('boils on twos', () => {
    expect(boilSeed(10)).toBe(boilSeed(11));
    expect(boilSeed(11)).not.toBe(boilSeed(12));
    expect(boilSeed(10, 3)).toBe(boilSeed(11, 3));
  });
});
