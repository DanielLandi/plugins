import { describe, expect, it } from 'vitest';
import { compositionSize } from './shape';

describe('compositionSize', () => {
  it('is 1080 high and as wide as the window shape, in even pixels', () => {
    expect(compositionSize(1600, 900)).toEqual({ width: 1920, height: 1080 });
    expect(compositionSize(390, 844)).toEqual({ width: 500, height: 1080 });
  });
  it('falls back to 16:9 for a window with no area yet', () => {
    expect(compositionSize(0, 0)).toEqual({ width: 1920, height: 1080 });
    expect(compositionSize(800, 0)).toEqual({ width: 1920, height: 1080 });
    expect(compositionSize(Number.NaN, 600)).toEqual({ width: 1920, height: 1080 });
  });
  it('clamps extreme shapes to 3:1 either way', () => {
    expect(compositionSize(5000, 500)).toEqual({ width: 3240, height: 1080 });
    expect(compositionSize(100, 1000)).toEqual({ width: 360, height: 1080 });
  });
});
