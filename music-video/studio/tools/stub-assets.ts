import { registerHooks } from 'node:module';

// Scenes import 3D model files (.glb, .gltf, .vrm), which only the bundler can load. Tools that read a video's
// modules in Node (the board, the web build) stub them: in Node only ids, times and components are needed.
// '@mv/avatars/<file>.vrm' (the installed avatars, a bundler alias) is stubbed before it is resolved.
const MODEL = /\.(glb|gltf|vrm)$/;
const STUB = 'data:text/javascript,export%20default%20%22%22%3B';

export const stubModelFiles = () =>
  registerHooks({
    resolve: (specifier, context, next) =>
      specifier.startsWith('@mv/avatars/') ? { url: STUB, shortCircuit: true } : next(specifier, context),
    load: (url, context, next) =>
      MODEL.test(url) ? { format: 'module', source: 'export default "";', shortCircuit: true } : next(url, context),
  });
