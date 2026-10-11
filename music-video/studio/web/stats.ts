import type { PlayerRef } from '@remotion/player';

/** ?stats: counts what the page really drew (read window.__mvStats() in the console). */
export const startStats = (player: PlayerRef) => {
  const deltas: number[] = [];
  let drawn = 0;
  let since = performance.now();
  let last = since;
  player.addEventListener('frameupdate', () => {
    drawn++;
  });
  const tick = (now: number) => {
    deltas.push(now - last);
    last = now;
    requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
  const w = window as unknown as Record<string, unknown>;
  w.__mvReset = () => {
    deltas.length = 0;
    drawn = 0;
    since = performance.now();
  };
  w.__mvStats = () => {
    const d = [...deltas].sort((a, b) => a - b);
    const seconds = (performance.now() - since) / 1000;
    return {
      seconds,
      drawnFps: drawn / seconds,
      medianFrameMs: d[Math.floor(d.length / 2)] ?? 0,
      p95FrameMs: d[Math.floor(d.length * 0.95)] ?? 0,
      slowFrames: d.filter((x) => x > 1000 / 30 + 1).length / Math.max(1, d.length),
    };
  };
};
