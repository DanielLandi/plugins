import React from 'react';
import { bridged, GLSL_HEADER, GLSL_LIB, hexToRgb, paramDefaults, Shader } from '../../../../src/core';
import meta from './transition.json';

type P = { color: string; drips: number; seed: number; hold: number };

// Paint = a band from the top whose edge falls with progress, smoothly joined to drips
// (capsules) that run ahead of it. Phase "out" plays the same shape backwards and upside
// down, so the paint slides off the bottom with its drips trailing upward.
const FRAG = `${GLSL_HEADER}
uniform float uT;
uniform float uSeed;
uniform int uDrips;
uniform vec3 uColor;
uniform int uFlip;
${GLSL_LIB}
float capsule(vec2 p, vec2 a, vec2 b, float r) {
  vec2 pa = p - a, ba = b - a;
  float h = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0);
  return length(pa - ba * h) - r;
}
void main() {
  vec2 p = frameUv();
  if (uFlip == 1) p.y = 1.0 - p.y;
  float aspect = uRes.x / uRes.y;
  float e = uT < 0.5 ? 4.0 * uT * uT * uT : 1.0 - pow(-2.0 * uT + 2.0, 3.0) / 2.0;
  float base = mix(-0.25, 1.15, e);
  float sdf = p.y - base - 0.012 * noise(vec2(p.x * 5.0, 0.0), uSeed);
  for (int i = 0; i < 40; i++) {
    if (i >= uDrips) break;
    float fi = float(i);
    float x = (fi + 0.5 + (hash1(vec2(fi, 1.0), uSeed) - 0.5) * 0.7) / float(uDrips) * aspect;
    float w = 0.012 + 0.022 * hash1(vec2(fi, 2.0), uSeed);
    float len = (0.05 + 0.3 * hash1(vec2(fi, 3.0), uSeed)) * smoothstep(0.0, 0.35, uT);
    sdf = smin(sdf, capsule(p, vec2(x, base - 0.05), vec2(x, base + len), w), 0.05);
  }
  if (uT <= 0.0) sdf = 1.0;
  if (uT >= 1.0) sdf = -1.0;
  float a = fill(sdf);
  outColor = vec4(uColor * a, a);
}
`;

const Paint: React.FC<{ t: number; flip: boolean; params: P }> = ({ t, flip, params }) => (
  <Shader frag={FRAG} uniforms={[['1f', 'uT', t], ['1f', 'uSeed', params.seed], ['1i', 'uDrips', params.drips], ['3f', 'uColor', hexToRgb(params.color)], ['1i', 'uFlip', flip ? 1 : 0]]} />
);

export default bridged<P>(paramDefaults<P>(meta), ({ phase, progress, params }) =>
  phase === 'in' ? <Paint t={progress} flip={false} params={params} /> : <Paint t={1 - progress} flip params={params} />,
);
