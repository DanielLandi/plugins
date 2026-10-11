import { describe, expect, it } from 'vitest';
import { dominant, downscale, hstack, judgeFrame, lumaStats, type Rgba } from './pixels';

const solid = (rgb: [number, number, number], w = 40, h = 20): Rgba => {
  const data = new Uint8Array(w * h * 4);
  for (let i = 0; i < w * h; i++) data.set([...rgb, 255], i * 4);
  return { data, width: w, height: h };
};
const noise = (w = 40, h = 20): Rgba => {
  const data = new Uint8Array(w * h * 4);
  for (let i = 0; i < w * h; i++) data.set([(i * 37) % 256, (i * 91) % 256, (i * 53) % 256, 255], i * 4);
  return { data, width: w, height: h };
};

describe('pixels', () => {
  it('measures luma', () => {
    expect(lumaStats(solid([0, 0, 0])).std).toBe(0);
    expect(lumaStats(noise()).std).toBeGreaterThan(20);
  });
  it('finds the dominant colour', () => {
    const d = dominant(solid([200, 10, 200]));
    expect(d.share).toBe(1);
    expect(d.color[0]).toBeGreaterThan(180);
  });
  it('fails a flat frame unless both scenes are flat', () => {
    expect(judgeFrame(solid([30, 30, 30]), noise(), noise())).toMatchObject({ ok: false });
    expect(judgeFrame(solid([30, 30, 30]), solid([30, 30, 30]), solid([10, 10, 10])).ok).toBe(true);
  });
  it('fails a frame blown out to white', () => {
    expect(judgeFrame(solid([255, 255, 255]), noise(), noise()).reason).toMatch(/blown out/);
  });
  it('fails a flood of a colour neither scene has, but not the scenes’ own colour', () => {
    // one pixel in ten is black, so the frame has texture and is not "flat"
    const magentaFlood = { ...noise(), data: solid([220, 0, 220]).data.map((v, i) => (i % 40 < 4 ? 0 : v)) };
    expect(judgeFrame(magentaFlood, solid([0, 0, 200]), noise()).reason).toMatch(/flooded/);
    const blueFlood = { ...noise(), data: solid([0, 0, 200]).data.map((v, i) => (i % 40 < 4 ? 0 : v)) };
    expect(judgeFrame(blueFlood, solid([0, 0, 200]), noise()).ok).toBe(true);
  });
  it('passes a busy frame', () => expect(judgeFrame(noise(), noise(), noise()).ok).toBe(true));
  it('scales and stacks for the panel', () => {
    const small = downscale(noise(), 10, 5);
    expect([small.width, small.height, small.data.length]).toEqual([10, 5, 200]);
    expect(hstack([small, small, small], 2).width).toBe(34);
  });
});
