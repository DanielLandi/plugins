import json
from pathlib import Path

import pytest

from musicvideo import studio
from musicvideo.cli import main


def test_new_video(mv_ws):
    dest = studio.new_video(mv_ws, "night-drive")
    assert dest == mv_ws.video_dir("night-drive")
    index = (dest / "index.tsx").read_text(encoding="utf-8")
    assert "__ID__" not in index and "night-drive" in index and "@mv/kit" in index
    assert mv_ws.work_for("night-drive").is_dir()
    with pytest.raises(Exception, match="already exists"):
        studio.new_video(mv_ws, "night-drive")
    with pytest.raises(Exception, match="lowercase"):
        studio.new_video(mv_ws, "Night Drive")


def test_cli_new_video(mv_ws, capsys):
    assert main(["new-video", "night-drive"]) == 0
    assert capsys.readouterr().out.strip() == str(mv_ws.video_dir("night-drive"))


def test_typecheck_config_links_the_video_into_the_engine(mv_ws, tmp_path):
    studio.new_video(mv_ws, "night-drive")
    (mv_ws.work_for("night-drive") / "public").mkdir(parents=True)
    (mv_ws.work_for("night-drive") / "public" / "timing.json").write_text("{}", encoding="utf-8")
    (mv_ws.work_for("night-drive") / "public" / "analysis.json").write_text("{}", encoding="utf-8")
    ctx = studio.video_context(mv_ws, "night-drive")
    rt = tmp_path / "rt"
    cfg_path = studio.typecheck_config(rt, ctx)
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    # The video is linked inside the engine folder, so packages (and their `exports` subpaths, such as
    # @remotion/google-fonts/<Family>) resolve from the engine's node_modules like any engine file.
    link = cfg_path.parent / "src"
    assert link.resolve() == ctx.dir.resolve()
    assert cfg["compilerOptions"]["preserveSymlinks"] is True
    assert cfg["include"][:2] == ["src/**/*.ts", "src/**/*.tsx"]
    assert cfg["compilerOptions"]["paths"]["@mv/kit/*"] == [f"{rt.as_posix()}/kit/*"]
    assert "*" not in cfg["compilerOptions"]["paths"]
    studio.typecheck_config(rt, ctx)  # again: the existing link is reused


@pytest.fixture
def fake_node(mv_ws, monkeypatch, tmp_path):
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
    (pub / "timing.json").write_text("{}", encoding="utf-8")
    (pub / "analysis.json").write_text("{}", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    return calls, rt, pub


def test_render_resolves_output_and_builds_args(fake_node, tmp_path):
    calls, rt, pub = fake_node
    assert main(["render", "night-drive", "night-drive-full", "out.mp4", "--muted"]) == 0
    cmd, cwd, env = calls[0]
    assert cmd[:3] == ["node", str(rt / "node_modules/@remotion/cli/remotion-cli.js"), "render"]
    assert cmd[3] == str(rt / ".entries" / "night-drive" / "index.ts")
    assert cmd[4:6] == ["night-drive-full", str((tmp_path / "out.mp4").resolve())]
    assert "--muted" in cmd and f"--public-dir={pub}" in cmd and "--gl=angle" in cmd
    assert cwd == rt and env["MV_VIDEO"] == "night-drive"


def test_studio_has_no_gl_flag(fake_node):
    calls, rt, pub = fake_node
    assert main(["studio", "night-drive"]) == 0
    assert not any(a.startswith("--gl=") for a in calls[0][0])


def test_render_needs_composition_and_output(fake_node, capsys):
    assert main(["render", "night-drive", "night-drive-full"]) == 2
    assert "usage: music-video render" in capsys.readouterr().err


def test_tools_pass_the_id_first(fake_node):
    calls, rt, pub = fake_node
    assert main(["stills", "night-drive", "night-drive-full", "out", "1,2", "--seconds"]) == 0
    assert main(["blur", "night-drive", "night-drive-full", "b.mp4", "--samples=32"]) == 0
    assert main(["board", "night-drive"]) == 0
    tsx = ["node", str(rt / "node_modules/tsx/dist/cli.mjs")]
    assert [c[0][:4] for c in calls] == [[*tsx, "tools/stills.ts", "night-drive"], [*tsx, "tools/blur.ts", "night-drive"],
                                         [*tsx, "tools/board.ts", "night-drive"]]
    assert calls[0][0][4:] == ["night-drive-full", str(Path("out").resolve()), "1,2", "--seconds"]


def test_typecheck_runs_tsc_on_generated_config(fake_node):
    calls, rt, pub = fake_node
    assert main(["typecheck", "night-drive"]) == 0
    cmd = calls[0][0]
    assert cmd[:4] == ["node", str(rt / "node_modules/typescript/bin/tsc"), "-p", str(rt / ".entries" / "night-drive" / "tsconfig.json")]


def test_stills_and_blur_outputs_resolve_against_the_callers_folder(fake_node, tmp_path):
    calls, rt, pub = fake_node
    assert main(["stills", "night-drive", "--seconds", "night-drive-full", "out stills", "1,2"]) == 0
    assert main(["blur", "night-drive", "night-drive-full", "b.mp4", "--samples=32"]) == 0
    stills, blur = calls[0][0], calls[1][0]
    assert stills[4:] == ["--seconds", "night-drive-full", str((tmp_path / "out stills").resolve()), "1,2"]
    assert blur[4:] == ["night-drive-full", str((tmp_path / "b.mp4").resolve()), "--samples=32"]
