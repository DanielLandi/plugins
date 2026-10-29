import json
import threading
import urllib.error
import urllib.request
from types import SimpleNamespace

import pytest
import yaml

from musicvideo.errors import MVError
from musicvideo.video import timing_editor
from musicvideo.video.paths import video_song
from musicvideo.video.timing_editor import (Editor, append_entries, fix_entries, landed, make_server, sung_text,
                                            trusted_host)


def word(i, text, start, end, line=0):
    return {"i": i, "text": text, "start": start, "end": end, "conf": 0.9, "source": "align", "line": line,
            "backing": False}


TIMING = {
    "version": 1, "duration": 3.0,
    "words": [word(0, "Rain", 0.4, 0.8), word(1, "9-to-5", 0.9, 1.4), word(2, "softly", 1.6, 2.4, 1)],
    "lines": [{"i": 0, "text": "Rain 9-to-5", "section": 0, "backing": False, "start": 0.4, "end": 1.4,
               "words": [0, 1]},
              {"i": 1, "text": "softly", "section": 0, "backing": False, "start": 1.6, "end": 2.4, "words": [2, 2]}],
    "sections": [{"i": 0, "name": "Verse 1", "start": 0.4, "end": 2.4, "lines": [0, 1]}],
}
SHOW = [{"word": "Nine-to-five", "show": "9-to-5"}]


def test_sung_text_maps_a_shown_word_back():
    assert sung_text("9-to-5", SHOW) == "Nine-to-five"
    assert sung_text("Rain", SHOW) == "Rain"


def test_fix_entries_use_the_shown_start_and_the_sung_word():
    entries = fix_entries(TIMING["words"], [{"i": 1, "start": 1.0004, "end": 1.5}, {"i": 0, "start": 0.5, "end": 0.9}],
                          SHOW)
    assert entries == [{"at": 0.4, "word": "Rain", "start": 0.5, "end": 0.9},
                       {"at": 0.9, "word": "Nine-to-five", "start": 1.0, "end": 1.5}]


def test_fix_entries_refuse_a_bad_word_or_a_too_short_one():
    with pytest.raises(MVError, match="no word number"):
        fix_entries(TIMING["words"], [{"i": 9, "start": 1, "end": 2}], [])
    with pytest.raises(MVError, match="shorter"):
        fix_entries(TIMING["words"], [{"i": 0, "start": 1.0, "end": 1.01}], [])


def test_append_entries_keeps_what_was_there(tmp_path):
    from datetime import datetime
    fixes = tmp_path / "timing-fixes.yaml"
    fixes.write_text("# by hand: the bridge is sung late\n- at: \"1:13\"\n  word: thunder\n  shift: 0.2", encoding="utf-8")
    append_entries(fixes, [{"at": 0.4, "word": "Rain", "start": 0.5, "end": 0.9}], datetime(2026, 10, 28, 19, 5))
    text = fixes.read_text(encoding="utf-8")
    assert text.startswith("# by hand: the bridge is sung late\n")
    assert "# timing editor, 2026-10-28 19:05\n" in text
    assert yaml.safe_load(text) == [{"at": "1:13", "word": "thunder", "shift": 0.2},
                                    {"at": 0.4, "word": "Rain", "start": 0.5, "end": 0.9}]


def test_landed_names_the_words_that_moved_elsewhere():
    assert landed(TIMING, [{"i": 0, "start": 0.4, "end": 0.8}]) == []
    assert landed(TIMING, [{"i": 0, "start": 0.5, "end": 0.8}]) == ["'Rain': placed 0.500–0.800, now 0.400–0.800"]


def test_trusted_host_is_this_computer_only():
    assert trusted_host("127.0.0.1:8644") and trusted_host("localhost:8644") and trusted_host("[::1]")
    assert not trusted_host("evil.example:8644") and not trusted_host(None)


@pytest.fixture
def editor_server(mv_ws, filed_song, monkeypatch):
    spec_id, _ = filed_song(seconds=3.0)
    paths = video_song(mv_ws, spec_id).paths
    paths.public.mkdir(parents=True, exist_ok=True)
    paths.timing.write_text(json.dumps(TIMING), encoding="utf-8")
    calls = {"align": 0, "fail": False}

    def fake_align(ws, sid, lang="en"):
        # The real align applies the fixes file: here, the editor's last entries are applied by hand.
        calls["align"] += 1
        if calls["fail"]:
            raise MVError("timing fix 'Rain' at 0.4: no such word within 3 s")
        timing = json.loads(paths.timing.read_text(encoding="utf-8"))
        for fix in yaml.safe_load(paths.fixes.read_text(encoding="utf-8")):
            w = next(w for w in timing["words"] if abs(w["start"] - fix["at"]) < 1e-6)
            w["start"], w["end"] = fix["start"], fix["end"]
        paths.timing.write_text(json.dumps(timing), encoding="utf-8")
        return SimpleNamespace(timing=timing)

    monkeypatch.setattr(timing_editor, "align", fake_align)
    monkeypatch.setattr(timing_editor, "analyze", lambda ws, sid: None)
    server = make_server(Editor(mv_ws, spec_id, "en"), port=0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}", paths, calls
    server.shutdown()
    server.server_close()


def post(url, payload):
    req = urllib.request.Request(f"{url}/save", data=json.dumps(payload).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as res:
            return res.status, json.loads(res.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_editor_serves_the_page_and_the_timing(editor_server):
    url, _, _ = editor_server
    page = urllib.request.urlopen(f"{url}/").read().decode()
    assert '"title": "Night Drive"' in page and "__CONFIG__" not in page
    assert json.loads(urllib.request.urlopen(f"{url}/timing.json").read())["words"][0]["text"] == "Rain"
    assert urllib.request.urlopen(f"{url}/audio/song").headers["Content-Type"] == "audio/mpeg"


def test_editor_refuses_another_host(editor_server):
    url, _, _ = editor_server
    req = urllib.request.Request(f"{url}/", headers={"Host": "evil.example"})
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(req)
    assert e.value.code == 403


def test_save_appends_fixes_and_returns_the_new_timing(editor_server):
    url, paths, calls = editor_server
    status, answer = post(url, {"moves": [{"i": 0, "start": 0.5, "end": 0.85}]})
    assert status == 200 and answer["saved"] == 1 and answer["off"] == []
    assert answer["timing"]["words"][0]["start"] == 0.5 and calls["align"] == 1
    assert yaml.safe_load(paths.fixes.read_text(encoding="utf-8")) == [
        {"at": 0.4, "word": "Rain", "start": 0.5, "end": 0.85}]


def test_a_failed_save_puts_the_fixes_file_back(editor_server):
    url, paths, calls = editor_server
    paths.fixes.parent.mkdir(parents=True, exist_ok=True)
    paths.fixes.write_text("# mine\n", encoding="utf-8")
    calls["fail"] = True
    status, answer = post(url, {"moves": [{"i": 0, "start": 0.5, "end": 0.85}]})
    assert status == 400 and "no such word" in answer["error"]
    assert paths.fixes.read_text(encoding="utf-8") == "# mine\n"


def test_cli_edit_timing_reads_the_video_language(mv_ws, monkeypatch):
    from musicvideo.cli import main
    seen = {}
    monkeypatch.setattr(timing_editor, "serve", lambda ws, sid, lang, port, open_page: seen.update(lang=lang, port=port))
    folder = mv_ws.video_dir("night-drive")
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "video.yaml").write_text("id: night-drive\nlang: pt\n", encoding="utf-8")
    assert main(["edit-timing", "night-drive", "--port", "9001"]) == 0
    assert seen == {"lang": "pt", "port": 9001}
