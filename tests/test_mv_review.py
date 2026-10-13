import json
import os
import subprocess

import pytest

from musicvideo.cli import main
from musicvideo.errors import MVError
from musicvideo.video.review import build_page, load_versions, record_version, review_dir
from musicvideo.workspace import load_workspace


def ff(*args):
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *args], check=True)


@pytest.fixture
def checked(mv_ws, filed_song, tmp_path):
    """Make a render and pass it through mux and qc, as a version must have been. Returns (spec_id, make)."""
    spec_id, _ = filed_song(seconds=4.0)

    def make(name, seconds=4, excerpt=None):
        silent = tmp_path / f"{name}-silent.mp4"
        ff("-f", "lavfi", "-i", f"testsrc2=size=320x240:rate=30:duration={seconds}", "-c:v", "libx264",
           "-pix_fmt", "yuv420p", "-an", str(silent))
        out = tmp_path / f"{name}.mp4"
        flags = ["--excerpt", excerpt] if excerpt else []
        assert main(["mux", str(silent), "--spec", spec_id, "--out", str(out), *flags]) == 0
        assert main(["qc", str(out), "--spec", spec_id, "--size", "320x240", *flags]) == 0
        return out

    return spec_id, make


def test_versions_are_numbered_per_scene_and_kept_as_copies(checked, capsys):
    spec_id, make = checked
    ws = load_workspace()
    first = make("relay")
    a = record_version(ws, spec_id, first, "relay", note="first pass")
    b = record_version(ws, spec_id, make("relay"), "relay", note="tape slower")
    c = record_version(ws, spec_id, make("street", seconds=2, excerpt="1-3"), "street", start=1.0)
    assert (a["n"], b["n"], c["n"]) == (1, 2, 1)
    assert c["start"] == 1.0 and c["duration"] == pytest.approx(2.0, abs=0.1)
    assert a["kind"] == "video" and a["qc"] == "PASS" and a["size"] == [320, 240]
    folder = review_dir(ws, spec_id)
    assert (folder / "media" / "relay-v1.mp4").is_file() and (folder / "media" / "relay-v1.jpg").is_file()
    first.unlink()  # the render can go: the review keeps its own copy
    assert (folder / "media" / "relay-v1.mp4").is_file()
    assert [v["note"] for v in load_versions(ws, spec_id)] == ["first pass", "tape slower", ""]


def test_page_carries_the_versions_and_escapes_them(checked):
    spec_id, make = checked
    ws = load_workspace()
    record_version(ws, spec_id, make("roof"), "roof", note="stars </script><b>brighter</b>")
    page = build_page(ws, spec_id).read_text(encoding="utf-8")
    assert "/*VERSIONS*/" not in page and "{{TITLE}}" not in page
    assert "</script><b>" not in page  # a note cannot close the script
    data = page.split("const DATA = ", 1)[1].split(";\n", 1)[0]
    assert json.loads(data.replace("<\\/", "</"))["versions"][0]["file"] == "media/roof-v1.mp4"


def test_a_render_must_have_passed_qc_and_not_changed_since(checked, tmp_path):
    spec_id, make = checked
    ws = load_workspace()
    loose = tmp_path / "unchecked.mp4"
    ff("-f", "lavfi", "-i", "testsrc2=size=320x240:rate=30:duration=1", "-c:v", "libx264", "-pix_fmt", "yuv420p",
       str(loose))
    with pytest.raises(MVError, match="no qc report"):
        record_version(ws, spec_id, loose, "relay")
    out = make("table")
    later = out.stat().st_mtime + 5
    os.utime(out, (later, later))
    with pytest.raises(MVError, match="changed after its qc"):
        record_version(ws, spec_id, out, "table")
    assert main(["qc", str(make("press")), "--spec", spec_id, "--size", "1920x1080"]) == 1
    with pytest.raises(MVError, match="failed qc"):
        record_version(ws, spec_id, tmp_path / "press.mp4", "press")
    assert load_versions(ws, spec_id) == []


def test_stills_need_no_qc_and_bad_names_are_refused(checked, tmp_path):
    spec_id, _ = checked
    ws = load_workspace()
    png = tmp_path / "frame.png"
    ff("-f", "lavfi", "-i", "testsrc2=size=320x240", "-frames:v", "1", str(png))
    v = record_version(ws, spec_id, png, "backroom", start=121.5)
    assert v["kind"] == "still" and v["file"] == "media/backroom-v1.png" and v["start"] == 121.5
    with pytest.raises(MVError, match="not a scene name"):
        record_version(ws, spec_id, png, "Back Room")
    with pytest.raises(MVError, match="does not exist"):
        record_version(ws, spec_id, tmp_path / "missing.png", "backroom")
    notes = tmp_path / "notes.txt"
    notes.write_text("x", encoding="utf-8")
    with pytest.raises(MVError, match="a version is a video"):
        record_version(ws, spec_id, notes, "backroom")


def test_cli_version_and_review(checked, capsys):
    spec_id, make = checked
    assert main(["review", spec_id]) == 0
    assert "no versions yet" in capsys.readouterr().out
    clip = make("counter", seconds=2, excerpt="1-3")
    assert main(["version", spec_id, str(clip), "--scene", "counter", "--excerpt", "1-3", "--note", "egg timer"]) == 0
    out = capsys.readouterr().out
    assert "kept counter v1 (0:01.0–0:03.0" in out and "index.html" in out
    assert main(["version", spec_id, str(clip), "--scene", "counter", "--excerpt", "1-3", "--at", "2"]) == 2
    assert main(["review", spec_id]) == 0
    assert "counter: v1 " in capsys.readouterr().out
