/** loop.json as written by music-video loop, as far as the page needs it. */
export type AudioMeta = { loopSamples: number; marginSamples: number; rate: number };

/**
 * Where to loop in the decoded buffer. The file holds the loop plus a margin that repeats its opening, so any window
 * of exactly one loop length that starts inside the margin is seamless; starting half a margin in also clears any
 * encoder priming a browser leaves at the front, and the margin's other half any padding at the back.
 */
export const loopBounds = (bufferSeconds: number, m: AudioMeta) => {
  const start = m.marginSamples / m.rate / 2;
  const end = start + m.loopSamples / m.rate;
  if (end > bufferSeconds) {
    throw new Error(`The loop audio is ${bufferSeconds.toFixed(3)} s, shorter than its loop window (${end.toFixed(3)} s)`);
  }
  return { start, end };
};

type Env = { AudioContext: typeof AudioContext; fetch: typeof fetch; navigator: Navigator };

const browser = (): Env => ({ AudioContext: window.AudioContext, fetch: window.fetch.bind(window), navigator: window.navigator });

/** How long after a fade-out the audio hardware is let go (the fade itself takes 0.3 s). */
const SLEEP_AFTER_MS = 400;
/** A download that has not finished by then is given up, so the button offers the sound again. */
const LOAD_TIMEOUT_MS = 30_000;

/**
 * The page's music: nothing until the first click, then one endless loop that later clicks fade out and in. While
 * muted the context is suspended, so a phone left on the page does not keep its audio hardware running.
 */
export const createSound = (url: string, meta: AudioMeta, env: Env = browser()) => {
  let ctx: AudioContext | null = null;
  let gain: GainNode | null = null;
  let on = false;
  let loading: Promise<boolean> | null = null;
  let sleep: ReturnType<typeof setTimeout> | undefined;

  const ramp = (to: number, seconds: number) => {
    if (!ctx || !gain) return;
    const now = ctx.currentTime;
    gain.gain.cancelScheduledValues(now);
    gain.gain.setValueAtTime(gain.gain.value, now);
    gain.gain.linearRampToValueAtTime(to, now + seconds);
  };

  const begin = async () => {
    // iOS: play through the silent switch, as a video would. Safari 17+; elsewhere the property does not exist.
    const session = (env.navigator as Navigator & { audioSession?: { type: string } }).audioSession;
    if (session) session.type = 'playback';
    // Created inside the click and before any await, or iOS keeps it suspended.
    const c = new env.AudioContext();
    ctx = c;
    void c.resume();
    gain = c.createGain();
    gain.gain.value = 0;
    gain.connect(c.destination);
    const abort = new AbortController();
    const timer = setTimeout(() => abort.abort(), LOAD_TIMEOUT_MS);
    let bytes: ArrayBuffer;
    try {
      const res = await env.fetch(url, { signal: abort.signal });
      if (!res.ok) throw new Error(`The loop audio failed to load: HTTP ${res.status}`);
      bytes = await res.arrayBuffer();
    } catch (e) {
      if (abort.signal.aborted) throw new Error(`The loop audio took too long to load (over ${LOAD_TIMEOUT_MS / 1000} s)`);
      throw e;
    } finally {
      clearTimeout(timer);
    }
    const buffer = await c.decodeAudioData(bytes);
    const { start, end } = loopBounds(buffer.duration, meta);
    const source = c.createBufferSource();
    source.buffer = buffer;
    source.loop = true;
    source.loopStart = start;
    source.loopEnd = end;
    source.connect(gain);
    source.start(0, start);
    on = true;
    ramp(1, 1.5);
    return on;
  };

  return {
    get started() {
      return ctx !== null;
    },
    /** The page is visible again: iOS suspends audio for calls and locks, so resume it if it was playing. */
    wake() {
      if (ctx && on) void ctx.resume();
    },
    toggle(): Promise<boolean> {
      if (loading) return loading;
      if (!ctx) {
        loading = begin()
          .catch((e) => {
            void ctx?.close();
            ctx = null;
            gain = null;
            on = false;
            throw e;
          })
          .finally(() => {
            loading = null;
          });
        return loading;
      }
      on = !on;
      clearTimeout(sleep);
      if (on) {
        void ctx.resume();
      } else {
        const c = ctx;
        sleep = setTimeout(() => {
          if (!on) void c.suspend();
        }, SLEEP_AFTER_MS);
      }
      ramp(on ? 1 : 0, 0.3);
      return Promise.resolve(on);
    },
  };
};
