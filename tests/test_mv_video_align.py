import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml

from musicvideo.cli import main
from musicvideo.workspace import load_workspace
from musicvideo.errors import MVError
from musicvideo.video.align import align
from musicvideo.video.paths import video_song


def fake_worker(calls, conf=0.9, count=None):
    def run(args):
        calls.append(args)
        cmd, song, lyrics_txt, lang, out = args
        assert cmd == "timing"
        out = Path(out)
        if not (out / "vocals.wav").exists():
            subprocess.run(["ffmpeg", "-loglevel", "error", "-i", song, "-y", str(out / "vocals.wav")], check=True)
        tokens = Path(lyrics_txt).read_text(encoding="utf-8").split()
        tokens = tokens[:count] if count is not None else tokens
        words = [{"word": w, "start": round(0.2 + 0.3 * i, 3), "end": round(0.45 + 0.3 * i, 3), "prob": conf}
                 for i, w in enumerate(tokens)]
        (out / "aligned.json").write_text(json.dumps({"words": words}), encoding="utf-8")
        if not (out / "transcript.json").exists():
            (out / "transcript.json").write_text(json.dumps({"words": words}), encoding="utf-8")
    return run


def test_align_writes_timing_and_subtitle_files(mv_ws, filed_song):
    spec_id, _ = filed_song()
    calls = []
    result = align(load_workspace(), spec_id, runner=fake_worker(calls))
    paths = video_song(load_workspace(), spec_id).paths
    assert calls == [["timing", str(paths.song), str(paths.align_input), "en", str(paths.root)]]
    timing = json.loads(paths.timing.read_text(encoding="utf-8"))
    assert result.timing_path == paths.timing
    assert len(timing["words"]) == 12 and len(timing["lines"]) == 2
    assert [s["name"] for s in timing["sections"]] == ["Verse 1", "Chorus"]
    for ext in ("lrc", "srt", "vtt"):
        assert paths.subtitle(ext).read_text(encoding="utf-8").strip()
    assert result.lyrics_source == "spec" and result.suspects == [] and result.missing == []


def test_align_prefers_the_as_sung_lyrics(mv_ws, filed_song):
    spec_id, _ = filed_song()
    paths = video_song(load_workspace(), spec_id).paths
    paths.as_sung.parent.mkdir(parents=True, exist_ok=True)  # the video's folder (new-video makes it)
    paths.as_sung.write_text("[Verse]\nHeadlights on tonight\n", encoding="utf-8")
    result = align(load_workspace(), spec_id, runner=fake_worker([]))
    assert result.lyrics_source == "as sung"
    assert [w["text"] for w in result.timing["words"]] == ["Headlights", "on", "tonight"]


def test_align_applies_the_users_fixes(mv_ws, filed_song):
    spec_id, _ = filed_song()
    paths = video_song(load_workspace(), spec_id).paths
    paths.fixes.parent.mkdir(parents=True, exist_ok=True)  # the video's folder (new-video makes it)
    paths.fixes.write_text(yaml.safe_dump([{"at": 0.2, "word": "Headlights", "shift": 0.1}]), encoding="utf-8")
    result = align(load_workspace(), spec_id, runner=fake_worker([]))
    first = result.timing["words"][0]
    assert (first["start"], first["source"]) == (0.3, "fixed")
    assert result.counts["fixed"] == 1


def test_align_lists_unsure_words(mv_ws, filed_song):
    spec_id, _ = filed_song()
    result = align(load_workspace(), spec_id, runner=fake_worker([], conf=0.05))
    assert len(result.suspects) == 12


def test_align_refuses_a_word_count_mismatch(mv_ws, filed_song):
    spec_id, _ = filed_song()
    with pytest.raises(MVError, match="5 words for 12 lyric words"):
        align(load_workspace(), spec_id, runner=fake_worker([], count=5))


def test_align_refuses_an_instrumental(mv_ws, filed_song):
    spec_id, _ = filed_song(suno={"model": "v6", "styles": "x", "instrumental": True, "lyrics": ""})
    with pytest.raises(MVError, match="instrumental"):
        align(load_workspace(), spec_id, runner=fake_worker([]))


def test_force_clears_the_cached_vocals_and_transcription(mv_ws, filed_song):
    spec_id, _ = filed_song()
    align(load_workspace(), spec_id, runner=fake_worker([]))
    paths = video_song(load_workspace(), spec_id).paths
    paths.transcript.write_text('{"words": []}', encoding="utf-8")
    os.utime(paths.vocals, (1_000_000, 1_000_000))

    align(load_workspace(), spec_id, runner=fake_worker([]))
    assert json.loads(paths.transcript.read_text(encoding="utf-8"))["words"] == []
    assert paths.vocals.stat().st_mtime == 1_000_000

    align(load_workspace(), spec_id, force=True, runner=fake_worker([]))
    assert json.loads(paths.transcript.read_text(encoding="utf-8"))["words"]
    assert paths.vocals.stat().st_mtime != 1_000_000


def test_a_new_take_invalidates_the_cached_vocals(mv_ws, filed_song):
    spec_id, _ = filed_song()
    align(load_workspace(), spec_id, runner=fake_worker([]))
    paths = video_song(load_workspace(), spec_id).paths
    before = paths.vocals.stat().st_size
    filed_song(seconds=3.0, freq=330)
    align(load_workspace(), spec_id, runner=fake_worker([]))
    assert paths.vocals.stat().st_size != before


def test_a_language_change_regenerates_the_transcript(mv_ws, filed_song):
    spec_id, _ = filed_song()
    align(load_workspace(), spec_id, lang="en", runner=fake_worker([]))
    paths = video_song(load_workspace(), spec_id).paths
    paths.transcript.write_text('{"words": []}', encoding="utf-8")
    align(load_workspace(), spec_id, lang="pt", runner=fake_worker([]))
    assert json.loads(paths.transcript.read_text(encoding="utf-8"))["words"]


def test_cli_prints_a_summary(mv_ws, filed_song, monkeypatch, capsys):
    spec_id, _ = filed_song()
    monkeypatch.setattr("musicvideo.video.align.run_worker", fake_worker([]))
    assert main(["align", spec_id, "--lang", "en"]) == 0
    out = capsys.readouterr().out
    assert "12 words, 2 lines" in out and "unsure words (0): none" in out


def test_the_worker_keeps_its_environment_and_models_in_the_install_folder(tmp_path, monkeypatch):
    from musicvideo.video import align as al
    seen = {}
    monkeypatch.setattr(al.subprocess, "run", lambda cmd, env=None, **k: seen.update(env=env) or type("R", (), {"returncode": 0})())
    al.run_worker(["beats", "a", "b"])
    install = tmp_path / "install"
    assert seen["env"]["UV_CACHE_DIR"] == str(install / "uv")
    assert seen["env"]["TORCH_HOME"] == str(install / "models" / "torch")
    assert seen["env"]["HF_HOME"] == str(install / "models" / "huggingface")


# ---------------------------------------------------------------- word starts on the first sound (onsets)

import wave

import numpy as np

ONSET_RATE = 44100
_rng = np.random.default_rng(3)


def _tone(s, f=220.0):
    t = np.arange(int(s * ONSET_RATE)) / ONSET_RATE
    return 0.3 * (np.sin(2 * np.pi * f * t) + 0.5 * np.sin(4 * np.pi * f * t))


def _silence(s):
    return _rng.normal(0, 1e-4, int(s * ONSET_RATE))


def _hiss(s):
    x = _rng.normal(0, 1, int(s * ONSET_RATE))
    spec = np.fft.rfft(x)
    spec[np.fft.rfftfreq(len(x), 1 / ONSET_RATE) < 4000] = 0
    y = np.fft.irfft(spec, len(x))
    return 0.1 * y / np.abs(y).max()


def _write_wav(path, samples):
    data = (np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes()
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(ONSET_RATE)
        f.writeframes(data)


def _with_stem(spec_id, samples):
    """Align once (so the cache key exists), then put a synthetic vocal stem in place of the separated one."""
    align(load_workspace(), spec_id, runner=fake_worker([]), onsets=False)
    _write_wav(video_song(load_workspace(), spec_id).paths.vocals, samples)


def _the_stem():
    """'the' (word 2, a fricative) is aligned at 0.80 s; its hiss starts at 0.65 s."""
    return np.concatenate([_tone(0.60), _silence(0.05), _hiss(0.15), _tone(3.4)])


def _video_yaml(spec_id, **values):
    folder = load_workspace().video_dir(spec_id)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "video.yaml").write_text(yaml.safe_dump({"id": spec_id, **values}), encoding="utf-8")
    return folder / "video.yaml"


def test_onsets_are_off_without_the_setting(mv_ws, filed_song):
    spec_id, _ = filed_song()
    _with_stem(spec_id, _the_stem())
    result = align(load_workspace(), spec_id, runner=fake_worker([]))
    assert result.onsets == "off (not set in video.yaml)"
    assert result.timing["words"][2]["start"] == 0.8 and not any("moved" in w for w in result.timing["words"])


def test_onsets_follow_video_yaml(mv_ws, filed_song):
    spec_id, _ = filed_song()
    _with_stem(spec_id, _the_stem())
    _video_yaml(spec_id, onsets=True)
    result = align(load_workspace(), spec_id, runner=fake_worker([]))
    words = result.timing["words"]
    assert result.onsets == "on (video.yaml)"
    assert abs(words[2]["start"] - 0.65) <= 0.01 and words[2]["source"] == "onset"
    assert words[1]["end"] == words[2]["start"]
    assert result.moves[0]["text"] == "the"


def test_a_cli_override_wins_for_one_run(mv_ws, filed_song):
    spec_id, _ = filed_song()
    _with_stem(spec_id, _the_stem())
    yaml_file = _video_yaml(spec_id, onsets=True)
    before = yaml_file.read_text(encoding="utf-8")
    result = align(load_workspace(), spec_id, runner=fake_worker([]), onsets=False)
    assert result.onsets == "off (--no-onsets)" and result.moves == []
    assert yaml_file.read_text(encoding="utf-8") == before


def test_a_shift_fix_keeps_its_old_meaning(mv_ws, filed_song):
    spec_id, _ = filed_song()
    _with_stem(spec_id, np.concatenate([_silence(0.1), _tone(4.0)]))  # the voice starts 0.1 s before Headlights
    _video_yaml(spec_id, onsets=True)
    paths = video_song(load_workspace(), spec_id).paths
    paths.fixes.write_text(yaml.safe_dump([{"at": 0.2, "word": "Headlights", "shift": 0.1}]), encoding="utf-8")
    first = align(load_workspace(), spec_id, runner=fake_worker([])).timing["words"][0]
    assert (first["start"], first["source"]) == (0.3, "fixed")


def test_cli_summary_reports_onsets(mv_ws, filed_song, monkeypatch, capsys):
    spec_id, _ = filed_song()
    _with_stem(spec_id, _the_stem())
    monkeypatch.setattr("musicvideo.video.align.run_worker", fake_worker([]))
    assert main(["align", spec_id, "--lang", "en", "--onsets"]) == 0
    line = next(l for l in capsys.readouterr().out.splitlines() if l.startswith("onsets:"))
    assert line.startswith("onsets: on (--onsets): 1 of 12 words moved")


def test_the_template_switches_onsets_on():
    template = Path(__file__).parents[1] / "music-video" / "studio" / "template" / "video.yaml"
    assert yaml.safe_load(template.read_text(encoding="utf-8"))["onsets"] is True
