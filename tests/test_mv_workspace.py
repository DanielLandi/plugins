import json
from pathlib import Path

import pytest

from musicvideo import workspace as w
from musicvideo.errors import MVError


def test_home_order(tmp_path, monkeypatch):
    monkeypatch.delenv("MUSIC_VIDEO_HOME", raising=False)
    monkeypatch.setenv("MV_SETTINGS", str(tmp_path / "s.json"))
    assert w.workspace_home() == w.DEFAULT_HOME
    w.remember_home(tmp_path / "saved")
    assert json.loads((tmp_path / "s.json").read_text(encoding="utf-8")) == {"workspace": str(tmp_path / "saved")}
    assert w.workspace_home() == tmp_path / "saved"
    monkeypatch.setenv("MUSIC_VIDEO_HOME", str(tmp_path / "env"))
    assert w.workspace_home() == tmp_path / "env"


def test_init_creates_layout_and_remembers(mv_ws, tmp_path):
    assert mv_ws.home.name == "My Videos é"
    assert (mv_ws.home / "specs").is_dir() and (mv_ws.home / "videos").is_dir()
    assert mv_ws.artist == "Test Artist" and mv_ws.billing_day == 15 and mv_ws.download_budget == 20
    assert mv_ws.results_for("x") == tmp_path / "My Results é" / "x"
    assert mv_ws.work_for("x") == tmp_path / "My Work é" / "x"
    assert mv_ws.album_dir("a") == tmp_path / "My Results é" / "albums" / "a"
    assert mv_ws.video_dir("x") == mv_ws.home / "videos" / "x"
    assert json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))["workspace"] == str(mv_ws.home)


def test_init_on_existing_workspace_only_remembers(mv_ws):
    before = (mv_ws.home / "config.yaml").read_text(encoding="utf-8")
    path, created = w.init_workspace(mv_ws.home, artist="Someone Else")
    assert (path, created) == (mv_ws.home, False)
    assert (mv_ws.home / "config.yaml").read_text(encoding="utf-8") == before


def test_defaults_keep_media_out_of_the_project(tmp_path, monkeypatch):
    monkeypatch.delenv("MV_CACHE_DIR")
    monkeypatch.delenv("MV_INSTALL_DIR")
    home = tmp_path / "ws"
    w.init_workspace(home, artist="A")
    ws = w.load_workspace(home)
    assert ws.results_for("v") == w.DEFAULT_RESULTS / "v"
    assert w.DEFAULT_RESULTS.parts[-2:] == ("Movies", "Music Videos")
    assert ws.work_for("v") == w.cache_dir() / "work" / "v"
    assert w.install_dir().name == "music-video" and "Caches" not in w.install_dir().parts
    assert w.DEFAULT_HOME.parts[-2:] == ("Documents", "Music Videos")


def test_an_older_config_with_media_dir_reads_as_results(tmp_path):
    home = tmp_path / "ws"
    home.mkdir()
    (home / "config.yaml").write_text("artist: A\nmedia_dir: ~/Somewhere/Media\n", encoding="utf-8")
    assert w.load_workspace(home).results_for("v") == Path.home() / "Somewhere" / "Media" / "v"


def test_broken_config_is_one_line(tmp_path):
    home = tmp_path / "ws"
    home.mkdir()
    (home / "config.yaml").write_text("artist: [unclosed\n", encoding="utf-8")
    with pytest.raises(MVError, match="config.yaml: not valid YAML"):
        w.load_workspace(home)


def test_broken_settings_file_is_one_line(tmp_path, monkeypatch):
    monkeypatch.delenv("MUSIC_VIDEO_HOME", raising=False)
    monkeypatch.setenv("MV_SETTINGS", str(tmp_path / "s.json"))
    (tmp_path / "s.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(MVError, match="s.json"):
        w.workspace_home()


@pytest.mark.parametrize("args, message", [(["--billing-day", "40"], "billing-day"),
                                            (["--download-budget", "-1"], "download-budget")])
def test_init_refuses_bad_numbers(tmp_path, args, message, capsys):
    from musicvideo.cli import main
    assert main(["init", "--path", str(tmp_path / "ws"), "--artist", "A", *args]) == 2
    assert message in capsys.readouterr().err
    assert not (tmp_path / "ws" / "config.yaml").exists()


def test_missing_workspace_says_init(tmp_path):
    with pytest.raises(MVError, match="music-video init"):
        w.load_workspace(tmp_path / "nowhere")


@pytest.mark.parametrize("bad", ["billing_day: 40", "billing_day: soon", "download_budget: -1", "artist: ''"])
def test_bad_config(mv_ws, bad):
    cfg = mv_ws.home / "config.yaml"
    cfg.write_text(cfg.read_text(encoding="utf-8") + bad + "\n", encoding="utf-8")
    with pytest.raises(MVError, match="config.yaml"):
        w.load_workspace()


def test_stored_and_filed_paths(mv_ws):
    inside = mv_ws.home / "specs" / "a.mp3"
    assert w.stored_path(mv_ws, inside) == str(Path("specs") / "a.mp3")
    assert w.filed_path(mv_ws, w.stored_path(mv_ws, inside)) == inside
    user = Path.home() / "Elsewhere" / "b.mp3"
    assert w.stored_path(mv_ws, user) == "~/" + str(Path("Elsewhere") / "b.mp3")
    assert w.filed_path(mv_ws, "~/Elsewhere/b.mp3") == user


def test_private_names(mv_ws):
    assert w.load_private_names(mv_ws) == []
    (mv_ws.home / "private-names.txt").write_text("# names\nAlex\n\n", encoding="utf-8")
    assert w.load_private_names(mv_ws) == ["Alex"]


def test_cli_init(tmp_path, monkeypatch, capsys):
    from musicvideo.cli import main
    monkeypatch.setenv("MV_SETTINGS", str(tmp_path / "s.json"))
    monkeypatch.delenv("MUSIC_VIDEO_HOME", raising=False)
    home = tmp_path / "Music Videos"
    assert main(["init", "--path", str(home), "--artist", "Night Owls", "--billing-day", "3", "--download-budget", "10"]) == 0
    assert "created" in capsys.readouterr().out
    assert w.load_workspace().artist == "Night Owls"
