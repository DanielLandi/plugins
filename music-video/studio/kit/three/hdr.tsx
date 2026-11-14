// HDR skies: an equirectangular .hdr (Radiance) or .exr image as the scene's background and the light it reflects
// (image-based lighting). Import the file from the video's folder, it is bundled as a URL like a model:
//   import sky from './textures/kloofendal_2k.hdr';
//   <HdrSky url={sky} />
// Poly Haven (polyhaven.com) has CC0 HDRIs; list them in the video's SOURCES.md. 1k–2k is plenty for lighting; the
// background needs 4k only when it is seen sharp behind a long lens. Under 64 px wide, three's PMREM (the blurred
// copies standard materials sample) is empty and the sky gives no light.
import { useThree } from '@react-three/fiber';
import React, { useEffect, useLayoutEffect, useState } from 'react';
import { cancelRender, delayRender } from 'remotion';
import * as THREE from 'three';
import { EXRLoader } from 'three/examples/jsm/loaders/EXRLoader.js';
import { HDRLoader } from 'three/examples/jsm/loaders/HDRLoader.js';
import { releaseWhenDrawn } from './settle';

export type HdrFormat = 'hdr' | 'exr';

/** The file's format, from its URL (bundled names keep their extension) or as given. */
export const hdrFormat = (url: string, format?: HdrFormat): HdrFormat => {
  if (format) return format;
  const ext = /\.(hdr|exr)(?:[?#].*)?$/i.exec(url)?.[1]?.toLowerCase();
  if (ext === 'hdr' || ext === 'exr') return ext;
  throw new Error(`${url} is not an .hdr or .exr file (pass format="hdr" or "exr" if it is one)`);
};

const cache = new Map<string, Promise<THREE.DataTexture>>();

/** Loads an HDR or EXR image once per bundle (every caller of the same URL shares it), ready as an equirectangular
 * background or environment. HDRLoader is three's new name for RGBELoader. */
export const loadHdr = (url: string, format?: HdrFormat): Promise<THREE.DataTexture> => {
  const f = hdrFormat(url, format);
  const key = `${f}:${url}`;
  let p = cache.get(key);
  if (!p) {
    const loader = f === 'exr' ? new EXRLoader() : new HDRLoader();
    p = loader.loadAsync(url).then((tex) => {
      tex.mapping = THREE.EquirectangularReflectionMapping;
      return tex;
    });
    cache.set(key, p);
  }
  return p;
};

/** The loaded texture, or null until it is in. (`<HdrSky>` holds the frame until it is drawn.) */
export const useHdr = (url: string, format?: HdrFormat): THREE.DataTexture | null => {
  const [tex, setTex] = useState<THREE.DataTexture | null>(null);
  useEffect(() => {
    let live = true;
    loadHdr(url, format)
      .then((t) => live && setTex(t))
      .catch((e) => cancelRender(new Error(`HDR ${url} did not load (${e instanceof Error ? e.message : e})`)));
    return () => {
      live = false;
    };
  }, [url, format]);
  return tex;
};

export type HdrSkyProps = {
  /** The imported .hdr or .exr file. */
  url: string;
  format?: HdrFormat;
  /** Show it behind everything (default true). False: it only lights the scene (keep a SkyDome or a colour). */
  background?: boolean;
  /** Light and reflect it on standard and physical materials (default true). */
  environment?: boolean;
  /** Brightness of the background as seen, and of the light it gives (1 = as captured). */
  backgroundIntensity?: number;
  environmentIntensity?: number;
  /** Blur the background (0–1), e.g. for a shallow-focus look; the lighting is unaffected. */
  blur?: number;
  /** Turn the sky about y (radians) to put its sun where the shot wants it. Background and light turn together. */
  rotation?: number;
};

/**
 * An HDR image as the scene's sky and light. Holds the render until the file is loaded and drawn, like `<Model>`.
 * Every value is a plain prop, so a scene can animate intensity or rotation per frame.
 */
export const HdrSky: React.FC<HdrSkyProps> = ({
  url, format, background = true, environment = true, backgroundIntensity = 1, environmentIntensity = 1, blur = 0, rotation = 0,
}) => {
  const tex = useHdr(url, format);
  const [handle] = useState(() => delayRender(`Loading HDR ${url}`));
  const scene = useThree((s) => s.scene);
  const advance = useThree((s) => s.advance);
  const gl = useThree((s) => s.gl);

  // Put the sky in (and give the scene back what it had when this unmounts).
  useLayoutEffect(() => {
    if (!tex) return;
    const before = { bg: scene.background, env: scene.environment };
    if (background) scene.background = tex;
    if (environment) scene.environment = tex;
    return () => {
      if (background && scene.background === tex) scene.background = before.bg;
      if (environment && scene.environment === tex) scene.environment = before.env;
    };
  }, [tex, scene, background, environment]);

  useLayoutEffect(() => {
    scene.backgroundIntensity = backgroundIntensity;
    scene.environmentIntensity = environmentIntensity;
    scene.backgroundBlurriness = blur;
    scene.backgroundRotation.set(0, rotation, 0);
    scene.environmentRotation.set(0, rotation, 0);
  }, [scene, backgroundIntensity, environmentIntensity, blur, rotation]);

  useEffect(() => {
    if (!tex) return;
    releaseWhenDrawn(handle, advance, gl);
  }, [tex, handle, advance, gl]);

  return null;
};
