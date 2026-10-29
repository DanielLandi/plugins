import json
import subprocess

import pytest

from musicvideo.cli import main
from musicvideo.workspace import load_workspace
from musicvideo.video.media import duration_s, has_filter
from musicvideo.video.paths import video_song
from musicvideo.video.preview import ass_time, build_ass, line_spans, render_preview


def word(i, text, start, end, line, backing=False):
    return {"i": i, "text": text, "start": start, "end": end, "conf": 0.9, "source": "align",
            "line": line, "backing": backing}


TIMING = {
    "version": 1, "duration": 3.0,
    "words": [word(0, "Rain", 0.4, 0.8, 0), word(1, "{falls}", 0.9, 1.4, 0),
              word(2, "soft", 1.6, 2.0, 1), word(3, "ly", 2.0, 2.4, 1, backing=True)],
    "lines": [{"i": 0, "text": "Rain {falls}", "section": 0, "backing": False, "start": 0.4, "end": 1.4,
               "words": [0, 1]},
              {"i": 1, "text": "soft (ly)", "section": 0, "backing": False, "start": 1.6, "end": 2.4,
               "words": [2, 3]}],
    "sections": [{"i": 0, "name": "Verse 1", "start": 0.4, "end": 2.4, "lines": [0, 1]}],
}
ANALYSIS = {"beats": [0.5, 1.0, 1.5, 2.0], "downbeats": [0.5, 2.0],
            "sections": [{"id": "verse-1", "name": "Verse 1", "start": 0.0, "end": 3.0, "sung": True}]}


def test_ass_time():
    assert ass_time(3725.456) == "1:02:05.46"


def test_line_spans_never_overlap_and_cover_their_words():
    spans = line_spans(TIMING["lines"])
    assert spans[0][1] <= spans[1][0]
    for (a, b), line in zip(spans, TIMING["lines"]):
        assert a <= line["start"] and b >= line["end"]


def test_build_ass_has_lines_labels_and_beats():
    ass = build_ass(TIMING, ANALYSIS)
    events = [e for e in ass.splitlines() if e.startswith("Dialogue:")]
    assert sum(",Sing," in e for e in events) == 2
    assert sum(",Down," in e for e in events) == 2 and sum(",Beat," in e for e in events) == 2
    assert any(",Label," in e and "Verse 1" in e for e in events)
    assert "\\kf" in ass and "(falls)" in ass and "{falls}" not in ass
    assert "{\\i1}ly{\\i0}" in ass


def test_build_ass_without_analysis_labels_from_timing_and_has_no_beats():
    events = [e for e in build_ass(TIMING, None).splitlines() if e.startswith("Dialogue:")]
    assert not any(",Beat," in e or ",Down," in e for e in events)
    assert any(",Label," in e and "Verse 1" in e for e in events)


@pytest.fixture
def libass(requires_ffmpeg):
    if not has_filter("ass"):
        pytest.skip("ffmpeg without libass")


def test_render_preview_survives_spaces_in_paths(tmp_path, libass):
    folder = tmp_path / "my dir"
    folder.mkdir()
    song = folder / "Night Owls - Song.mp3"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=330:duration=3",
                    "-c:a", "libmp3lame", "-y", str(song)], check=True)
    ass = folder / "preview.ass"
    ass.write_text(build_ass(TIMING, ANALYSIS), encoding="utf-8")
    out = render_preview(song, song, ass, folder / "preview.mp4", duration=3.0)
    assert duration_s(out) == pytest.approx(3.0, abs=0.2)


def test_cli_preview(mv_ws, filed_song, libass, capsys):
    spec_id, _ = filed_song(seconds=3.0)
    paths = video_song(load_workspace(), spec_id).paths
    paths.timing.write_text(json.dumps(TIMING), encoding="utf-8")
    assert main(["preview", spec_id]) == 0
    out = capsys.readouterr().out
    assert str(paths.preview) in out and "no beat dots" in out
    assert paths.preview.is_file()


def test_line_spans_tight_lines_clamp_and_chain():
    lines = [{"start": 1.0, "end": 2.0}, {"start": 2.2, "end": 3.0}, {"start": 6.0, "end": 7.0}]
    assert line_spans(lines) == pytest.approx([(0.4, 2.0), (2.0, 3.4), (5.4, 7.4)])


def test_line_spans_minimum_length_floor():
    lines = [{"start": 1.0, "end": 2.0}, {"start": 2.05, "end": 2.05}, {"start": 2.3, "end": 3.0}]
    assert line_spans(lines)[1] == pytest.approx((2.0, 2.1))


def test_build_ass_exact_karaoke_centiseconds():
    ass = build_ass(TIMING, None)
    sing = [e for e in ass.splitlines() if ",Sing," in e][0]
    assert sing.endswith("{\\k40}{\\kf40}Rain {\\k10}{\\kf50}(falls)")


def test_build_ass_escapes_backslashes():
    timing = json.loads(json.dumps(TIMING))
    timing["words"][0]["text"] = "a\\b"
    ass = build_ass(timing, None)
    assert "a/b" in ass and "a\\b" not in ass


def test_render_preview_names_missing_drawtext(tmp_path, monkeypatch):
    from musicvideo.errors import MVError
    monkeypatch.setattr("musicvideo.video.preview.has_filter", lambda name: name != "drawtext")
    with pytest.raises(MVError, match="drawtext"):
        render_preview(tmp_path / "s.mp3", tmp_path / "s.mp3", tmp_path / "p.ass", tmp_path / "o.mp4", 1.0)


def test_page_x_wraps_every_page():
    from musicvideo.video.preview import PAGE_S, WIDTH, page_x
    assert page_x(0.0) == 0 and page_x(PAGE_S / 2) == WIDTH // 2
    assert page_x(PAGE_S + 1.0) == page_x(1.0) == round(WIDTH / PAGE_S)


def test_build_ass_with_duration_draws_the_waveform_panel():
    events = [e for e in build_ass(TIMING, ANALYSIS, duration=3.0).splitlines() if e.startswith("Dialogue:")]
    marks = [e for e in events if ",Mark," in e and "\\p1" not in e]
    assert [m.rsplit("}", 1)[1] for m in marks] == ["Rain", "(falls)", "soft", "ly"]
    seconds = [e.rsplit("}", 1)[1] for e in events if ",Tick," in e and "\\p1" not in e]
    assert seconds == ["0:00", "0:01", "0:02"]
    assert any(",Grid," in e and "\\p1" in e for e in events)


def test_panel_puts_each_word_on_its_own_page():
    from musicvideo.video.preview import panel_events
    words = [word(0, "late", 9.9, 10.1, 0), word(1, "early", 10.2, 10.5, 0)]
    events = panel_events(words, duration=12.0)
    late = [e for e in events if e.endswith("}late")][0]
    early = [e for e in events if e.endswith("}early")][0]
    assert late.split(",")[1] == ass_time(0.0) and late.split(",")[2] == ass_time(10.0)
    assert early.split(",")[1] == ass_time(10.0) and early.split(",")[2] == ass_time(12.0)
    assert "\\pos(1270," in late and "\\pos(29," in early


def test_build_ass_without_duration_has_no_panel():
    assert ",Mark," not in build_ass(TIMING, ANALYSIS)
