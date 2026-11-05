import json
import threading
import urllib.error
import urllib.request

import pytest

import mv_home_demo
from musicvideo import requests as rq
from musicvideo.video import home
from musicvideo.video.home import Home, detail, make_server, projects, read_lyric_options, read_takes


@pytest.fixture
def demo(mv_ws):
    return mv_ws, mv_home_demo.build(mv_ws)


def test_the_home_lists_every_video_its_stage_and_what_waits(demo):
    ws, ids = demo
    state = projects(ws)
    by = {v["id"]: v for v in state["videos"]}
    assert set(by) == {"lantern-lake", "kite-weather", "paper-boats", "tide-clock"}
    assert (by["lantern-lake"]["stage"], by["lantern-lake"]["stage_name"]) == (2, "Lyrics")
    assert by["lantern-lake"]["waiting"] == "pick a lyric (or ask for new options)"
    assert by["kite-weather"]["waiting"] == "listen to the takes and pick one"
    assert by["kite-weather"]["title"] == "Kite Weather"
    assert by["paper-boats"]["waiting"] == "notes on draft v2 (sections page)"   # what Claude wrote in video.yaml
    assert (by["paper-boats"]["requests"], by["paper-boats"]["notes"]) == (1, 1)
    assert by["tide-clock"]["stage"] == 10 and by["tide-clock"]["done"]
    assert [s["id"] for s in state["songs"]] == ["morning-ferry"]                 # a song with no video
    assert [r["data"]["topic"] for r in state["queued"]] == ["a lighthouse keeper who collects lost radio songs"]
    assert state["downloads"]["budget"] == 20


def test_a_request_in_flight_clears_the_derived_wait(demo):
    ws, _ = demo
    rq.video_queue(ws, "lantern-lake").add("pick-lyric", {"option": "B", "round": 1})
    assert {v["id"]: v for v in projects(ws)["videos"]}["lantern-lake"]["waiting"] == ""


def test_a_video_view_has_ten_stages_and_what_each_has(demo):
    ws, _ = demo
    d = detail(ws, "paper-boats")
    assert [s["name"] for s in d["stages"]] == ["Concept", "Lyrics", "Song", "Timing", "Look", "Sample", "Production",
                                                "Delivery", "Web page", "Clean up"]
    assert [s["state"] for s in d["stages"]][:8] == ["done"] * 6 + ["now", "later"]
    prod = d["stages"][6]
    assert prod["links"][0]["page"] == "sections" and "draft v2" in prod["links"][0]["label"]
    assert d["requests"][0]["kind"] == "variant"
    kite = detail(ws, "kite-weather")
    assert [x["name"] for x in kite["directions"]] == ["sunny indie pop", "warm folk", "chillwave"]
    assert kite["directions"][0]["styles"] == "indie pop, handclaps, bright guitars"
    assert [(t["round"], t["direction"]) for t in kite["takes"]] == [(2, 2), (2, 2), (1, 1), (1, 1)]
    assert kite["generator"] == "Suno"
    done = detail(ws, "tide-clock")
    assert [s["state"] for s in done["stages"]][7:] == ["done", "optional", "now"]
    assert done["work_size"] == 2048
    import shutil
    shutil.rmtree(ws.work_for("tide-clock"))
    assert detail(ws, "tide-clock")["stages"][9]["state"] == "done"            # cleaned up
    assert [f["name"] for f in done["finals"]] == ["Tide Clock (vertical).mp4", "Tide Clock.mp4", "Tide Clock.srt",
                                                   "thumbnail.png"]
    with pytest.raises(home.MVError, match="no video"):
        detail(ws, "../etc")


def test_lyric_options_are_read_leniently(tmp_path):
    f = tmp_path / "lyric-options.yaml"
    assert read_lyric_options(f) == {"rounds": [], "final": None, "error": None}
    f.write_text("rounds:\n  - options:\n      - lyrics: 'la la'\n      - title: Two\n", encoding="utf-8")
    got = read_lyric_options(f)
    assert [(o["key"], o["title"]) for o in got["rounds"][0]["options"]] == [("A", ""), ("B", "Two")]
    f.write_text("rounds: [\n", encoding="utf-8")
    assert "not valid YAML" in read_lyric_options(f)["error"]
    f.write_text("- just a list\n", encoding="utf-8")
    assert "expected `rounds:`" in read_lyric_options(f)["error"]


def test_takes_keep_only_web_addresses_and_mark_the_kept_one():
    spec = {"rounds": [{"changes": "direction 3: dusk", "suno_urls": ["https://example.com/a", "javascript:x"]}],
            "kept": {"take_url": "https://example.com/a"}}
    assert read_takes(spec) == [{"round": 1, "changes": "direction 3: dusk", "direction": 3,
                                 "url": "https://example.com/a", "kept": True}]


# --- the server ------------------------------------------------------------------------------------------------

@pytest.fixture
def home_server(demo):
    ws, ids = demo
    app = Home(ws)
    server = make_server(app, port=0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}", ws
    app.pages.close()
    server.shutdown()
    server.server_close()


def get(url, headers=None):
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers or {}), timeout=30) as r:
        return r.status, dict(r.headers), r.read()


def post(url, payload, headers=None):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST",
                                 headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def test_state_video_and_requests_over_http(home_server):
    url, ws = home_server
    assert b"<title>" in get(url + "/")[2]
    state = json.loads(get(url + "/api/state")[2])
    assert len(state["videos"]) == 4
    status, data = post(url + "/api/request", {"video": "lantern-lake", "kind": "pick-lyric",
                                               "data": {"option": "C", "round": 1, "note": "the chorus of A"}})
    assert status == 200 and data["request"]["text"] == "Use lyric C (round 1): the chorus of A"
    status, data = post(url + "/api/request", {"video": None, "kind": "new-video", "data": {"topic": "fog horns"}})
    assert status == 200 and data["request"]["id"] == "r2"
    assert post(url + "/api/request", {"video": None, "action": "cancel", "id": "r2"})[0] == 200
    assert post(url + "/api/request", {"video": "nope", "kind": "message", "data": {"note": "x"}})[0] == 400
    assert post(url + "/api/request", {"video": "lantern-lake", "kind": "launch"})[0] == 400
    view = json.loads(get(url + "/api/video/lantern-lake")[2])
    assert view["requests"][0]["state"] == "new" and view["lyrics"]["rounds"][0]["options"][2]["key"] == "C"
    with pytest.raises(urllib.error.HTTPError) as e:
        get(url + "/api/video/nope")
    assert e.value.code == 400


def test_files_come_only_from_the_videos_own_folders(home_server):
    url, ws = home_server
    status, headers, body = get(url + "/v/tide-clock/results/Tide%20Clock.mp4", {"Range": "bytes=0-1"})
    assert status == 206 and body == b"de" and headers["Content-Type"] == "video/mp4"
    (ws.results_for("tide-clock") / "notes.txt").write_text("private", encoding="utf-8")
    review = ws.work_for("paper-boats") / "review"
    (review / "index.html").write_text("<p>review</p>", encoding="utf-8")
    assert get(url + "/v/paper-boats/review/index.html")[2] == b"<p>review</p>"
    for bad in ("/v/tide-clock/results/notes.txt", "/v/tide-clock/results/..%2F..%2Fconfig.yaml",
                "/v/tide-clock/web/../../config.yaml", "/v/paper-boats/review/versions.json/../../x",
                "/v/../results/x", "/v/tide-clock/look/a/x.png", "/v/tide-clock/preview.mp4",
                "/v/paper-boats/review/.hidden"):
        with pytest.raises(urllib.error.HTTPError) as e:
            get(url + bad)
        assert e.value.code in (403, 404), bad


def test_another_host_or_origin_is_refused(home_server):
    url, _ = home_server
    with pytest.raises(urllib.error.HTTPError) as e:
        get(url + "/api/state", {"Host": "evil.example"})
    assert e.value.code == 403
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(urllib.request.Request(
            url + "/api/request", data=b'{"video":null,"kind":"new-video","data":{"topic":"x"}}', method="POST",
            headers={"Content-Type": "application/json", "Origin": "http://evil.example"}), timeout=10)
    assert e.value.code == 403


def test_opening_a_page_needs_what_it_shows(home_server):
    url, _ = home_server
    status, data = post(url + "/api/open", {"video": "lantern-lake", "page": "sections"})
    assert status == 400 and "no draft of lantern-lake" in data["error"]
    status, data = post(url + "/api/open", {"video": "lantern-lake", "page": "shell"})
    assert status == 400 and "no page" in data["error"]
