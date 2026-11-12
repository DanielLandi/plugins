import json
import subprocess
from pathlib import Path

import pytest

from musicvideo.cli import main
from musicvideo.errors import MVError
from musicvideo.workspace import load_workspace
from musicvideo.video.mux import mux
from musicvideo.video.paths import video_song
from musicvideo.video.qc import run_qc
from mv_fixtures import BT709


def ff(*args):
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *args], check=True)



@pytest.fixture
def media(tmp_path, make_mp3):  # make_mp3 skips the test when ffmpeg is missing
    song = tmp_path / "song.mp3"
    ff("-f", "lavfi", "-i", "anoisesrc=color=pink:seed=7:amplitude=0.5:duration=4", "-ac", "1",
       "-c:a", "libmp3lame", "-b:a", "192k", str(song))

    def video(name, src="testsrc2=size=320x240:rate=30:duration=4", extra=()):
        out = tmp_path / name
        ff("-f", "lavfi", "-i", src, *extra, "-c:v", "libx264", "-pix_fmt", "yuv420p", *BT709, "-an", str(out))
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
    assert failed(run_qc(out, song, tmp / "qc")) == {"black", "flash"}  # a 3-frame dip is a flash too


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


def test_cli_mux_and_qc_with_a_video_that_borrows_a_song(mv_ws, filed_song, media, capsys):
    # a test-bed video's video.yaml says `song: <song id>`: --spec <video id> means that song
    spec_id, _ = filed_song(seconds=4.0)
    vdir = mv_ws.video_dir("test-bed")
    vdir.mkdir(parents=True)
    (vdir / "video.yaml").write_text(f"song: {spec_id}\n", encoding="utf-8")
    song, video, tmp = media
    final = tmp / "bed-final.mp4"
    assert main(["mux", str(video("bed.mp4")), "--spec", "test-bed", "--out", str(final)]) == 0
    assert main(["qc", str(final), "--spec", "test-bed", "--size", "320x240"]) == 0
    assert "PASS  audio" in capsys.readouterr().out


def test_a_tail_runs_silent_past_the_song(media):
    # an end screen: the video runs 2 s past the 4 s song; mux pads the song with silence, qc expects the longer length
    song, video, tmp = media
    # testsrc, not testsrc2: testsrc2 grows its grey box for one frame at 3.5 s, which the flicker scan catches
    out = mux(video("tail.mp4", src="testsrc=size=320x240:rate=30:duration=6"), song, tmp / "tail-out.mp4", tail=2.0)
    report = run_qc(out, song, tmp / "qc", size=(320, 240), tail=2.0)
    assert report["result"] == "PASS", report
    assert {"duration", "audio"} <= failed(run_qc(out, song, tmp / "qc"))
    with pytest.raises(MVError):
        mux(video("tail.mp4"), song, tmp / "x.mp4", excerpt=(1.0, 3.0), tail=2.0)
    with pytest.raises(MVError):
        run_qc(out, song, tmp / "qc", excerpt=(1.0, 3.0), tail=2.0)


def test_cli_tail(mv_ws, filed_song, media):
    spec_id, _ = filed_song(seconds=4.0)
    song, video, tmp = media
    final = tmp / "cli-tail.mp4"
    clip = video("cli-tail-silent.mp4", src="testsrc=size=320x240:rate=30:duration=7")  # see above
    assert main(["mux", str(clip), "--spec", spec_id, "--out", str(final), "--tail", "3"]) == 0
    assert main(["qc", str(final), "--spec", spec_id, "--tail", "3"]) == 0
    assert main(["qc", str(final), "--spec", spec_id]) == 1


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


SRC = "testsrc2=size=320x240:rate=30"   # mean luma about 120, always moving
DARK = f"{SRC},lutyuv=y=val/3"           # the same picture, mean luma about 40
NEAR_BLACK = "color=c=0x0c0c0c:size=320x240:rate=30"   # luma about 27: dark, but not black to blackdetect


def spliced(media, name, *parts):
    """A 4 s video from lavfi parts given as (source, frames), joined with hard cuts."""
    song, video, tmp = media
    graph = ";".join(f"{src},trim=end_frame={n},setpts=PTS-STARTPTS[p{i}]" for i, (src, n) in enumerate(parts))
    graph += ";" + "".join(f"[p{i}]" for i in range(len(parts))) + f"concat=n={len(parts)}:v=1:a=0"
    v = video(name, src="nullsrc=size=320x240:rate=30:duration=4", extra=("-filter_complex", graph))
    return mux(v, song, tmp / f"{Path(name).stem}-out.mp4")


def flash_detail(report):
    return next(c["detail"] for c in report["checks"] if c["id"] == "flash")


def test_one_near_black_frame_at_a_cut_fails_flash(media):
    # A scene mounted before its fonts were ready: one nearly empty, dark (not black) frame at the cut.
    song, _, tmp = media
    out = spliced(media, "blank1.mp4", (SRC, 60), (NEAR_BLACK, 1), (SRC, 59))
    report = run_qc(out, song, tmp / "qc")
    assert failed(report) == {"flash"}
    assert "2.00 s" in flash_detail(report) and "dark" in flash_detail(report)


def test_a_two_frame_dip_fails_flash(media):
    song, _, tmp = media
    report = run_qc(spliced(media, "blank2.mp4", (SRC, 45), (NEAR_BLACK, 2), (SRC, 73)), song, tmp / "qc")
    assert failed(report) == {"flash"}
    assert "1.50 s (2 frames)" in flash_detail(report)


def test_a_five_frame_dip_into_a_dark_scene_fails_flash(media):
    # The real one: five nearly empty frames (luma 28) between two frames of the same bright scene.
    song, _, tmp = media
    report = run_qc(spliced(media, "blank5.mp4", (SRC, 60), (NEAR_BLACK, 5), (SRC, 55)), song, tmp / "qc")
    assert failed(report) == {"flash"}
    assert "2.00 s (5 frames)" in flash_detail(report)


def test_a_single_white_frame_fails_flash(media):
    song, _, tmp = media
    out = spliced(media, "white1.mp4", (SRC, 75), ("color=c=white:size=320x240:rate=30", 1), (SRC, 44))
    report = run_qc(out, song, tmp / "qc")
    assert failed(report) == {"flash"}
    assert "white at 2.50 s" in flash_detail(report)


@pytest.mark.parametrize("parts", [((SRC, 60), (DARK, 60)), ((DARK, 60), (SRC, 60))], ids=["bright-to-dark", "dark-to-bright"])
def test_a_hard_cut_between_bright_and_dark_is_a_step_not_a_flash(media, parts):
    song, _, tmp = media
    # a scene change: declared, as qc --spec does from analysis.json (an undeclared one fails hard-cut, below)
    assert run_qc(spliced(media, "cut.mp4", *parts), song, tmp / "qc", cuts=[2.0])["result"] == "PASS"


def test_a_fade_through_dark_is_not_a_flash(media):
    song, _, tmp = media
    out = spliced(media, "fade.mp4", (f"{SRC},fade=t=out:st=1.6:d=0.4:color=0x0c0c0c", 60),
                  (f"{SRC},fade=t=in:st=0:d=0.4:color=0x0c0c0c", 60))
    assert run_qc(out, song, tmp / "qc")["result"] == "PASS"


def test_a_flash_inside_a_declared_hold_passes(media):
    song, _, tmp = media
    out = spliced(media, "heldflash.mp4", (SRC, 60), (NEAR_BLACK, 1), (SRC, 59))
    assert "flash" in failed(run_qc(out, song, tmp / "qc"))
    assert motion(run_qc(out, song, tmp / "qc", holds=[(1.9, 2.2)])) == set()


# The motion scans (flicker, pop, hard-cut, jitter): each fails on a planted fault, passes on a clean clip, and a
# designed hold over the fault lets it through.
BOX = "drawbox=x=120:y=90:w=48:h=48:color=0xf0d070:t=fill"
# A still set with one small thing drifting across it (still enough for freezedetect: these tests read only the
# motion scans).
STILL_BG = ("color=c=0x3a4a5a:size=320x240:rate=30:duration=4,drawgrid=w=40:h=40:t=2:c=0x8090a0,"
            "drawbox=x='10+20*t':y=200:w=10:h=10:color=white:t=fill")


def planted(media, name, vf, src=f"{SRC}:duration=4"):
    song, video, tmp = media
    v = video(name, src=src, extra=("-vf", vf))
    return mux(v, song, tmp / f"{Path(name).stem}-out.mp4")


def motion(report):
    return failed(report) & {"flicker", "pop", "hard-cut", "jitter"}


def detail(report, check):
    return next(c["detail"] for c in report["checks"] if c["id"] == check)


@pytest.mark.parametrize("src", [f"{SRC}:duration=4", STILL_BG], ids=["moving", "still"])
def test_a_clean_clip_passes_every_motion_scan(media, src):
    song, _, tmp = media
    report = run_qc(planted(media, "clean.mp4", "null", src=src), song, tmp / "qc")
    assert motion(report) == set(), report
    assert "in 120 frames" in detail(report, "flicker")   # it says how much it compared


def test_a_box_shown_for_one_frame_flickers(media):
    song, _, tmp = media
    out = planted(media, "flick.mp4", f"{BOX}:enable='eq(n,60)'", src=STILL_BG)
    report = run_qc(out, song, tmp / "qc")
    assert motion(report) == {"flicker"}
    assert "2.00–2.03 s" in detail(report, "flicker")
    assert motion(run_qc(out, song, tmp / "qc", holds=[(1.9, 2.2)])) == set()


def test_a_box_that_appears_in_one_frame_pops(media):
    song, _, tmp = media
    out = planted(media, "pop.mp4", f"{BOX}:enable='gte(n,60)'", src=STILL_BG)
    report = run_qc(out, song, tmp / "qc")
    assert motion(report) == {"pop"}
    assert "2.00 s" in detail(report, "pop")
    assert motion(run_qc(out, song, tmp / "qc", holds=[(1.9, 2.2)])) == set()
    # on a sung word's first frames it is taken for the subtitles' word highlight
    assert motion(run_qc(out, song, tmp / "qc", words=[2.0])) == set()


def test_an_entrance_over_eight_frames_is_not_a_pop(media):
    song, _, tmp = media
    _, video, _ = media
    vf = (f"{STILL_BG}[a];color=c=0xf0d070:size=48x48:rate=30:duration=4,format=yuva420p,"
          "fade=t=in:st=2.0:d=0.27:alpha=1[o];[a][o]overlay=120:90")
    v = video("ease.mp4", src="nullsrc=size=320x240:rate=30:duration=4", extra=("-filter_complex", vf))
    out = mux(v, song, tmp / "ease-out.mp4")
    assert motion(run_qc(out, song, tmp / "qc")) == set()


def test_a_hard_cut_inside_a_scene_fails_unless_declared(media):
    song, _, tmp = media
    out = spliced(media, "cut2.mp4", (SRC, 60), ("smptebars=size=320x240:rate=30", 60))
    report = run_qc(out, song, tmp / "qc")
    assert motion(report) == {"hard-cut"}
    assert "2.00 s" in detail(report, "hard-cut")
    assert run_qc(out, song, tmp / "qc", cuts=[2.0])["result"] == "PASS"            # a scene change or --cut
    assert motion(run_qc(out, song, tmp / "qc", holds=[(1.9, 2.2)])) == set()


def test_declared_cuts_are_song_time_and_shift_into_an_excerpt(media):
    song, video, tmp = media
    graph = (f"{SRC},trim=end_frame=30,setpts=PTS-STARTPTS[a];smptebars=size=320x240:rate=30,trim=end_frame=30,"
             "setpts=PTS-STARTPTS[b];[a][b]concat=n=2:v=1:a=0")
    clip = video("cutclip.mp4", src="nullsrc=size=320x240:rate=30:duration=2", extra=("-filter_complex", graph))
    out = mux(clip, song, tmp / "cutclip-out.mp4", excerpt=(1.0, 3.0))
    assert "hard-cut" in failed(run_qc(out, song, tmp / "qc", excerpt=(1.0, 3.0)))
    assert run_qc(out, song, tmp / "qc", excerpt=(1.0, 3.0), cuts=[2.0])["result"] == "PASS"


# A still, textured picture larger than the frame, for camera moves made with crop.
WANDER = "smptehdbars=size=400x300:rate=30:duration=4,drawgrid=w=23:h=17:t=1:c=black"


def test_a_camera_that_wanders_and_comes_back_jitters(media):
    song, _, tmp = media
    out = planted(media, "jitter.mp4", "crop=320:240:x='40+5*sin(2*PI*3*t)':y=30", src=WANDER)
    report = run_qc(out, song, tmp / "qc")
    assert motion(report) == {"jitter"}
    assert run_qc(out, song, tmp / "qc", holds=[(0.0, 4.0)])["result"] == "PASS"
    # a video that jolts on the beat by design is not scanned
    jolted = run_qc(out, song, tmp / "qc", jolts=True)
    assert jolted["result"] == "PASS" and "jolts" in detail(jolted, "jitter")


def test_a_steady_pan_is_not_jitter(media):
    song, _, tmp = media
    out = planted(media, "pan.mp4", "crop=320:240:x='10+15*t':y=30", src=WANDER)
    assert motion(run_qc(out, song, tmp / "qc")) == set()


def test_cli_qc_reads_scene_changes_cuts_words_and_jolts(mv_ws, filed_song, media, capsys):
    spec_id, _ = filed_song(seconds=4.0)
    song, video, tmp = media
    paths = video_song(load_workspace(), spec_id).paths
    graph = (f"{SRC},trim=end_frame=60,setpts=PTS-STARTPTS[a];smptebars=size=320x240:rate=30,trim=end_frame=60,"
             "setpts=PTS-STARTPTS[b];[a][b]concat=n=2:v=1:a=0")
    final = tmp / "ctx-final.mp4"
    assert main(["mux", str(video("ctx.mp4", src="nullsrc=size=320x240:rate=30:duration=4",
                                  extra=("-filter_complex", graph))), "--spec", spec_id, "--out", str(final)]) == 0
    assert main(["qc", str(final), "--spec", spec_id]) == 1
    assert "FAIL  hard-cut" in capsys.readouterr().out
    assert main(["qc", str(final), "--spec", spec_id, "--cut", "2.0"]) == 0
    vdir = mv_ws.video_dir(spec_id)
    vdir.mkdir(parents=True, exist_ok=True)
    (vdir / "video.yaml").write_text("cuts: [2.0]\n", encoding="utf-8")
    assert main(["qc", str(final), "--spec", spec_id]) == 0
    (vdir / "video.yaml").write_text("cuts: []\njolts: true\n", encoding="utf-8")
    paths.analysis.write_text(json.dumps({"sections": [{"start": 0.0}, {"start": 2.0}]}), encoding="utf-8")
    capsys.readouterr()
    assert main(["qc", str(final), "--spec", spec_id]) == 0   # a scene change, from analysis.json
    assert "not scanned: the video jolts" in capsys.readouterr().out


def test_untagged_or_wrongly_tagged_colour_fails_and_says_what_is_wrong(media):
    song, video, tmp = media
    plain = tmp / "untagged-silent.mp4"
    ff("-f", "lavfi", "-i", "testsrc=size=320x240:rate=30:duration=4", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(plain))
    report = run_qc(mux(plain, song, tmp / "untagged.mp4"), song, tmp / "qc")
    assert failed(report) == {"colour"}
    text = detail(report, "colour")
    assert "primaries unknown" in text and "transfer unknown" in text and "matrix unknown" in text and "bt709" in text
    bt601 = tmp / "bt601-silent.mp4"
    ff("-f", "lavfi", "-i", "testsrc=size=320x240:rate=30:duration=4", "-c:v", "libx264", "-pix_fmt", "yuv420p",
       "-bsf:v", "h264_metadata=colour_primaries=6:transfer_characteristics=6:matrix_coefficients=6", str(bt601))
    report = run_qc(mux(bt601, song, tmp / "bt601.mp4"), song, tmp / "qc")
    assert failed(report) == {"colour"} and "matrix smpte170m" in detail(report, "colour")
    good = run_qc(mux(video("tagged.mp4", src="testsrc=size=320x240:rate=30:duration=4"), song, tmp / "tagged-out.mp4"),
                  song, tmp / "qc")
    assert good["result"] == "PASS" and "bt709" in detail(good, "colour")
