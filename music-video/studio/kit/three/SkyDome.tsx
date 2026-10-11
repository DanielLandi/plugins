import React, { useMemo } from 'react';
import * as THREE from 'three';
import type { Vec3 } from './camera';

const vertex = /* glsl */ `
varying vec3 vDir;
void main() {
  vDir = normalize(position);
  vec4 p = modelViewMatrix * vec4(position, 1.0);
  gl_Position = projectionMatrix * p;
  gl_Position.z = gl_Position.w; // always at the far plane
}`;

const fragment = /* glsl */ `
uniform vec3 zenith; uniform vec3 horizon; uniform vec3 ground; uniform vec3 sunColor; uniform vec3 sunDir;
uniform float sunSize; uniform float glow; uniform float band;
varying vec3 vDir;
void main() {
  vec3 d = normalize(vDir);
  float h = d.y;
  vec3 c = h > 0.0 ? mix(horizon, zenith, pow(clamp(h / band, 0.0, 1.0), 0.6)) : mix(horizon, ground, clamp(-h * 6.0, 0.0, 1.0));
  float s = max(dot(d, normalize(sunDir)), 0.0);
  c += sunColor * glow * pow(s, 8.0);                       // the glow round the sun
  c = mix(c, sunColor * 1.6, smoothstep(1.0 - sunSize, 1.0 - sunSize * 0.7, s)); // the disc
  gl_FragColor = vec4(c, 1.0);
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`;

/**
 * A gradient sky with a sun disc, drawn behind everything. All values are plain props, so a scene animates the sky
 * by passing new colours each frame.
 */
export const SkyDome: React.FC<{
  zenith: THREE.ColorRepresentation;
  horizon: THREE.ColorRepresentation;
  ground?: THREE.ColorRepresentation;
  sunColor?: THREE.ColorRepresentation;
  /** Direction towards the sun (need not be normalised). */
  sunDir?: Vec3;
  /** Disc radius as 1 - cos(angle); 0 hides the disc. */
  sunSize?: number;
  glow?: number;
  /** How high above the horizon the gradient reaches the zenith colour (0–1). */
  band?: number;
}> = ({ zenith, horizon, ground = horizon, sunColor = '#ffffff', sunDir = [0, 0.2, -1], sunSize = 0.0015, glow = 0.4, band = 0.6 }) => {
  const material = useMemo(
    () =>
      new THREE.ShaderMaterial({
        vertexShader: vertex,
        fragmentShader: fragment,
        side: THREE.BackSide,
        depthWrite: false,
        fog: false,
        uniforms: {
          zenith: { value: new THREE.Color() }, horizon: { value: new THREE.Color() }, ground: { value: new THREE.Color() },
          sunColor: { value: new THREE.Color() }, sunDir: { value: new THREE.Vector3() },
          sunSize: { value: 0 }, glow: { value: 0 }, band: { value: 0.6 },
        },
      }),
    [],
  );
  const u = material.uniforms;
  u.zenith.value.set(zenith);
  u.horizon.value.set(horizon);
  u.ground.value.set(ground);
  u.sunColor.value.set(sunColor);
  u.sunDir.value.set(...sunDir);
  u.sunSize.value = sunSize;
  u.glow.value = glow;
  u.band.value = band;
  return (
    <mesh material={material} renderOrder={-1} frustumCulled={false}>
      <sphereGeometry args={[1000, 32, 16]} />
    </mesh>
  );
};

/** Mixes two colours (hex or names) in linear space: `x` 0 gives a, 1 gives b. */
export const mixColor = (a: THREE.ColorRepresentation, b: THREE.ColorRepresentation, x: number) =>
  new THREE.Color(a).lerp(new THREE.Color(b), Math.min(1, Math.max(0, x))).getHexString().replace(/^/, '#');
