import json

import numpy as np
import pytest

from musicvideo.cli import main
from musicvideo.workspace import load_workspace
from musicvideo.errors import MVError
from musicvideo.video.analyze import analyze, build_sections, energy_curves, pick_hits, tempo
from musicvideo.video.paths import video_song

SR = 22050


def synthetic():
    t = np.arange(2 * SR) / SR
    return np.concatenate([np.zeros(2 * SR), 0.8 * np.sin(2 * np.pi * 100 * t),
                           0.8 * np.sin(2 * np.pi * 6000 * t)]).astype(np.float32)


def test_energy_curves_follow_loudness_and_bands():
    curves = energy_curves(synthetic(), SR)
    assert set(curves) == {"rms", "low", "mid", "high"}
    assert all(len(v) == 180 for v in curves.values())
    low, high, rms = (np.array(curves[k]) for k in ("low", "high", "rms"))
    assert rms[5:55].max() < 0.01
    assert low[66:114].mean() > 0.5 and low[126:174].mean() < 0.1
    assert high[126:174].mean() > 0.5 and high[66:114].mean() < 0.1
    assert max(max(v) for v in curves.values()) <= 1.0


def test_hits_find_the_drop_and_keep_their_distance():
    hits = pick_hits(energy_curves(synthetic(), SR))
    assert any(abs(h["t"] - 2.0) <= 0.2 for h in hits)
    assert max(h["strength"] for h in hits) == 1.0
    times = [h["t"] for h in hits]
    assert all(b - a >= 4.0 for a, b in zip(times, times[1:]))


def section(i, name, start, end):
    return {"i": i, "name": name, "start": start, "end": end, "lines": None if start is None else [0, 0]}


def test_sections_name_gaps_after_wordless_tags_and_cover_the_song():
    timing = {"sections": [section(0, "Piano Intro", None, None), section(1, "Verse 1", 16.0, 40.0),
                           section(2, "Pre-Chorus", 41.0, 50.0), section(3, "Chorus", 50.5, 70.0),
                           section(4, "Instrumental Break", None, None), section(5, "Chorus", 80.0, 100.0)]}
    got = build_sections(timing, 110.0)
    assert [(s["id"], s["start"], s["end"], s["sung"]) for s in got] == [
        ("piano-intro", 0.0, 16.0, False), ("verse-1", 16.0, 41.0, True), ("pre-chorus", 41.0, 50.5, True),
        ("chorus", 50.5, 70.0, True), ("instrumental-break", 70.0, 80.0, False), ("chorus-2", 80.0, 100.0, True),
        ("outro", 100.0, 110.0, False)]


def test_a_song_that_starts_singing_at_once_has_no_intro():
    got = build_sections({"sections": [section(0, "Verse", 0.5, 20.0)]}, 21.0)
    assert [(s["id"], s["start"], s["end"]) for s in got] == [("verse", 0.0, 21.0)]


def test_an_instrumental_is_one_section():
    assert build_sections({}, 30.0) == [{"id": "instrumental", "name": "Instrumental", "start": 0.0,
                                          "end": 30.0, "sung": False}]


def test_tempo_from_beats():
    assert tempo([0.0, 0.5, 1.0, 1.5]) == 120.0
    assert tempo([1.0]) == 0.0


def fake_beats(args):
    cmd, song, out = args
    assert cmd == "beats"
    with open(out, "w") as f:
        json.dump({"beats": [0.0, 0.5, 1.0, 1.5, 2.0], "downbeats": [0.0, 2.0]}, f)


def test_analyze_writes_analysis_json(mv_ws, filed_song):
    spec_id, _ = filed_song(seconds=4.0)
    paths = video_song(load_workspace(), spec_id).paths
    paths.timing.write_text(json.dumps({"sections": [section(0, "Verse", 0.2, 3.0)]}), encoding="utf-8")
    data = analyze(load_workspace(), spec_id, runner=fake_beats)
    saved = json.loads(paths.analysis.read_text(encoding="utf-8"))
    assert saved == data
    assert data["fps"] == 30 and data["tempo"] == 120.0 and data["downbeats"] == [0.0, 2.0]
    assert len(data["energy"]["rms"]) == pytest.approx(120, abs=2)
    assert data["sections"][0]["start"] == 0.0 and data["sections"][-1]["end"] == data["duration"]


def test_analyze_needs_timing_first(mv_ws, filed_song):
    spec_id, _ = filed_song()
    with pytest.raises(MVError, match="align"):
        analyze(load_workspace(), spec_id, runner=fake_beats)


def test_cli_prints_the_map(mv_ws, filed_song, monkeypatch, capsys):
    spec_id, _ = filed_song(seconds=4.0)
    video_song(load_workspace(), spec_id).paths.timing.write_text(
        json.dumps({"sections": [section(0, "Verse", 0.2, 3.0)]}), encoding="utf-8")
    monkeypatch.setattr("musicvideo.video.analyze.run_worker", fake_beats)
    assert main(["analyze", spec_id]) == 0
    out = capsys.readouterr().out
    assert "120.0 bpm" in out and "verse" in out
