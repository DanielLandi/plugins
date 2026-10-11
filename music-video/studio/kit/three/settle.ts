import { continueRender } from 'remotion';
import type * as THREE from 'three';

/**
 * Releases a delayRender handle only once a redraw has really finished on the GPU: redraw, then gl.finish() and a
 * one-pixel read-back, which block until every queued draw is done. A world's first frame (dozens of shaders
 * compiling, reflections, shadows, bloom) was otherwise still in flight when Remotion took the picture, and came out
 * blank or half drawn (draft v1: the first frame of every render tab).
 */
export const releaseWhenDrawn = (handle: number, redraw: (timestamp: number) => void, gl: THREE.WebGLRenderer) => {
  redraw(performance.now());
  const ctx = gl.getContext();
  ctx.finish();
  ctx.readPixels(0, 0, 1, 1, ctx.RGBA, ctx.UNSIGNED_BYTE, new Uint8Array(4));
  continueRender(handle);
};
