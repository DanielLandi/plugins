// A long render can hang with every process idle (seen on a 1.5-hour stall: the browser waiting on itself, no frame
// failing, so Remotion's per-frame timeout never fired, and its progress line repeated unchanged). watchedRun runs a
// command, passes its output through, and kills it with everything it started when no new progress line has appeared
// for `stallMs`, so the caller can start it again.
import { spawn, spawnSync } from 'node:child_process';

/** A progress line without its estimate, which a hung render can keep repeating unchanged. */
const progressOf = (line: string) => line.replace(/,?\s*time remaining:.*$/i, '').trim();

/** Remembers when the output last showed a line it had not just shown (the start counts as one). */
export class StallWatch {
  private last = '';
  private at: number;
  constructor(private stallMs: number, private now: () => number = Date.now) {
    this.at = now();
  }
  feed(text: string) {
    for (const raw of text.split(/[\r\n]+/)) {
      const line = progressOf(raw);
      if (line && line !== this.last) {
        this.last = line;
        this.at = this.now();
      }
    }
  }
  /** The last line shown (what it stalled on). */
  get line() {
    return this.last;
  }
  stalled() {
    return this.stallMs > 0 && this.now() - this.at >= this.stallMs;
  }
}

/** Every process started by `pid`, at any depth (a browser can leave its launcher's process group). */
const descendants = (pid: number): number[] => {
  const ps = spawnSync('ps', ['-A', '-o', 'pid=,ppid='], { encoding: 'utf-8' });
  const kids = new Map<number, number[]>();
  for (const row of (ps.stdout ?? '').split('\n')) {
    const [p, pp] = row.trim().split(/\s+/).map(Number);
    if (p && pp) kids.set(pp, [...(kids.get(pp) ?? []), p]);
  }
  const all: number[] = [];
  const walk = (p: number) => (kids.get(p) ?? []).forEach((k) => (all.push(k), walk(k)));
  walk(pid);
  return all;
};

/** Kill a process and everything it started, at once (a hung one ignores a plain kill). */
export const killTree = (pid: number) => {
  if (process.platform === 'win32') {
    spawnSync('taskkill', ['/pid', String(pid), '/T', '/F']);
    return;
  }
  for (const p of [pid, ...descendants(pid)]) {
    try {
      process.kill(p, 'SIGKILL');
    } catch {
      // already gone
    }
  }
};

/** Run a command, passing its output through; 'stalled' when it was killed for showing no progress. */
export const watchedRun = (cmd: string, args: string[], opts: { cwd: string; env: NodeJS.ProcessEnv; stallMs: number; checkMs?: number }) =>
  new Promise<{ status: number | null; stalled: boolean; line: string }>((done) => {
    const child = spawn(cmd, args, { cwd: opts.cwd, env: opts.env, stdio: ['inherit', 'pipe', 'pipe'] });
    const watch = new StallWatch(opts.stallMs);
    let stalled = false;
    child.stdout.on('data', (d: Buffer) => (process.stdout.write(d), watch.feed(d.toString())));
    child.stderr.on('data', (d: Buffer) => (process.stderr.write(d), watch.feed(d.toString())));
    const timer = setInterval(() => {
      if (!stalled && watch.stalled() && child.pid) {
        stalled = true;
        killTree(child.pid);
      }
    }, opts.checkMs ?? 30000);
    child.on('close', (status) => {
      clearInterval(timer);
      done({ status, stalled, line: watch.line });
    });
  });

/** watchedRun, started again (up to `tries` runs in all) while it stalls; `say` reports each restart and a give-up. */
export const retriedRun = async (
  cmd: string,
  args: string[],
  opts: { cwd: string; env: NodeJS.ProcessEnv; stallMs: number; checkMs?: number; tries: number; label: string; say?: (m: string) => void },
) => {
  const say = opts.say ?? ((m: string) => console.error(m));
  const min = Number((opts.stallMs / 60000).toPrecision(2));
  let run = await watchedRun(cmd, args, opts), n = 1;
  while (run.stalled && n < opts.tries) {
    n += 1;
    say(`${opts.label}: no progress for ${min} min (at "${run.line}"): stopped it; starting again (try ${n} of ${opts.tries})`);
    run = await watchedRun(cmd, args, opts);
  }
  if (run.stalled) say(`${opts.label}: no progress for ${min} min (at "${run.line}") on the last try: giving up`);
  return { ...run, tries: n };
};

/** tools/watched.ts's arguments: [--stall=<min>] [--retries=<n>] [--label=<name>] -- <command> [args…]. */
export const watchedArgs = (argv: string[]) => {
  const split = argv.indexOf('--');
  if (split < 0 || split === argv.length - 1) throw new Error('usage: watched.ts [--stall=15] [--retries=2] [--label=render] -- <command> [args…]');
  const flags: Record<string, string> = Object.fromEntries(argv.slice(0, split).map((a) => {
    const i = a.indexOf('=');
    return i < 0 ? [a.replace(/^--/, ''), 'true'] : [a.slice(2, i), a.slice(i + 1)];
  }));
  return {
    stallMs: Number(flags.stall ?? 15) * 60000,
    tries: 1 + Math.max(0, Number(flags.retries ?? 2)),
    label: flags.label ?? 'render',
    cmd: argv[split + 1],
    args: argv.slice(split + 2),
  };
};
