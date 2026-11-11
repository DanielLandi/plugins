import pytest
import yaml

from mv_fixtures import valid_spec
from musicvideo.spec import find_spec, iter_specs, save_spec, slugify, validate


def test_valid_spec_passes():
    assert validate(valid_spec()) == []


@pytest.mark.parametrize("field", ["id", "title", "kind", "status"])
def test_required(field):
    data = valid_spec()
    del data[field]
    assert f"missing field: {field}" in validate(data)


def test_artist_and_genre_not_required():
    data = valid_spec()
    assert "artist" not in data and "genre" not in data and validate(data) == []


def test_only_originals():
    assert any("original" in e for e in validate(valid_spec(kind="cover")))


def test_private_names_checked():
    data = valid_spec(title="Alex on the Road")
    assert any("Alex" in e for e in validate(data, ["Alex"]))


def test_find_and_iter(mv_ws):
    save_spec(mv_ws.specs_dir / "night-drive.yaml", valid_spec())
    assert find_spec(mv_ws, "night-drive").name == "night-drive.yaml"
    assert [d["id"] for _, d in iter_specs(mv_ws)] == ["night-drive"]
    with pytest.raises(Exception, match="no spec 'nope'"):
        find_spec(mv_ws, "nope")


def test_cli_new_and_validate(mv_ws, capsys):
    from musicvideo.cli import main
    assert main(["new", "--title", "Night Drive"]) == 0
    path = mv_ws.specs_dir / "night-drive.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert data["kind"] == "original" and data["status"] == "drafted"
    assert main(["new", "--title", "Night Drive"]) == 2
    assert main(["new", "--title", "Night Drive", "--id", "night-drive-2"]) == 0
    assert main(["validate", "night-drive"]) == 1  # styles and lyrics still empty
    assert "missing field: suno.styles" in capsys.readouterr().out


def test_slugify_accents():
    assert slugify("Café Noir à Minuit") == "cafe-noir-a-minuit"


def test_a_spec_without_a_generator_is_a_suno_song():
    from musicvideo.spec import generator
    assert generator(valid_spec()) == "suno"
    assert validate(valid_spec(generator="suno")) == []


def test_an_unknown_generator_is_named():
    errors = validate(valid_spec(generator="other"))
    assert "unknown generator 'other' (known: suno)" in errors


def test_the_generator_needs_its_settings_block():
    data = valid_spec(generator="suno")
    del data["suno"]
    assert "missing field: suno (the suno generator's settings)" in validate(data)


def test_new_names_the_generator(mv_ws):
    from musicvideo.cli import main
    assert main(["new", "--title", "Night Drive"]) == 0
    data = yaml.safe_load((mv_ws.specs_dir / "night-drive.yaml").read_text(encoding="utf-8"))
    assert data["generator"] == "suno" and "suno" in data


def test_validate_warns_once_when_private_names_are_missing(mv_ws, write_spec, capsys):
    from musicvideo.cli import main
    write_spec()
    write_spec(id="tide-clock", title="Tide Clock")
    assert main(["validate", "--all"]) == 0  # a warning, never a failure
    captured = capsys.readouterr()
    assert captured.err.count("warning: no private-names.txt in") == 1
    assert "private names were not checked" in captured.err
    assert "private-names" not in captured.out


def test_validate_with_a_private_names_file_does_not_warn(mv_ws, write_spec, capsys):
    from musicvideo.cli import main
    write_spec()
    (mv_ws.home / "private-names.txt").write_text("# nobody yet\n", encoding="utf-8")
    assert main(["validate", "night-drive"]) == 0
    assert "private-names.txt" not in capsys.readouterr().err


def test_validate_still_enforces_listed_private_names(mv_ws, write_spec, capsys):
    from musicvideo.cli import main
    write_spec(title="Alex on the Road")
    (mv_ws.home / "private-names.txt").write_text("# names\nAlex\n", encoding="utf-8")
    assert main(["validate", "night-drive"]) == 1
    captured = capsys.readouterr()
    assert "private name 'Alex' appears in the song" in captured.out
    assert "private-names.txt" not in captured.err
