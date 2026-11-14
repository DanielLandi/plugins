// How an <Avatar>'s meshes are drawn: shadows, a material hook, the outline width and the silhouette. Kept apart from
// the component so it can be tested without a renderer; <Avatar> calls it in a layout effect, before the frame that
// releases the render is drawn.
import * as THREE from 'three';

/** Change or replace one of the model's materials (MToon ones have `isMToonMaterial`; outline passes also have
 * `isOutline`). Return a material to use instead, or nothing to keep it (edits in place stay). */
export type AvatarMaterialHook = (m: THREE.Material, mesh: THREE.Mesh) => THREE.Material | void;

export type DressOptions = {
  outline: number;
  silhouette: string | null;
  castShadow: boolean;
  receiveShadow: boolean;
  materials?: AvatarMaterialHook;
};

type Mats = THREE.Material | THREE.Material[];

/** Apply the options to every mesh under root. The hook runs once per material, the first time; later calls only
 * change shadows, outline and silhouette. */
export const dressAvatar = (root: THREE.Object3D, o: DressOptions) => {
  root.traverse((obj) => {
    const mesh = obj as THREE.Mesh;
    if (!mesh.isMesh) return;
    mesh.castShadow = o.castShadow;
    mesh.receiveShadow = o.receiveShadow;
    let mats = mesh.userData.mvMats as Mats | undefined;
    if (!mats) {
      const own = mesh.material as Mats;
      const hook = o.materials;
      const swap = (m: THREE.Material) => (hook ? hook(m, mesh) ?? m : m);
      mats = Array.isArray(own) ? own.map(swap) : swap(own);
      mesh.userData.mvMats = mats;
    }
    for (const m of Array.isArray(mats) ? mats : [mats]) {
      const toon = m as THREE.Material & { outlineWidthFactor?: number; userData: { mvOutline?: number } };
      if (typeof toon.outlineWidthFactor === 'number') {
        toon.userData.mvOutline ??= toon.outlineWidthFactor;
        toon.outlineWidthFactor = toon.userData.mvOutline * o.outline;
      }
    }
    if (o.silhouette) {
      const flat = (mesh.userData.mvFlat ??= new THREE.MeshBasicMaterial()) as THREE.MeshBasicMaterial;
      flat.color.set(o.silhouette);
      mesh.material = Array.isArray(mats) ? mats.map(() => flat) : flat;
    } else {
      mesh.material = mats;
    }
  });
};
