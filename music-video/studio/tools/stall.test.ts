import { mkdtempSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { StallWatch, watchedRun } from './stall';

const alive = (pid: number) => {
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
};

describe('StallWatch', () => {
  it('counts a new progress line as progress, and a repeated one (whatever its estimate) as none', () => {
    let t = 0;
    const w = new StallWatch(1000, () => t);
    w.feed('Bundling 6%\n');
    t = 900;
    w.feed('Rendered 10/100, time remaining: 2m 1s\r');
    t = 1800;
    expect(w.stalled()).toBe(false);
    w.feed('Rendered 10/100, time remaining: 2m 1s\rRendered 10/100, time remaining: 1m 59s\n');
    expect(w.stalled()).toBe(false);
    t = 1900;
    expect(w.stalled()).toBe(true);
    expect(w.line).toBe('Rendered 10/100');
    w.feed('Rendered 11/100, time remaining: 2m\n');
    expect(w.stalled()).toBe(false);
  });
  it('treats silence from the start as a stall, and 0 as never', () => {
    let t = 0;
    const w = new StallWatch(500, () => t), off = new StallWatch(0, () => t);
    t = 600;
    expect(w.stalled()).toBe(true);
    expect(off.stalled()).toBe(false);
  });
});

describe('watchedRun', () => {
  it('kills a command that stops showing progress, and what it started', async () => {
    const dir = mkdtempSync(join(tmpdir(), 'mv-stall-test-'));
    const pidFile = join(dir, 'child.pid');
    // a parent that starts a detached child (as a browser leaves its launcher's group), then repeats one line forever
    const script = `
      const { spawn } = require('node:child_process');
      const c = spawn(process.execPath, ['-e', 'setInterval(() => {}, 1000)'], { detached: true, stdio: 'ignore' });
      require('node:fs').writeFileSync(${JSON.stringify(pidFile)}, String(c.pid));
      console.log('Rendered 1/10, time remaining: 1s');
      setInterval(() => console.log('Rendered 1/10, time remaining: 1s'), 20);`;
    const r = await watchedRun(process.execPath, ['-e', script], { cwd: dir, env: process.env, stallMs: 300, checkMs: 50 });
    expect(r.stalled).toBe(true);
    expect(r.line).toBe('Rendered 1/10');
    const child = Number(readFileSync(pidFile, 'utf-8'));
    await new Promise((ok) => setTimeout(ok, 100));
    expect(alive(child)).toBe(false);
  });
  it('passes a finished command through with its status', async () => {
    const r = await watchedRun(process.execPath, ['-e', 'console.log("done"); process.exit(3)'], { cwd: tmpdir(), env: process.env, stallMs: 5000, checkMs: 50 });
    expect(r).toEqual({ status: 3, stalled: false, line: 'done' });
  });
});
