import { describe, expect, it } from 'vitest';
import { layoutOf, safeRect } from './safe';

describe('safe areas', () => {
  it('landscape keeps 5% on every side', () => {
    const r = safeRect(1920, 1080);
    expect(r.x).toBeCloseTo(96);
    expect(r.y).toBeCloseTo(54);
    expect(r.width).toBeCloseTo(1728);
    expect(r.height).toBeCloseTo(972);
  });
  it('portrait keeps clear of the platform buttons and captions', () => {
    const r = safeRect(1080, 1920);
    expect(r.x).toBeCloseTo(54);
    expect(r.y).toBeCloseTo(268.8);
    expect(r.width).toBeCloseTo(896.4);
    expect(r.height).toBeCloseTo(1228.8);
  });
  it('picks the layout from the frame', () => {
    expect(layoutOf(1920, 1080)).toBe('landscape');
    expect(layoutOf(1080, 1920)).toBe('portrait');
  });
});
