import * as THREE from 'three';
import { describe, expect, it } from 'vitest';
import { dressAvatar } from './dress';

/** A stand-in for a VRM scene: a skinned body with a toon material and its outline pass, and a plain mesh. */
const model = () => {
  const root = new THREE.Group();
  const toon = Object.assign(new THREE.MeshBasicMaterial(), { outlineWidthFactor: 0.01, isMToonMaterial: true });
  const outline = Object.assign(new THREE.MeshBasicMaterial(), { outlineWidthFactor: 0.01, isMToonMaterial: true, isOutline: true });
  const body = new THREE.Mesh(new THREE.BufferGeometry(), [toon, outline]);
  const hair = new THREE.Mesh(new THREE.BufferGeometry(), new THREE.MeshBasicMaterial());
  root.add(body, hair);
  return { root, body, hair, toon, outline };
};
const base = { outline: 1, silhouette: null, castShadow: false, receiveShadow: false };

describe('dressAvatar', () => {
  it('switches shadows on and off for every mesh', () => {
    const m = model();
    dressAvatar(m.root, { ...base, castShadow: true, receiveShadow: true });
    expect([m.body.castShadow, m.body.receiveShadow, m.hair.castShadow, m.hair.receiveShadow]).toEqual([true, true, true, true]);
    dressAvatar(m.root, base);
    expect([m.body.castShadow, m.hair.receiveShadow]).toEqual([false, false]);
  });

  it('swaps materials through the hook once per material, keeping arrays as arrays', () => {
    const m = model();
    let calls = 0;
    const lit = new THREE.MeshStandardMaterial();
    const hidden = new THREE.MeshBasicMaterial({ visible: false });
    const materials = (mat: THREE.Material, mesh: THREE.Mesh) => {
      calls++;
      expect(mesh.isMesh).toBe(true);
      const t = mat as THREE.Material & { isMToonMaterial?: boolean; isOutline?: boolean };
      if (t.isOutline) return hidden;
      if (t.isMToonMaterial) return lit;
      return undefined; // keep it
    };
    dressAvatar(m.root, { ...base, materials });
    expect(m.body.material).toEqual([lit, hidden]);
    expect(m.hair.material).toBeInstanceOf(THREE.MeshBasicMaterial);
    expect(calls).toBe(3);
    // Dressing again (an outline or a shadow change on a later frame) never runs the hook again.
    dressAvatar(m.root, { ...base, outline: 2, castShadow: true, materials });
    expect(calls).toBe(3);
    expect(m.body.material).toEqual([lit, hidden]);
  });

  it('a hook that edits a material in place and returns nothing keeps the edit', () => {
    const m = model();
    dressAvatar(m.root, { ...base, materials: (mat) => { (mat as THREE.MeshBasicMaterial).color.set('#ff0000'); } });
    expect((m.hair.material as THREE.MeshBasicMaterial).color.getHexString()).toBe('ff0000');
  });

  it('still scales the outline and paints a silhouette over the hooked materials, and gives them back', () => {
    const m = model();
    dressAvatar(m.root, { ...base, outline: 2 });
    expect((m.toon as unknown as { outlineWidthFactor: number }).outlineWidthFactor).toBeCloseTo(0.02, 12);
    dressAvatar(m.root, { ...base, outline: 1, silhouette: '#000000' });
    expect((m.toon as unknown as { outlineWidthFactor: number }).outlineWidthFactor).toBeCloseTo(0.01, 12);
    expect((m.hair.material as THREE.MeshBasicMaterial).color.getHexString()).toBe('000000');
    dressAvatar(m.root, base);
    expect(m.body.material).toEqual([m.toon, m.outline]);
  });
});
