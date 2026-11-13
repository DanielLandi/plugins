"""The cartoon character engine on the real, installed engine: the bake-off's cartoon starter (two inked rubber-hose
characters on a rooftop) renders, and a frame rendered alone is pixel-identical to the same frame reached in sequence
(the rig, the boil and the springs are pure functions of time). Skipped when the engine is not installed (music-video
doctor installs it); needs no avatars."""
import shutil
import subprocess

import numpy as np
import pytest
from PIL import Image

from musicvideo import studio
from musicvideo.cli import main
from musicvideo.errors import MVError

pytestmark = pytest.mark.studio
FRAME = 75  # 2.5 s in: the plum has stopped short, the bean is about to turn


@pytest.fixture
def cartoon_video(mv_ws, monkeypatch):
    monkeypatch.delenv("MV_INSTALL_DIR")  # the real engine (work and results stay in tmp)
    try:
        studio.ensure_ready()
    except MVError:
        pytest.skip("run music-video doctor first")
    assert main(["new-video", "cartoon-check"]) == 0
    pub = mv_ws.work_for("cartoon-check") / "public"
    pub.mkdir(parents=True)
    for name in ("timing.json", "analysis.json"):
        shutil.copy(studio.PLUGIN_STUDIO / "fixture" / "song" / name, pub / name)
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", "8",
                    str(pub / "song.mp3")], check=True)
    assert main(["bakeoff", "new", "cartoon-check", "--engines", "cartoon", "--from", "0"]) == 0
    return mv_ws


def _png(path):
    return np.asarray(Image.open(path).convert("RGB"), dtype=np.int16)


def test_cartoon_bakeoff_renders_two_characters(cartoon_video, tmp_path):
    out = tmp_path / "cartoon.png"
    assert main(["typecheck", "cartoon-check"]) == 0
    assert main(["still", "cartoon-check", "cartoon-check-bakeoff-cartoon", str(out), f"--frame={FRAME}"]) == 0
    img = _png(out)
    assert out.stat().st_size > 50_000
    assert img.std() > 20  # two inked characters and a city at dusk: far from one flat colour
    # Ink: a good share of near-black pixels (the brush lines), as a drawn frame has.
    assert (img.max(axis=2) < 70).mean() > 0.01


def test_seeked_frame_equals_sequential(cartoon_video, tmp_path):
    seq = tmp_path / "seq"
    assert main(["render", "cartoon-check", "cartoon-check-bakeoff-cartoon", str(seq), "--sequence",
                 "--image-format=png", f"--frames=0-{FRAME}", "--concurrency=1"]) == 0
    frames = sorted(seq.glob("*.png"))
    assert len(frames) == FRAME + 1
    alone = tmp_path / "alone.png"
    assert main(["still", "cartoon-check", "cartoon-check-bakeoff-cartoon", str(alone), f"--frame={FRAME}"]) == 0
    assert np.array_equal(_png(frames[-1]), _png(alone))
