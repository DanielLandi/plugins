import { useFrame, useThree } from '@react-three/fiber';
import React, { useMemo } from 'react';
import { useVideoConfig } from 'remotion';
import * as THREE from 'three';
import { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js';
import { OutputPass } from 'three/examples/jsm/postprocessing/OutputPass.js';
import { RenderPass } from 'three/examples/jsm/postprocessing/RenderPass.js';
import { ShaderPass } from 'three/examples/jsm/postprocessing/ShaderPass.js';
import { UnrealBloomPass } from 'three/examples/jsm/postprocessing/UnrealBloomPass.js';
import { RoundedBoxGeometry } from 'three/examples/jsm/geometries/RoundedBoxGeometry.js';
import { SanitizeShader } from './sanitize';
import { hash } from './surfaces';

// The finishing kit: a film-print post, relief maps for procedural textures, bevelled boxes, and the pieces that give
// flat canvases depth (paper with thickness and a lifted corner, thumbtacks, screws, soft contact shadows, carved
// mitred mouldings, wavy newsprint). Lengths are in metres (a card is ~0.1–0.2 wide).

/* ------------------------------------------------------------------ the film-print post ------------------------ */

type Vec3 = readonly [number, number, number];

/** The look of `FinishPost`. Start from `FINISH_DEFAULTS` and override per video: `{ ...FINISH_DEFAULTS, grain: 0.08 }`. */
export type FinishSettings = {
  /** multiplies the `bloom` prop */
  bloomGain: number;
  /** luminance above which a pixel blooms */
  threshold: number;
  /** bloom radius, 0–1 */
  radius: number;
  /** the tint of the bloom's five rings, tight to wide; warming the wide ones to amber-red gives halation */
  halation: readonly Vec3[];
  /** film grain strength (strongest in the mid-tones) and its clump size in pixels at 1080p */
  grain: number;
  grainSize: number;
  vignette: number;
  /** print contrast: a gentle S per channel, 0–1 */
  contrast: number;
  /** how far the blacks are lifted, toward `warmLift`, or toward `coolLift` where the picture is already blue */
  lift: number;
  warmLift: Vec3;
  coolLift: Vec3;
  /** lens softness toward the corners, in pixels at 1920 wide (the middle is untouched) */
  soft: number;
  /** colour fringe toward the corners, in pixels at 1920 wide */
  fringe: number;
};

/** A warm film print: halation round the lights, visible grain, soft corners. */
export const FINISH_DEFAULTS: FinishSettings = {
  bloomGain: 1.1,
  threshold: 0.95,
  radius: 0.55,
  halation: [[1, 1, 1], [1, 0.96, 0.9], [1, 0.84, 0.68], [1, 0.7, 0.5], [1, 0.58, 0.4]],
  grain: 0.12,
  grainSize: 1.5,
  vignette: 0.42,
  contrast: 0.16,
  lift: 0.02,
  warmLift: [1.0, 0.72, 0.5],
  coolLift: [0.45, 0.6, 1.0],
  soft: 1.6,
  fringe: 0.9,
};

const PrintShader = {
  uniforms: {
    tDiffuse: { value: null },
    uTime: { value: 0 },
    res: { value: new THREE.Vector2(1920, 1080) },
    grain: { value: 0.05 },
    grainSize: { value: 1.5 },
    vignette: { value: 0.42 },
    contrast: { value: 0.16 },
    lift: { value: 0.02 },
    warmLift: { value: new THREE.Vector3(1, 0.72, 0.5) },
    coolLift: { value: new THREE.Vector3(0.45, 0.6, 1) },
    tint: { value: new THREE.Vector3(1, 1, 1) },
    soft: { value: 1.6 },
    fringe: { value: 0.9 },
  },
  vertexShader: `varying vec2 vUv; void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
  fragmentShader: `uniform sampler2D tDiffuse; uniform float uTime, grain, grainSize, vignette, contrast, lift, soft, fringe;
    uniform vec3 warmLift, coolLift, tint; uniform vec2 res; varying vec2 vUv;
    float h(vec2 p) { return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }
    float vn(vec2 p) {
      vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
      return mix(mix(h(i), h(i + vec2(1.0, 0.0)), f.x), mix(h(i + vec2(0.0, 1.0)), h(i + vec2(1.0, 1.0)), f.x), f.y);
    }
    void main() {
      vec2 q = vUv - 0.5; q.x *= res.x / res.y;
      float r = length(q);
      vec2 px = 1.0 / res;
      vec3 c = texture2D(tDiffuse, vUv).rgb;
      // the lens: softer toward the corners only, with a faint colour fringe (red out, blue in)
      float e = smoothstep(0.42, 0.98, r);
      if (e > 0.002) {
        float s = soft * e;
        vec3 b = texture2D(tDiffuse, vUv + vec2(s, 0.0) * px).rgb + texture2D(tDiffuse, vUv - vec2(s, 0.0) * px).rgb
               + texture2D(tDiffuse, vUv + vec2(0.0, s) * px).rgb + texture2D(tDiffuse, vUv - vec2(0.0, s) * px).rgb;
        c = mix(c, b * 0.25, 0.75 * e);
        vec2 d = normalize(vUv - 0.5 + 1e-5) * fringe * e * px;
        c.r = mix(c.r, texture2D(tDiffuse, vUv + d).r, e);
        c.b = mix(c.b, texture2D(tDiffuse, vUv - d).b, e);
      }
      const vec3 W = vec3(0.2126, 0.7152, 0.0722);
      // print contrast: a gentle S per channel
      c = clamp(c, 0.0, 1.0);
      c = mix(c, c * c * (3.0 - 2.0 * c), contrast);
      // the shoulder: highlights lose a little colour, like a print
      float L = dot(c, W);
      c = mix(vec3(L), c, 1.0 - 0.22 * smoothstep(0.62, 1.0, L));
      // the toe: blacks lifted a touch, toward warm brown, or toward night blue where the picture is already blue
      float blue = clamp((c.b - c.r) * 6.0, 0.0, 1.0);
      c += mix(warmLift, coolLift, blue) * lift * (1.0 - smoothstep(0.0, 0.4, L));
      c *= tint;
      // a soft vignette, a little warm as it falls off
      float v = vignette * smoothstep(0.28, 1.12, r);
      c *= mix(vec3(1.0), vec3(0.86, 0.8, 0.76), v) * (1.0 - v * 0.75);
      // film grain: clumped, a new pattern every frame, strongest in the mid-tones
      vec2 g = gl_FragCoord.xy / grainSize + vec2(h(vec2(floor(uTime * 30.0), 1.7)), h(vec2(floor(uTime * 30.0), 9.1))) * 417.0;
      float n = vn(g) * 0.65 + vn(g * 2.13 + 31.0) * 0.35 - 0.5;
      float nc = vn(g * 1.31 + 77.0) - 0.5;
      L = dot(c, W);
      float amt = grain * (0.35 + 2.2 * L * (1.0 - L));
      c += amt * (vec3(n) + vec3(0.12, -0.04, -0.1) * nc);
      gl_FragColor = vec4(c, 1.0);
    }`,
};

/**
 * The film-print post, in place of a plain bloom composer (it takes over the render, like any EffectComposer here):
 * the scene, the sanitize pass, bloom with its wide rings tinted (halation round the lamps), tone mapping, then the
 * print: contrast, shoulder, toe lift, `tint`, vignette, corner lens softness and fringe, and film grain. `t` is the
 * song time (the grain changes every 1/30 s), `bloom` the bloom strength before `bloomGain`. Every other look value
 * is a prop, defaulting to `FINISH_DEFAULTS`: `<FinishPost t={t} bloom={0.2} {...LOOK} />`. Grain, softness and
 * fringe scale with the frame size, so a 4K or vertical render matches 1080p.
 */
export const FinishPost: React.FC<{ t: number; bloom: number; tint?: Vec3 } & Partial<FinishSettings>> = ({
  t,
  bloom,
  tint = [1, 1, 1],
  bloomGain = FINISH_DEFAULTS.bloomGain,
  threshold = FINISH_DEFAULTS.threshold,
  radius = FINISH_DEFAULTS.radius,
  halation = FINISH_DEFAULTS.halation,
  grain = FINISH_DEFAULTS.grain,
  grainSize = FINISH_DEFAULTS.grainSize,
  vignette = FINISH_DEFAULTS.vignette,
  contrast = FINISH_DEFAULTS.contrast,
  lift = FINISH_DEFAULTS.lift,
  warmLift = FINISH_DEFAULTS.warmLift,
  coolLift = FINISH_DEFAULTS.coolLift,
  soft = FINISH_DEFAULTS.soft,
  fringe = FINISH_DEFAULTS.fringe,
}) => {
  const { gl, scene, camera } = useThree();
  const { width, height } = useVideoConfig();
  const composer = useMemo(() => {
    const c = new EffectComposer(gl, new THREE.WebGLRenderTarget(width, height, { type: THREE.HalfFloatType, samples: 4 }));
    c.setPixelRatio(1);
    c.setSize(width, height);
    c.addPass(new RenderPass(scene, camera));
    c.addPass(new ShaderPass(SanitizeShader));
    const b = new UnrealBloomPass(new THREE.Vector2(width / 2, height / 2), bloom, radius, threshold);
    c.addPass(b);
    c.addPass(new OutputPass());
    const print = new ShaderPass(PrintShader);
    print.uniforms.res.value.set(width, height);
    c.addPass(print);
    return { c, print, b };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gl, scene, camera, width, height]);
  // the bloom pass reads these on every render, so a change of look applies on the next frame
  composer.b.strength = bloom * bloomGain;
  composer.b.radius = radius;
  composer.b.threshold = threshold;
  halation.forEach((v, i) => composer.b.bloomTintColors[i]?.set(...v));
  const u = composer.print.uniforms;
  u.uTime.value = t;
  u.grain.value = grain;
  u.grainSize.value = grainSize * Math.max(1, height / 1080);
  u.vignette.value = vignette;
  u.contrast.value = contrast;
  u.lift.value = lift;
  u.warmLift.value.set(...warmLift);
  u.coolLift.value.set(...coolLift);
  u.tint.value.set(...tint);
  u.soft.value = soft * (width / 1920);
  u.fringe.value = fringe * (width / 1920);
  useFrame(() => composer.c.render(), 1);
  return null;
};

/* ------------------------------------------------------------------ relief and bevels -------------------------- */

const reliefs = new WeakMap<THREE.Texture, { bump: THREE.Texture; scale: number }>();
/**
 * Registers a bump map that matches a colour map (it takes the map's repeat), so every material built with that map
 * through `reliefParams` catches the light on its grain: wood, brick, cork, plaster drawn on a canvas.
 */
export const setRelief = (map: THREE.Texture, bump: THREE.Texture, scale: number) => {
  bump.wrapS = bump.wrapT = THREE.RepeatWrapping;
  bump.repeat.copy(map.repeat);
  bump.anisotropy = 8;
  reliefs.set(map, { bump, scale });
};
/**
 * The material parameters that add a map's registered relief (`setRelief`), scaled by `amount`; none when the map has
 * no relief or `amount` is 0. Spread them into a material: `{ map, ...reliefParams(map) }`.
 */
export const reliefParams = (map?: THREE.Texture, amount = 1): THREE.MeshStandardMaterialParameters => {
  const r = map && amount > 0 ? reliefs.get(map) : undefined;
  return r ? { bumpMap: r.bump, bumpScale: r.scale * amount } : {};
};

const boxCache = new Map<string, THREE.BufferGeometry>();
/**
 * A box with softly rounded edges (radius ≤ 1.2 cm and ≤ 18% of its thinnest side), cached by size; null when the box
 * is too thin to round (use a plain box then) or after 3000 sizes (a guard against a size that changes every frame).
 * Real edges catch a highlight, so boxes stop reading as cut from card.
 */
export const bevelBox = (size: readonly [number, number, number]): THREE.BufferGeometry | null => {
  const key = size.map((v) => v.toFixed(4)).join('|');
  let g = boxCache.get(key);
  if (!g) {
    if (boxCache.size > 3000) return null;
    const r = Math.min(0.012, Math.min(...size) * 0.18);
    if (r < 0.0015) return null;
    g = new RoundedBoxGeometry(size[0], size[1], size[2], 2, r);
    boxCache.set(key, g);
  }
  return g;
};

/* ------------------------------------------------------------------ small canvas helpers ----------------------- */

const texCache = new Map<string, THREE.CanvasTexture>();
const tex = (key: string, w: number, h: number, draw: (x: CanvasRenderingContext2D) => void, srgb = true) => {
  let t = texCache.get(key);
  if (!t) {
    const c = document.createElement('canvas');
    c.width = w;
    c.height = h;
    draw(c.getContext('2d')!);
    t = new THREE.CanvasTexture(c);
    if (srgb) t.colorSpace = THREE.SRGBColorSpace;
    t.wrapS = t.wrapT = THREE.RepeatWrapping;
    t.anisotropy = 8;
    texCache.set(key, t);
  }
  return t;
};

const shadowMats = new Map<string, THREE.MeshBasicMaterial>();
/**
 * A soft contact shadow for something lying on a surface: a blurred dark rectangle (w×h world units, `blur` its
 * softness in the same units), optionally darker toward one corner (`corner`: [±1, ±1]; a lifted corner throws a
 * wider shadow). Cached; `userData.size` holds the plane size it needs (the rectangle plus its blur).
 */
export const shadowMat = (w: number, h: number, blur: number, opacity: number, corner: [number, number] | null = null) => {
  const key = `${w.toFixed(3)}|${h.toFixed(3)}|${blur.toFixed(3)}|${opacity}|${corner}`;
  let m = shadowMats.get(key);
  if (!m) {
    const pad = blur * 2.2;
    const S = 256 / (w + 2 * pad);
    const W = 256, H = Math.max(16, Math.round((h + 2 * pad) * S));
    // an alpha map is read from the green channel: white on black
    const t = tex(`shadow|${key}`, W, H, (x) => {
      x.fillStyle = '#000';
      x.fillRect(0, 0, W, H);
      x.fillStyle = '#fff';
      x.filter = `blur(${Math.max(1, blur * S * 0.7)}px)`;
      x.fillRect(pad * S, pad * S, w * S, h * S);
      if (corner) {
        const cx = (pad + (corner[0] > 0 ? w : 0)) * S, cy = (pad + (corner[1] < 0 ? h : 0)) * S;
        x.filter = `blur(${Math.max(2, blur * S * 1.6)}px)`;
        x.globalAlpha = 0.6;
        x.beginPath(); x.arc(cx - corner[0] * 6, cy + corner[1] * 6, 0.18 * S, 0, Math.PI * 2); x.fill();
      }
    }, false);
    m = new THREE.MeshBasicMaterial({ color: '#000000', alphaMap: t, transparent: true, opacity, depthWrite: false });
    m.userData.size = [w + 2 * pad, h + 2 * pad];
    shadowMats.set(key, m);
  }
  return m;
};

/**
 * A soft shadow plane (see `shadowMat`) facing +z, its rectangle centred on the given position. Put it a hair behind
 * the card, sign or frame it belongs to, offset a little away from the light.
 */
export const SoftShadow: React.FC<{ w: number; h: number; blur?: number; opacity?: number; corner?: [number, number] | null } & Omit<React.ComponentProps<'mesh'>, 'children'>> = ({
  w, h, blur = 0.03, opacity = 0.5, corner = null, ...m
}) => {
  const mat = shadowMat(w, h, blur, opacity, corner);
  const [W, H] = mat.userData.size as [number, number];
  return (
    <mesh material={mat} renderOrder={1} {...m}>
      <planeGeometry args={[W, H]} />
    </mesh>
  );
};

/* ------------------------------------------------------------------ paper ------------------------------------- */

const paperGeo = new Map<string, THREE.BufferGeometry>();
/**
 * An index card with thickness, hanging from a pin at its top: the lower edge stands a few millimetres off the board
 * and one lower corner (`corner`: -1 left, 1 right) curls up toward the viewer by `lift`. Centred, facing +z.
 * Box groups: 0–3 edges, 4 front, 5 back, so pass materials as [edge, edge, edge, edge, face, back]
 * (`paperEdgeMat()` for the edges and back).
 */
export const cardGeometry = (w: number, h: number, corner: -1 | 1, lift = 0.055, thick = 0.0035) => {
  const key = `${w}|${h}|${corner}|${lift}|${thick}`;
  let g = paperGeo.get(key);
  if (!g) {
    g = new THREE.BoxGeometry(w, h, thick, 28, 20, 1);
    const p = g.attributes.position as THREE.BufferAttribute;
    const cx = (corner * w) / 2, cy = -h / 2;
    const R = Math.min(w, h) * 0.5;
    for (let i = 0; i < p.count; i++) {
      const x = p.getX(i), y = p.getY(i);
      const hang = 0.006 * Math.pow(Math.max(0, (h / 2 - y) / h), 1.6);
      const d = Math.hypot(x - cx, y - cy);
      const c = Math.max(0, 1 - d / R);
      p.setZ(i, p.getZ(i) + hang + lift * c * c * c);
    }
    g.computeVertexNormals();
    paperGeo.set(key, g);
  }
  return g;
};

/** Cut paper edge and the plain back of a card (one shared material). */
export const paperEdgeMat = (() => {
  let m: THREE.MeshStandardMaterial | null = null;
  return () => (m ??= new THREE.MeshStandardMaterial({ color: '#d9ccb0', roughness: 0.9 }));
})();

/**
 * Newsprint that is not quite flat: a gentle cockle across the sheet, a little more toward its loose lower edge.
 * A plane of w×h in its own xy, displaced along z by at most `amp`; `seed` varies the pattern between sheets.
 */
export const wavyPlane = (w: number, h: number, amp = 0.0025, seed = 1, segs: [number, number] = [32, 44]) => {
  const key = `wavy|${w}|${h}|${amp}|${seed}|${segs}`;
  let g = paperGeo.get(key);
  if (!g) {
    g = new THREE.PlaneGeometry(w, h, segs[0], segs[1]);
    const p = g.attributes.position as THREE.BufferAttribute;
    for (let i = 0; i < p.count; i++) {
      const x = p.getX(i) / w, y = p.getY(i) / h;
      const loose = 0.55 + 0.45 * Math.min(1, Math.max(0, 0.5 - y));
      const z = Math.sin(x * 7.1 + seed + Math.sin(y * 3.3 + seed) * 1.2) * 0.55
        + Math.sin(y * 9.7 - x * 2.3 + seed * 2.1) * 0.3 + Math.sin((x + y) * 17 + seed) * 0.15;
      p.setZ(i, amp * loose * z);
    }
    g.computeVertexNormals();
    paperGeo.set(key, g);
  }
  return g;
};

/* ------------------------------------------------------------------ hardware ---------------------------------- */

const tackGeo = (() => {
  let g: THREE.LatheGeometry | null = null;
  return () => {
    if (!g) {
      const pts = [[0, 0.016], [0.01, 0.0156], [0.019, 0.0138], [0.026, 0.0104], [0.031, 0.0064], [0.034, 0.0034], [0.0345, 0.0012], [0.033, 0], [0.004, 0], [0.004, -0.012], [0, -0.014]]
        .map(([r, y]) => new THREE.Vector2(r, y));
      g = new THREE.LatheGeometry(pts, 40);
      g.rotateX(Math.PI / 2);
    }
    return g;
  };
})();
/** A brass thumbtack facing +z: a domed head on a short shank, with its soft shadow on the paper below it. */
export const Thumbtack: React.FC<{ position: [number, number, number]; scale?: number }> = ({ position, scale = 1 }) => {
  const brass = useMemo(() => new THREE.MeshStandardMaterial({ color: '#b48a46', metalness: 0.75, roughness: 0.32 }), []);
  return (
    <group position={position} scale={scale}>
      <SoftShadow w={0.05} h={0.05} blur={0.012} opacity={0.55} position={[0.006, -0.012, -0.0005]} />
      <mesh geometry={tackGeo()} material={brass} castShadow position={[0, 0, 0.0005]} />
    </group>
  );
};

/** A domed screw head facing +z with its slot (`rot` turns the slot), for signs and frames. */
export const Screw: React.FC<{ position: [number, number, number]; r?: number; rot?: number }> = ({ position, r = 0.022, rot = 0 }) => {
  const brass = useMemo(() => new THREE.MeshStandardMaterial({ color: '#c09a56', metalness: 0.8, roughness: 0.34 }), []);
  const slot = useMemo(() => new THREE.MeshStandardMaterial({ color: '#1a120a', roughness: 0.9 }), []);
  return (
    <group position={position} rotation={[0, 0, rot]}>
      <mesh material={brass} scale={[1, 1, 0.45]} castShadow><sphereGeometry args={[r, 20, 10, 0, Math.PI * 2, 0, Math.PI / 2]} /></mesh>
      <mesh material={brass} rotation={[Math.PI / 2, 0, 0]}><cylinderGeometry args={[r, r, 0.003, 20]} /></mesh>
      <mesh material={slot} position={[0, 0, r * 0.42]}><boxGeometry args={[r * 1.7, r * 0.22, r * 0.12]} /></mesh>
    </group>
  );
};

/* ------------------------------------------------------------------ carved mouldings ---------------------------- */

/** A moulding profile from the outer edge inward: [inset u, height z, shade 0–1 (baked occlusion)]; repeat a point
 * to make a crisp edge there. Build the curved parts with `arcPts`. */
export type Profile = [number, number, number][];

const frameGeo = new Map<string, THREE.BufferGeometry>();
/**
 * A picture frame of four mitred lengths of moulding swept along a W×H outer rectangle (centred, in its xy plane, z up
 * out of the wall). UV u runs along each length in metres × `uvScale` (so a wood texture's grain follows the piece),
 * v across the profile; vertex colours carry the profile's shade (use a material with `vertexColors: true`).
 * Cached by `key`: give each distinct frame its own.
 */
export const frameGeometry = (key: string, W: number, H: number, profile: Profile, uvScale = 1) => {
  let g = frameGeo.get(key);
  if (g) return g;
  const pos: number[] = [], uv: number[] = [], col: number[] = [], idx: number[] = [];
  // arc length across the profile, for v
  const arc = [0];
  for (let i = 1; i < profile.length; i++) arc.push(arc[i - 1] + Math.hypot(profile[i][0] - profile[i - 1][0], profile[i][1] - profile[i - 1][1]));
  const sides: { o: [number, number]; d: [number, number]; w: [number, number]; L: number; seed: number }[] = [
    { o: [0, -H / 2], d: [1, 0], w: [0, 1], L: W, seed: 0 },
    { o: [W / 2, 0], d: [0, 1], w: [-1, 0], L: H, seed: 0.37 },
    { o: [0, H / 2], d: [-1, 0], w: [0, -1], L: W, seed: 0.61 },
    { o: [-W / 2, 0], d: [0, -1], w: [1, 0], L: H, seed: 0.13 },
  ];
  for (const s of sides) {
    const base = pos.length / 3;
    profile.forEach(([u, z, shade], i) => {
      for (const e of [-1, 1]) {
        const a = e * (s.L / 2 - u);
        pos.push(s.o[0] + s.w[0] * u + s.d[0] * a, s.o[1] + s.w[1] * u + s.d[1] * a, z);
        uv.push((a + s.L / 2) * uvScale + s.seed * 3.1, arc[i] * uvScale * 2 + s.seed);
        col.push(shade, shade, shade);
      }
    });
    for (let i = 0; i < profile.length - 1; i++) {
      const a0 = base + i * 2, a1 = a0 + 1, b0 = a0 + 2, b1 = a0 + 3;
      idx.push(a0, a1, b1, a0, b1, b0);
    }
  }
  g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
  g.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
  g.setIndex(idx);
  g.computeVertexNormals();
  frameGeo.set(key, g);
  return g;
};

/**
 * A rounded piece of profile: n+1 points on the arc of radius r round (cx, cz), from angle a0 to a1 (radians), each
 * shaded by `shade(k)` with k running 0–1 along the arc. Spread several into a `Profile`, dropping a shared first point
 * with `.slice(1)`.
 */
export const arcPts = (cx: number, cz: number, r: number, a0: number, a1: number, n: number, shade: (k: number) => number): Profile =>
  Array.from({ length: n + 1 }, (_, k) => {
    const a = a0 + ((a1 - a0) * k) / n;
    return [cx + Math.cos(a) * r, cz + Math.sin(a) * r, shade(k / n)] as [number, number, number];
  });

/** A wood texture for mouldings, in the given base tone: fine straight grain along u, a few darker figure lines and
 * pores. Cached per tone. */
export const mouldingWoodTex = (tone: string) =>
  tex(`mwood|${tone}`, 1024, 256, (x) => {
    x.fillStyle = tone;
    x.fillRect(0, 0, 1024, 256);
    for (let i = 0; i < 90; i++) {
      const y0 = hash(i * 1.7) * 256;
      x.strokeStyle = hash(i + 4) > 0.45 ? `rgba(30,14,4,${0.18 + hash(i) * 0.25})` : `rgba(255,214,160,${0.06 + hash(i * 2) * 0.08})`;
      x.lineWidth = 0.6 + hash(i + 3) * 2.2;
      x.beginPath();
      for (let X = 0; X <= 1024; X += 16) x.lineTo(X, y0 + Math.sin(X * 0.006 + i) * 4 + Math.sin(X * 0.031 + i * 2) * 1.2);
      x.stroke();
    }
    for (let i = 0; i < 2600; i++) {
      x.fillStyle = `rgba(20,8,2,${0.15 + hash(i * 3) * 0.2})`;
      x.fillRect(hash(i * 7) * 1024, hash(i * 11) * 256, 2 + hash(i) * 5, 1);
    }
  });
/** The same grain as height, for a moulding's bump map (linear data, not colour); also suits painted mouldings. */
export const mouldingBumpTex = () =>
  tex('mwood-bump', 1024, 256, (x) => {
    x.fillStyle = '#808080';
    x.fillRect(0, 0, 1024, 256);
    for (let i = 0; i < 90; i++) {
      const y0 = hash(i * 1.7) * 256;
      x.strokeStyle = hash(i + 4) > 0.45 ? 'rgba(0,0,0,0.5)' : 'rgba(255,255,255,0.25)';
      x.lineWidth = 0.6 + hash(i + 3) * 2.2;
      x.beginPath();
      for (let X = 0; X <= 1024; X += 16) x.lineTo(X, y0 + Math.sin(X * 0.006 + i) * 4 + Math.sin(X * 0.031 + i * 2) * 1.2);
      x.stroke();
    }
  }, false);
