import React from 'react';
import { bridged, GLSL_HEADER, GLSL_LIB, hexToRgb, paramDefaults, Shader } from '../../../../src/core';
import meta from './transition.json';

type P = { color: string; drops: number; seed: number; hold: number };

// Each drop is a circle whose radius races out then slows (like ink soaking into paper).
// Two octaves of noise push the edge in and out: a coarse wobble and fine fibres.
// A faint second edge just outside the solid ink gives the soaked "bleed" halo.
const FRAG = `${GLSL_HEADER}
uniform float uT;
uniform float uSeed;
uniform int uDrops;
uniform vec3 uColor;
uniform int uInvert;
${GLSL_LIB}
void main() {
  vec2 p = frameUv();
  float aspect = uRes.x / uRes.y;
  float sdf = 1e3;
  for (int i = 0; i < 9; i++) {
    if (i >= uDrops) break;
    vec2 c = vec2(hash1(vec2(float(i), 1.0), uSeed) * aspect * 0.8 + aspect * 0.1, hash1(vec2(float(i), 2.0), uSeed) * 0.8 + 0.1);
    float birth = float(i) / float(uDrops) * 0.45;
    float s = clamp((uT - birth) / (1.0 - birth), 0.0, 1.0);
    float r = 1.35 * pow(s, 2.0) * (0.8 + 0.4 * hash1(vec2(float(i), 3.0), uSeed));
    if (s <= 0.0) continue;
    vec2 d = p - c;
    float n = fbm(p * 4.0 + float(i), uSeed) * 0.09 + noise(p * 60.0, uSeed + float(i)) * 0.012;
    sdf = smin(sdf, length(d) - r + n * min(r * 3.0, 1.0), 0.06);
  }
  sdf -= smoothstep(0.88, 1.0, uT) * 3.0;
  if (uT <= 0.0) sdf = 1.0;
  float a = max(fill(sdf), 0.28 * fill(sdf - 0.022 - 0.01 * noise(p * 30.0, uSeed)));
  if (uInvert == 1) a = 1.0 - a;
  outColor = vec4(uColor * a, a);
}
`;

const Ink: React.FC<{ t: number; seed: number; invert: boolean; params: P }> = ({ t, seed, invert, params }) => (
  <Shader frag={FRAG} uniforms={[['1f', 'uT', t], ['1f', 'uSeed', seed], ['1i', 'uDrops', params.drops], ['3f', 'uColor', hexToRgb(params.color)], ['1i', 'uInvert', invert ? 1 : 0]]} />
);

export default bridged<P>(paramDefaults<P>(meta), ({ phase, progress, params }) =>
  phase === 'in' ? <Ink t={progress} seed={params.seed} invert={false} params={params} /> : <Ink t={progress} seed={params.seed + 1} invert params={params} />,
);
