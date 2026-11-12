import json
from pathlib import Path

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

    def ready(video_id=None, lane=None):  # as the real one, it takes the command's lease on the engine
        if video_id is not None:
            studio.take_lease(rt, video_id, lane)
        return rt
    monkeypatch.setattr(studio, "ensure_ready", ready)
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
    # The file itself, extension included (a video may also have a web/ folder next to web.tsx), re-exported with
    # `export *` so a missing `web` reaches the build's own one-line check instead of failing Node's import.
    text = entry.read_text(encoding="utf-8")
    assert text.startswith("export * from ") and text.rstrip().endswith('/src/web.tsx";')


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


@pytest.mark.parametrize("source", ["export async function web() {}\n", "export * from './scene';\n",
                                    "export class web {}\n", "const w = 1;\nexport { w as web };\n"])
def test_valid_ways_of_exporting_web_are_not_refused(mv_ws, web_video, source):
    calls, rt = web_video
    (mv_ws.video_dir("night-drive") / "web.tsx").write_text(source, encoding="utf-8")
    assert main(["web", "night-drive"]) == 0 and calls


def test_the_marker_is_the_build_tools_marker():
    # Python refuses foreign folders and the build writes the marker: they must agree, or every rebuild is refused.
    ts = (studio.PLUGIN_STUDIO / "tools" / "web-out.ts").read_text(encoding="utf-8")
    assert f"MARK = '{studio.WEB_MARK}'" in ts


def test_a_foreign_folder_with_a_binary_readme_is_refused_cleanly(mv_ws, web_video, tmp_path, capsys):
    foreign = tmp_path / "site"
    foreign.mkdir()
    (foreign / "README.md").write_bytes(b"\xff\xfe not utf-8")
    assert main(["web", "night-drive", "--out", str(foreign)]) == 2
    assert "not a web build" in capsys.readouterr().err


def test_a_command_holds_a_lease_while_it_runs(mv_ws, web_video, monkeypatch):
    calls, rt = web_video
    seen = []
    monkeypatch.setattr(studio, "run_node", lambda cmd, cwd, env: seen.append(studio.live_leases(rt)) or 0)
    assert main(["web", "night-drive"]) == 0
    assert len(seen[0]) == 1 and seen[0][0]["video"] == "night-drive"
    assert seen[0][0]["source"] == str(studio.PLUGIN_STUDIO)
    assert studio.live_leases(rt) == [] and not list((rt / studio.LEASES).iterdir())


def test_a_stopped_web_build_leaves_no_staging_folder(mv_ws, web_video, monkeypatch):
    # Ctrl-C stops node at once: web.ts's own `finally` never runs, so the folder is made and removed from here.
    import tempfile
    calls, rt = web_video
    seen = []

    def node_stopped(cmd, cwd, env):  # what tools/web.ts does, then the Ctrl-C
        stage = env.get("MV_WEB_STAGE") or tempfile.mkdtemp(prefix="web-data-", dir=Path(env["MV_WEB_ENTRY"]).parent)
        (Path(stage) / "score.json").write_text("{}", encoding="utf-8")
        seen.append(Path(stage))
        raise KeyboardInterrupt
    monkeypatch.setattr(studio, "run_node", node_stopped)
    with pytest.raises(KeyboardInterrupt):
        main(["web", "night-drive"])
    entry_dir = rt / ".entries" / "night-drive"
    assert seen[0].parent == entry_dir and seen[0].name.startswith("web-data-")
    assert not list(entry_dir.glob("web-data-*"))


def test_web_stages_song_data_per_run():
    # Two web builds at once (different videos) once shared <engine>/web/.data/score.json and swapped pages (#18).
    ts = (studio.PLUGIN_STUDIO / "tools" / "web.ts").read_text(encoding="utf-8")
    page = (studio.PLUGIN_STUDIO / "web" / "main.tsx").read_text(encoding="utf-8")
    assert "join(web, '.data')" not in ts and "mkdtempSync(join(dirname(entryFile), 'web-data-'))" in ts
    assert "process.env.MV_WEB_STAGE ??" in ts  # the folder music-video made, and removes even after a Ctrl-C
    assert "finally" in ts and "rmSync(stage" in ts
    assert "from '@mv/web-data/score.json?url'" in page and "./.data/" not in page
