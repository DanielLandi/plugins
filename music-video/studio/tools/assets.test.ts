import { describe, expect, it } from 'vitest';
import { webpackOverride } from '../webpack-override';
import { MODEL } from './stub-assets';

// Scenes import their 3D files as URLs: models and characters, and HDR/EXR skies (issue #36).
const FILES = ['car.glb', 'tree.gltf', 'hero.vrm', 'textures/sky_2k.hdr', 'textures/sky_2k.exr'];

describe('3D file imports', () => {
  it('the bundler emits every 3D file type as a URL', () => {
    const config = webpackOverride({}) as { module?: { rules?: { test?: RegExp; type?: string }[] } };
    const rules = config.module?.rules ?? [];
    for (const f of FILES) {
      expect(rules.some((r) => r.type === 'asset/resource' && r.test?.test(f)), f).toBe(true);
    }
  });
  it('the Node tools stub every 3D file type', () => {
    for (const f of FILES) expect(MODEL.test(`file:///v/${f}`), f).toBe(true);
    expect(MODEL.test('file:///v/scene.tsx')).toBe(false);
  });
});
