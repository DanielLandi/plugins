"""The 3D Stage on the real, installed engine (#9): a scene that sets the renderer's exposure itself keeps it on the
first frame a render tab draws (a still), instead of the Stage's default overwriting it after that frame's render.
Skipped when the engine is not installed (music-video doctor installs it)."""
import shutil
import subprocess

import numpy as np
import pytest
from PIL import Image

from musicvideo import studio
from musicvideo.cli import main
from musicvideo.errors import MVError

pytestmark = pytest.mark.studio

INDEX = """import React from 'react';
import { Composition } from 'remotion';
import { useThree } from '@react-three/fiber';
import { songMetadata, SongProvider, type SongProps } from '@mv/kit';
import { Stage } from '@mv/kit/three';

// The scene sets the exposure itself, in its body, as a scene may.
const OwnExposure: React.FC = () => {
  const { gl } = useThree();
  gl.toneMappingExposure = 2.5;
  return null;
};

const Wall: React.FC = () => (
  <>
    <ambientLight intensity={1} />
    <mesh position={[0, 5, 0]}>
      <planeGeometry args={[80, 50]} />
      <meshStandardMaterial color="#606060" />
    </mesh>
  </>
);

const Body: React.FC<SongProps> = ({ data }) =>
  data ? <SongProvider data={data}><Stage><OwnExposure /><Wall /></Stage></SongProvider> : null;
const Prop: React.FC<SongProps> = ({ data }) =>
  data ? <SongProvider data={data}><Stage exposure={2.5}><Wall /></Stage></SongProvider> : null;

const common = { fps: 30, durationInFrames: 1, width: 640, height: 360, defaultProps: { data: null } as SongProps };

export const Compositions: React.FC = () => (
  <>
    <Composition id="exposure-body" component={Body} {...common} calculateMetadata={songMetadata<SongProps>()} />
    <Composition id="exposure-prop" component={Prop} {...common} calculateMetadata={songMetadata<SongProps>()} />
  </>
);
"""


@pytest.fixture
def exposure_video(mv_ws, monkeypatch):
    monkeypatch.delenv("MV_INSTALL_DIR")  # the real engine (work and results stay in tmp)
    try:
        studio.ensure_ready()
    except MVError:
        pytest.skip("run music-video doctor first")
    assert main(["new-video", "exposure-check"]) == 0
    pub = mv_ws.work_for("exposure-check") / "public"
    pub.mkdir(parents=True)
    for name in ("timing.json", "analysis.json"):
        shutil.copy(studio.PLUGIN_STUDIO / "fixture" / "song" / name, pub / name)
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", "8",
                    str(pub / "song.mp3")], check=True)
    (mv_ws.video_dir("exposure-check") / "index.tsx").write_text(INDEX, encoding="utf-8")
    return mv_ws


def _luma(path):
    return float(np.asarray(Image.open(path).convert("L"), dtype=np.float64).mean())


def test_a_scene_keeps_its_own_exposure_on_the_first_frame(exposure_video, tmp_path):
    body, prop = tmp_path / "body.png", tmp_path / "prop.png"
    assert main(["still", "exposure-check", "exposure-body", str(body), "--frame=0"]) == 0
    assert main(["still", "exposure-check", "exposure-prop", str(prop), "--frame=0"]) == 0
    assert _luma(prop) > 40  # the wall is lit, not black
    assert abs(_luma(body) - _luma(prop)) < 1.5, (_luma(body), _luma(prop))
