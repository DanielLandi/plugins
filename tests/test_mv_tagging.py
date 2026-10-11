from mutagen.id3 import GEOB, ID3, TPE1, TXXX, WOAS

from mv_fixtures import valid_spec
from musicvideo.albums import Credit
from musicvideo.tagging import display_lyrics, write_tags

ARTIST = "Test Artist"
CREDIT = Credit(artist=ARTIST, album="Night Drive", genre=None, era=None, year=2026, cover=None)


def test_display_lyrics_strips_section_tags_and_extra_blank_lines():
    text = "[Verse 1]\nHeadlights on\n\n\n\n[Chorus]\nKeep on  \n"
    assert display_lyrics(text) == "Headlights on\n\nKeep on"


def test_tags_round_trip(tmp_path, make_mp3):
    mp3 = make_mp3(tmp_path / "a.mp3")
    write_tags(mp3, valid_spec(kept={"take_url": "https://suno.com/song/a"}), CREDIT)
    tags = ID3(mp3)
    assert tags["TIT2"].text == ["Night Drive"]
    assert tags["TPE1"].text == [ARTIST]
    assert tags["TALB"].text == ["Night Drive"]
    assert "TCON" not in tags and "TCOM" not in tags
    assert str(tags["TDRC"].text[0]) == "2026"
    assert tags["TXXX:SPEC_ID"].text == ["night-drive"]
    assert tags["TXXX:TAKE_URL"].text == ["https://suno.com/song/a"]
    assert tags["TXXX:KIND"].text == ["original"]
    assert tags["TXXX:GENERATOR"].text == ["Suno v6"]
    assert "[Verse 1]" not in tags.getall("USLT")[0].text


def test_no_take_url_no_frame(tmp_path, make_mp3):
    mp3 = make_mp3(tmp_path / "a.mp3")
    write_tags(mp3, valid_spec(), CREDIT)
    assert "TXXX:TAKE_URL" not in ID3(mp3)


def test_suno_metadata_wiped_but_cover_kept(tmp_path, make_mp3):
    mp3 = make_mp3(tmp_path / "a.mp3", comment="made with suno.com", cover=b"\xff\xd8suno-art")
    tags = ID3(mp3)
    tags.add(TPE1(encoding=3, text="some_suno_user"))
    tags.add(WOAS(url="https://suno.com/song/x"))
    tags.add(TXXX(encoding=1, desc="comment", text="made with suno; id=x"))
    tags.save(mp3)
    cover = tmp_path / "cover.png"
    cover.write_bytes(b"\x89PNGcover")
    write_tags(mp3, valid_spec(), CREDIT._replace(cover=cover))
    tags = ID3(mp3)
    assert tags.getall("COMM") == [] and tags.getall("WOAS") == []
    assert "TXXX:comment" not in tags
    assert tags["TPE1"].text == [ARTIST]
    covers = tags.getall("APIC")
    assert len(covers) == 1 and covers[0].data == b"\xff\xd8suno-art"


def test_c2pa_content_credentials_are_preserved(tmp_path, make_mp3):
    mp3 = make_mp3(tmp_path / "a.mp3")
    tags = ID3(mp3)
    tags.add(GEOB(encoding=3, mime="application/c2pa", filename="c2pa",
                  desc="c2pa manifest store", data=b"\x00\x00jumbc2pa"))
    tags.save(mp3)
    write_tags(mp3, valid_spec(), CREDIT)
    frames = ID3(mp3).getall("GEOB")
    assert len(frames) == 1 and frames[0].data == b"\x00\x00jumbc2pa"


def test_cover_used_when_file_has_none(tmp_path, make_mp3):
    mp3 = make_mp3(tmp_path / "a.mp3")
    cover = tmp_path / "cover.png"
    cover.write_bytes(b"\x89PNGcover")
    write_tags(mp3, valid_spec(), CREDIT._replace(cover=cover))
    covers = ID3(mp3).getall("APIC")
    assert covers[0].mime == "image/png" and covers[0].data == b"\x89PNGcover"


def test_instrumental_has_no_lyrics_frame(tmp_path, make_mp3):
    mp3 = make_mp3(tmp_path / "a.mp3")
    spec = valid_spec(title="Slow Waltz")
    del spec["suno"]["lyrics"]
    del spec["suno"]["vocal_gender"]
    spec["suno"]["instrumental"] = True
    write_tags(mp3, spec, CREDIT)
    tags = ID3(mp3)
    assert tags.getall("USLT") == []
    assert tags["TIT2"].text == ["Slow Waltz"]
