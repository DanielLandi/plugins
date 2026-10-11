import json
import os
import time

import pytest

from musicvideo import studio
from musicvideo.errors import MVError


def _tree(root, files):
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")


def test_sync_copies_updates_and_prunes(tmp_path):
    src, dest = tmp_path / "src", tmp_path / "rt"
    _tree(src, {"kit/a.ts": "a", "package-lock.json": "{}", "node_modules/x/i.js": "no"})
    studio.sync_runtime(src, dest)
    assert (dest / "kit/a.ts").read_text(encoding="utf-8") == "a"
    assert not (dest / "node_modules/x/i.js").exists()  # never copied from the plugin
    _tree(dest, {"node_modules/keep/i.js": "installed", ".entries/v/index.ts": "e"})
    time.sleep(0.01)
    _tree(src, {"kit/a.ts": "changed", "kit/b.ts": "b"})
    (src / "package-lock.json").unlink()
    studio.sync_runtime(src, dest)
    assert (dest / "kit/a.ts").read_text(encoding="utf-8") == "changed"
    assert (dest / "kit/b.ts").exists() and not (dest / "package-lock.json").exists()
    assert (dest / "node_modules/keep/i.js").exists() and (dest / ".entries/v/index.ts").exists()


def test_not_installed_says_doctor(tmp_path, monkeypatch):
    monkeypatch.setenv("MV_CACHE_DIR", str(tmp_path / "cache"))
    src = tmp_path / "src"
    _tree(src, {"package-lock.json": '{"v": 1}'})
    monkeypatch.setattr(studio, "PLUGIN_STUDIO", src)
    with pytest.raises(MVError, match="music-video doctor"):
        studio.ensure_ready()
    rt = studio.runtime_dir()
    (rt / "node_modules").mkdir()
    (rt / studio.LOCK_STAMP).write_text(studio.lock_hash(rt), encoding="utf-8")
    assert studio.ensure_ready() == rt
    _tree(src, {"package-lock.json": '{"v": 2}'})  # a plugin update changed the packages
    with pytest.raises(MVError, match="music-video doctor"):
        studio.ensure_ready()


def test_entry_imports_video_with_space(tmp_path):
    vdir = tmp_path / "My Videos é" / "videos" / "night-drive"
    _tree(vdir, {"index.tsx": "export const Compositions = () => null;"})
    entry = studio.write_entry(tmp_path / "rt", vdir, "night-drive")
    text = entry.read_text(encoding="utf-8")
    assert json.dumps((vdir / "index.tsx").as_posix()) in text
    assert "registerRoot(Compositions)" in text
    with pytest.raises(MVError, match="music-video new-video other"):
        studio.write_entry(tmp_path / "rt", tmp_path / "missing", "other")


def test_video_context(mv_ws):
    vdir = mv_ws.video_dir("short")
    _tree(vdir, {"index.tsx": "", "video.yaml": "id: short\ngl: swangle\nsong: night-drive\n"})
    with pytest.raises(MVError, match="music-video align night-drive"):
        studio.video_context(mv_ws, "short")
    pub = mv_ws.work_for("night-drive") / "public"
    _tree(pub, {"timing.json": "{}", "analysis.json": "{}"})
    ctx = studio.video_context(mv_ws, "short")
    assert (ctx.song, ctx.gl, ctx.public, ctx.work) == ("night-drive", "swangle", pub, mv_ws.work_for("short"))


def test_tool_env(mv_ws, tmp_path):
    vdir = mv_ws.video_dir("night-drive")
    _tree(vdir, {"index.tsx": ""})
    _tree(mv_ws.work_for("night-drive") / "public", {"timing.json": "{}", "analysis.json": "{}"})
    ctx = studio.video_context(mv_ws, "night-drive")
    env = studio.tool_env(tmp_path / "rt", ctx, tmp_path / "rt/.entries/night-drive/index.ts")
    assert env["MV_STUDIO"] == str(tmp_path / "rt") and env["MV_GL"] == "angle"
    assert env["MV_PUBLIC"] == str(ctx.public) and env["INIT_CWD"] == os.getcwd()
    link = tmp_path / "rt" / ".entries" / "night-drive" / "src"
    assert env["MV_VIDEO_DIR"] == str(link) and link.resolve() == vdir.resolve()
    assert "--preserve-symlinks" in env["NODE_OPTIONS"].split()


def test_plugin_studio_is_the_shipped_engine():
    assert (studio.PLUGIN_STUDIO / "package.json").is_file() and (studio.PLUGIN_STUDIO / "kit").is_dir()


def test_sync_never_deletes_what_it_did_not_copy(tmp_path):
    src, dest = tmp_path / "src", tmp_path / "rt"
    _tree(src, {"kit/a.ts": "a", "tools/t.ts": "t"})
    studio.sync_runtime(src, dest)
    _tree(dest, {"blur out.mp4": "a render", "kit/notes.txt": "mine"})
    (src / "tools/t.ts").unlink()
    studio.sync_runtime(src, dest)
    assert (dest / "blur out.mp4").is_file() and (dest / "kit/notes.txt").is_file()
    assert not (dest / "tools/t.ts").exists()


def test_video_context_names_the_missing_step(mv_ws, write_spec):
    _tree(mv_ws.video_dir("night-drive"), {"index.tsx": ""})
    pub = mv_ws.work_for("night-drive") / "public"
    _tree(pub, {"timing.json": "{}"})
    with pytest.raises(MVError, match=r"no analysis\.json .*: run music-video analyze night-drive$"):
        studio.video_context(mv_ws, "night-drive")
    (pub / "timing.json").unlink()
    _tree(pub, {"analysis.json": "{}"})
    with pytest.raises(MVError, match=r"no timing\.json .*: run music-video align night-drive"):
        studio.video_context(mv_ws, "night-drive")
    # An instrumental has no words to time: the song map is enough.
    spec = write_spec()
    import yaml
    data = yaml.safe_load(spec.read_text(encoding="utf-8"))
    data["suno"] = {"model": "v6", "styles": "instrumental", "instrumental": True, "lyrics": ""}
    spec.write_text(yaml.safe_dump(data), encoding="utf-8")
    assert studio.video_context(mv_ws, "night-drive").public == pub


def test_the_engine_lives_in_the_install_folder(tmp_path):
    assert studio.runtime_dir() == tmp_path / "install" / "engine"


def test_an_old_engine_in_the_cache_is_moved_not_reinstalled(tmp_path):
    old = tmp_path / "cache" / "studio"
    _tree(old, {"node_modules/remotion/index.js": "x", studio.LOCK_STAMP: "h"})
    assert studio.migrate_old_runtime() is True
    assert (studio.runtime_dir() / "node_modules/remotion/index.js").is_file() and not old.exists()
    _tree(old, {"node_modules/other.js": "y"})
    assert studio.migrate_old_runtime() is False  # the new one exists: leave both alone
    assert old.exists()


def test_a_missing_tool_script_says_doctor(tmp_path, monkeypatch):
    monkeypatch.setattr(studio.shutil, "which", lambda name: "/usr/bin/" + name)
    rt = tmp_path / "rt"
    with pytest.raises(MVError, match="music-video doctor"):
        studio.tool(rt, "tsx")
    script = rt / studio.SCRIPTS["tsx"]
    script.parent.mkdir(parents=True)
    script.write_text("", encoding="utf-8")
    assert studio.tool(rt, "tsx") == ["/usr/bin/node", str(script)]


def test_install_includes_the_build_tools(tmp_path, monkeypatch):
    # tsx and typescript are dev dependencies: an npm set to omit them would leave the engine without its tools.
    calls = []
    monkeypatch.setattr(studio.shutil, "which", lambda name: name)
    monkeypatch.setattr(studio.subprocess, "run", lambda cmd, **k: calls.append(cmd) or type("R", (), {"returncode": 0})())
    rt = tmp_path / "rt"
    rt.mkdir()
    for name in studio.SCRIPTS.values():
        (rt / name).parent.mkdir(parents=True, exist_ok=True)
        (rt / name).write_text("", encoding="utf-8")
    studio.install(rt)
    assert calls[0][:2] == ["npm", "ci"] and "--include=dev" in calls[0]
