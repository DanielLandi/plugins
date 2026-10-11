import pytest

from musicvideo.workspace import load_workspace
from musicvideo.errors import MVError
from musicvideo.video.paths import video_song


def test_copies_the_song_into_the_video_public_folder(mv_ws, filed_song):
    spec_id, mp3 = filed_song()
    song = video_song(load_workspace(), spec_id)
    assert song.paths.root == mv_ws.media_for(spec_id)
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
    assert song.paths.root == mv_ws.media_for("night-drive")
    assert song.paths.song.is_file()


def test_paths_command(mv_ws, capsys):
    import json
    from musicvideo.cli import main
    assert main(["paths", "night-drive"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["public"] == str(mv_ws.media_for("night-drive") / "public")
    assert out["video"] == str(mv_ws.video_dir("night-drive"))
    assert out["renders"] == str(mv_ws.media_for("night-drive") / "renders")
