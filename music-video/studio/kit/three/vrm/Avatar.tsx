// VRM characters (three-vrm: MToon cel shading, spring-bone hair and cloth, expressions, look-at) driven by a pure
// function of time. Adapted from the three-vrm research round. Each <Avatar> loads its own copy of the model.
import { useThree } from '@react-three/fiber';
import { VRMLoaderPlugin, VRMUtils, type VRM, type VRMHumanBoneName } from '@pixiv/three-vrm';
import React, { useEffect, useLayoutEffect, useMemo, useState } from 'react';
import { cancelRender, delayRender, useCurrentFrame, useVideoConfig } from 'remotion';
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import type { Vec3 } from '../camera';
import { releaseWhenDrawn } from '../settle';
import type { Pose } from './motion';
import { replayTo, type Replayable, type ReplayState } from './replay';

/** Where a character is and what it does at one moment. */
export type AvatarState = {
  /** Feet position on the ground (world units are metres; the samples are about 1.5 m tall). */
  pos: Vec3;
  /** Turn about y in radians; 0 faces +z (towards a default camera). faceYaw() points it at something. */
  yaw: number;
  pose: Pose;
  /** Hips offset in metres (crouch with a negative y, hop with a positive one). */
  hips?: Vec3;
  /** Expression weights 0–1: happy, angry, sad, relaxed, blink, aa, ih, ou, ee, oh, or the model's own (the VRoid
   * samples add 'Surprised'). */
  expr?: Record<string, number>;
  /** A world point the eyes and head follow, or null to look straight ahead. */
  lookAt?: Vec3 | null;
  /** Extra force on hair and cloth springs (world units, added to gravity): a gust, a shockwave, a dash. */
  wind?: Vec3;
};
export type Drive = (t: number) => AvatarState;

/** The yaw that turns a character standing at `from` to face `to`. */
export const faceYaw = (from: Vec3, to: Vec3) => Math.atan2(to[0] - from[0], to[2] - from[2]);

const TIMEOUT_MS = 120_000;

/** Loads a VRM (its own instance per caller), holding the render until the model is in the scene. */
export const useVrm = (url: string): { vrm: VRM | null; handle: number } => {
  const [vrm, setVrm] = useState<VRM | null>(null);
  const [handle] = useState(() => delayRender(`Loading avatar ${url}`, { timeoutInMilliseconds: TIMEOUT_MS }));
  useEffect(() => {
    let live = true;
    const loader = new GLTFLoader();
    loader.register((parser) => new VRMLoaderPlugin(parser));
    loader
      .loadAsync(url)
      .then((gltf) => {
        const v = gltf.userData.vrm as VRM | undefined;
        if (!v) throw new Error('not a VRM file (no VRM extension)');
        VRMUtils.removeUnnecessaryVertices(gltf.scene);
        VRMUtils.combineSkeletons(gltf.scene);
        VRMUtils.rotateVRM0(v);
        // Posed bounds change every frame: never cull a character at the edge of the picture.
        v.scene.traverse((o) => {
          o.frustumCulled = false;
        });
        if (live) setVrm(v);
      })
      .catch((e) =>
        cancelRender(new Error(`avatar ${url} did not load (${e instanceof Error ? e.message : e}): for the samples ` +
          'run music-video avatars install')));
    return () => {
      live = false;
    };
  }, [url]);
  return { vrm, handle };
};

type Base = { dir: THREE.Vector3; power: number };
const tmp = new THREE.Vector3();
const windV = new THREE.Vector3();

/** Pose a VRM for one moment. VRM 0.x models are turned round by rotateVRM0 and mirror x/z in normalized space. */
const applyState = (vrm: VRM, s: AvatarState, look: THREE.Object3D, base: Map<unknown, Base>) => {
  const v0 = vrm.meta?.metaVersion === '0';
  vrm.scene.position.set(...s.pos);
  vrm.scene.rotation.set(0, s.yaw + (v0 ? Math.PI : 0), 0);
  const h = vrm.humanoid;
  for (const name of Object.keys(h.humanBones)) h.getNormalizedBoneNode(name as VRMHumanBoneName)?.quaternion.identity();
  for (const [name, [x, y, z]] of Object.entries(s.pose)) {
    h.getNormalizedBoneNode(name as VRMHumanBoneName)?.rotation.set(v0 ? -x : x, y, v0 ? -z : z, 'XYZ');
  }
  const hips = h.getNormalizedBoneNode('hips');
  if (hips) {
    const rest = (hips.userData.mvRest ??= hips.position.clone()) as THREE.Vector3;
    hips.position.copy(rest);
    if (s.hips) hips.position.add(tmp.set(v0 ? -s.hips[0] : s.hips[0], s.hips[1], v0 ? -s.hips[2] : s.hips[2]));
  }
  const em = vrm.expressionManager;
  if (em) {
    for (const e of em.expressions) em.setValue(e.expressionName, 0);
    for (const [k, w] of Object.entries(s.expr ?? {})) em.setValue(k, w);
  }
  if (vrm.lookAt) {
    if (s.lookAt) {
      look.position.set(...s.lookAt);
      look.updateMatrixWorld();
      vrm.lookAt.target = look;
      vrm.lookAt.autoUpdate = true;
    } else {
      vrm.lookAt.target = null;
      vrm.lookAt.autoUpdate = false;
      vrm.lookAt.yaw = 0;
      vrm.lookAt.pitch = 0;
    }
  }
  const sb = vrm.springBoneManager;
  if (sb) {
    windV.set(...(s.wind ?? [0, 0, 0]));
    for (const j of sb.joints) {
      let b = base.get(j);
      if (!b) {
        b = { dir: j.settings.gravityDir.clone(), power: j.settings.gravityPower };
        base.set(j, b);
      }
      tmp.copy(b.dir).multiplyScalar(b.power).add(windV);
      const p = tmp.length();
      j.settings.gravityPower = p;
      if (p > 1e-6) j.settings.gravityDir.copy(tmp).divideScalar(p);
    }
  }
};

/** The VRM as something replayTo can bring to any frame. */
const replayable = (vrm: VRM, look: THREE.Object3D): Replayable<AvatarState> => {
  const base = new Map<unknown, Base>();
  return {
    apply: (s) => applyState(vrm, s, look, base),
    step: (dt) => {
      vrm.scene.updateMatrixWorld(true);
      vrm.update(dt);
    },
    reset: () => {
      vrm.scene.updateMatrixWorld(true);
      vrm.update(0);
      vrm.springBoneManager?.reset();
    },
  };
};

export type AvatarProps = {
  /** The .vrm file: `import a from '@mv/avatars/vroid-sample-1.vrm'`, or a CC0/OFL file in the video's folder. */
  url: string;
  /** The character at song time t (seconds, the kit's clock: useSongTime). */
  drive: Drive;
  /**
   * Song seconds where its physics starts: the scene's start (or the bake-off window's). Any frame replays the
   * springs from here (from its nearest frame), so a late scene does not replay the whole song. Before it, the
   * character holds its pose at that frame.
   */
  from?: number;
  /** Multiplies the MToon outline width (1 = as modelled; 1.5–2 reads more hand-inked). */
  outline?: number;
  /** Draw the whole character in one flat colour (an impact frame), or null for its own materials. */
  silhouette?: string | null;
};

/**
 * A VRM character on the stage. Its pose, place, face and the wind on its hair come from `drive(t)` (t in song
 * seconds); spring bones replay deterministically from `from`, so any frame renders the same alone or in sequence.
 */
export const Avatar: React.FC<AvatarProps> = ({ url, drive, from = 0, outline = 1, silhouette = null }) => {
  const { vrm, handle } = useVrm(url);
  const advance = useThree((s) => s.advance);
  const gl = useThree((s) => s.gl);
  const invalidate = useThree((s) => s.invalidate);
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const look = useMemo(() => new THREE.Object3D(), []);
  const sim = useMemo(() => (vrm ? { r: replayable(vrm, look), mem: { frame: -1 } as ReplayState } : null), [vrm, look]);
  const [released, setReleased] = useState(false);

  useLayoutEffect(() => {
    if (!vrm) return;
    vrm.scene.traverse((o) => {
      const mesh = o as THREE.Mesh;
      if (!mesh.isMesh) return;
      const mats = (mesh.userData.mvMats ??= mesh.material) as THREE.Material | THREE.Material[];
      for (const m of Array.isArray(mats) ? mats : [mats]) {
        const toon = m as THREE.Material & { outlineWidthFactor?: number; userData: { mvOutline?: number } };
        if (typeof toon.outlineWidthFactor === 'number') {
          toon.userData.mvOutline ??= toon.outlineWidthFactor;
          toon.outlineWidthFactor = toon.userData.mvOutline * outline;
        }
      }
      if (silhouette) {
        const flat = (mesh.userData.mvFlat ??= new THREE.MeshBasicMaterial()) as THREE.MeshBasicMaterial;
        flat.color.set(silhouette);
        mesh.material = Array.isArray(mats) ? mats.map(() => flat) : flat;
      } else {
        mesh.material = mats;
      }
    });
  }, [vrm, outline, silhouette]);

  useLayoutEffect(() => {
    if (!sim) return;
    const start = Math.round(from * fps);
    // Song time from the frame the replay starts on, so the pose keeps the scene's clock (useSongTime) exactly.
    replayTo(sim.r, sim.mem, drive, Math.max(0, frame - start), fps, 4, 1, start);
    invalidate();
  }, [sim, drive, from, frame, fps, invalidate]);

  useEffect(() => {
    if (!vrm || released) return;
    setReleased(true);
    // The model arrives after Remotion's frame was drawn: draw again with it, then let the frame go.
    releaseWhenDrawn(handle, advance, gl);
  }, [vrm, released, handle, advance, gl]);

  return vrm ? <primitive object={vrm.scene} /> : null;
};
