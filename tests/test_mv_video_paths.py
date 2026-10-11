import pytest

from musicvideo.workspace import load_workspace
from musicvideo.errors import MVError
from musicvideo.video.paths import video_song


def test_copies_the_song_into_the_video_public_folder(mv_ws, filed_song):
    spec_id, mp3 = filed_song()
    song = video_song(load_workspace(), spec_id)
    assert song.paths.root == mv_ws.work_for(spec_id)
    assert song.paths.deliver == mv_ws.results_for(spec_id)
    assert song.paths.song == song.paths.root / "public" / "song.mp3"
    assert song.paths.song.read_bytes() == mp3.read_bytes()
    assert song.paths.timing == song.paths.root / "public" / "timing.json"
    assert song.paths.subtitle("srt") == song.paths.root / "lyrics.srt"
    assert song.source == mp3


def test_recopies_when_the_library_file_changes(mv_ws, filed_song):
    spec_id, mp3 = filed_song(seconds=2.0)
    video_song(load_workspace(), spec_id)
    filed_song(seconds=3.0)  # same spec and file, longer audio
    song = video_song(load_workspace(), spec_id)
    assert song.paths.song.read_bytes() == mp3.read_bytes()


def test_refuses_a_song_that_is_not_filed(mv_ws, write_spec):
    path = write_spec(status="drafted")
    with pytest.raises(MVError, match="not filed"):
        video_song(load_workspace(), path.stem)


def test_refuses_when_the_library_file_is_gone(mv_ws, filed_song):
    spec_id, mp3 = filed_song()
    mp3.unlink()
    with pytest.raises(MVError, match="missing"):
        video_song(load_workspace(), spec_id)


def test_video_song_media_under_workspace_media(mv_ws, filed_song):
    spec_id, _ = filed_song()
    song = video_song(load_workspace(), spec_id)
    assert song.paths.root == mv_ws.work_for("night-drive")
    assert song.paths.song.is_file()


def test_paths_command(mv_ws, capsys):
    import json
    from musicvideo.cli import main
    assert main(["paths", "night-drive"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["public"] == str(mv_ws.work_for("night-drive") / "public")
    assert out["video"] == str(mv_ws.video_dir("night-drive"))
    assert out["renders"] == str(mv_ws.work_for("night-drive") / "renders")
    assert out["work"] == str(mv_ws.work_for("night-drive"))
    assert out["results"] == str(mv_ws.results_for("night-drive"))
    assert out["web"] == str(mv_ws.results_for("night-drive") / "web")


def test_paths_follow_a_borrowed_song(mv_ws, capsys):
    import json
    from musicvideo.cli import main
    vdir = mv_ws.video_dir("short")
    vdir.mkdir(parents=True)
    (vdir / "video.yaml").write_text("song: night-drive\n", encoding="utf-8")
    assert main(["paths", "short"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["public"] == str(mv_ws.work_for("night-drive") / "public")
    assert out["work"] == str(mv_ws.work_for("short"))


def test_clean_deletes_only_the_work_folder(mv_ws, capsys):
    from musicvideo.cli import main
    work, results = mv_ws.work_for("night-drive"), mv_ws.results_for("night-drive")
    (work / "renders").mkdir(parents=True)
    (work / "renders" / "draft.mp4").write_bytes(b"x" * 2048)
    results.mkdir(parents=True)
    (results / "final.mp4").write_bytes(b"y")
    assert main(["clean", "night-drive"]) == 0
    assert not work.exists() and (results / "final.mp4").is_file()
    assert "freed" in capsys.readouterr().out
    assert main(["clean", "night-drive"]) == 0  # nothing left: still fine


@pytest.mark.parametrize("bad", ["", "..", ".", "/tmp", "Night Drive", "a/b"])
def test_clean_refuses_anything_but_a_video_id(mv_ws, bad, capsys):
    from musicvideo.cli import main
    (mv_ws.work_for("night-drive") / "renders").mkdir(parents=True)
    assert main(["clean", bad]) == 2
    assert "video id" in capsys.readouterr().err
    assert mv_ws.work_for("night-drive").is_dir() and (mv_ws.home / "config.yaml").is_file()


@pytest.mark.parametrize("work_dir", ["{results}", "{home}"])
def test_clean_refuses_a_work_folder_that_holds_finals_or_the_project(mv_ws, work_dir, capsys):
    from musicvideo.cli import main
    cfg = mv_ws.home / "config.yaml"
    value = work_dir.format(results=mv_ws.results_dir, home=mv_ws.home)
    cfg.write_text(cfg.read_text(encoding="utf-8").replace(f"work_dir: {mv_ws.work_dir}", f"work_dir: {value}"),
                   encoding="utf-8")
    finals = mv_ws.results_for("night-drive")
    finals.mkdir(parents=True)
    (finals / "final.mp4").write_bytes(b"y")
    assert main(["clean", "night-drive"]) == 2
    assert "work_dir" in capsys.readouterr().err
    assert (finals / "final.mp4").is_file() and (mv_ws.home / "config.yaml").is_file()


def test_hand_written_corrections_live_with_the_video_not_in_the_work_folder(mv_ws, filed_song):
    spec_id, _ = filed_song()
    p = video_song(load_workspace(), spec_id).paths
    assert p.fixes == mv_ws.video_dir(spec_id) / "timing-fixes.yaml"
    assert p.as_sung == mv_ws.video_dir(spec_id) / "lyrics-as-sung.txt"


def test_corrections_left_in_an_older_work_folder_are_still_read(mv_ws, filed_song):
    spec_id, _ = filed_song()
    old = mv_ws.work_for(spec_id) / "timing-fixes.yaml"
    old.parent.mkdir(parents=True, exist_ok=True)
    old.write_text("[]\n", encoding="utf-8")
    assert video_song(load_workspace(), spec_id).paths.fixes == old
    (mv_ws.video_dir(spec_id)).mkdir(parents=True, exist_ok=True)
    (mv_ws.video_dir(spec_id) / "timing-fixes.yaml").write_text("[]\n", encoding="utf-8")
    assert video_song(load_workspace(), spec_id).paths.fixes == mv_ws.video_dir(spec_id) / "timing-fixes.yaml"


def test_clean_keeps_the_corrections(mv_ws, filed_song):
    from musicvideo.cli import main
    spec_id, _ = filed_song()
    p = video_song(load_workspace(), spec_id).paths
    p.fixes.parent.mkdir(parents=True, exist_ok=True)
    p.fixes.write_text("[]\n", encoding="utf-8")
    assert main(["clean", spec_id]) == 0
    assert p.fixes.is_file()
