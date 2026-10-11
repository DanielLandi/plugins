import json
import subprocess
from pathlib import Path

import pytest

from musicvideo.cli import main
from musicvideo.workspace import load_workspace
from musicvideo.video.mux import mux
from musicvideo.video.paths import video_song
from musicvideo.video.qc import run_qc


def ff(*args):
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *args], check=True)


@pytest.fixture
def media(tmp_path, make_mp3):  # make_mp3 skips the test when ffmpeg is missing
    song = tmp_path / "song.mp3"
    ff("-f", "lavfi", "-i", "anoisesrc=color=pink:seed=7:amplitude=0.5:duration=4", "-ac", "1",
       "-c:a", "libmp3lame", "-b:a", "192k", str(song))

    def video(name, src="testsrc2=size=320x240:rate=30:duration=4", extra=()):
        out = tmp_path / name
        ff("-f", "lavfi", "-i", src, *extra, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", str(out))
        return out

    return song, video, tmp_path


def ff_codec(path, kind):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", f"{kind}:0", "-show_entries",
                          "stream=codec_name", "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True)
    return out.stdout.strip()


def failed(report):
    return {c["id"] for c in report["checks"] if not c["ok"]}


def test_full_mux_is_aac_in_sync_and_passes(media):
    # AAC, not the MP3 stream copied as is: players (QuickTime) play no sound from MP3 inside MP4.
    song, video, tmp = media
    out = mux(video("silent.mp4"), song, tmp / "final.mp4")
    codec = ff_codec(out, "a")
    assert codec == "aac"
    report = run_qc(out, song, tmp / "qc", size=(320, 240))
    assert report["result"] == "PASS", report
    assert (tmp / "qc" / "final-sheet.png").is_file()
    assert json.loads((tmp / "qc" / "qc-final.json").read_text(encoding="utf-8"))["result"] == "PASS"


def test_full_audio_that_is_late_or_another_sound_fails(media):
    song, video, tmp = media
    late = tmp / "late.mp4"
    ff("-i", str(video("silent.mp4")), "-itsoffset", "0.25", "-i", str(song), "-map", "0:v", "-map", "1:a",
       "-c:v", "copy", "-c:a", "aac", "-shortest", str(late))
    assert "audio" in failed(run_qc(late, song, tmp / "qc"))
    other = tmp / "other.mp4"
    ff("-i", str(video("silent.mp4")), "-f", "lavfi", "-i", "anoisesrc=d=4:c=pink:seed=99", "-map", "0:v", "-map", "1:a",
       "-c:v", "copy", "-c:a", "aac", "-shortest", str(other))
    assert "audio" in failed(run_qc(other, song, tmp / "qc"))


def test_excerpt_in_sync_passes_and_a_shifted_one_fails(media):
    song, video, tmp = media
    clip = video("clip.mp4", src="testsrc2=size=320x240:rate=30:duration=2")
    good = mux(clip, song, tmp / "good.mp4", excerpt=(1.0, 3.0))
    assert run_qc(good, song, tmp / "qc", excerpt=(1.0, 3.0))["result"] == "PASS"
    late = mux(clip, song, tmp / "late.mp4", excerpt=(1.5, 3.5))
    report = run_qc(late, song, tmp / "qc", excerpt=(1.0, 3.0))
    assert failed(report) == {"audio"}
    assert "offset" in next(c["detail"] for c in report["checks"] if c["id"] == "audio")


def test_black_in_the_middle_fails_unless_declared(media):
    song, video, tmp = media
    v = video("black.mp4", src="testsrc2=size=320x240:rate=30:duration=1.25",
              extra=("-f", "lavfi", "-i", "color=black:size=320x240:rate=30:duration=1.5",
                     "-f", "lavfi", "-i", "testsrc2=size=320x240:rate=30:duration=1.25",
                     "-filter_complex", "[0][1][2]concat=n=3:v=1:a=0"))
    out = mux(v, song, tmp / "black-out.mp4")
    assert failed(run_qc(out, song, tmp / "qc")) == {"black"}
    assert run_qc(out, song, tmp / "qc", holds=[(1.2, 2.8)])["result"] == "PASS"


def test_three_black_frames_in_the_middle_fail(media):
    # A draft once had 13 black frames inside a transition; 0.5 s let them through.
    song, video, tmp = media
    v = video("blip.mp4", src="testsrc2=size=320x240:rate=30:duration=1.9",
              extra=("-f", "lavfi", "-i", "color=black:size=320x240:rate=30:duration=0.1",
                     "-f", "lavfi", "-i", "testsrc2=size=320x240:rate=30:duration=2.0",
                     "-filter_complex", "[0][1][2]concat=n=3:v=1:a=0"))
    out = mux(v, song, tmp / "blip-out.mp4")
    assert failed(run_qc(out, song, tmp / "qc")) == {"black"}


def test_frozen_stretch_fails_unless_declared(media):
    song, video, tmp = media
    v = video("frozen.mp4", src="testsrc2=size=320x240:rate=30:duration=1",
              extra=("-vf", "tpad=stop_mode=clone:stop_duration=3"))
    out = mux(v, song, tmp / "frozen-out.mp4")
    assert failed(run_qc(out, song, tmp / "qc")) == {"frozen"}
    assert run_qc(out, song, tmp / "qc", holds=[(0.9, 4.0)])["result"] == "PASS"


def test_wrong_size_and_rate_fail(media):
    song, video, tmp = media
    out = mux(video("pal.mp4", src="testsrc2=size=320x240:rate=25:duration=4"), song, tmp / "pal-out.mp4")
    assert "format" in failed(run_qc(out, song, tmp / "qc", size=(1920, 1080)))


def test_cli_mux_and_qc(mv_ws, filed_song, media, capsys):
    spec_id, _ = filed_song(seconds=4.0)
    song, video, tmp = media
    final = tmp / "cli-final.mp4"
    assert main(["mux", str(video("cli.mp4")), "--spec", spec_id, "--out", str(final)]) == 0
    assert main(["qc", str(final), "--spec", spec_id, "--size", "320x240"]) == 0
    assert "PASS  audio" in capsys.readouterr().out
    assert (video_song(load_workspace(), spec_id).paths.qc / "cli-final-sheet.png").is_file()
    assert main(["qc", str(final), "--spec", spec_id, "--size", "1920x1080"]) == 1
    assert main(["qc", str(final), "--spec", spec_id, "--excerpt", "3-1"]) == 2  # a bad argument is an error; a failed check is 1


def test_silent_excerpt_track_fails(media):
    song, video, tmp = media
    clip = video("clip.mp4", src="testsrc2=size=320x240:rate=30:duration=2")
    bad = tmp / "silent-track.mp4"
    ff("-i", str(clip), "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", "2", "-map", "0:v", "-map", "1:a",
       "-c:v", "copy", "-c:a", "aac", str(bad))
    report = run_qc(bad, song, tmp / "qc", excerpt=(1.0, 3.0))
    assert failed(report) == {"audio"}
    assert "no audio signal" in next(c["detail"] for c in report["checks"] if c["id"] == "audio")


def test_truncated_video_under_the_full_song_fails_duration(media):
    song, video, tmp = media
    out = mux(video("short.mp4", src="testsrc2=size=320x240:rate=30:duration=2"), song, tmp / "short-out.mp4")
    assert "duration" in failed(run_qc(out, song, tmp / "qc"))


def test_holds_are_song_time_and_shift_into_the_excerpt(media):
    song, video, tmp = media
    # excerpt-time 0.5-1.5 black inside a 2 s clip
    clip = video("holdclip.mp4", src="testsrc2=size=320x240:rate=30:duration=0.5",
                 extra=("-f", "lavfi", "-i", "color=black:size=320x240:rate=30:duration=1",
                        "-f", "lavfi", "-i", "testsrc2=size=320x240:rate=30:duration=0.5",
                        "-filter_complex", "[0][1][2]concat=n=3:v=1:a=0"))
    out = mux(clip, song, tmp / "hold-out.mp4", excerpt=(1.0, 3.0))
    assert run_qc(out, song, tmp / "qc", excerpt=(1.0, 3.0), holds=[(1.5, 2.5)])["result"] == "PASS"
    assert "black" in failed(run_qc(out, song, tmp / "qc", excerpt=(1.0, 3.0), holds=[(0.5, 1.5)]))


def test_a_dark_background_with_a_small_blinking_element_is_not_black_or_frozen(media):
    song, video, tmp = media
    v = video("dark.mp4", src="color=c=0x101418:size=320x240:rate=30:duration=4",
              extra=("-vf", "drawbox=x=150:y=110:w=20:h=20:color=white:t=fill:enable='lt(mod(t,0.5),0.25)'"))
    out = mux(v, song, tmp / "dark-out.mp4")
    assert not failed(run_qc(out, song, tmp / "qc")) & {"black", "frozen"}


def test_a_dot_blinking_over_a_still_background_is_not_frozen(media):
    song, video, tmp = media
    v = video("dot.mp4", src="color=c=0x13294b:size=1280x720:rate=30:duration=4",
              extra=("-vf", "drawbox=x=620:y=340:w=40:h=40:color=white:t=fill:enable='lt(mod(t,0.5),0.25)'"))
    out = mux(v, song, tmp / "dot-out.mp4")
    assert "frozen" not in failed(run_qc(out, song, tmp / "qc"))


def test_a_long_video_gets_paged_sheets(media):
    song, video, tmp = media
    v = video("long.mp4", src="testsrc2=size=320x240:rate=10:duration=25")
    report = run_qc(v, song, tmp / "qc")
    assert (tmp / "qc" / "long-sheet.png").is_file()
    assert report["pages"] == [str(tmp / "qc" / f"long-sheet-0{n}.png") for n in (1, 2)]
    assert all(Path(x).is_file() for x in report["pages"])
    assert run_qc(video("short.mp4"), song, tmp / "qc")["pages"] == []
