import path from 'node:path';
import type { WebpackOverrideFn } from '@remotion/bundler';

// The runtime folder (music-video sets MV_STUDIO; tools run with it as cwd). User videos live outside it, so
// '@mv/kit' and '@mv/assets' are aliases and packages resolve from the runtime's node_modules first. 3D models
// (.glb, and .vrm characters) are imported as files. '@mv/avatars' is the install folder's downloaded avatars
// (music-video avatars install; MV_AVATARS is set by music-video for every tool). Shared by remotion.config.ts (the
// CLI) and every tools/*.ts that calls bundle().
const studio = process.env.MV_STUDIO ?? process.cwd();

export const webpackOverride: WebpackOverrideFn = (config) => ({
  ...config,
  resolve: {
    ...config.resolve,
    alias: {
      ...((config.resolve?.alias as Record<string, string>) ?? {}),
      '@mv/kit': path.join(studio, 'kit'),
      '@mv/assets': path.join(studio, 'assets'),
      '@mv/avatars': process.env.MV_AVATARS ?? path.join(studio, 'avatars'),
    },
    modules: [path.join(studio, 'node_modules'), ...(config.resolve?.modules ?? ['node_modules'])],
  },
  module: {
    ...config.module,
    rules: [...(config.module?.rules ?? []), { test: /\.(glb|gltf|vrm)$/, type: 'asset/resource' }],
  },
});
