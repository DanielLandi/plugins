// Render a song composition with motion blur: render at `steps` sub-frames per output frame, then average `samples`
// sub-frames centred on each frame's time (the shutter: samples / steps of the frame, 8 of 16 = 180°), so the blurred
// cut stays in sync with the sharp one.
//   music-video blur <video-id> <composition> <out.mp4> [--samples=8] [--shutter=180] [--frames=a-b] [--crf=16] [--scale=1] [--props='{"lyrics":"none"}']
// --scale renders at that multiple of the composition's size (2: a 1920×1080 composition comes out 3840×2160).
// --frames are output (30 fps) frames, inclusive. The result is silent: music-video mux adds the song as usual.
// The scene must read time in seconds (the kit's useSongTime), never in frames.
import { spawnSync } from 'node:child_process';
import { mkdtempSync, readdirSync, rmSync, statSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const studio = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const args = process.argv.slice(2);
const flags: Record<string, string> = Object.fromEntries(args.filter((a) => a.startsWith('--')).map((a) => {
  const i = a.indexOf('=');
  return i < 0 ? [a.slice(2), 'true'] : [a.slice(2, i), a.slice(i + 1)];
}));
const [id, composition, outArg] = args.filter((a) => !a.startsWith('--'));
if (!id || !composition || !outArg) {
  console.error('usage: music-video blur <video-id> <composition> <out.mp4> [--samples=8] [--shutter=180] [--frames=a-b] [--crf=16] [--scale=1]');
  process.exit(1);
}
const out = resolve(process.env.INIT_CWD ?? process.cwd(), outArg);
const samples = Math.max(2, Number(flags.samples ?? 8));
const shutter = Math.min(360, Math.max(1, Number(flags.shutter ?? 180)));
const steps = Math.max(samples, Math.round((samples * 360) / shutter));

const work = mkdtempSync(join(tmpdir(), 'mv-blur-'));
const sub = join(work, 'subframes.mp4');
// The Remotion CLI's own script, run with node (no shell, so it works the same on Windows), on this video's entry.
const cli = join(studio, 'node_modules', '@remotion', 'cli', 'remotion-cli.js');
const entry = process.env.MV_ENTRY ?? join(studio, 'index.ts');
const renderArgs = [cli, 'render', entry, composition, sub, '--muted', '--crf=8',
  `--public-dir=${process.env.MV_PUBLIC ?? join(studio, 'fixture', 'public')}`, `--gl=${process.env.MV_GL ?? 'angle'}`,
  // The composition's own props (e.g. lyrics: 'none' for a clean cut) pass through; subframes is added.
  `--props=${JSON.stringify({ ...(flags.props ? JSON.parse(flags.props) : {}), subframes: steps })}`,
  // A long render meets heavy first frames (a world's canvas created mid-song): allow 5 min per frame, not 30 s.
  `--timeout=${flags.timeout ?? 300000}`];
if (flags.scale) renderArgs.push(`--scale=${flags.scale}`);
// Output frame k averages sub-frames k·steps − half … k·steps + half − 1 (the first frame gets the later half only).
const half = Math.floor(samples / 2);
let first = 0;
if (flags.frames) {
  const [a, b] = flags.frames.split('-').map(Number);
  first = Math.max(0, a * steps - half);
  renderArgs.push(`--frames=${first}-${b * steps + half - 1}`);
}
console.log(`motion blur: ${samples} samples over a ${shutter}° shutter (${steps} sub-frames per frame, ${30 * steps} fps)`);
const t0 = performance.now();
const render = spawnSync(process.execPath, renderArgs, { stdio: 'inherit', cwd: studio, env: process.env });
if (render.status !== 0) process.exit(render.status ?? 1);
console.log(`rendered sub-frames in ${((performance.now() - t0) / 1000).toFixed(0)} s`);

// tmix averages each sub-frame with the samples-1 before it; keep the one that closes each frame's shutter.
const close = (((half - 1 - first) % steps) + steps) % steps;
const filter = `tmix=frames=${samples},select='eq(mod(n\\,${steps})\\,${close})',setpts=N/(30*TB)`;
const ff = spawnSync('ffmpeg', ['-loglevel', 'error', '-y', '-i', sub, '-vf', filter, '-r', '30', '-c:v', 'libx264',
  '-crf', String(flags.crf ?? 16), '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out], { stdio: 'inherit' });
const bytes = readdirSync(work).reduce((n, f) => n + statSync(join(work, f)).size, 0);
rmSync(work, { recursive: true, force: true }); // only this run's own temporary folder
if (ff.status !== 0) process.exit(ff.status ?? 1);
console.log(`${out}  (${(bytes / 1e6).toFixed(0)} MB of sub-frames discarded)`);
