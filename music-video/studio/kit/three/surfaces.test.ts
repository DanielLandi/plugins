import { describe, expect, it } from 'vitest';
import type { TimingLine, TimingWord } from '../types';
import { bareEnd, hash, sungWords } from './surfaces';

const word = (i: number, text: string, start: number): TimingWord => ({
  i, text, start, end: start + 0.3, conf: 1, source: 'test', line: 0, backing: false,
});
const words = [word(0, 'before', 0), word(1, 'one', 1), word(2, 'two', 2), word(3, 'three', 3), word(4, 'after', 4)];
const line: TimingLine = { i: 0, text: 'one two three', section: 0, backing: false, start: 1, end: 3.3, words: [1, 3] };

describe('sungWords', () => {
  it('returns only the line\'s words that have started', () => {
    expect(sungWords(words, line, 0.5)).toEqual([]);
    expect(sungWords(words, line, 2.5)).toEqual(['one', 'two']);
    expect(sungWords(words, line, 9)).toEqual(['one', 'two', 'three']);
  });

  it('shows a word slightly before it is sung (the lead)', () => {
    expect(sungWords(words, line, 1.95)).toEqual(['one', 'two']);
    expect(sungWords(words, line, 1.9)).toEqual(['one']);
    expect(sungWords(words, line, 1.9, 0.2)).toEqual(['one', 'two']);
    expect(sungWords(words, line, 1.99, 0)).toEqual(['one']);
  });
});

describe('bareEnd', () => {
  it('drops trailing commas, semicolons and colons only', () => {
    expect(bareEnd('one two,')).toBe('one two');
    expect(bareEnd('one two;:,')).toBe('one two');
    expect(bareEnd('one, two')).toBe('one, two');
    expect(bareEnd('one two.')).toBe('one two.');
    expect(bareEnd('one two?')).toBe('one two?');
  });
});

describe('hash', () => {
  it('stays in [0, 1) and is deterministic', () => {
    for (let i = -500; i < 500; i++) {
      const n = i * 0.73;
      const v = hash(n);
      expect(v).toBeGreaterThanOrEqual(0);
      expect(v).toBeLessThan(1);
      expect(hash(n)).toBe(v);
    }
  });

  it('spreads its values', () => {
    const vs = Array.from({ length: 1000 }, (_, i) => hash(i));
    const mean = vs.reduce((a, b) => a + b, 0) / vs.length;
    expect(mean).toBeGreaterThan(0.4);
    expect(mean).toBeLessThan(0.6);
    expect(new Set(vs.map((v) => Math.floor(v * 10))).size).toBe(10);
  });
});
