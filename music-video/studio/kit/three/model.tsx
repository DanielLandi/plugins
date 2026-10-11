import { useThree } from '@react-three/fiber';
import React, { useEffect, useMemo, useState } from 'react';
import { cancelRender, delayRender } from 'remotion';
import * as THREE from 'three';
import { releaseWhenDrawn } from './settle';
import { GLTFLoader, type GLTF } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { clone as cloneSkinned } from 'three/examples/jsm/utils/SkeletonUtils.js';

// 3D models (CC0 GLBs in studio/assets/models, imported as URLs: `import car from '@mv/assets/models/suv-quaternius.glb'`).

const cache = new Map<string, Promise<GLTF>>();

/** Loads a GLB once per bundle; every caller of the same URL shares the result. */
export const loadModel = (url: string): Promise<GLTF> => {
  let p = cache.get(url);
  if (!p) {
    p = new GLTFLoader().loadAsync(url);
    cache.set(url, p);
  }
  return p;
};

/** The loaded model, or null until it has loaded. (`<Model>` holds the frame until it is drawn.) */
export const useModel = (url: string): GLTF | null => {
  const [gltf, setGltf] = useState<GLTF | null>(null);
  useEffect(() => {
    let live = true;
    loadModel(url)
      .then((g) => live && setGltf(g))
      .catch((e) => cancelRender(e));
    return () => {
      live = false;
    };
  }, [url]);
  return gltf;
};

export type ModelProps = Omit<React.ComponentProps<'group'>, 'children' | 'scale'> & {
  url: string;
  /** Scale uniformly so the model is this tall (world units). Otherwise `length` (longest horizontal side). */
  height?: number;
  length?: number;
  /** Turn the model about y before placing it (radians), e.g. to point a car's nose along +z. */
  yaw?: number;
  /** An animation clip name (or a unique part of it) and the time into it in seconds; looped. */
  clip?: string;
  clipTime?: number;
  /** Change materials after cloning (recolour, flat shading…). Called once per material per instance. */
  material?: (m: THREE.Material, mesh: THREE.Mesh) => THREE.Material;
  shadows?: boolean;
};

/**
 * A model placed with its base centre at the group's origin, fitted to `height` or `length`. Each instance is its
 * own clone (skinned models included), so one URL can appear many times with different poses.
 */
export const Model: React.FC<ModelProps> = ({ url, height, length, yaw = 0, clip, clipTime = 0, material, shadows = true, ...group }) => {
  const gltf = useModel(url);
  // The canvas only redraws when the frame changes, and the model arrives later: hold the frame, redraw once the
  // model is in the scene, then release it.
  const [handle] = useState(() => delayRender(`Loading model ${url}`));
  const advance = useThree((s) => s.advance);
  const gl = useThree((s) => s.gl);
  const inst = useMemo(() => {
    if (!gltf) return null;
    const root = cloneSkinned(gltf.scene);
    root.traverse((o) => {
      const mesh = o as THREE.Mesh;
      if (!mesh.isMesh) return;
      mesh.castShadow = shadows;
      mesh.receiveShadow = shadows;
      const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
      const next = mats.map((m) => (material ? material(m.clone(), mesh) : m.clone()));
      mesh.material = Array.isArray(mesh.material) ? next : next[0];
      // Skinned bounds change with the pose; never cull them at the edge of the frame.
      if ((mesh as THREE.SkinnedMesh).isSkinnedMesh) mesh.frustumCulled = false;
    });
    root.rotation.y = yaw;
    root.updateMatrixWorld(true);
    const box = new THREE.Box3().setFromObject(root);
    const size = box.getSize(new THREE.Vector3());
    const s = height ? height / size.y : length ? length / Math.max(size.x, size.z) : 1;
    const centre = box.getCenter(new THREE.Vector3());
    const holder = new THREE.Group();
    root.position.set(-centre.x, -box.min.y, -centre.z);
    holder.add(root);
    holder.scale.setScalar(s);
    const mixer = gltf.animations.length ? new THREE.AnimationMixer(root) : null;
    return { holder, mixer };
    // material is a function prop: callers pass a stable one (module-level), so it is not a dependency.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gltf, height, length, yaw, shadows]);

  useEffect(() => {
    if (!inst) return;
    releaseWhenDrawn(handle, advance, gl);
  }, [inst, advance, handle, gl]);

  if (!gltf || !inst) return null;
  if (inst.mixer && clip) {
    const c = gltf.animations.find((a) => a.name === clip) ?? gltf.animations.find((a) => a.name.includes(clip));
    if (!c) throw new Error(`No animation "${clip}" in ${url} (has: ${gltf.animations.map((a) => a.name).join(', ')})`);
    inst.mixer.stopAllAction();
    inst.mixer.clipAction(c).play();
    // setTime resets and advances: the pose depends only on clipTime, never on the frame rendered before.
    inst.mixer.setTime(clipTime % c.duration);
  }
  return (
    <group {...group}>
      <primitive object={inst.holder} />
    </group>
  );
};
