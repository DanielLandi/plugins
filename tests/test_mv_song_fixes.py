import subprocess

import pytest

from musicvideo.cli import main
from musicvideo.errors import MVError
from musicvideo.video.paths import video_song
from musicvideo.video.songfix import filter_graph, lifted_song, load_lifts
from musicvideo.workspace import load_workspace


def rms_db(path, start, length):
    out = subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-ss", str(start), "-t", str(length), "-i", str(path), "-af",
         "astats=metadata=1,ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-", "-f", "null", "-"],
        capture_output=True, text=True, check=True).stdout
    return float(out.strip().splitlines()[-1].split("=")[1])


def as_wav(path, tmp_path):
    """Measure against a WAV decode: seeking inside an MP3 reads about 0.2 dB off."""
    wav = tmp_path / f"{path.stem}-ref.wav"
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(path), "-c:a", "pcm_s16le", str(wav)],
                   check=True)
    return wav


@pytest.fixture
def song(filed_song):
    spec_id, _ = filed_song(seconds=6.0, freq=2600)
    return spec_id, video_song(load_workspace(), spec_id)


def write_fixes(song, text):
    path = song.paths.song_fixes
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_no_fixes_means_the_original_song(song):
    _, s = song
    assert lifted_song(s.paths) == s.paths.song


def test_a_lift_raises_only_its_stretch_and_is_cached(song, tmp_path):
    _, s = song
    write_fixes(s, "- at: 2.0\n  to: 4.0\n  gain_db: 12\n  fade_in: 0.2\n  fade_out: 0.2\n  note: a whisper\n")
    out = lifted_song(s.paths)
    ref = as_wav(s.paths.song, tmp_path)
    assert out.name == "song-lifted.wav"
    assert rms_db(out, 2.5, 1.0) - rms_db(ref, 2.5, 1.0) == pytest.approx(12, abs=0.3)
    assert rms_db(out, 0.5, 1.0) == pytest.approx(rms_db(ref, 0.5, 1.0), abs=0.05)
    assert rms_db(out, 4.5, 1.0) == pytest.approx(rms_db(ref, 4.5, 1.0), abs=0.05)
    built = out.stat().st_mtime_ns
    assert lifted_song(s.paths).stat().st_mtime_ns == built  # unchanged fixes: not rebuilt


def test_the_hiss_cut_keeps_the_top_band_at_the_song_level(filed_song):
    spec_id, _ = filed_song(seconds=6.0, freq=9000)
    s = video_song(load_workspace(), spec_id)
    write_fixes(s, "- {at: 2.0, to: 4.0, gain_db: 12, hiss_cut_hz: 4000, denoise: true}\n")
    assert rms_db(lifted_song(s.paths), 2.5, 1.0) < rms_db(s.paths.song, 2.5, 1.0)


def test_bad_fixes_are_refused(song, tmp_path):
    _, s = song
    for text, message in [
        ("- {at: 1, gain_db: 6}\n", "to is required"),
        ("- {at: 1, to: 2, gain_db: 30}\n", "gain_db must be"),
        ("- {at: 1, to: 1.2, fade_in: 0.2, fade_out: 0.2}\n", "longer than its two fades"),
        ("- {at: 1, to: 2, loud: yes}\n", "unknown keys loud"),
        ("- {at: 1, to: 3}\n- {at: 2, to: 4}\n", "overlap"),
        ('- at: 1\n  note: "a": b\n', "not valid YAML"),
    ]:
        with pytest.raises(MVError, match=message):
            load_lifts(write_fixes(s, text))


def test_a_lift_may_start_while_the_one_before_fades_out(song):
    _, s = song
    lifts = load_lifts(write_fixes(s, "- {at: 2.5, to: 3.9, gain_db: 12}\n- {at: 1.4, to: 2.6, fade_out: 0.15}\n"))
    assert [lift["at"] for lift in lifts] == [1.4, 2.5]
    assert filter_graph(lifts).count("[l") == 4  # two lifted copies, each produced and mixed


def test_mux_and_qc_use_the_lifted_song(song, tmp_path):
    spec_id, s = song
    write_fixes(s, "- {at: 2.0, to: 4.0, gain_db: 9}\n")
    silent = tmp_path / "silent.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                    "testsrc2=size=320x240:rate=30:duration=6", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an",
                    str(silent)], check=True)
    out = tmp_path / "draft.mp4"
    assert main(["mux", str(silent), "--spec", spec_id, "--out", str(out)]) == 0
    assert rms_db(out, 2.5, 1.0) - rms_db(s.paths.song, 2.5, 1.0) == pytest.approx(9, abs=0.7)
    assert main(["qc", str(out), "--spec", spec_id, "--size", "320x240"]) == 0  # in sync with the lifted song
