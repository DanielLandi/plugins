import { describe, expect, it } from 'vitest';
import { loopLayout, loopScore, loopSongFrames, scaleCuts, seamOpacity } from './loop';
import type { CutSpec } from './series';
import type { SongData } from './types';

const span = { from: 18, to: 108.5, fade: 2.5 };

describe('loopLayout', () => {
  it('sizes the loop and its seam in frames', () => {
    expect(loopLayout(span, 60)).toEqual({ frames: 5430, mainFrom: -1080, seamAt: 5280, seamFrames: 150, seamFrom: -930 });
  });

  it('wraps with no cut: the last frame shows the song frame just before the first', () => {
    const L = loopLayout(span, 60);
    expect(loopSongFrames(L, L.frames - 1).seam).toBe(loopSongFrames(L, 0).main - 1);
    expect(seamOpacity(L.seamFrames - 1, L.seamFrames)).toBe(1);
  });

  it('has no seam before the seam, and starts it almost transparent', () => {
    const L = loopLayout(span, 60);
    expect(loopSongFrames(L, L.seamAt - 1).seam).toBeNull();
    expect(loopSongFrames(L, L.seamAt).seam).toBe(930);
    expect(seamOpacity(0, L.seamFrames)).toBeLessThan(0.001);
  });

  it('still wraps when the times are not whole frames', () => {
    const L = loopLayout({ from: 18.01, to: 108.47, fade: 2.49 }, 30);
    expect(loopSongFrames(L, L.frames - 1).seam).toBe(loopSongFrames(L, 0).main - 1);
  });

  it('refuses a seam that reaches before the song, swallows the loop, or has no length', () => {
    expect(() => loopLayout({ from: 1, to: 50, fade: 2 }, 60)).toThrow(/too early/);
    expect(() => loopLayout({ from: 10, to: 13, fade: 2 }, 60)).toThrow(/too short/);
    expect(() => loopLayout({ from: 10, to: 50, fade: 0 }, 60)).toThrow(/positive/);
  });
});

describe('scaleCuts', () => {
  const cut = (frames: number): CutSpec => ({ from: 'a', to: 'b', carrier: '', why: '', landsOn: '', transition: 'crossfade', frames });

  it('keeps each cut its length in seconds', () => {
    expect(scaleCuts([cut(13), cut(26)], 60).map((c) => c.frames)).toEqual([26, 52]);
    expect(scaleCuts([cut(13)], 30)[0].frames).toBe(13);
    expect(scaleCuts([cut(13)], 24)[0].frames).toBe(10);
  });
});

describe('loopScore', () => {
  const word = (i: number, text: string) => ({ i, text, start: i, end: i + 0.5, conf: 1, source: 'x', line: 0, backing: false });
  const data = {
    timing: {
      version: 1, duration: 120,
      words: [word(0, 'Morning'), word(1, 'silver,'), word(2, 'Water'), word(3, 'City'), word(4, 'lights')],
      lines: [{ i: 0, text: 'Morning wakes up silver', section: 0, backing: false, start: 0, end: 2, words: [0, 1] }],
      sections: [{ i: 0, name: 'Verse 1', start: 0, end: 2, lines: [0, 0] }],
    },
    analysis: {
      version: 1, duration: 120, fps: 30, tempo: 136.4, beats: [0.4, 0.84], downbeats: [0.4],
      sections: [{ id: 'intro', name: 'Intro', start: 0, end: 15, sung: false }],
      energy: { rms: [0.5], low: [0.4], mid: [0.3], high: [0.2] }, hits: [{ t: 47.8, strength: 1 }],
    },
  } as SongData;

  it('keeps only the looked-up words, matched like findWord (case, punctuation and Latin accents ignored), and no lines', () => {
    const s = loopScore(data, ['silver', 'water']);
    expect(s.timing.words.map((w) => w.text)).toEqual(['silver,', 'Water']);
  });

  it('keeps only the named words in any script, accents and case aside', () => {
    const many = { ...data, timing: { ...data.timing,
      words: [word(0, 'Ônibus,'), word(1, 'дорога'), word(2, 'ночь'), word(3, '道'), word(4, '夜')] } };
    const s = loopScore(many as SongData, ['onibus', 'Дорога', '道']);
    expect(s.timing.words.map((w) => w.text)).toEqual(['Ônibus,', 'дорога', '道']);
    expect(s.timing.lines).toEqual([]);
    expect(s.timing.sections).toEqual([]);
  });

  it('drops beats, downbeats and hits, and keeps tempo, energy and sections', () => {
    const s = loopScore(data, []);
    expect(s.analysis).toMatchObject({ beats: [], downbeats: [], hits: [], tempo: 136.4, energy: data.analysis.energy });
    expect(s.analysis.sections).toEqual(data.analysis.sections);
  });

  it('is idempotent', () => {
    const once = loopScore(data, ['silver']);
    expect(loopScore(once, ['silver'])).toEqual(once);
  });
});
