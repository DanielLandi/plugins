import React from 'react';
import * as THREE from 'three';
import { TextGeometry } from 'three/examples/jsm/geometries/TextGeometry.js';
import { Font, type FontData } from 'three/examples/jsm/loaders/FontLoader.js';
import type { TimingWord } from '../types';
import outfit800 from './fonts/outfit-800.json';

// Outfit ExtraBold (OFL, fonts/OFL.txt), the same family as the 2D lyrics; made by tools/typeface.py.
export const OUTFIT_800 = new Font(outfit800 as unknown as FontData);

export type TextOpts = {
  size: number;
  /** Extrusion along +z, in world units. */
  depth?: number;
  /** A rounded edge, as a fraction of size (0 = sharp). */
  bevel?: number;
  font?: Font;
  /** 'center' puts the middle of the advance at x = 0; 'left' starts at x = 0. */
  align?: 'center' | 'left';
};

const cache = new Map<string, THREE.BufferGeometry>();

/**
 * Extruded text with its baseline on y = 0, its depth centred on z = 0, and x per `align`. Cached: the same text and
 * options return the same geometry, so a scene can call this every frame.
 */
export const textGeometry = (text: string, { size, depth = size * 0.25, bevel = 0.04, font = OUTFIT_800, align = 'center' }: TextOpts) => {
  const key = [text, size, depth, bevel, align, font.data.familyName].join('|');
  const hit = cache.get(key);
  if (hit) return hit;
  const b = bevel * size;
  const g = new TextGeometry(text, {
    font, size, depth, curveSegments: 8,
    bevelEnabled: b > 0, bevelThickness: b, bevelSize: b * 0.6, bevelSegments: 3,
  });
  const width = advance(text, size, font);
  g.translate(align === 'center' ? -width / 2 : 0, 0, -depth / 2);
  g.computeVertexNormals();
  cache.set(key, g);
  return g;
};

/** The advance width of a text in world units (three's text has no kerning, so this is exact for it). */
export const advance = (text: string, size: number, font = OUTFIT_800) => {
  const scale = size / font.data.resolution;
  return [...text].reduce((w, ch) => w + ((font.data.glyphs[ch] ?? font.data.glyphs['?'])?.ha ?? 0) * scale, 0);
};

/** The cap height in world units (an 'H' at this size), for stacking lines. */
export const capHeight = (size: number) => size * 0.7;

type MeshProps = Omit<React.ComponentProps<'mesh'>, 'geometry' | 'children'>;

/** A word as one extruded mesh. Pass the material as the child. */
export const Text3D: React.FC<MeshProps & TextOpts & { text: string; children: React.ReactNode }> = ({
  text, size, depth, bevel, font, align, children, ...mesh
}) => (
  <mesh geometry={textGeometry(text, { size, depth, bevel, font, align })} castShadow receiveShadow {...mesh}>
    {children}
  </mesh>
);

export type Letter = { ch: string; i: number; x: number; width: number };

/** Lays out a text's letters for per-letter animation: x is each letter's left edge, the whole text centred. */
export const layoutLetters = (text: string, size: number, font = OUTFIT_800): Letter[] => {
  const total = advance(text, size, font);
  let x = -total / 2;
  return [...text].map((ch, i) => {
    const width = advance(ch, size, font);
    const letter = { ch, i, x, width };
    x += width;
    return letter;
  });
};

/**
 * A text as separate letter meshes. `place` gives each letter its transform (relative to where it sits in the
 * word); the letter's origin is the middle of its baseline, so rotations pivot naturally.
 */
export const Letters: React.FC<
  TextOpts & {
    text: string;
    place?: (letter: Letter, count: number) => { position?: [number, number, number]; rotation?: [number, number, number]; scale?: number | [number, number, number]; visible?: boolean };
    children: React.ReactNode;
  } & Omit<React.ComponentProps<'group'>, 'children'>
> = ({ text, size, depth, bevel, font, place, children, ...group }) => {
  const letters = layoutLetters(text, size, font);
  return (
    <group {...group}>
      {letters.map((l) => {
        if (l.ch === ' ') return null;
        const p = place?.(l, letters.length) ?? {};
        const [dx, dy, dz] = p.position ?? [0, 0, 0];
        return (
          <mesh
            key={l.i}
            geometry={textGeometry(l.ch, { size, depth, bevel, font, align: 'center' })}
            position={[l.x + l.width / 2 + dx, dy, dz]}
            rotation={p.rotation ?? [0, 0, 0]}
            scale={p.scale ?? 1}
            visible={p.visible ?? true}
            castShadow
            receiveShadow
          >
            {children}
          </mesh>
        );
      })}
    </group>
  );
};

const norm = (s: string) => s.toLowerCase().replace(/[^a-z0-9]/g, '');

/** The first sung word matching `text` (case and punctuation ignored) that starts at or after `after` seconds. */
export const findWord = (words: readonly TimingWord[], text: string, after = 0): TimingWord => {
  const w = words.find((x) => !x.backing && x.start >= after - 0.05 && norm(x.text) === norm(text));
  if (!w) throw new Error(`No sung word "${text}" after ${after}s`);
  return w;
};

/** The sung words of one line, from the first matching word onward (`text` is the whole line as sung). */
export const findLine = (words: readonly TimingWord[], text: string, after = 0): TimingWord[] => {
  const parts = text.split(/\s+/).filter(Boolean);
  const first = findWord(words, parts[0], after);
  const at = words.indexOf(first);
  return parts.map((p, n) => {
    const w = words[at + n];
    if (!w || norm(w.text) !== norm(p)) throw new Error(`Line "${text}" does not match the timing at word ${n + 1}`);
    return w;
  });
};

/** 0 → 1 with a small overshoot, starting `lead` seconds before `start` and taking `dur`. For a word's entrance. */
export const entrance = (t: number, start: number, dur = 0.35, lead = 0.08) => {
  const x = Math.min(1, Math.max(0, (t - (start - lead)) / dur));
  const c = 1.70158;
  return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2;
};

/** 0 → 1 over [from, to], smooth. */
export const smooth = (t: number, from: number, to: number) => {
  const x = Math.min(1, Math.max(0, (t - from) / (to - from)));
  return x * x * (3 - 2 * x);
};
