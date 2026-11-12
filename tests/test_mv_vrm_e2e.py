"""The vrm character engine on the real, installed engine: the bake-off's vrm starter (two VRoid samples) renders,
and a frame rendered alone matches the same frame reached in sequence (spring bones replay deterministically).
Skipped when the engine or the avatars are not installed (music-video doctor installs both)."""
import shutil
import subprocess

import numpy as np
import pytest
from PIL import Image

from musicvideo import avatars, studio
from musicvideo.cli import main
from musicvideo.errors import MVError

pytestmark = pytest.mark.studio
FRAME = 45


@pytest.fixture
def vrm_video(mv_ws, monkeypatch):
    monkeypatch.delenv("MV_INSTALL_DIR")  # the real engine and avatars (work and results stay in tmp)
    try:
        studio.ensure_ready()
    except MVError:
        pytest.skip("run music-video doctor first")
    if any(avatars.state(a) != "ok" for a in avatars.AVATARS):
        pytest.skip("the character avatars are not installed: run music-video avatars install")
    assert main(["new-video", "vrm-check"]) == 0
    pub = mv_ws.work_for("vrm-check") / "public"
    pub.mkdir(parents=True)
    for name in ("timing.json", "analysis.json"):
        shutil.copy(studio.PLUGIN_STUDIO / "fixture" / "song" / name, pub / name)
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", "8",
                    str(pub / "song.mp3")], check=True)
    assert main(["bakeoff", "new", "vrm-check", "--engines", "vrm", "--from", "0"]) == 0
    return mv_ws


def _png(path):
    return np.asarray(Image.open(path).convert("RGB"), dtype=np.float64)


def _psnr(a, b):
    mse = float(np.mean((a - b) ** 2))
    return float("inf") if mse == 0 else 10 * np.log10(255.0 ** 2 / mse)


def test_vrm_bakeoff_renders_two_characters(vrm_video, tmp_path):
    out = tmp_path / "vrm.png"
    assert main(["typecheck", "vrm-check"]) == 0
    assert main(["still", "vrm-check", "vrm-check-bakeoff-vrm", str(out), f"--frame={FRAME}"]) == 0
    img = _png(out)
    assert out.stat().st_size > 50_000
    # Characters in front of a sky and a roof: far from one flat colour.
    assert img.std() > 20


def test_seeked_frame_matches_sequential(vrm_video, tmp_path):
    seq = tmp_path / "seq"
    assert main(["render", "vrm-check", "vrm-check-bakeoff-vrm", str(seq), "--sequence", "--image-format=png",
                 f"--frames=0-{FRAME}", "--concurrency=1"]) == 0
    frames = sorted(seq.glob("*.png"))
    assert len(frames) == FRAME + 1
    alone = tmp_path / "alone.png"
    assert main(["still", "vrm-check", "vrm-check-bakeoff-vrm", str(alone), f"--frame={FRAME}"]) == 0
    assert _psnr(_png(frames[-1]), _png(alone)) >= 60
