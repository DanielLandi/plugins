import json

import pytest

from musicvideo import studio
from musicvideo.cli import main
from musicvideo.errors import MVError


@pytest.fixture
def web_video(mv_ws, monkeypatch, tmp_path):
    calls = []
    rt = tmp_path / "rt"
    for script in studio.SCRIPTS.values():  # a fake engine with its tools' entry scripts
        (rt / script).parent.mkdir(parents=True, exist_ok=True)
        (rt / script).write_text("", encoding="utf-8")
    monkeypatch.setattr(studio, "ensure_ready", lambda: rt)
    monkeypatch.setattr(studio, "node", lambda: "node")
    monkeypatch.setattr(studio, "run_node", lambda cmd, cwd, env: calls.append((cmd, cwd, env)) or 0)
    studio.new_video(mv_ws, "night-drive")
    pub = mv_ws.work_for("night-drive") / "public"
    pub.mkdir(parents=True)
    for name in ("timing.json", "analysis.json"):
        (pub / name).write_text("{}", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    return calls, rt


def test_web_builds_into_the_results_folder(mv_ws, web_video):
    calls, rt = web_video
    assert main(["web", "night-drive", "--title", "Night Drive", "--background", "#101820"]) == 0
    cmd, cwd, env = calls[0]
    assert cmd[:4] == ["node", str(rt / "node_modules/tsx/dist/cli.mjs"), "tools/web.ts", "night-drive"]
    assert cmd[cmd.index("--out") + 1] == str(mv_ws.results_for("night-drive") / "web")
    assert cmd[cmd.index("--title") + 1] == "Night Drive" and cmd[cmd.index("--background") + 1] == "#101820"
    assert "--audio" not in cmd
    entry = rt / ".entries" / "night-drive" / "web.ts"
    assert env["MV_WEB_ENTRY"] == str(entry)
    # The file itself, extension included: a video may also have a web/ folder next to web.tsx.
    assert entry.read_text(encoding="utf-8").rstrip().endswith('/src/web.tsx";')


def test_web_with_an_audio_loop_needs_the_loop_first(mv_ws, web_video, capsys):
    calls, rt = web_video
    assert main(["web", "night-drive", "--audio-loop", "rain-song"]) == 2
    assert "music-video loop rain-song" in capsys.readouterr().err
    loop = mv_ws.work_for("rain-song") / "loop"
    loop.mkdir(parents=True)
    (loop / "loop.m4a").write_bytes(b"x")
    (loop / "loop.json").write_text("{}", encoding="utf-8")
    assert main(["web", "night-drive", "--audio-loop", "rain-song"]) == 0
    cmd = calls[0][0]
    assert cmd[cmd.index("--audio") + 1] == str(loop)


def test_a_video_without_a_web_entry_says_how_to_add_one(mv_ws, web_video, capsys):
    (mv_ws.video_dir("night-drive") / "web.tsx").unlink()
    assert main(["web", "night-drive"]) == 2
    err = capsys.readouterr().err
    assert "web.tsx" in err and "export const web" in err


def test_relative_out_resolves_against_the_caller(web_video, tmp_path):
    calls, rt = web_video
    assert main(["web", "night-drive", "--out", "site/page"]) == 0
    cmd = calls[0][0]
    assert cmd[cmd.index("--out") + 1] == str((tmp_path / "site" / "page").resolve())


def test_a_foreign_output_folder_is_refused_in_one_line(mv_ws, web_video, tmp_path, capsys):
    calls, rt = web_video
    foreign = tmp_path / "site"
    foreign.mkdir()
    (foreign / "keep.txt").write_text("mine", encoding="utf-8")
    assert main(["web", "night-drive", "--out", str(foreign)]) == 2
    err = capsys.readouterr().err.strip()
    assert err.startswith("error:") and "not a web build" in err and "\n" not in err
    assert calls == [] and (foreign / "keep.txt").is_file()
    a_file = tmp_path / "page.html"
    a_file.write_text("x", encoding="utf-8")
    assert main(["web", "night-drive", "--out", str(a_file)]) == 2
    assert "not a folder" in capsys.readouterr().err


def test_a_web_entry_without_the_export_is_named(mv_ws, web_video, capsys):
    (mv_ws.video_dir("night-drive") / "web.tsx").write_text("export const other = 1;\n", encoding="utf-8")
    assert main(["web", "night-drive"]) == 2
    assert "export const web" in capsys.readouterr().err
