import json

import numpy as np
import pytest

from musicvideo.cli import main
from musicvideo.video.analyze import analyze
from musicvideo.video.drums import SR, find_hits, grid_fit
from musicvideo.video.paths import video_song
from musicvideo.workspace import load_workspace

RNG = np.random.default_rng(7)


def band_noise(n, lo, hi):
    spec = np.fft.rfft(RNG.standard_normal(n))
    f = np.fft.rfftfreq(n, 1 / SR)
    spec[(f < lo) | (f > hi)] = 0
    x = np.fft.irfft(spec, n)
    return x / np.abs(x).max()


def place(out, at, sound):
    i = int(at * SR)
    n = min(len(sound), len(out) - i)
    out[i:i + n] += sound[:n]


def env(n, tau):
    return np.exp(-np.arange(n) / SR / tau)


KICK = 0.9 * np.sin(2 * np.pi * 60 * np.arange(int(0.3 * SR)) / SR) * env(int(0.3 * SR), 0.08)
SNARE = 0.5 * band_noise(int(0.25 * SR), 1300, 4800) * env(int(0.25 * SR), 0.07)
HAT = 0.3 * band_noise(int(0.05 * SR), 8000, 15000) * env(int(0.05 * SR), 0.008)
CRASH = 0.4 * band_noise(int(1.0 * SR), 6000, 15000) * env(int(1.0 * SR), 0.3)


def groove(seconds=8.0):
    """120 bpm: kicks on 1 and 3, snares on 2 and 4, hats on the eighths, a crash on bar 3's downbeat."""
    x = np.zeros(int(seconds * SR))
    beats = [0.25 + 0.5 * k for k in range(int((seconds - 0.5) / 0.5))]
    want = []
    for k, b in enumerate(beats):
        kind = "kick" if k % 2 == 0 else "snare"
        place(x, b, KICK if kind == "kick" else SNARE)
        want.append((b, kind))
    for k in range(len(beats) * 2):
        t = 0.25 + 0.25 * k + 0.125   # the offbeat eighths (on the beats the kick and snare sit)
        if t < seconds - 0.3:
            place(x, t, HAT)
            if not beats[8] < t < beats[8] + 0.3:   # under the crash's loudest ring a hat is not heard
                want.append((t, "hat"))
    place(x, beats[8], CRASH)
    want.append((beats[8], "crash"))
    return x, beats, sorted(want)


def voice(seconds=8.0):
    """A sung line: a harmonic tone in syllables, its energy where a snare's is."""
    t = np.arange(int(seconds * SR)) / SR
    tone = sum(np.sin(2 * np.pi * 220 * h * t) / h for h in range(1, 20))
    gate = ((t * 3.1) % 1.0 < 0.6).astype(float)
    return 0.6 * tone * np.convolve(gate, np.ones(400) / 400, mode="same")


def matched(hits, want, kind, tol=0.03):
    got = [h["t"] for h in hits if h["kind"] == kind]
    times = [t for t, k in want if k == kind]
    return sum(any(abs(g - t) <= tol for g in got) for t in times), len(got), len(times)


@pytest.mark.parametrize("kind", ["kick", "snare", "hat", "crash"])
def test_each_kind_is_found_on_time(kind):
    mix, _, want = groove()
    hits = find_hits(mix)
    found, got, expected = matched(hits, want, kind)
    assert found == expected, (kind, found, expected)
    assert got <= expected + 1, [h for h in hits if h["kind"] == kind]   # nothing much invented
    assert all(0 < h["strength"] <= 1 for h in hits)


def test_the_vocal_stem_is_taken_off_before_measuring():
    drums, _, want = groove()
    sung = voice()
    noisy = find_hits(drums + sung)
    clean = find_hits(drums + sung, vocals=sung)
    found, got, expected = matched(clean, want, "snare")
    assert found == expected and got <= expected + 1
    assert len(noisy) > len(clean)   # without the stem, syllables read as hits


def test_the_grid_fit_says_how_far_beats_sit_from_the_drums():
    mix, beats, _ = groove()
    hits = find_hits(mix)
    assert grid_fit(beats, hits) < 0.05
    assert grid_fit([b + 0.25 for b in beats], hits) > 0.4   # half a beat off
    assert grid_fit(beats, []) is None


def fake_beats(args):
    with open(args[2], "w") as f:
        json.dump({"beats": [0.25, 0.75, 1.25, 1.75], "downbeats": [0.25]}, f)


def section(i, name, start, end):
    return {"i": i, "name": name, "start": start, "end": end, "lines": [0, 0]}


def test_analyze_writes_the_drums_and_says_where_they_came_from(mv_ws, filed_song):
    spec_id, _ = filed_song(seconds=4.0)
    paths = video_song(load_workspace(), spec_id).paths
    paths.timing.write_text(json.dumps({"sections": [section(0, "Verse", 0.2, 3.0)]}), encoding="utf-8")
    data = analyze(load_workspace(), spec_id, runner=fake_beats)
    assert data["drums"]["source"] == "mix"
    assert isinstance(data["drums"]["hits"], list)


def test_analyze_takes_the_vocal_stem_off_when_align_left_one(mv_ws, filed_song, monkeypatch, capsys):
    import subprocess
    spec_id, _ = filed_song(seconds=4.0)
    paths = video_song(load_workspace(), spec_id).paths
    paths.timing.write_text(json.dumps({"sections": [section(0, "Verse", 0.2, 3.0)]}), encoding="utf-8")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=f=440:d=4", "-ar", "44100",
                    str(paths.vocals)], check=True)
    monkeypatch.setattr("musicvideo.video.analyze.run_worker", fake_beats)
    assert main(["analyze", spec_id]) == 0
    saved = json.loads(paths.analysis.read_text(encoding="utf-8"))
    assert saved["drums"]["source"] == "mix minus vocals"
    out = capsys.readouterr().out
    assert "drums:" in out and "mix minus the vocal stem" in out
