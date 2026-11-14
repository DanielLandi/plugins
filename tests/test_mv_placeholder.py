"""A silent placeholder song: working on a video's picture before (or without) its song."""
import json
import subprocess

import pytest
import yaml

from musicvideo import studio
from musicvideo.cli import main
from musicvideo.errors import MVError
from musicvideo.video.media import duration_s, probe
from musicvideo.video.paths import video_song
from musicvideo.video.placeholder import declared


@pytest.fixture
def ws(mv_ws, requires_ffmpeg):
    return mv_ws


def public(ws, video_id):
    return ws.work_for(video_id) / "public"


def meta(ws, video_id):
    return yaml.safe_load((ws.video_dir(video_id) / "video.yaml").read_text(encoding="utf-8"))


def test_placeholder_writes_a_silent_song_a_steady_grid_and_no_words(ws, capsys):
    assert main(["new-video", "skate"]) == 0
    assert main(["placeholder", "skate", "--seconds", "10"]) == 0
    out = capsys.readouterr().out
    assert "placeholder" in out and "10 s" in out and "120 bpm" in out
    assert meta(ws, "skate")["placeholder"] == {"seconds": 10.0, "bpm": 120.0}
    # the template's comments stay
    assert "# A silent placeholder song" in (ws.video_dir("skate") / "video.yaml").read_text(encoding="utf-8")
    pub = public(ws, "skate")
    assert abs(duration_s(pub / "song.mp3") - 10.0) < 0.1
    timing = json.loads((pub / "timing.json").read_text(encoding="utf-8"))
    assert timing == {"version": 1, "duration": 10.0, "words": [], "lines": [], "sections": [], "placeholder": True}
    analysis = json.loads((pub / "analysis.json").read_text(encoding="utf-8"))
    assert analysis["placeholder"] is True and analysis["duration"] == 10.0 and analysis["tempo"] == 120.0
    assert analysis["beats"][:3] == [0.0, 0.5, 1.0] and analysis["beats"][-1] == 9.5
    assert analysis["downbeats"] == [0.0, 2.0, 4.0, 6.0, 8.0]
    assert analysis["sections"] == [{"id": "part-1", "name": "Part 1", "start": 0.0, "end": 10.0, "sung": False}]
    assert len(analysis["energy"]["rms"]) == 300 and set(analysis["energy"]) == {"rms", "low", "mid", "high"}
    assert analysis["hits"] == []


def test_a_long_placeholder_is_cut_into_eight_bar_parts(ws):
    assert main(["new-video", "skate", "--placeholder", "38", "--bpm", "120"]) == 0
    analysis = json.loads((public(ws, "skate") / "analysis.json").read_text(encoding="utf-8"))
    # 8 bars at 120 bpm = 16 s; a last part shorter than 4 bars joins the one before it
    assert [(s["id"], s["start"], s["end"]) for s in analysis["sections"]] == [
        ("part-1", 0.0, 16.0), ("part-2", 16.0, 38.0)]
    assert meta(ws, "skate")["placeholder"] == {"seconds": 38.0, "bpm": 120.0}


def test_placeholder_can_change_length_and_tempo(ws):
    assert main(["new-video", "skate", "--placeholder", "10"]) == 0
    assert main(["placeholder", "skate", "--seconds", "6", "--bpm", "90"]) == 0
    assert meta(ws, "skate")["placeholder"] == {"seconds": 6.0, "bpm": 90.0}
    analysis = json.loads((public(ws, "skate") / "analysis.json").read_text(encoding="utf-8"))
    assert analysis["duration"] == 6.0 and analysis["tempo"] == 90.0
    text = (ws.video_dir("skate") / "video.yaml").read_text(encoding="utf-8")
    assert text.count("placeholder:") == 1


@pytest.mark.parametrize("args, says", [
    (["placeholder", "nope", "--seconds", "10"], "no video"),
    (["placeholder", "skate", "--seconds", "0"], "seconds"),
    (["placeholder", "skate", "--seconds", "10", "--bpm", "500"], "bpm"),
])
def test_placeholder_refuses_bad_input(ws, args, says, capsys):
    assert main(["new-video", "skate"]) == 0
    assert main(args) == 2
    assert says in capsys.readouterr().err


def test_a_video_that_borrows_a_song_gets_no_placeholder(ws, capsys):
    assert main(["new-video", "bed"]) == 0
    path = ws.video_dir("bed") / "video.yaml"
    path.write_text("song: night-drive\n" + path.read_text(encoding="utf-8"), encoding="utf-8")
    assert main(["placeholder", "bed", "--seconds", "10"]) == 2
    assert "borrows" in capsys.readouterr().err


def test_a_filed_song_gets_no_placeholder(ws, filed_song, capsys):
    spec_id, _ = filed_song(seconds=4.0)
    assert main(["new-video", spec_id]) == 0
    assert main(["placeholder", spec_id, "--seconds", "10"]) == 2
    assert "filed" in capsys.readouterr().err


def test_the_placeholder_comes_back_after_clean(ws):
    assert main(["new-video", "skate", "--placeholder", "8"]) == 0
    assert main(["clean", "skate"]) == 0
    assert not public(ws, "skate").exists()
    ctx = studio.video_context(ws, "skate")   # what render, still, studio and typecheck run first
    assert ctx.public == public(ws, "skate")
    assert json.loads((ctx.public / "analysis.json").read_text(encoding="utf-8"))["duration"] == 8.0
    assert (ctx.public / "song.mp3").is_file() and (ctx.public / "timing.json").is_file()


def test_paths_shows_the_placeholder(ws, capsys):
    assert main(["new-video", "skate", "--placeholder", "8"]) == 0
    capsys.readouterr()
    assert main(["paths", "skate"]) == 0
    assert json.loads(capsys.readouterr().out)["placeholder"] == {"seconds": 8.0, "bpm": 120.0}


def test_the_real_song_replaces_the_placeholder(ws, filed_song):
    assert main(["new-video", "night-drive", "--placeholder", "8"]) == 0
    pub = public(ws, "night-drive")
    spec_id, mp3 = filed_song(seconds=4.0)   # the song arrives later, with the same id
    song = video_song(ws, spec_id)            # what align, analyze, mux and qc run first
    assert song.paths.public == pub
    assert abs(duration_s(pub / "song.mp3") - 4.0) < 0.1   # the real song, not the 8 s of silence
    assert not (pub / "timing.json").exists() and not (pub / "analysis.json").exists()
    assert meta(ws, "night-drive")["placeholder"] is None
    with pytest.raises(MVError, match="align"):
        studio.video_context(ws, "night-drive")   # no silent stand-in comes back


def test_declared_reads_a_number_or_a_mapping():
    assert declared({}) is None and declared({"placeholder": None}) is None
    assert declared({"placeholder": 12}) == {"seconds": 12.0, "bpm": 120.0}
    assert declared({"placeholder": {"seconds": 12, "bpm": 100}}) == {"seconds": 12.0, "bpm": 100.0}
    with pytest.raises(MVError):
        declared({"placeholder": "long"})


# qc of a video in placeholder (or --silent) mode: every picture check, nothing that needs a song.

def clip(path, seconds=4, src="testsrc=size=320x240:rate=30", audio=False):
    from mv_fixtures import BT709
    args = ["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", f"{src}:duration={seconds}"]
    if audio:
        args += ["-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo", "-t", str(seconds), "-c:a", "aac"]
    args += ["-c:v", "libx264", "-pix_fmt", "yuv420p", *BT709, str(path)]
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(args, check=True)
    return path


def lines(out):
    return {line.split()[1]: line.split()[0] for line in out.splitlines() if line[:4] in ("PASS", "FAIL", "SKIP")}


@pytest.mark.parametrize("audio", [False, True], ids=["muted", "silent-track"])
def test_qc_of_a_placeholder_video_checks_the_picture_and_skips_the_song(ws, tmp_path, capsys, audio):
    assert main(["new-video", "skate", "--placeholder", "4"]) == 0
    video = clip(ws.work_for("skate") / "renders" / "draft.mp4", audio=audio)
    capsys.readouterr()
    assert main(["qc", str(video), "--spec", "skate", "--size", "320x240"]) == 0
    out = capsys.readouterr().out
    seen = lines(out)
    assert seen["audio"] == "SKIP" and seen["lyrics"] == "SKIP"
    assert {seen[c] for c in ("format", "duration", "colour", "black", "flash", "frozen", "flicker", "pop",
                              "hard-cut", "jitter", "placeholder")} == {"PASS"}
    assert "not a final" in out
    report = json.loads((ws.work_for("skate") / "qc" / "qc-draft.json").read_text(encoding="utf-8"))
    assert report["result"] == "PASS" and report["placeholder"] is True


def test_qc_of_a_placeholder_still_fails_on_the_picture(ws, capsys):
    assert main(["new-video", "skate", "--placeholder", "4"]) == 0
    video = clip(ws.work_for("skate") / "renders" / "draft.mp4", seconds=2)   # too short for the 4 s placeholder
    assert main(["qc", str(video), "--spec", "skate"]) == 1
    assert lines(capsys.readouterr().out)["duration"] == "FAIL"


def test_a_placeholder_video_in_the_results_folder_fails(ws, capsys):
    assert main(["new-video", "skate", "--placeholder", "4"]) == 0
    video = clip(ws.results_for("skate") / "Skate.mp4")
    assert main(["qc", str(video), "--spec", "skate"]) == 1
    out = capsys.readouterr().out
    assert lines(out)["placeholder"] == "FAIL" and "not a final" in out


def test_qc_silent_checks_a_clip_with_no_song_at_all(ws, capsys):
    # a test bed or proof of concept: no spec, no placeholder
    assert main(["new-video", "poc"]) == 0
    video = clip(ws.work_for("poc") / "renders" / "a.mp4")
    assert main(["qc", str(video), "--spec", "poc"]) == 2
    assert "--silent" in capsys.readouterr().err
    assert main(["qc", str(video), "--spec", "poc", "--silent"]) == 0
    seen = lines(capsys.readouterr().out)
    assert seen["audio"] == "SKIP" and seen["duration"] == "SKIP" and "placeholder" not in seen
    assert main(["qc", str(video), "--spec", "poc", "--silent", "--excerpt", "10-14"]) == 0
    assert lines(capsys.readouterr().out)["duration"] == "PASS"
    assert (ws.work_for("poc") / "qc" / "qc-a.json").is_file()


def test_run_qc_without_a_song_never_fails_for_missing_audio(tmp_path, requires_ffmpeg):
    from musicvideo.video.qc import run_qc
    video = clip(tmp_path / "v.mp4")
    report = run_qc(video, None, tmp_path / "qc", length=4.0)
    assert report["result"] == "PASS", report
    checks = {c["id"]: c for c in report["checks"]}
    assert checks["audio"]["skipped"] and "no song" in checks["audio"]["detail"]
    assert "no audio" in checks["format"]["detail"] and checks["format"]["ok"]
    assert probe(video)  # sanity: the clip has no audio stream and still passed


def test_new_video_with_a_bad_placeholder_makes_no_folder(ws, capsys):
    assert main(["new-video", "skate", "--placeholder", "-3"]) == 2
    assert "seconds" in capsys.readouterr().err
    assert not ws.video_dir("skate").exists()
