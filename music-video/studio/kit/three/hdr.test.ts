import { describe, expect, it } from 'vitest';
import { hdrFormat } from './hdr';

describe('hdrFormat', () => {
  it('reads the format from the bundled URL', () => {
    expect(hdrFormat('/static/a1b2c3.hdr')).toBe('hdr');
    expect(hdrFormat('/static/textures/kloppenheim_2k.HDR')).toBe('hdr');
    expect(hdrFormat('https://x/y/sky.exr?v=2#a')).toBe('exr');
  });
  it('an explicit format wins, and an unknown one is an error that names the file', () => {
    expect(hdrFormat('/static/blob', 'exr')).toBe('exr');
    expect(() => hdrFormat('/static/sky.jpg')).toThrow(/sky\.jpg/);
  });
});
