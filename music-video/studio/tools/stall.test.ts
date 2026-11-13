import { mkdtempSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { retriedRun, StallWatch, watchedArgs, watchedRun } from './stall';

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

describe('retriedRun', () => {
  it('starts a stalled command again, and stops once it finishes', async () => {
    const dir = mkdtempSync(join(tmpdir(), 'mv-retry-test-'));
    const mark = join(dir, 'tried');
    // the first try hangs on one line; the second finishes
    const script = `
      const fs = require('node:fs');
      if (!fs.existsSync(${JSON.stringify(mark)})) { fs.writeFileSync(${JSON.stringify(mark)}, ''); console.log('Rendered 1/10'); setInterval(() => {}, 1000); }
      else { console.log('Rendered 10/10'); process.exit(0); }`;
    const said: string[] = [];
    const r = await retriedRun(process.execPath, ['-e', script], { cwd: dir, env: process.env, stallMs: 300, checkMs: 50, tries: 3, label: 'render', say: (m) => said.push(m) });
    expect(r).toEqual({ status: 0, stalled: false, line: 'Rendered 10/10', tries: 2 });
    expect(said).toEqual(['render: no progress for 0.005 min (at "Rendered 1/10"): stopped it; starting again (try 2 of 3)']);
  });
  it('gives up after the last try and says so', async () => {
    const said: string[] = [];
    const r = await retriedRun(process.execPath, ['-e', 'console.log("Bundling"); setInterval(() => {}, 1000)'], { cwd: tmpdir(), env: process.env, stallMs: 200, checkMs: 50, tries: 2, label: 'render', say: (m) => said.push(m) });
    expect(r.stalled).toBe(true);
    expect(r.tries).toBe(2);
    expect(said.at(-1)).toBe('render: no progress for 0.0033 min (at "Bundling") on the last try: giving up');
  });
});

describe('watchedArgs', () => {
  it('reads the watch flags before -- and the command after it', () => {
    expect(watchedArgs(['--stall=30', '--retries=0', '--label=render', '--', 'node', 'cli.js', '--stall=x'])).toEqual({ stallMs: 1800000, tries: 1, label: 'render', cmd: 'node', args: ['cli.js', '--stall=x'] });
    expect(watchedArgs(['--', 'node'])).toEqual({ stallMs: 900000, tries: 3, label: 'render', cmd: 'node', args: [] });
  });
  it('refuses a call without a command', () => {
    expect(() => watchedArgs(['--stall=15'])).toThrow(/usage/);
  });
});
