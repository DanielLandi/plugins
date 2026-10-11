import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

/** First line of the README every web build writes: how a later build knows a folder is its own to empty. */
export const MARK = '<!-- built by music-video web -->';

/** The build empties its output first, so it refuses any folder that is neither empty nor one of its own builds. */
export const checkOut = (dir: string) => {
  if (!existsSync(dir) || readdirSync(dir).length === 0) return;
  const file = join(dir, 'README.md');
  if (existsSync(file) && readFileSync(file, 'utf8').startsWith(MARK)) return;
  throw new Error(`${dir} is not empty and is not a web build (no README.md starting with "${MARK}"): refusing to empty it`);
};

export const readme = (video: string, builtAt: string, sound: boolean) => `${MARK}
# Build output: do not edit

The live web page of the music video \`${video}\`, built ${builtAt} by \`music-video web ${video}\`. Rebuild it
instead of editing anything here. Every file under assets/ carries a content hash in its name, so a CDN that
caches .js and .css for hours never serves a stale build; only index.html must be fresh.

- Drawing: Remotion Player (https://www.remotion.dev), the video's own scenes, rendered live in the browser.
${sound ? '- Sound: a seamless loop of the song, muted until the visitor turns it on.\n' : ''}`;
