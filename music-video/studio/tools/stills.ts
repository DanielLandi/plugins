// Render several stills of one composition with a single bundle, plus a contact sheet of them.
//   music-video stills <video-id> <composition> <out-dir> <frame>[,<frame>…] [--seconds] [--scale=0.5]
// With --seconds the list is song seconds (for compositions that start at 0 or an Excerpt, give its `from` with
// --from=<s>); otherwise composition frames. music-video passes the video's entry (MV_ENTRY), public folder
// (MV_PUBLIC) and --gl mode (MV_GL).
import { bundle } from '@remotion/bundler';
import { webpackOverride } from '../webpack-override';
import { renderStill, selectComposition } from '@remotion/renderer';
import { execFileSync } from 'node:child_process';
import { mkdirSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const studio = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const args = process.argv.slice(2);
const flags = Object.fromEntries(args.filter((a) => a.startsWith('--')).map((a) => a.slice(2).split('=')).map(([k, v]) => [k, v ?? 'true']));
const [id, compositionId, outArg, list] = args.filter((a) => !a.startsWith('--'));
// This runs in the engine folder: the out dir is relative to where music-video was called from (INIT_CWD).
const outDir = outArg && resolve(process.env.INIT_CWD ?? process.cwd(), outArg);
if (!id || !compositionId || !outDir || !list) {
  console.error('usage: music-video stills <video-id> <composition> <out-dir> <frame,frame,…> [--seconds --from=<s>] [--scale=0.5]');
  process.exit(1);
}
const gl = (process.env.MV_GL ?? 'angle') as 'angle';
const publicDir = process.env.MV_PUBLIC ?? join(studio, 'fixture', 'public');

const envVariables = { REMOTION_VIDEO: id };
const serveUrl = await bundle({ entryPoint: process.env.MV_ENTRY ?? join(studio, 'index.ts'), publicDir, webpackOverride });
const composition = await selectComposition({ serveUrl, id: compositionId, envVariables, inputProps: {}, chromiumOptions: { gl } });
const fps = composition.fps;
const from = Number(flags.from ?? 0);
const frames = list.split(',').map(Number).map((v) => (flags.seconds ? Math.round((v - from) * fps) : v));
mkdirSync(outDir, { recursive: true });
const outputs: string[] = [];
for (const frame of frames) {
  const output = join(outDir, `${compositionId}-${String(frame).padStart(5, '0')}.png`);
  const t0 = performance.now();
  await renderStill({
    composition, serveUrl, output, frame, envVariables, inputProps: composition.props, imageFormat: 'png',
    scale: Number(flags.scale ?? 1), chromiumOptions: { gl },
  });
  console.log(`${output}  (frame ${frame}, ${(frame / fps + from).toFixed(2)} s, ${((performance.now() - t0) / 1000).toFixed(1)} s)`);
  outputs.push(output);
}
if (outputs.length > 1) {
  const sheet = join(outDir, `${compositionId}-sheet.png`);
  const cols = Math.min(outputs.length, 4);
  execFileSync('ffmpeg', [
    '-loglevel', 'error', '-y', ...outputs.flatMap((o) => ['-i', o]),
    '-filter_complex', `${outputs.map((_, i) => `[${i}:v]scale=360:-1[v${i}]`).join(';')};${outputs.map((_, i) => `[v${i}]`).join('')}xstack=inputs=${outputs.length}:layout=${outputs.map((_, i) => `${(i % cols) ? Array.from({ length: i % cols }, () => 'w0').join('+') : '0'}_${Math.floor(i / cols) ? Array.from({ length: Math.floor(i / cols) }, () => 'h0').join('+') : '0'}`).join('|')}:fill=black`,
    sheet,
  ]);
  console.log(sheet);
}
