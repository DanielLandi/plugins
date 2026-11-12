import json
import os
import subprocess

import pytest

from musicvideo.cli import main
from musicvideo.errors import MVError
from musicvideo.video.review import TEMPLATE, build_page, load_versions, mark_review, record_version, review_dir
from musicvideo.workspace import load_workspace
from mv_fixtures import BT709


def ff(*args):
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *args], check=True)


@pytest.fixture
def checked(mv_ws, filed_song, tmp_path):
    """Make a render and pass it through mux and qc, as a version must have been. Returns (spec_id, make)."""
    spec_id, _ = filed_song(seconds=4.0)

    def make(name, seconds=4, excerpt=None):
        silent = tmp_path / f"{name}-silent.mp4"
        ff("-f", "lavfi", "-i", f"testsrc2=size=320x240:rate=30:duration={seconds}", "-c:v", "libx264",
           "-pix_fmt", "yuv420p", *BT709, "-an", str(silent))
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


def test_a_new_version_waits_for_review_and_only_the_newest_of_a_scene_waits(checked):
    spec_id, make = checked
    ws = load_workspace()
    record_version(ws, spec_id, make("relay"), "relay")
    record_version(ws, spec_id, make("relay"), "relay", variant="b")
    record_version(ws, spec_id, make("street"), "street")
    assert [v["review"]["state"] for v in load_versions(ws, spec_id)] == ["waiting", "waiting", "waiting"]
    record_version(ws, spec_id, make("relay"), "relay")
    states = [(v["scene"], v["n"], v["review"]["state"]) for v in load_versions(ws, spec_id)]
    # relay v1 is replaced by v3; the variant (v2) and the other scene still wait
    assert states == [("relay", 1, "replaced"), ("relay", 2, "waiting"), ("street", 1, "waiting"),
                      ("relay", 3, "waiting")]
    assert load_versions(ws, spec_id)[0]["review"]["by"] == 3


def test_reviewed_keeps_the_users_words_and_known_issues_stay_on_top(checked):
    spec_id, make = checked
    ws = load_workspace()
    record_version(ws, spec_id, make("roof"), "roof", issues=["2:10.4: the sign flickers for two frames"])
    mark_review(ws, spec_id, "roof:v1", issue="the moon pops in at 2:14.0")
    v = mark_review(ws, spec_id, "roof:v1", reviewed="the stars should be brighter")
    assert v["review"]["state"] == "reviewed" and v["review"]["said"] == "the stars should be brighter"
    assert v["review"]["at"]
    saved = load_versions(ws, spec_id)[0]   # persisted in the review data
    assert saved["issues"] == ["2:10.4: the sign flickers for two frames", "the moon pops in at 2:14.0"]
    assert saved["review"]["state"] == "reviewed"
    page = build_page(ws, spec_id).read_text(encoding="utf-8")
    data = json.loads(page.split("const DATA = ", 1)[1].split(";\n", 1)[0].replace("<\\/", "</"))
    assert data["versions"][0]["issues"][1] == "the moon pops in at 2:14.0"
    assert mark_review(ws, spec_id, "roof v1", waiting=True)["review"]["state"] == "waiting"
    with pytest.raises(MVError, match="no version roof:v9"):
        mark_review(ws, spec_id, "roof:v9", waiting=True)
    with pytest.raises(MVError, match="scene:vN"):
        mark_review(ws, spec_id, "roof", waiting=True)


def test_the_page_puts_known_issues_first_and_shows_the_marks():
    page = TEMPLATE.read_text(encoding="utf-8")
    card = page.split("function card(", 1)[1].split("\n}\n", 1)[0]
    assert card.index("issues") < card.index("<dl>")          # known issues right under the title, before the facts
    assert "waiting review" in page and "reviewed" in page


def test_cli_issues_and_review_marks(checked, capsys):
    spec_id, make = checked
    clip = make("counter", seconds=2, excerpt="1-3")
    assert main(["version", spec_id, str(clip), "--scene", "counter", "--excerpt", "1-3",
                 "--issue", "0:01.5: the timer's hand jumps", "--issue", "no shadow yet"]) == 0
    assert "2 known issues" in capsys.readouterr().out
    assert main(["review", spec_id]) == 0
    assert "counter: v1 " in (out := capsys.readouterr().out) and "waiting review" in out
    assert main(["review", spec_id, "--version", "counter:v1", "--reviewed", "slower, and keep the shadow"]) == 0
    assert main(["review", spec_id]) == 0
    assert "reviewed: slower, and keep the shadow" in capsys.readouterr().out
    assert main(["review", spec_id, "--version", "counter:v1", "--issue", "the egg cracks late"]) == 0
    assert load_versions(load_workspace(), spec_id)[0]["issues"][-1] == "the egg cracks late"
    assert main(["review", spec_id, "--reviewed", "x"]) == 2   # a mark needs --version
