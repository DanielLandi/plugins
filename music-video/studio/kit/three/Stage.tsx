import { ThreeCanvas } from '@remotion/three';
import React from 'react';
import { useVideoConfig } from 'remotion';
import * as THREE from 'three';
import { SongProvider, useSongData } from '../SongContext';

/**
 * A full-frame 3D stage. ThreeCanvas runs its own React renderer, so the song context is provided again inside it:
 * every kit hook (useSongTime, useBeat, useSongData) works in 3D children.
 */
export const Stage: React.FC<{
  children: React.ReactNode;
  background?: THREE.ColorRepresentation;
  fov?: number;
  exposure?: number;
  shadows?: boolean;
}> = ({ children, background = '#000000', fov = 50, exposure = 1, shadows = true }) => {
  const { width, height } = useVideoConfig();
  const data = useSongData();
  return (
    <ThreeCanvas
      width={width}
      height={height}
      shadows={shadows}
      dpr={1}
      camera={{ fov, near: 0.1, far: 4000, position: [0, 5, 20] }}
      // Renderer settings go in `gl`, which is applied before the scene renders (and again only when they change), so
      // a scene that sets gl.toneMappingExposure itself keeps it, on the first frame too. (onCreated runs after the
      // scene's first render and would overwrite it: #9.)
      gl={{
        antialias: true,
        preserveDrawingBuffer: true,
        toneMapping: THREE.ACESFilmicToneMapping,
        toneMappingExposure: exposure,
        outputColorSpace: THREE.SRGBColorSpace,
      }}
      style={{ backgroundColor: new THREE.Color(background).getStyle() }}
    >
      <color attach="background" args={[background]} />
      <SongProvider data={data}>{children}</SongProvider>
    </ThreeCanvas>
  );
};
