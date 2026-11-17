import { describe, expect, it } from 'vitest';
import { approachScale, coverScale, insideOpening, joinProgress, PASSAGE_DEFAULTS } from './reel';

describe('passage', () => {
  const W = 1920, H = 1080;
  it('covers every corner of the frame at its full scale', () => {
    for (const [x, y] of [[0.5, 0.42], [0.2, 0.3], [0.85, 0.6]]) {
      const p = { ...PASSAGE_DEFAULTS, x, y };
      const s = coverScale(W, H, p);
      const hh = (p.size * H * s) / 2;
      const b = { cx: x * W, cy: y * H, hw: hh * p.aspect, hh, r: Math.min(hh * p.aspect, hh) * 0.9 };
      for (const [cx, cy] of [[0, 0], [W, 0], [0, H], [W, H]]) expect(insideOpening(b, cx, cy)).toBe(true);
    }
  });
  it('grows like an exit coming closer: slowly, then fast, reaching full at the end', () => {
    const full = 25;
    const s = [0, 0.25, 0.5, 0.75, 0.9, 1].map((q) => approachScale(q, full));
    expect(s[0]).toBeCloseTo(1);
    expect(s[5]).toBeCloseTo(full);
    for (let i = 1; i < s.length; i++) expect(s[i]).toBeGreaterThan(s[i - 1]);
    expect(s[2] - s[1]).toBeLessThan(s[5] - s[4]);
  });
  it("puts the join's last frame at progress 1", () => {
    expect(joinProgress(44 / 45, 45)).toBe(1);
    expect(joinProgress(0, 45)).toBe(0);
  });
});
