// Build a live web page that draws one video's web entry (its web.tsx) with Remotion Player, on a loop:
//   music-video web <video-id> --out <dir> [--audio <loop dir>] [--title T] [--description D] [--label L]
//                   [--background #hex]
// music-video passes the entry (MV_WEB_ENTRY), the video folder (MV_VIDEO_DIR) and the song data (MV_PUBLIC).
// The output folder is emptied first, so it must be empty or an earlier build (tools/web-out.ts).
import { createHash } from 'node:crypto';
import { copyFileSync, existsSync, mkdirSync, readdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { registerHooks } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { build, type Plugin } from 'vite';
import { loopScore } from '../kit/loop';
import type { SongData } from '../kit/types';
import type { WebEntry } from '../kit/web';
import { checkOut, readme } from './web-out';

const studio = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const web = join(studio, 'web');
const [id, ...rest] = process.argv.slice(2);
const arg = (name: string) => {
  const i = rest.indexOf(`--${name}`);
  return i >= 0 ? rest[i + 1] : undefined;
};
const outArg = arg('out');
const entryFile = process.env.MV_WEB_ENTRY;
if (!id || !outArg || !entryFile) {
  console.error('usage: music-video web <video-id> --out <dir> [--audio <loop dir>] [--title …] [--background #hex]');
  process.exit(1);
}
const out = resolve(outArg);
checkOut(out);

// The entry's `words` (if any) decide which sung words the page keeps. Scenes may import 3D models, which only the
// bundler can load: stub them while reading the entry in Node.
registerHooks({
  load: (url, context, next) =>
    /\.(glb|gltf)$/.test(url) ? { format: 'module', source: 'export default "";', shortCircuit: true } : next(url, context),
});
const { web: entry } = (await import(pathToFileURL(entryFile).href)) as { web: WebEntry };

const json = <T,>(path: string) => JSON.parse(readFileSync(path, 'utf8')) as T;
const publicDir = process.env.MV_PUBLIC ?? join(studio, 'fixture', 'song');
const data: SongData = { timing: json(join(publicDir, 'timing.json')), analysis: json(join(publicDir, 'analysis.json')) };
const score = entry.words ? loopScore(data, entry.words) : data;

// web/.data/ is what main.tsx imports: this build's song data.
const stage = join(web, '.data');
rmSync(stage, { recursive: true, force: true });
mkdirSync(stage);
const audioDir = arg('audio');
let audio: Record<string, unknown> | null = null;
let audioBytes: Buffer | null = null;
if (audioDir) {
  const meta = json<{ loopSamples: number; marginSamples: number; rate: number }>(join(audioDir, 'loop.json'));
  audioBytes = readFileSync(join(audioDir, 'loop.m4a'));
  const hash = createHash('sha256').update(audioBytes).digest('hex').slice(0, 8);
  // Under assets/ with a content hash, like every other asset, so a host may cache it forever.
  audio = { loopSamples: meta.loopSamples, marginSamples: meta.marginSamples, rate: meta.rate, file: `assets/loop-${hash}.m4a` };
}
writeFileSync(join(stage, 'score.json'), JSON.stringify({ data: score, audio }));

const escape = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const fields: Record<string, string> = {
  TITLE: arg('title') ?? id,
  DESCRIPTION: arg('description') ?? '',
  LABEL: arg('label') ?? 'An animation drawn live in the browser',
  BACKGROUND: arg('background') ?? '#000000',
};
// A video can shape its page from a web/ folder of its own: web/styles.css (bundled), web/fonts/<Family>.ts (used in
// place of @remotion/google-fonts/<Family>, so the page self-hosts or skips a font instead of fetching it from
// Google), and licence .txt files (copied next to index.html).
const videoWeb = join(process.env.MV_VIDEO_DIR ?? join(studio, 'fixture'), 'web');
const videoStyles = join(videoWeb, 'styles.css');
const selfHostedFonts: Plugin = {
  name: 'music-video-fonts',
  enforce: 'pre',
  resolveId: (source) => {
    const family = /^@remotion\/google-fonts\/(\w+)$/.exec(source)?.[1];
    const stand = family && join(videoWeb, 'fonts', `${family}.ts`);
    return stand && existsSync(stand) ? stand : null;
  },
};
const htmlFields: Plugin = {
  name: 'music-video-fields',
  transformIndexHtml: (html) => html.replace(/%MV_(\w+)%/g, (_, k: string) => escape(fields[k] ?? '')),
};

await build({
  configFile: false,
  root: web,
  base: './',
  logLevel: 'warn',
  plugins: [selfHostedFonts, htmlFields],
  assetsInclude: ['**/*.glb', '**/*.gltf'],
  resolve: {
    preserveSymlinks: true,
    alias: [
      { find: '@mv/web-entry', replacement: entryFile },
      { find: '@mv/web-styles', replacement: existsSync(videoStyles) ? videoStyles : join(web, 'no-styles.css') },
      { find: /^@mv\/kit/, replacement: join(studio, 'kit') },
      { find: /^@mv\/assets/, replacement: join(studio, 'assets') },
    ],
    dedupe: ['react', 'react-dom', 'remotion', 'three', '@remotion/player', '@react-three/fiber'],
  },
  esbuild: { jsx: 'automatic' },
  build: { outDir: out, emptyOutDir: true, assetsInlineLimit: 0, chunkSizeWarningLimit: 8192 },
});

if (audioBytes && audio) writeFileSync(join(out, audio.file as string), audioBytes);
if (existsSync(videoWeb)) {
  for (const name of readdirSync(videoWeb).filter((n) => n.endsWith('.txt'))) copyFileSync(join(videoWeb, name), join(out, name));
}
writeFileSync(join(out, 'README.md'), readme(id, new Date().toISOString().slice(0, 10), Boolean(audio)));
console.log(join(out, 'index.html'));
