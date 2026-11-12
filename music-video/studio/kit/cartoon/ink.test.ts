import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { cast } from './cast';
import { ImpactBurst } from './fx';
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
});
