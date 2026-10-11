import { describe, expect, it, vi } from 'vitest';
import { createSound, loopBounds, type AudioMeta } from './sound';

const meta: AudioMeta = { loopSamples: 44100 * 100, marginSamples: 44100, rate: 44100 };

describe('loopBounds', () => {
  it('loops exactly one loop length, starting half a margin in', () => {
    const { start, end } = loopBounds(101, meta);
    expect(start).toBeCloseTo(0.5, 9);
    expect(end - start).toBeCloseTo(100, 9);
  });
  it('stays inside a buffer that kept encoder priming and padding', () => {
    expect(loopBounds(101 + 3136 / 44100, meta).end).toBeLessThan(101);
  });
  it('refuses a file shorter than its loop', () => {
    expect(() => loopBounds(99, meta)).toThrow(/shorter than its loop/);
  });
});

const fakeEnv = (status: number | 'stall' = 200) => {
  const session = { type: 'auto' };
  const sources: Array<Record<string, unknown> & { start: ReturnType<typeof vi.fn> }> = [];
  const order: string[] = [];
  const contexts: FakeContext[] = [];
  class FakeContext {
    currentTime = 0;
    destination = {};
    constructor() { order.push('context'); contexts.push(this); }
    resume = vi.fn(async () => {});
    suspend = vi.fn(async () => {});
    close = vi.fn(async () => {});
    createGain() {
      return { gain: { value: 0, cancelScheduledValues() {}, setValueAtTime() {}, linearRampToValueAtTime: vi.fn() }, connect() {} };
    }
    createBufferSource() {
      const s = { buffer: null, loop: false, loopStart: 0, loopEnd: 0, connect() {}, start: vi.fn() };
      sources.push(s);
      return s;
    }
    async decodeAudioData() { return { duration: 101 }; }
  }
  const fetch = vi.fn((_url: string, init?: { signal?: AbortSignal }) => {
    order.push('fetch');
    if (status === 'stall') {
      return new Promise((_, reject) => init?.signal?.addEventListener('abort', () => reject(new Error('aborted'))));
    }
    return Promise.resolve(status === 200 ? { ok: true, status, arrayBuffer: async () => new ArrayBuffer(8) } : { ok: false, status });
  });
  const env = {
    AudioContext: FakeContext as unknown as typeof AudioContext,
    fetch: fetch as unknown as typeof globalThis.fetch,
    navigator: { audioSession: session } as unknown as Navigator,
  };
  return { env, session, sources, order, contexts };
};

describe('createSound', () => {
  it('starts one endless loop on the first click, playing through the iPhone silent switch', async () => {
    const f = fakeEnv();
    const sound = createSound('loop.m4a', meta, f.env);
    expect(await sound.toggle()).toBe(true);
    expect(f.session.type).toBe('playback');
    expect(f.order.slice(0, 2)).toEqual(['context', 'fetch']); // the context exists before any await (iOS)
    expect(f.sources[0]).toMatchObject({ loop: true, loopStart: 0.5, loopEnd: 100.5 });
    expect(f.sources[0].start).toHaveBeenCalledWith(0, 0.5);
  });

  it('mutes and unmutes without ever starting a second copy', async () => {
    const f = fakeEnv();
    const sound = createSound('loop.m4a', meta, f.env);
    await sound.toggle();
    expect(await sound.toggle()).toBe(false);
    expect(await sound.toggle()).toBe(true);
    expect(f.sources).toHaveLength(1);
  });

  it('lets the audio hardware sleep while muted, and wakes it to unmute', async () => {
    vi.useFakeTimers();
    try {
      const f = fakeEnv();
      const sound = createSound('loop.m4a', meta, f.env);
      await sound.toggle();
      const ctx = f.contexts[0];
      expect(await sound.toggle()).toBe(false);
      expect(ctx.suspend).not.toHaveBeenCalled(); // still fading out
      vi.advanceTimersByTime(500);
      expect(ctx.suspend).toHaveBeenCalledTimes(1);
      ctx.resume.mockClear();
      expect(await sound.toggle()).toBe(true);
      expect(ctx.resume).toHaveBeenCalledTimes(1);
      // off and straight back on, inside the fade: it never sleeps
      await sound.toggle();
      await sound.toggle();
      vi.advanceTimersByTime(500);
      expect(ctx.suspend).toHaveBeenCalledTimes(1);
    } finally {
      vi.useRealTimers();
    }
  });

  it('gives up on a stalled download after 30 s, so a later click can retry', async () => {
    vi.useFakeTimers();
    try {
      const f = fakeEnv('stall');
      const sound = createSound('loop.m4a', meta, f.env);
      const first = sound.toggle();
      const failed = expect(first).rejects.toThrow(/took too long/);
      await vi.advanceTimersByTimeAsync(30_000);
      await failed;
      expect(sound.started).toBe(false);
    } finally {
      vi.useRealTimers();
    }
  });

  it('wakes the audio when the page comes back, only if it was playing', async () => {
    const f = fakeEnv();
    const sound = createSound('loop.m4a', meta, f.env);
    sound.wake(); // nothing started yet: nothing to wake
    await sound.toggle();
    const ctx = f.contexts[0];
    ctx.resume.mockClear();
    sound.wake();
    expect(ctx.resume).toHaveBeenCalledTimes(1);
    await sound.toggle(); // muted
    ctx.resume.mockClear();
    sound.wake();
    expect(ctx.resume).not.toHaveBeenCalled();
  });

  it('reports a failed load and retries from scratch on the next click', async () => {
    const bad = fakeEnv(404);
    const sound = createSound('loop.m4a', meta, bad.env);
    await expect(sound.toggle()).rejects.toThrow(/404/);
    expect(sound.started).toBe(false);
    await expect(sound.toggle()).rejects.toThrow(/404/);
    expect(bad.order.filter((x) => x === 'context')).toHaveLength(2);
  });
});
