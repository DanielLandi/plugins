import os
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from mutagen.id3 import ID3

from mv_fixtures import valid_spec
from musicvideo.cli import main
from musicvideo.errors import MVError
from musicvideo.ingest import find_candidates, ingest, library_filename
from musicvideo.spec import load_spec, save_spec
from musicvideo.workspace import stored_path

SPEC_ID = "night-drive"


def _minutes_ago(n):
    return (datetime.now().astimezone() - timedelta(minutes=n)).isoformat(timespec="seconds")


@pytest.fixture
def downloaded(write_spec):
    return write_spec(status="downloaded",
                      kept={"take_url": "https://suno.com/song/a", "downloaded_at": _minutes_ago(1)})


def test_ingest_files_into_media_folder_with_space(mv_ws, write_spec, make_mp3):
    path = write_spec(status="generated")
    mp3 = make_mp3(mv_ws.downloads_dir / "Night Drive.mp3")
    dest = ingest(mv_ws, SPEC_ID)
    assert dest == mv_ws.results_for(SPEC_ID) / "Test Artist - Night Drive.mp3"
    data = load_spec(path)
    assert data["status"] == "filed" and data["kept"]["file"] == stored_path(mv_ws, dest)
    assert data["kept"]["filed_at"]
    assert not mp3.exists()
    assert ID3(dest)["TPE1"].text == ["Test Artist"]


def test_partial_and_wav_downloads_are_ignored(mv_ws, downloaded):
    (mv_ws.downloads_dir / "Night Drive.mp3.crdownload").write_bytes(b"partial")
    (mv_ws.downloads_dir / "Night Drive.wav").write_bytes(b"RIFF")
    with pytest.raises(MVError, match="--file"):
        ingest(mv_ws, SPEC_ID)


def test_old_file_with_same_title_is_ignored(mv_ws, downloaded, make_mp3):
    old = make_mp3(mv_ws.downloads_dir / "Night Drive.mp3")
    day_ago = time.time() - 86400
    os.utime(old, (day_ago, day_ago))
    with pytest.raises(MVError, match="no finished MP3"):
        ingest(mv_ws, SPEC_ID)


def test_two_candidates_asks_for_file(mv_ws, downloaded, make_mp3):
    make_mp3(mv_ws.downloads_dir / "Night Drive.mp3")
    make_mp3(mv_ws.downloads_dir / "Night Drive (1).mp3")
    with pytest.raises(MVError, match="several candidates"):
        ingest(mv_ws, SPEC_ID)


def test_punctuated_title_matches_and_filename_is_legal(mv_ws, write_spec, make_mp3):
    write_spec(id="city-dawn", title="City: At/Dawn?", status="downloaded",
               kept={"take_url": "u", "downloaded_at": _minutes_ago(1)})
    make_mp3(mv_ws.downloads_dir / "City At Dawn.mp3")
    assert ingest(mv_ws, "city-dawn").name == "Test Artist - City At Dawn.mp3"


def test_file_flag_rejects_wav(mv_ws, downloaded, tmp_path):
    wav = tmp_path / "x.wav"
    wav.write_bytes(b"RIFF")
    with pytest.raises(MVError, match="only MP3"):
        ingest(mv_ws, SPEC_ID, wav)


def test_file_flag_without_download_record_uses_file_time(mv_ws, write_spec, make_mp3, tmp_path):
    path = write_spec(status="generated")
    ingest(mv_ws, SPEC_ID, make_mp3(tmp_path / "anything.mp3"))
    data = load_spec(path)
    assert data["status"] == "filed" and data["kept"]["downloaded_at"]


def test_same_file_owned_by_other_spec(mv_ws, write_spec, make_mp3, tmp_path):
    other = valid_spec(id="other-song", status="filed",
                       kept={"downloaded_at": _minutes_ago(5),
                             "file": stored_path(mv_ws, mv_ws.results_for(SPEC_ID) / "Test Artist - Night Drive.mp3")})
    save_spec(mv_ws.specs_dir / "other-song.yaml", other)
    write_spec(status="generated")
    with pytest.raises(MVError, match="already belongs to spec 'other-song'"):
        ingest(mv_ws, SPEC_ID, make_mp3(tmp_path / "a.mp3"))


def test_library_filename():
    assert library_filename("A/B", 'x: "y"?') == "A B - x y.mp3"


def test_find_candidates_newest_first(mv_ws, make_mp3):
    a = make_mp3(mv_ws.downloads_dir / "Night Drive.mp3")
    os.utime(a, (time.time() - 30, time.time() - 30))
    b = make_mp3(mv_ws.downloads_dir / "Night Drive (1).mp3")
    assert find_candidates(mv_ws.downloads_dir, "Night Drive", None) == [b, a]


def test_cli_ingest(mv_ws, downloaded, make_mp3, capsys):
    make_mp3(mv_ws.downloads_dir / "Night Drive.mp3")
    assert main(["ingest", SPEC_ID]) == 0
    assert "Test Artist - Night Drive.mp3" in capsys.readouterr().out


def test_a_file_from_outside_the_downloads_folder_is_copied_not_moved(mv_ws, write_spec, make_mp3, tmp_path):
    write_spec(status="generated")
    mine = make_mp3(tmp_path / "My Music" / "keep me.mp3")
    dest = ingest(mv_ws, SPEC_ID, mine)
    assert dest.is_file() and mine.is_file()  # the user's own copy stays


def test_a_download_is_moved_out_of_the_downloads_folder(mv_ws, write_spec, make_mp3):
    write_spec(status="generated")
    download = make_mp3(mv_ws.downloads_dir / "Night Drive.mp3")
    ingest(mv_ws, SPEC_ID, download)
    assert not download.exists()


def test_a_link_outside_downloads_is_kept_even_if_it_points_into_them(mv_ws, write_spec, make_mp3, tmp_path):
    write_spec(status="generated")
    download = make_mp3(mv_ws.downloads_dir / "Night Drive.mp3")
    link = tmp_path / "elsewhere" / "link.mp3"
    link.parent.mkdir()
    link.symlink_to(download)
    ingest(mv_ws, SPEC_ID, link)
    assert link.is_symlink()  # the user's own link, outside the downloads folder, stays
