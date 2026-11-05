import json
import threading
import time

import pytest

from musicvideo import requests as rq
from musicvideo.cli import main
from musicvideo.errors import MVError


@pytest.fixture
def video(mv_ws):
    (mv_ws.video_dir("paper-boats") / "requests").parent.mkdir(parents=True)
    return "paper-boats"


def test_a_request_goes_new_taken_done_and_ids_are_never_reused(mv_ws, video):
    q = rq.video_queue(mv_ws, video)
    a = q.add("pick-lyric", {"option": "B", "round": 1, "note": "take the chorus from A"})
    assert (a["id"], a["state"], a["text"]) == ("r1", "new", "Use lyric B (round 1): take the chorus from A")
    b = q.add("message", {"note": "warmer colours, please"})
    q.cancel(b["id"])
    c = q.add("approve", {"stage": "timing"})
    assert c["id"] == "r3"                                   # r2 was cancelled, never reused
    q.take("r1", "merging B with the chorus of A")
    with pytest.raises(MVError, match="already started"):
        q.cancel("r1")
    q.update("r1", "writing lyrics.md")
    done = q.done("r1", "final lyrics written; next: the song's directions")
    assert done["state"] == "done" and done["taken_at"] and done["done_at"]
    assert [r["id"] for r in q.open()] == ["r3"]
    with pytest.raises(MVError, match="already done"):
        q.take("r1")
    with pytest.raises(MVError, match="no request"):
        q.take("r9")


@pytest.mark.parametrize("kind, data, error", [
    ("launch", {}, "unknown request"),
    ("pick-lyric", {"option": ""}, "the option is empty"),
    ("pick-lyric", {"option": "B", "colour": "red"}, "takes no colour"),
    ("create-takes", {"directions": []}, "at least one direction"),
    ("create-takes", {"directions": [0]}, "numbered from 1"),
    ("use-take", {"url": "javascript:alert(1)"}, "starts with https://"),
    ("approve", {"stage": "everything"}, "no stage"),
    ("message", {"note": "  "}, "the message is empty"),
    ("message", {"note": "x" * 4001}, "too long"),
    ("new-video", {"topic": "boats"}, "goes on the home"),
])
def test_requests_are_checked(mv_ws, video, kind, data, error):
    with pytest.raises(MVError, match=error):
        rq.video_queue(mv_ws, video).add(kind, data)


def test_new_videos_go_on_the_home_queue(mv_ws):
    home = rq.home_queue(mv_ws)
    r = home.add("new-video", {"topic": "paper boats racing down a gutter after rain"})
    assert r["text"] == "Start a video on: paper boats racing down a gutter after rain"
    with pytest.raises(MVError, match="belongs to a video"):
        home.add("message", {"note": "hi"})
    home.done(r["id"], "started paper-boats", "paper-boats")
    assert home.all()[0]["video"] == "paper-boats"


def test_refs_name_a_queue_and_a_request(mv_ws, video):
    assert rq.parse_ref("paper-boats:r3") == ("paper-boats", "r3")
    assert rq.parse_ref("_home:r1") == ("_home", "r1")
    for bad in ("paper-boats", "paper-boats:3", "paper-boats:rx"):
        with pytest.raises(MVError, match="is not a request"):
            rq.parse_ref(bad)
    with pytest.raises(MVError, match="not a video id"):
        rq.queue(mv_ws, "../x")
    with pytest.raises(MVError, match="no video folder"):
        rq.queue(mv_ws, "no-such-video")


def test_cli_lists_takes_and_finishes_requests(mv_ws, video, capsys):
    rq.home_queue(mv_ws).add("new-video", {"topic": "lanterns on a lake"})
    rq.video_queue(mv_ws, video).add("use-take", {"url": "https://example.com/song/take-2", "round": 2})
    assert main(["requests"]) == 0
    out = capsys.readouterr().out
    assert "2 open request(s)" in out and "_home:r1 · NEW · new-video" in out
    assert "paper-boats:r1 · NEW · use-take" in out and "Use this take: https://example.com/song/take-2" in out
    assert main(["requests", "--take", "paper-boats:r1", "--message", "recording the download"]) == 0
    assert "paper-boats:r1 is taken" in capsys.readouterr().out
    assert main(["requests", "--done", "_home:r1", "--video", "lanterns", "--message", "started lanterns"]) == 0
    capsys.readouterr()
    assert main(["requests", video, "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert [(d["ref"], d["state"], d["message"]) for d in data] == [("paper-boats:r1", "taken", "recording the download")]
    assert main(["requests", "--done", "nope"]) == 2
    assert main(["requests", "--all", "--json"]) == 0
    assert len(json.loads(capsys.readouterr().out)) == 2


def test_wait_returns_when_a_request_arrives_and_times_out_otherwise(mv_ws, video, capsys):
    assert rq.wait_for_new(mv_ws, timeout=0.3, every=0.05) == []
    q = rq.video_queue(mv_ws, video)
    threading.Timer(0.3, lambda: q.add("message", {"note": "the boat should be red"})).start()
    t0 = time.monotonic()
    found = rq.wait_for_new(mv_ws, timeout=10, every=0.05)
    assert time.monotonic() - t0 < 5
    assert [(n, r["id"]) for n, r in found] == [("paper-boats", "r1")]
    # one already waiting: back at once, so a request is never missed
    assert main(["requests", "--wait", "--timeout", "5"]) == 0
    assert "1 new request(s)" in capsys.readouterr().out
    q.take("r1")
    assert main(["requests", "--wait", "--timeout", "0.2"]) == 0
    assert "no new requests" in capsys.readouterr().out
