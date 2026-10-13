import { useEffect, useState } from 'react';
import { continueRender, delayRender } from 'remotion';
import * as THREE from 'three';
import type { TimingLine, TimingWord } from '../types';

// Lyric surfaces: lyrics written on things in the world (letters, screens, signs, balloons) instead of as subtitles.
// Each surface is a canvas texture redrawn only when what it shows changes (a new sung word), so it is a pure function
// of the song time.

/** Font sets already loaded in this tab: a scene that mounts later (a cut's incoming side) draws on its first frame. */
const loadedFonts = new Set<string>();

/**
 * Holds the render until the given web fonts can be used by a 2D canvas, and until the scene has drawn once with them.
 * Pass the results of `loadFont(...)` from `@remotion/google-fonts`; returns true once they are usable, and a scene
 * draws its surfaces only then. The render is released two animation frames after that, so a frame is never captured
 * with the world still blank: without this, a scene that mounted mid-render (the incoming side of a cut) gave blank
 * frames at the cut.
 */
export const useFontsReady = (fonts: { fontFamily: string; waitUntilDone: () => Promise<unknown> }[]) => {
  const key = fonts.map((f) => f.fontFamily).join('|');
  const [already] = useState(() => loadedFonts.has(key));
  const [handle] = useState(() => (already ? null : delayRender('Fonts for lyric surfaces')));
  const [ready, setReady] = useState(already);
  useEffect(() => {
    if (handle === null) return;
    Promise.all(fonts.map((f) => f.waitUntilDone()))
      .then(() => Promise.all(fonts.map((f) => document.fonts.load(`40px "${f.fontFamily}"`))))
      .then(() => {
        loadedFonts.add(key);
        setReady(true);
        requestAnimationFrame(() => requestAnimationFrame(() => continueRender(handle)));
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return ready;
};

type Surface = { canvas: HTMLCanvasElement; ctx: CanvasRenderingContext2D; tex: THREE.CanvasTexture; key: string };
const surfaces = new Map<string, Surface>();

/**
 * A canvas texture named `id`, `w`×`h` px. `draw` runs only when `key` changes (pass what the surface shows, e.g.
 * the number of words revealed), so the same frame always draws the same picture. The canvas is cleared before each
 * draw and the context's state restored after it.
 */
export const surfaceTexture = (id: string, w: number, h: number, key: string, draw: (x: CanvasRenderingContext2D) => void) => {
  let s = surfaces.get(id);
  if (!s) {
    const canvas = document.createElement('canvas');
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext('2d')!;
    const tex = new THREE.CanvasTexture(canvas);
    tex.colorSpace = THREE.SRGBColorSpace;
    tex.anisotropy = 8;
    s = { canvas, ctx, tex, key: '' };
    surfaces.set(id, s);
  }
  if (s.key !== key) {
    s.ctx.save();
    s.ctx.clearRect(0, 0, w, h);
    draw(s.ctx);
    s.ctx.restore();
    s.tex.needsUpdate = true;
    s.key = key;
  }
  return s.tex;
};

/** The words of a line that have started by time t (with a small lead so a word lands with the voice). */
export const sungWords = (words: readonly TimingWord[], line: TimingLine, t: number, lead = 0.06) => {
  const [a, b] = line.words;
  const out: string[] = [];
  for (let i = a; i <= b; i++) if (words[i].start - lead <= t) out.push(words[i].text);
  return out;
};

/** A line standing alone on its surface (a card, a calendar, a tag) drops its trailing comma, semicolon or colon.
 * Keep the punctuation where the next line follows on the same surface. */
export const bareEnd = (text: string) => text.replace(/[,;:]+$/, '');

/** Word-wraps `text` to `maxWidth` with the context's current font. */
export const wrap = (x: CanvasRenderingContext2D, text: string, maxWidth: number) => {
  const out: string[] = [];
  let cur = '';
  for (const w of text.split(/\s+/).filter(Boolean)) {
    const next = cur ? `${cur} ${w}` : w;
    if (cur && x.measureText(next).width > maxWidth) {
      out.push(cur);
      cur = w;
    } else cur = next;
  }
  if (cur) out.push(cur);
  return out;
};

/** A seeded 0–1 noise for paper grain and wobble (no Math.random at render time). */
export const hash = (n: number) => {
  const s = Math.sin(n * 127.1 + 311.7) * 43758.5453;
  return s - Math.floor(s);
};

/** Speckles the canvas like paper: fibres in `ink` and a soft warm vignette. */
export const paperGrain = (x: CanvasRenderingContext2D, w: number, h: number, ink: string, amount = 0.05, seed = 1) => {
  x.save();
  for (let i = 0; i < (w * h) / 900; i++) {
    x.globalAlpha = amount * hash(i * 3 + seed);
    x.fillStyle = ink;
    x.fillRect(hash(i * 7 + seed) * w, hash(i * 11 + seed) * h, 1 + hash(i * 13) * 2, 1);
  }
  const g = x.createRadialGradient(w / 2, h / 2, Math.min(w, h) * 0.3, w / 2, h / 2, Math.max(w, h) * 0.75);
  g.addColorStop(0, 'rgba(0,0,0,0)');
  g.addColorStop(1, 'rgba(60,40,20,0.18)');
  x.globalAlpha = 1;
  x.fillStyle = g;
  x.fillRect(0, 0, w, h);
  x.restore();
};
