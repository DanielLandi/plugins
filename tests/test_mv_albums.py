import json
from datetime import datetime, timedelta

import pytest
from mutagen.id3 import ID3

from mv_fixtures import valid_spec
from musicvideo.albums import build_manifest, credit, load_album
from musicvideo.cli import main
from musicvideo.errors import MVError
from musicvideo.ingest import ingest
from musicvideo.spec import load_spec, save_spec, validate

ALBUM = """title: Night Shift
year: 2025
styles:
  synthwave:
    artist: The Late Lights
    album: Neon Hours
    genre: Synthwave
    era: 1980s
  jazz:
    artist: Blue Room Trio
    genre: Jazz
"""


@pytest.fixture
def album(mv_ws):
    (mv_ws.home / "albums").mkdir()
    (mv_ws.home / "albums" / "night-shift.yaml").write_text(ALBUM, encoding="utf-8")
    return mv_ws


def _ago(minutes):
    return (datetime.now().astimezone() - timedelta(minutes=minutes)).isoformat(timespec="seconds")


def test_load_and_credit_per_style(album):
    a = load_album(album, "night-shift")
    assert (a.title, a.year, a.artist) == ("Night Shift", 2025, "Test Artist")  # the project's artist by default
    c = credit(album, valid_spec(album="night-shift", style="synthwave"))
    assert (c.artist, c.album, c.genre, c.era, c.year) == ("The Late Lights", "Neon Hours", "Synthwave", "1980s", 2025)
    c = credit(album, valid_spec(album="night-shift", style="jazz"))
    assert (c.artist, c.album, c.genre, c.era) == ("Blue Room Trio", "Night Shift", "Jazz", None)


def test_a_song_without_an_album_is_its_own_single(album):
    c = credit(album, valid_spec())
    assert (c.artist, c.album, c.genre) == ("Test Artist", "Night Drive", None)
    assert c.year == datetime.now().year


def test_an_unknown_style_is_named(album):
    errors = validate(valid_spec(album="night-shift", style="polka"), album=load_album(album, "night-shift"))
    assert "style 'polka' is not in album 'night-shift' (styles: jazz, synthwave)" in errors
    assert "style missing: album 'night-shift' credits by style (styles: jazz, synthwave)" in validate(
        valid_spec(album="night-shift"), album=load_album(album, "night-shift"))


def test_an_unknown_album_is_named(album):
    with pytest.raises(MVError, match=r"no album 'nope' \(.*albums.nope\.yaml\)"):
        load_album(album, "nope")


def test_ingest_files_into_the_album_and_writes_the_manifest(album, make_mp3):
    save_spec(album.specs_dir / "night-drive.yaml", valid_spec(
        album="night-shift", style="synthwave", status="downloaded",
        kept={"take_url": "https://example.com/take/1", "downloaded_at": _ago(1)}))
    make_mp3(album.downloads_dir / "Night Drive.mp3")
    dest = ingest(album, "night-drive")
    assert dest == album.album_dir("night-shift") / "The Late Lights - Night Drive.mp3"
    tags = ID3(dest)
    assert (tags["TPE1"].text, tags["TALB"].text, tags["TCON"].text) == (["The Late Lights"], ["Neon Hours"], ["Synthwave"])
    assert str(tags["TDRC"].text[0]) == "2025"
    manifest = json.loads((album.album_dir("night-shift") / "manifest.json").read_text(encoding="utf-8"))
    assert [m["file"] for m in manifest] == ["The Late Lights - Night Drive.mp3"]
    entry = manifest[0]
    assert set(entry) == {"id", "title", "artist", "album", "genre", "era", "kind", "duration_s", "file", "sha256",
                          "added_at"}
    assert (entry["artist"], entry["album"], entry["genre"], entry["era"]) == ("The Late Lights", "Neon Hours",
                                                                              "Synthwave", "1980s")
    assert 0.5 < entry["duration_s"] < 2.0 and len(entry["sha256"]) == 64
    assert load_spec(album.specs_dir / "night-drive.yaml")["status"] == "filed"


def test_manifest_order_and_only_filed_songs(album, make_mp3, tmp_path):
    for sid, title, at in (("b-song", "B Song", _ago(5)), ("a-song", "A Song", _ago(5)), ("c-song", "C Song", _ago(9))):
        save_spec(album.specs_dir / f"{sid}.yaml", valid_spec(id=sid, title=title, album="night-shift", style="jazz",
                                                              status="generated"))
        ingest(album, sid, make_mp3(tmp_path / f"{sid}.mp3"))
        data = load_spec(album.specs_dir / f"{sid}.yaml")
        data["kept"]["filed_at"] = at
        save_spec(album.specs_dir / f"{sid}.yaml", data)
    save_spec(album.specs_dir / "d-song.yaml", valid_spec(id="d-song", album="night-shift", style="jazz"))
    assert [e["id"] for e in build_manifest(album, "night-shift")] == ["c-song", "a-song", "b-song"]


def test_manifest_refuses_a_missing_file(album, make_mp3, tmp_path):
    save_spec(album.specs_dir / "night-drive.yaml", valid_spec(album="night-shift", style="jazz", status="generated"))
    dest = ingest(album, "night-drive", make_mp3(tmp_path / "x.mp3"))
    dest.unlink()
    with pytest.raises(MVError, match="night-drive: filed audio missing"):
        build_manifest(album, "night-shift")


def test_album_command_rewrites_the_manifest(album, make_mp3, tmp_path, capsys):
    save_spec(album.specs_dir / "night-drive.yaml", valid_spec(album="night-shift", style="jazz", status="generated"))
    ingest(album, "night-drive", make_mp3(tmp_path / "x.mp3"))
    (album.album_dir("night-shift") / "manifest.json").unlink()
    assert main(["album", "night-shift"]) == 0
    assert "1 song" in capsys.readouterr().out
    assert (album.album_dir("night-shift") / "manifest.json").is_file()


def test_validate_command_checks_the_album(album, capsys):
    save_spec(album.specs_dir / "night-drive.yaml", valid_spec(album="night-shift", style="polka"))
    assert main(["validate", "night-drive"]) == 1
    assert "style 'polka'" in capsys.readouterr().out


def test_album_command_refuses_an_unknown_album(album, capsys):
    assert main(["album", "night-shfit"]) == 2
    assert "no album 'night-shfit'" in capsys.readouterr().err
    assert not album.album_dir("night-shfit").exists()


def test_manifest_rechecks_styles(album, make_mp3, tmp_path):
    save_spec(album.specs_dir / "night-drive.yaml", valid_spec(album="night-shift", style="jazz", status="generated"))
    ingest(album, "night-drive", make_mp3(tmp_path / "x.mp3"))
    path = album.home / "albums" / "night-shift.yaml"
    path.write_text(path.read_text(encoding="utf-8").replace("  jazz:", "  swing:"), encoding="utf-8")
    with pytest.raises(MVError, match="night-drive: style 'jazz' is not in album 'night-shift'"):
        build_manifest(album, "night-shift")


@pytest.mark.parametrize("text, message", [("title: X\nstyles:\n  - jazz\n", "styles"), ("- just a list\n", "mapping"),
                                            ("title: X\ncover: missing.png\n", "cover")])
def test_a_malformed_album_is_one_line(album, text, message):
    (album.home / "albums" / "bad.yaml").write_text(text, encoding="utf-8")
    with pytest.raises(MVError, match=message):
        load_album(album, "bad")


@pytest.mark.parametrize("cover", ["5", "[a.png]", "{x: 1}"])
def test_a_cover_that_is_not_a_file_name_is_named(album, cover):
    (album.home / "albums" / "bad.yaml").write_text(f"title: X\ncover: {cover}\n", encoding="utf-8")
    with pytest.raises(MVError, match="cover"):
        load_album(album, "bad")
