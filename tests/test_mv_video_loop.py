import json
import subprocess

import numpy as np
import pytest

from musicvideo.errors import MVError
from musicvideo.video.loop import MARGIN_S, XFADE_S, build_loop, loop_points, make_loop
from musicvideo.video.media import duration_s

SR = 1000


def song(seconds: float, fade: float = 10.0, lead: float = 0.0) -> np.ndarray:
    """Noise at a steady level, then a linear fade to silence, after `lead` seconds of silence."""
    rng = np.random.default_rng(1)
    body = int((seconds - fade - lead) * SR)
    level = np.concatenate([np.zeros(int(lead * SR)), np.full(body, 0.3), np.linspace(0.3, 0.0, int(fade * SR))])
    return (rng.standard_normal((len(level), 2)) * level[:, None]).astype(np.float32)


def test_loop_points_snap_to_downbeats_before_the_ending():
    audio = song(70)  # full level to 60 s, half level at 65 s
    downbeats = [1.0 + 2 * i for i in range(35)]  # 1, 3, … 69
    start, end = loop_points(audio, SR, downbeats)
    assert start == 1.0
    assert end == 57.0  # the last downbeat no later than min(65 - 4, 70 - 12)


def test_loop_points_without_a_beat_grid_use_the_first_sound():
    start, end = loop_points(song(72, lead=2.0), SR, None)
    assert start == pytest.approx(2.0, abs=0.01)
    assert end == pytest.approx(60.0, abs=0.5)  # 72 - 12


def test_loop_points_take_an_explicit_end():
    assert loop_points(song(70), SR, None, end=40.0) == (pytest.approx(0.0, abs=0.01), 40.0)


def test_loop_points_refuse_a_song_too_short_to_loop():
    with pytest.raises(MVError, match="too short"):
        loop_points(song(40), SR, None)


def test_build_loop_wraps_without_a_seam():
    t = np.arange(80 * SR) / SR
    x = np.stack([np.sin(2 * np.pi * 3 * t), np.cos(2 * np.pi * 3 * t)], axis=1).astype(np.float32) * 0.5
    out, n, margin = build_loop(x, SR, 0.0, 50.0)
    assert n == 50 * SR and margin == int(MARGIN_S * SR)
    assert len(out) == n + margin
    # played back to back, the last loop sample is followed by what followed it in the song
    np.testing.assert_allclose(out[n - 1], x[n - 1], atol=1e-6)
    np.testing.assert_allclose(out[0], x[n], atol=1e-6)
    # the margin repeats the opening, so any one-loop window inside it is seamless too
    np.testing.assert_array_equal(out[n:], out[:margin])
    # after the crossfade the opening is the song itself
    k = int(XFADE_S * SR)
    np.testing.assert_allclose(out[k:n], x[k:n], atol=1e-6)
    assert np.abs(out).max() <= 1.0


def test_build_loop_needs_room_for_the_crossfade():
    with pytest.raises(MVError, match="crossfade"):
        build_loop(song(60), SR, 0.0, 58.0)


def test_make_loop_writes_the_loop_its_meta_and_a_seam_preview(tmp_path, requires_ffmpeg):
    src = tmp_path / "s.wav"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=220:duration=75",
                    "-ac", "2", "-y", str(src)], check=True)
    meta = make_loop(src, tmp_path / "loop", end=50.0)
    out = tmp_path / "loop"
    assert meta == json.loads((out / "loop.json").read_text())
    assert meta["rate"] == 44100 and meta["marginSamples"] == 44100
    assert meta["loopSamples"] == pytest.approx(50 * 44100, abs=2)  # the sine starts at 0: the loop starts a sample in
    assert duration_s(out / "loop.m4a") == pytest.approx(51.0, abs=0.1)
    assert duration_s(out / "seam-preview.m4a") == pytest.approx(20.0, abs=0.1)
    assert meta["onDownbeats"] is False
    assert meta["clipped"] == 0


def sine_wav(path, volume: float = 1.0):
    subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=220:duration=75",
                    "-af", f"volume={volume}", "-ac", "2", "-y", str(path)], check=True)
    return path


def test_make_loop_says_when_it_snapped_to_the_beat_grid(tmp_path, requires_ffmpeg):
    src = sine_wav(tmp_path / "s.wav")
    meta = make_loop(src, tmp_path / "loop", downbeats=[0.5 + 2 * i for i in range(35)])
    assert meta["onDownbeats"] is True
    assert (meta["start_s"], meta["end_s"]) == (0.5, 62.5)  # the last downbeat before 75 - 12
    few = make_loop(src, tmp_path / "loop2", downbeats=[0.5, 2.5, 4.5])  # under 8: not trusted
    assert few["onDownbeats"] is False


def test_make_loop_counts_the_samples_its_crossfade_clipped(tmp_path, requires_ffmpeg):
    # 220 Hz over a 50 s loop is a whole number of cycles: head and tail are in phase, so the equal-power sum
    # reaches 1.41 times the level. ffmpeg's sine peaks at 0.088, so ×10 is 0.88 of full scale and the sum clips.
    meta = make_loop(sine_wav(tmp_path / "loud.wav", volume=10), tmp_path / "loop", end=50.0)
    assert meta["clipped"] > 0


def test_loop_command_writes_into_the_work_folder(mv_ws, filed_song, capsys):
    from musicvideo.cli import main
    spec_id, _ = filed_song(seconds=60.0)
    assert main(["loop", spec_id]) == 0
    out = mv_ws.work_for(spec_id) / "loop"
    assert (out / "loop.m4a").is_file() and (out / "loop.json").is_file() and (out / "seam-preview.m4a").is_file()
    assert "listen to the seam" in capsys.readouterr().out


def test_encode_never_holds_a_temp_file_open_for_ffmpeg(tmp_path, requires_ffmpeg, monkeypatch):
    # On Windows a NamedTemporaryFile cannot be reopened by another process while it is open: ffmpeg would fail.
    import tempfile

    from musicvideo.video import loop as lp

    def refuse(*a, **k):
        raise AssertionError("encode must not use NamedTemporaryFile")
    monkeypatch.setattr(tempfile, "NamedTemporaryFile", refuse)
    out = lp.encode(np.zeros((44100, 2), dtype=np.float32), 44100, tmp_path / "x.m4a")
    assert out.stat().st_size > 0
