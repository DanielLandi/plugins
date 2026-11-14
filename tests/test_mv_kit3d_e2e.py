"""The 3D kit's scene helpers on the real, installed engine (issue #36): an imported .hdr sky bundles and shows, an
<Avatar>'s material hook and shadows are already on the first released frame (a still), two-bone IK puts a real
VRM 0.x foot on its world target, and a character riding a path with air drag on its hair renders the same frame
alone and in sequence. Skipped when the engine or the avatars are not installed (music-video doctor installs both)."""
import shutil
import struct
import subprocess

import numpy as np
import pytest
from PIL import Image

from musicvideo import avatars, studio
from musicvideo.cli import main
from musicvideo.errors import MVError

pytestmark = pytest.mark.studio
FRAME = 30
SKY = (0.05, 0.6, 0.15)  # linear RGB of the test sky: plainly green on screen

# The scene: shared by two takes that differ only in castShadow (the raw take is the shadowless twin).
SCENE = """import { useFrame } from '@react-three/fiber';
import React, { useCallback } from 'react';
import { AbsoluteFill, cancelRender } from 'remotion';
import * as THREE from 'three';
import { useSongTime, type BakeoffProps } from '@mv/kit';
import {
  Avatar, CameraRig, HdrSky, makePath, poses, ride, Stage, withIK, type AvatarState, type HumanRig, type Vec3,
} from '@mv/kit/three';
import sample from '@mv/avatars/vroid-sample-1.vrm';
import sky from './sky.hdr';

const MAGENTA = new THREE.MeshBasicMaterial({ color: '#ff00ff', toneMapped: false });
let skeleton: THREE.Skeleton | null = null;
/** Every material becomes flat magenta; the skinned body's skeleton is kept for the IK check. */
const paint = (_m: THREE.Material, mesh: THREE.Mesh) => {
  const s = (mesh as THREE.SkinnedMesh).skeleton;
  if (s) skeleton = s;
  return MAGENTA;
};

const PATH = makePath([[-1.5, 0, 0.3], [0, 0, 0], [1.5, 0, 0.3]]);
const turn = (yaw: number, v: Vec3): Vec3 => [v[0] * Math.cos(yaw) + v[2] * Math.sin(yaw), v[1], -v[0] * Math.sin(yaw) + v[2] * Math.cos(yaw)];
const add = (a: Vec3, b: Vec3): Vec3 => [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
/** Where the left ankle must be at t: a step ahead of the hips, just above the floor. */
const footTarget = (t: number): Vec3 => {
  const p = ride(PATH, t, 1);
  return add(p.pos, turn(p.yaw, [0.1, 0.12, 0.22]));
};

const drive = (t: number, rig: HumanRig): AvatarState => {
  const p = ride(PATH, t, 1);
  const base: AvatarState = { pos: p.pos, yaw: p.yaw, pose: poses.relax, hips: [0, -0.08, 0], expr: {} };
  return withIK(rig, base, { leftLeg: { target: footTarget(t), pole: turn(p.yaw, [0, 0, 1]) } });
};

/** Fails the render when the model's real left ankle is not where IK was asked to put it. */
const FootCheck: React.FC = () => {
  const t = useSongTime();
  useFrame(() => {
    if (!skeleton) return;
    const bone = skeleton.bones.find((b) => b.name === 'J_Bip_L_Foot');
    if (!bone) return cancelRender(new Error('no J_Bip_L_Foot bone in the skeleton'));
    bone.updateWorldMatrix(true, false);
    const at = new THREE.Vector3().setFromMatrixPosition(bone.matrixWorld);
    const miss = at.distanceTo(new THREE.Vector3(...footTarget(t)));
    if (miss > 0.015) cancelRender(new Error(`IK foot is ${miss.toFixed(3)} m from its target at t=${t}`));
  });
  return null;
};

export const Kit36: React.FC<BakeoffProps & { shadow: boolean }> = ({ from, shadow }) => {
  const d = useCallback(drive, []);
  return (
    <AbsoluteFill>
      <Stage fov={45}>
        <CameraRig keys={[{ t: 0, pos: [0, 1.4, 5], look: [0, 0.8, 0], fov: 45 }]} fov={45} />
        <HdrSky url={sky} />
        <directionalLight position={[-3, 6, 3]} intensity={3} castShadow shadow-mapSize={[2048, 2048]} />
        <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
          <planeGeometry args={[12, 12]} />
          <meshStandardMaterial color="#ffffff" roughness={1} />
        </mesh>
        <Avatar url={sample} drive={d} from={from} materials={paint} castShadow={shadow} airDrag={0.3} />
        <FootCheck />
      </Stage>
    </AbsoluteFill>
  );
};
"""
TAKE = """import React from 'react';
import type { BakeoffProps } from '@mv/kit';
import { Kit36 } from '../kit36';

export const Bakeoff: React.FC<BakeoffProps> = (p) => <Kit36 {...p} shadow={%s} />;
"""


def _rgbe(rgb):
    """One linear RGB colour as a Radiance RGBE pixel."""
    v = max(rgb)
    m, e = np.frexp(v)
    scale = m * 256.0 / v
    return bytes([int(c * scale) for c in rgb] + [int(e) + 128])


def write_hdr(path, rgb, w=256, h=128):
    """A flat-coloured equirectangular .hdr (uncompressed scanlines). At least 64 px wide: three's PMREM gives no
    light from a smaller one."""
    head = f"#?RADIANCE\nFORMAT=32-bit_rle_rgbe\n\n-Y {h} +X {w}\n".encode("ascii")
    path.write_bytes(head + _rgbe(rgb) * (w * h))


@pytest.fixture
def kit_video(mv_ws, monkeypatch):
    monkeypatch.delenv("MV_INSTALL_DIR")  # the real engine and avatars (work and results stay in tmp)
    try:
        studio.ensure_ready()
    except MVError:
        pytest.skip("run music-video doctor first")
    if avatars.state(avatars.AVATARS[0]) != "ok":
        pytest.skip("the character avatars are not installed: run music-video avatars install")
    assert main(["new-video", "kit-check"]) == 0
    pub = mv_ws.work_for("kit-check") / "public"
    pub.mkdir(parents=True)
    for name in ("timing.json", "analysis.json"):
        shutil.copy(studio.PLUGIN_STUDIO / "fixture" / "song" / name, pub / name)
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", "8",
                    str(pub / "song.mp3")], check=True)
    assert main(["bakeoff", "new", "kit-check", "--engines", "vrm", "--from", "0"]) == 0
    vdir = mv_ws.video_dir("kit-check")
    write_hdr(vdir / "sky.hdr", SKY)
    (vdir / "kit36.tsx").write_text(SCENE, encoding="utf-8")
    (vdir / "bakeoff" / "vrm.tsx").write_text(TAKE % "true", encoding="utf-8")
    (vdir / "bakeoff" / "raw.tsx").write_text(TAKE % "false", encoding="utf-8")
    return mv_ws


def _png(path):
    return np.asarray(Image.open(path).convert("RGB"), dtype=np.float64)


def _psnr(a, b):
    mse = float(np.mean((a - b) ** 2))
    return float("inf") if mse == 0 else 10 * np.log10(255.0 ** 2 / mse)


def test_rgbe_pixel_round_trips():
    r, g, b, e = _rgbe(SKY)
    back = [(c + 0.5) / 256 * 2.0 ** (e - 128) for c in (r, g, b)]
    assert np.allclose(back, SKY, atol=0.01)


def test_hdr_sky_material_hook_shadows_and_ik_on_the_first_released_frame(kit_video, tmp_path):
    assert main(["typecheck", "kit-check"]) == 0
    lit, unlit = tmp_path / "shadow.png", tmp_path / "noshadow.png"
    # A still is the first frame a fresh tab releases: everything below must already be there.
    assert main(["still", "kit-check", "kit-check-bakeoff-vrm", str(lit), f"--frame={FRAME}"]) == 0
    assert main(["still", "kit-check", "kit-check-bakeoff-raw", str(unlit), f"--frame={FRAME}"]) == 0
    a, b = _png(lit), _png(unlit)
    # The imported .hdr is the background: the top of the frame (sky above the horizon) is its green.
    top = a[: a.shape[0] // 10].reshape(-1, 3).mean(axis=0)
    assert top[1] > top[0] + 60 and top[1] > top[2] + 60, top
    # The material hook painted the character flat magenta.
    magenta = (a[..., 0] > 200) & (a[..., 1] < 60) & (a[..., 2] > 200)
    assert magenta.sum() > 3000, magenta.sum()
    # castShadow: with it, part of the floor is much darker than in the shadowless twin.
    body = magenta | ((b[..., 0] > 200) & (b[..., 1] < 60) & (b[..., 2] > 200))
    shade = ((b - a).mean(axis=2) > 25) & ~body
    assert shade.sum() > 1500, shade.sum()
    # The .hdr also lights the scene: in the shadow only the sky's light is left, and it is green.
    lit_by_sky = a[shade].mean(axis=0)
    assert lit_by_sky[1] > lit_by_sky[0] + 40 and lit_by_sky[1] > lit_by_sky[2] + 40, lit_by_sky


def test_riding_with_air_drag_seeked_frame_matches_sequential(kit_video, tmp_path):
    seq = tmp_path / "seq"
    assert main(["render", "kit-check", "kit-check-bakeoff-vrm", str(seq), "--sequence", "--image-format=png",
                 f"--frames=0-{FRAME}", "--concurrency=1"]) == 0
    frames = sorted(seq.glob("*.png"))
    assert len(frames) == FRAME + 1
    alone = tmp_path / "alone.png"
    assert main(["still", "kit-check", "kit-check-bakeoff-vrm", str(alone), f"--frame={FRAME}"]) == 0
    assert _psnr(_png(frames[-1]), _png(alone)) >= 60
