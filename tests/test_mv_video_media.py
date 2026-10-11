import subprocess

import numpy as np
import pytest

from musicvideo.errors import MVError
from musicvideo.video.media import decode_mono, duration_s, rms_envelope


def test_decode_and_duration(tmp_path, make_mp3):
    mp3 = make_mp3(tmp_path / "s.mp3")
    assert duration_s(mp3) == pytest.approx(1.0, abs=0.1)
    samples = decode_mono(mp3, 8000)
    assert samples.dtype == np.float32
    assert len(samples) == pytest.approx(8000, abs=800)


def test_decode_a_slice(tmp_path, requires_ffmpeg):
    wav = tmp_path / "t.wav"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
                    "-y", str(wav)], check=True)
    assert len(decode_mono(wav, 8000, start=1.0, duration=0.5)) == pytest.approx(4000, abs=80)


def test_decode_missing_file_raises(tmp_path, requires_ffmpeg):
    with pytest.raises(MVError, match="decoding"):
        decode_mono(tmp_path / "nope.mp3")


def test_rms_envelope_frames():
    sr = 1000
    samples = np.concatenate([np.zeros(500), np.ones(500)]).astype(np.float32)
    env = rms_envelope(samples, sr, 0.1)
    assert len(env) == 10
    assert env[:5].max() == 0.0 and env[5:].min() == pytest.approx(1.0)
