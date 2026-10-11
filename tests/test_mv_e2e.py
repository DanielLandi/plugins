import shutil
import subprocess

import pytest

from musicvideo import studio
from musicvideo.cli import main

pytestmark = pytest.mark.studio


@pytest.fixture
def smoke_video(mv_ws, monkeypatch):
    """A fresh workspace video (the template) with the fixture song, rendered by the real, installed engine."""
    monkeypatch.delenv("MV_INSTALL_DIR")  # use the real, installed engine (work and results stay in tmp)
    if not studio.is_installed(studio.runtime_dir()):
        pytest.skip("run music-video doctor first")
    assert main(["new-video", "smoke-test"]) == 0
    pub = mv_ws.work_for("smoke-test") / "public"
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
    (smoke_video.work_for("smoke-test") / "public" / "timing.json").unlink()
    out = tmp_path / "instrumental.png"
    assert main(["still", "smoke-test", "smoke-test-full", str(out), "--frame=30"]) == 0
    assert out.stat().st_size > 10_000


def test_web_builds_a_page_and_rebuilds_it(smoke_video, tmp_path):
    out = tmp_path / "page"
    assert main(["web", "smoke-test", "--out", str(out), "--title", "Smoke Test", "--background", "#c9d3e6"]) == 0
    html = (out / "index.html").read_text(encoding="utf-8")
    assert "<title>Smoke Test</title>" in html and "%MV_" not in html
    # The page colour comes from the build; the bundled stylesheet (linked after it) must not override it.
    assert "--background: #c9d3e6" in html
    css = "".join(p.read_text(encoding="utf-8") for p in (out / "assets").glob("*.css"))
    assert "--background:#" not in css.replace(" ", "")
    assert list((out / "assets").glob("*.js"))
    assert main(["web", "smoke-test", "--out", str(out), "--title", "Again"]) == 0  # its own build: replaced
    assert "<title>Again</title>" in (out / "index.html").read_text(encoding="utf-8")
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (foreign / "keep.txt").write_text("mine", encoding="utf-8")
    assert main(["web", "smoke-test", "--out", str(foreign)]) != 0
    assert (foreign / "keep.txt").read_text(encoding="utf-8") == "mine"


def test_a_video_can_self_host_its_page_fonts_and_styles(smoke_video, tmp_path):
    web = smoke_video.video_dir("smoke-test") / "web"
    (web / "fonts").mkdir(parents=True)
    (web / "styles.css").write_text(".self-hosted-marker { color: #123456; }\n", encoding="utf-8")
    (web / "OFL-Test.txt").write_text("licence text", encoding="utf-8")
    # The page must use the video's stand-in, not fetch the font from Google.
    (web / "fonts" / "Inter.ts").write_text(
        "export const loadFont = () => {\n  (globalThis as Record<string, unknown>).selfHosted = 'SelfHostedInter';\n"
        "  return { fontFamily: 'SelfHostedInter' };\n};\n", encoding="utf-8")
    entry = smoke_video.video_dir("smoke-test") / "web.tsx"
    entry.write_text("import { loadFont } from '@remotion/google-fonts/Inter';\nloadFont();\n"
                     + entry.read_text(encoding="utf-8"), encoding="utf-8")
    out = tmp_path / "page"
    assert main(["web", "smoke-test", "--out", str(out)]) == 0
    css = "".join(p.read_text(encoding="utf-8") for p in (out / "assets").glob("*.css"))
    js = "".join(p.read_text(encoding="utf-8") for p in (out / "assets").glob("*.js"))
    assert "#123456" in css and "SelfHostedInter" in js and "fonts.gstatic.com" not in js
    assert (out / "OFL-Test.txt").read_text(encoding="utf-8") == "licence text"


def test_the_page_music_is_a_hashed_asset(smoke_video, tmp_path):
    # Everything under assets/ is content-hashed, so a host may cache it forever: the audio loop belongs there.
    loop = smoke_video.work_for("rain-song") / "loop"
    loop.mkdir(parents=True)
    (loop / "loop.m4a").write_bytes(b"\0" * 4096)
    (loop / "loop.json").write_text('{"loopSamples": 441000, "marginSamples": 44100, "rate": 44100}', encoding="utf-8")
    out = tmp_path / "page"
    assert main(["web", "smoke-test", "--out", str(out), "--audio-loop", "rain-song"]) == 0
    audio = list((out / "assets").glob("loop-*.m4a"))
    assert len(audio) == 1 and not list(out.glob("*.m4a"))
    score = next((out / "assets").glob("score-*.json")).read_text(encoding="utf-8")
    assert f'"file":"assets/{audio[0].name}"' in score
