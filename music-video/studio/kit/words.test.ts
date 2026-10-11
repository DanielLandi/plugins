import { describe, expect, it } from 'vitest';
import { findLine, findWord } from './three/text3d';
import { normWord } from './words';

const w = (i: number, text: string, start: number) =>
  ({ i, text, start, end: start + 0.4, conf: 1, source: 'x', line: 0, backing: false });

describe('normWord', () => {
  it('ignores case, punctuation and Latin accents', () => {
    expect(normWord('Ônibus,')).toBe(normWord('onibus'));
    expect(normWord("You'll")).toBe('youll');
  });
  it('keeps every script, and the marks that change a word outside Latin', () => {
    expect(normWord('Дорога!')).toBe('дорога');
    expect(normWord('काम')).not.toBe(normWord('कम'));
    expect(normWord('が')).not.toBe(normWord('か'));
    expect(normWord('道')).toBe('道');
  });
});

describe('scene word lookup', () => {
  const words = [w(0, 'дорога', 1), w(1, 'ночь', 2), w(2, 'Ônibus,', 3), w(3, 'lotado', 4)];
  it('finds non-Latin words by their own letters', () => {
    expect(findWord(words, 'ночь').start).toBe(2);
    expect(findWord(words, 'дорога').start).toBe(1);
  });
  it('finds accented words written without accents, and lines', () => {
    expect(findWord(words, 'onibus').start).toBe(3);
    expect(findLine(words, 'Ônibus lotado').map((x) => x.start)).toEqual([3, 4]);
  });
});
