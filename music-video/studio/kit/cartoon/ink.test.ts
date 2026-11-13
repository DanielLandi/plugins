import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { cast } from './cast';
import { ImpactBurst, zoomAt, zoomMap } from './fx';
import { InkShapes, inkPath } from './ink';
import { boilSeed, ramp, springStep } from './motion';
import { buildCharacter, type Pose } from './rig';

// A short piece of acting: a walk-in, a double take with a smear and a mouth morph.
const pose = (t: number): Pose => ({
  x: 300 + 200 * t, ground: 900, face: 1, walk: 1 - ramp(t, 1, 1.2), walkPhase: t,
  sy: 1 + 0.4 * springStep(t, 1.3), eyeScale: 1 + 0.8 * springStep(t, 1.3), smear: t > 1.6 && t < 1.9 ? 0.8 : 0,
  mouth: ['smile', 'shout', ramp(t, 1.2, 1.4)], armF: { world: [900, 600 - 100 * t], wiggle: 20, wigglePhase: t * 9 },
});
const frame = (f: number) => renderToStaticMarkup(
  createElement('svg', null, createElement(InkShapes, { shapes: buildCharacter(cast.bean, pose(f / 30)), seed: boilSeed(f) })));

describe('brush ink', () => {
  it('a frame drawn alone equals the same frame drawn after the ones before it', () => {
    const alone = frame(52);
    for (let f = 0; f < 52; f++) frame(f);
    expect(frame(52)).toBe(alone);
  });

  it('draws real paths', () => {
    const svg = frame(40);
    expect(svg).not.toMatch(/NaN|undefined|Infinity/);
    expect((svg.match(/<path /g) ?? []).length).toBeGreaterThan(20);
  });

  it('boils: another seed redraws the lines a little differently', () => {
    const shapes = buildCharacter(cast.plum, { x: 600, ground: 900, face: -1 });
    const draw = (seed: number) => renderToStaticMarkup(createElement('svg', null, createElement(InkShapes, { shapes, seed })));
    expect(draw(3)).toBe(draw(3));
    expect(draw(3)).not.toBe(draw(4));
  });

  it('inks a set piece with the same brush', () => {
    const d = inkPath([[0, 0], [100, 10], [200, 0], [150, 80]], 7, 6, true);
    expect(d.startsWith('M ')).toBe(true);
    expect(d).toBe(inkPath([[0, 0], [100, 10], [200, 0], [150, 80]], 7, 6, true));
  });

  it('an impact burst leaves no stray dots as it fades', () => {
    const svg = renderToStaticMarkup(createElement('svg', null, createElement(ImpactBurst, { t: 6.58, t0: 6, x: 900, y: 600 })));
    expect(svg).not.toContain('stroke-linecap');
  });

  it('impact strokes thin out as they shorten, so none pops off in one frame', () => {
    for (let f = 0; f < 18; f++) {
      const svg = renderToStaticMarkup(createElement('svg', null, createElement(ImpactBurst, { t: 6 + f / 30, t0: 6, x: 900, y: 600 })));
      for (const m of svg.matchAll(/d="M ([\d.-]+) ([\d.-]+) L ([\d.-]+) ([\d.-]+)" stroke="[^"]+" stroke-width="([\d.]+)"/g)) {
        const len = Math.hypot(+m[3] - +m[1], +m[4] - +m[2]);
        expect(+m[5]).toBeLessThanOrEqual(len / 3 + 0.01);
      }
    }
  });

  it('the burst shrinks to nothing smoothly before it goes', () => {
    const radius = (dt: number) => {
      const svg = renderToStaticMarkup(createElement('svg', null, createElement(ImpactBurst, { t: 6 + dt, t0: 6, x: 900, y: 600, r: 150 })));
      const d = svg.match(/<path d="(M [^"]+ Z)" fill="#ffffff"/)?.[1];
      if (!d) return 0;
      const nums = d.match(/-?[\d.]+/g)!.map(Number);
      let r = 0;
      for (let k = 0; k < nums.length; k += 2) r = Math.max(r, Math.hypot(nums[k] - 900, nums[k + 1] - 600));
      return r;
    };
    for (let f = 6; f < 20; f++) expect(Math.abs(radius((f + 1) / 30) - radius(f / 30))).toBeLessThan(30);
  });
});

describe('the camera', () => {
  it('a push-in keeps its focus point fixed in any composition size', () => {
    for (const [fx, fy] of [[760, 520], [300, 1500]] as const) {
      const map = zoomMap(0.5, fx, fy);
      expect(map([fx, fy])).toEqual([fx, fy]);
      expect(map([fx + 100, fy])).toEqual([fx + 150, fy]);
      const style = zoomAt(0.5, fx, fy);
      expect(style.transformOrigin).toBe('0 0');
      expect(style.transform).toContain(`translate(${fx}px, ${fy}px) scale(1.5) translate(${-fx}px, ${-fy}px)`);
    }
  });
});

describe('review fixes (#34)', () => {
  it('scale 0 draws nothing, and no scale puts a NaN in a path', () => {
    const at = (scale: number) => buildCharacter(cast.bean, { ...pose(1.7), scale, lift: 40 });
    expect(at(0)).toEqual([]);
    expect(at(-0.5)).toEqual([]);
    for (const scale of [0, -0.5, 1e-4, 0.01, 1]) {
      const svg = renderToStaticMarkup(createElement('svg', null, createElement(InkShapes, { shapes: at(scale), seed: 3 })));
      expect(svg).not.toMatch(/NaN|Infinity|undefined/);
    }
  });
});
