// The transition board: renders every cut of a video at 10%…90% (plus 35% and 65% for the panel), fails blank,
// blown-out or flooded frames, and writes one review panel per cut.
//   music-video board <video-id>
// The stills are rendered with `lyrics: 'none'` so the pixel judgement sees only the scenes, never the overlay.
// One browser is opened for the whole run and closed at the end, even on error; renders/board/ is cleared first.
import { bundle } from '@remotion/bundler';
import { webpackOverride } from '../webpack-override';
import { openBrowser, renderStill, selectComposition } from '@remotion/renderer';
import { mkdirSync, rmSync, readFileSync, writeFileSync } from 'node:fs';
import { registerHooks } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { PNG } from 'pngjs';
import { layoutSeries, type CutSpec, type SceneSpec } from '../kit/series';
import { downscale, hstack, judgeFrame, type Rgba } from './pixels';

const studio = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const id = process.argv[2];
if (!id) {
  console.error('usage: music-video board <video-id>');
  process.exit(1);
}
// music-video passes the video's code folder, its media folder and the song's public folder.
const root = process.env.MV_MEDIA ?? '.';
const publicDir = process.env.MV_PUBLIC ?? join(root, 'public');
const videoDir = process.env.MV_VIDEO_DIR ?? join(studio, 'fixture');
// scenes.ts imports the scenes themselves; in Node only their ids and times are needed, so 3D model files (which only
// the bundler can load) are stubbed out here.
registerHooks({
  load: (url, context, next) =>
    /\.(glb|gltf)$/.test(url) ? { format: 'module', source: 'export default "";', shortCircuit: true } : next(url, context),
});
const { scenes } = (await import(pathToFileURL(join(videoDir, 'scenes.ts')).href)) as { scenes: SceneSpec[] };
const { cuts } = (await import(pathToFileURL(join(videoDir, 'cuts.ts')).href)) as { cuts: CutSpec[] };
const analysis = JSON.parse(readFileSync(join(publicDir, 'analysis.json'), 'utf8')) as { duration: number };
const layout = layoutSeries(scenes, cuts, analysis.duration, 30);
if (!layout.cuts.length) {
  console.log('No cuts yet: the video is a single scene.');
  process.exit(0);
}
const gl = process.env.MV_GL ?? 'angle';
const envVariables = { REMOTION_VIDEO: id };
const serveUrl = await bundle({ entryPoint: process.env.MV_ENTRY ?? join(studio, 'index.ts'), publicDir, webpackOverride });
const inputProps = { lyrics: 'none' };
const chromiumOptions = { gl: gl as 'angle' | 'swangle' | 'egl' | 'swiftshader' | 'vulkan' | 'angle-egl' };
const composition = await selectComposition({ serveUrl, id: `${id}-full`, envVariables, inputProps });
const outDir = join(root, 'renders', 'board');
rmSync(outDir, { recursive: true, force: true });
mkdirSync(outDir, { recursive: true });

const browser = await openBrowser('chrome', { chromiumOptions });
const still = async (frame: number, name: string): Promise<Rgba> => {
  const output = join(outDir, name);
  await renderStill({ composition, serveUrl, output, frame, envVariables, inputProps, imageFormat: 'png',
    chromiumOptions, puppeteerInstance: browser });
  const png = PNG.sync.read(readFileSync(output));
  return { data: new Uint8Array(png.data), width: png.width, height: png.height };
};
const writePng = (img: Rgba, path: string) => {
  const png = new PNG({ width: img.width, height: img.height });
  png.data = Buffer.from(img.data);
  writeFileSync(path, PNG.sync.write(png));
};

const report = [];
let failed = 0;
try {
  for (const [n, slot] of layout.cuts.entries()) {
    const tag = `cut-${String(n + 1).padStart(2, '0')}`;
    const { frames } = slot.cut;
    const at = (p: number) => slot.startFrame + Math.round(frames * p);
    const a = await still(Math.max(0, slot.startFrame - 1), `${tag}-a.png`);
    const b = await still(Math.min(layout.totalFrames - 1, slot.startFrame + frames), `${tag}-b.png`);
    const problems: string[] = [];
    for (let k = 1; k <= 9; k++) {
      const verdict = judgeFrame(await still(at(k / 10), `${tag}-${k * 10}.png`), a, b);
      if (!verdict.ok) problems.push(`${k * 10}%: ${verdict.reason}`);
    }
    const mids = [await still(at(0.35), `${tag}-35.png`), await still(at(0.65), `${tag}-65.png`)];
    const panel = join(outDir, `${tag}.png`);
    writePng(hstack([a, ...mids, b].map((img) => downscale(img, 480, Math.round((480 * img.height) / img.width)))), panel);
    if (problems.length) failed++;
    report.push({ cut: `${slot.cut.from} → ${slot.cut.to}`, transition: slot.cut.transition, frames, carrier: slot.cut.carrier,
      why: slot.cut.why, landsOn: slot.cut.landsOn, ok: !problems.length, problems, panel });
    console.log(`${problems.length ? 'FAIL' : 'PASS'}  ${tag} ${slot.cut.from} → ${slot.cut.to} · ${slot.cut.transition} ${frames}f · carried by ${slot.cut.carrier}`);
    for (const p of problems) console.log(`        ${p}`);
  }
} finally {
  await browser.close({ silent: true });
}
writeFileSync(join(outDir, 'board.json'), JSON.stringify(report, null, 1));
console.log(`board: ${outDir}`);
process.exit(failed ? 1 : 0);
