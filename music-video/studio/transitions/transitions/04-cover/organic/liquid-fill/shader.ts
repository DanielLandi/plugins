// Liquid fill as a signed-distance field, one pass per pixel.
//
// Every seed is a blob: a circle that is born at `birth` and grows. Blobs never
// touch at first: where two meet, a vein of background is kept between them
// (an Apollonius-style border, rounded where three meet). Later the vein width
// drops below zero in noisy patches, so the veins pinch into droplets and
// vanish, and the whole screen ends up covered.
//
// Units: y runs 0..1 over the frame height, x runs 0..aspect.
import { GLSL_HEADER, GLSL_LIB } from '../../../../src/core';

export const MAX_SEEDS = 200;

export const FRAG = `${GLSL_HEADER}
#define MAX_SEEDS ${MAX_SEEDS}
uniform float uT;
uniform vec4 uSeeds[MAX_SEEDS];
uniform int uCount;
uniform float uMaxR;
uniform float uGap;
uniform float uJunction;
uniform float uWobble;
uniform float uSeed;
uniform vec3 uColor;
uniform int uInvert;
${GLSL_LIB}

float easeOutCubic(float x) { x = clamp(x, 0.0, 1.0); return 1.0 - pow(1.0 - x, 3.0); }

void main() {
  vec2 frag = vec2(gl_FragCoord.x, uRes.y - gl_FragCoord.y);
  float px = 1.0 / uRes.y;
  vec2 p = frag * px;

  // Slow liquid wobble: warp the domain with drifting noise.
  float t = uT;
  vec2 w = vec2(noise(p * 3.1 + vec2(t * 1.3, 0.0), uSeed), noise(p * 3.1 + vec2(5.2, -t * 1.1), uSeed));
  vec2 q = p + w * uWobble;

  // Three smallest blob distances.
  float s1 = 1e3, s2 = 1e3, s3 = 1e3;
  for (int i = 0; i < MAX_SEEDS; i++) {
    if (i >= uCount) break;
    vec4 s = uSeeds[i];
    float g = easeOutCubic((t - s.z) * s.w);
    // Unborn blobs sit far away so they neither show nor push on neighbours.
    float r = g <= 0.0 ? -1.0 : mix(0.004, uMaxR, g);
    float d = length(q - s.xy) - r;
    if (d < s1) { s3 = s2; s2 = s1; s1 = d; }
    else if (d < s2) { s3 = s2; s2 = d; }
    else if (d < s3) { s3 = d; }
  }

  // Distance to the border shared with the nearest neighbour, rounded at junctions.
  float border = smin((s2 - s1) * 0.5, (s3 - s1) * 0.5, uJunction);

  // Vein width: constant while the cells hold, then it drops below zero in
  // noisy patches so the veins break into droplets before they disappear.
  float merge = smoothstep(0.58, 0.94, t);
  float n = noise(p * 7.0 + 31.0, uSeed) * 0.5 + noise(p * 19.0 - 7.0, uSeed) * 0.18;
  float gap = uGap * (1.0 - merge * 2.2) + n * uGap * 1.6 * merge;

  float sdf = smax(s1, gap - border, uGap * 1.5);
  // Flood the last few percent so the final frame is always fully covered.
  sdf -= smoothstep(0.9, 1.0, t) * 0.25;
  if (t <= 0.0) sdf = 1.0;

  // Anti-alias over one screen pixel of the field's actual slope, so edges stay
  // crisp where the warped field is stretched or squeezed.
  float a = fill(sdf);
  if (uInvert == 1) a = 1.0 - a;
  outColor = vec4(uColor * a, a); // premultiplied
}
`;
