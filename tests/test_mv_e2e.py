import shutil
import subprocess

import pytest

from musicvideo import studio
from musicvideo.cli import main

pytestmark = pytest.mark.studio


@pytest.fixture
def smoke_video(mv_ws, monkeypatch):
    """A fresh workspace video (the template) with the fixture song, rendered by the real, installed engine."""
    monkeypatch.delenv("MV_CACHE_DIR")
    if not studio.is_installed(studio.runtime_dir()):
        pytest.skip("run music-video doctor first")
    assert main(["new-video", "smoke-test"]) == 0
    pub = mv_ws.media_for("smoke-test") / "public"
    pub.mkdir(parents=True)
    for name in ("timing.json", "analysis.json"):
        shutil.copy(studio.PLUGIN_STUDIO / "fixture" / "song" / name, pub / name)
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", "8",
                    str(pub / "song.mp3")], check=True)
    return mv_ws


def test_board_runs_on_a_workspace_video(smoke_video):
    # The board imports the video's scenes.ts in Node: its packages and @mv/kit must resolve from the engine.
    assert main(["board", "smoke-test"]) == 0


def test_fresh_workspace_renders_a_still(smoke_video, tmp_path):
    out = tmp_path / "still.png"
    assert main(["typecheck", "smoke-test"]) == 0
    assert main(["still", "smoke-test", "smoke-test-full", str(out), "--frame=30"]) == 0
    assert out.stat().st_size > 10_000


def test_an_instrumental_renders_without_timing(smoke_video, write_spec, tmp_path):
    from mv_fixtures import valid_spec
    from musicvideo.spec import save_spec
    save_spec(smoke_video.specs_dir / "smoke-test.yaml", valid_spec(
        id="smoke-test", suno={"model": "v6", "styles": "instrumental", "instrumental": True, "lyrics": ""}))
    (smoke_video.media_for("smoke-test") / "public" / "timing.json").unlink()
    out = tmp_path / "instrumental.png"
    assert main(["still", "smoke-test", "smoke-test-full", str(out), "--frame=30"]) == 0
    assert out.stat().st_size > 10_000
