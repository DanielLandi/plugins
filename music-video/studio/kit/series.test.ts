import { describe, expect, it } from 'vitest';
import { layoutSeries, type CutSpec } from './series';

const cut = (from: string, to: string, frames: number): CutSpec => ({
  from, to, frames, transition: 'iris', carrier: 'c', why: 'w', landsOn: 'l',
});
const scenes = [{ id: 'a', from: 0 }, { id: 'b', from: 10 }, { id: 'c', from: 20 }];

describe('layoutSeries', () => {
  it('lengthens scenes so each cut is centred on its boundary and the total is the song', () => {
    const l = layoutSeries(scenes, [cut('a', 'b', 20), cut('b', 'c', 15)], 30, 30);
    expect(l.scenes).toEqual([
      { id: 'a', durationInFrames: 310, startFrame: 0 },
      { id: 'b', durationInFrames: 317, startFrame: 290 },
      { id: 'c', durationInFrames: 308, startFrame: 592 },
    ]);
    expect(l.cuts.map((c) => c.startFrame)).toEqual([290, 592]);
    const sceneFrames = l.scenes.reduce((s, x) => s + x.durationInFrames, 0);
    expect(sceneFrames - 35).toBe(l.totalFrames);
    expect(l.totalFrames).toBe(900);
  });
  it('at a sub-frame rate (a multiple of 30) cuts keep their length in time and land where the 30 fps cut does', () => {
    const base = layoutSeries([{ id: 'a', from: 0 }, { id: 'b', from: 32.46 }], [cut('a', 'b', 18)], 40, 30);
    const sub = layoutSeries([{ id: 'a', from: 0 }, { id: 'b', from: 32.46 }], [cut('a', 'b', 18)], 40, 30 * 64);
    expect(sub.cuts[0].startFrame).toBe(base.cuts[0].startFrame * 64);
    expect(sub.cuts[0].cut.frames).toBe(18 * 64);
    expect(sub.totalFrames).toBe(base.totalFrames * 64);
  });
  it('a single scene needs no cuts', () => {
    expect(layoutSeries([{ id: 'all', from: 0 }], [], 5, 30).scenes).toEqual([{ id: 'all', durationInFrames: 150, startFrame: 0 }]);
  });
  it('names a missing cut', () => {
    expect(() => layoutSeries(scenes, [cut('a', 'b', 10)], 30, 30)).toThrow('No cut from "b" to "c" in cuts.ts');
  });
  it('names a cut longer than its scene', () => {
    expect(() => layoutSeries(scenes, [cut('a', 'b', 700), cut('b', 'c', 10)], 30, 30)).toThrow(/Cut a → b \(700 frames\) is longer than a scene/);
  });
  it('wants the first scene at 0 and scenes in order', () => {
    expect(() => layoutSeries([{ id: 'a', from: 1 }], [], 30, 30)).toThrow('The first scene must start at 0 s, not 1');
    expect(() => layoutSeries([{ id: 'a', from: 0 }, { id: 'b', from: 40 }], [cut('a', 'b', 4)], 30, 30)).toThrow(/Scene "b" has no length/);
  });
  it('refuses cuts between scenes that are not neighbours', () => {
    expect(() => layoutSeries(scenes, [cut('a', 'b', 10), cut('b', 'c', 10), cut('a', 'c', 10)], 30, 30)).toThrow('not neighbours: a → c');
  });
});
