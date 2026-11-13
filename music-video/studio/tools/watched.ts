// Run a long command (a plain render) under the stall watch, as blur does: no new progress line for --stall minutes
// (15; 0 turns the watch off) kills it with everything it started and starts it again, --retries times (2).
//   tsx tools/watched.ts [--stall=15] [--retries=2] [--label=render] -- <command> [args…]
// Exits with the command's status (1 when it was killed for stalling on the last try).
import { retriedRun, watchedArgs } from './stall';

let w: ReturnType<typeof watchedArgs>;
try {
  w = watchedArgs(process.argv.slice(2));
} catch (e) {
  console.error((e as Error).message);
  process.exit(2);
}
const run = await retriedRun(w.cmd, w.args, { cwd: process.cwd(), env: process.env, stallMs: w.stallMs, tries: w.tries, label: w.label });
process.exit(run.stalled ? 1 : (run.status ?? 1));
