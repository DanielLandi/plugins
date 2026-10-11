// Smoke test: bundle the studio and render one still of each fixture composition.
//   npm run smoke   (part of npm test; the first run downloads Remotion's headless Chrome once)
import { bundle } from '@remotion/bundler';
import { webpackOverride } from '../webpack-override';
import { renderStill, selectComposition } from '@remotion/renderer';
import { execFileSync } from 'node:child_process';
import { mkdirSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { PNG } from 'pngjs';
import { fixtureAnalysis, fixtureTiming } from '../fixture/data';

const studio = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const dir = mkdtempSync(join(tmpdir(), 'mv-smoke-'));
const publicDir = join(dir, 'public');
mkdirSync(publicDir);
writeFileSync(join(publicDir, 'timing.json'), JSON.stringify(fixtureTiming));
writeFileSync(join(publicDir, 'analysis.json'), JSON.stringify(fixtureAnalysis));
execFileSync('ffmpeg', ['-loglevel', 'error', '-f', 'lavfi', '-i', 'sine=frequency=330:duration=4', '-c:a', 'libmp3lame',
  '-y', join(publicDir, 'song.mp3')]);

const envVariables = { REMOTION_VIDEO: 'fixture' };
const serveUrl = await bundle({ entryPoint: join(studio, 'index.ts'), publicDir, webpackOverride });
for (const [id, frame] of [['fixture-full', 45], ['fixture-vertical', 20]] as const) {
  const composition = await selectComposition({ serveUrl, id, envVariables, inputProps: {} });
  const output = join(dir, `${id}.png`);
  await renderStill({ composition, serveUrl, output, frame, envVariables, inputProps: {}, imageFormat: 'png', chromiumOptions: { gl: 'angle' } });
  const png = PNG.sync.read(readFileSync(output));
  let sum = 0;
  let sum2 = 0;
  for (let i = 0; i < png.width * png.height; i++) {
    const y = 0.2126 * png.data[i * 4] + 0.7152 * png.data[i * 4 + 1] + 0.0722 * png.data[i * 4 + 2];
    sum += y;
    sum2 += y * y;
  }
  const n = png.width * png.height;
  const std = Math.sqrt(Math.max(0, sum2 / n - (sum / n) ** 2));
  if (std < 3) throw new Error(`${id} frame ${frame} is a flat frame: ${output}`);
  console.log(`ok  ${id} frame ${frame}: ${png.width}x${png.height} → ${output}`);
}
