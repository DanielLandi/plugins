import base64
import io
import json
import subprocess
import threading
import urllib.error
import urllib.request

import pytest

from musicvideo.cli import main
from musicvideo.errors import MVError
from musicvideo.video import sections
from musicvideo.video.sections import (Notes, Sections, describe, make_server, pick_source, read_scenes,
                                       section_ranges)

FPS = 10
STEP = 12   # each frame's grey level is N * STEP, so a grabbed frame says which one it is

SCENES_TS = """import type { SceneEntry } from '@mv/kit';

// The full video: a comment above the list, not a scene's note.
export const scenes: SceneEntry[] = [
  // the street at dusk, the first lights
  { id: 'street', from: 0, Component: Street },
  // the roof:
  // stars over the city
  { id: 'roof', from: 0.8, Component: Roof }, { id: 'sky', from: 1.4, Component: Sky },
];
"""


def write_scenes(video_dir, text=SCENES_TS):
    video_dir.mkdir(parents=True, exist_ok=True)
    (video_dir / "scenes.ts").write_text(text, encoding="utf-8")


def numbered_video(path, seconds=2.0):
    """A VP9 video whose frame N is a flat grey of level N * STEP (plays in the test browser, unlike H.264)."""
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                    f"color=c=black:s=160x90:r={FPS}:d={seconds}", "-f", "lavfi", "-i",
                    f"sine=frequency=330:duration={seconds}",
                    "-vf", f"geq=lum='N*{STEP}':cb=128:cr=128", "-c:v", "libvpx-vp9", "-crf", "4", "-b:v", "0",
                    "-g", "5", "-pix_fmt", "yuv420p", "-c:a", "libopus", "-shortest", str(path)], check=True)
    return path


def level(n):
    """Frame n's grey as an RGB image shows it: luma N*STEP expanded from the video's limited range."""
    return max(0.0, (n * STEP - 16) * 255 / 219)


def grey(png_bytes):
    from PIL import Image, ImageStat
    return ImageStat.Stat(Image.open(io.BytesIO(png_bytes)).convert("L")).mean[0]


# --- the sections ----------------------------------------------------------------------------------------------

def test_read_scenes_takes_each_entry_and_the_comments_right_above_it(tmp_path):
    write_scenes(tmp_path)
    assert read_scenes(tmp_path) == [
        {"id": "street", "from": 0.0, "note": "the street at dusk, the first lights"},
        {"id": "roof", "from": 0.8, "note": "the roof: stars over the city"},
        {"id": "sky", "from": 1.4, "note": ""}]


def test_read_scenes_reads_the_template_and_refuses_what_it_cannot_place(tmp_path):
    write_scenes(tmp_path, "export const scenes = [{ id: 'verse', from: 0, Component: Verse }, "
                           "{ id: 'chorus', from: 2.2, Component: Chorus }];\n")
    assert [(s["id"], s["from"]) for s in read_scenes(tmp_path)] == [("verse", 0.0), ("chorus", 2.2)]
    write_scenes(tmp_path, "[{ id: 'verse', from: BAR * 4, Component: Verse }]")
    with pytest.raises(MVError, match="starts at `BAR`"):
        read_scenes(tmp_path)
    write_scenes(tmp_path, "export const scenes = [];")
    with pytest.raises(MVError, match="no scenes found"):
        read_scenes(tmp_path)
    with pytest.raises(MVError, match="no scenes.ts"):
        read_scenes(tmp_path / "nowhere")


def test_sections_run_to_the_next_start_and_only_cover_the_render():
    scenes = [{"id": "a", "from": 0, "note": ""}, {"id": "b", "from": 10, "note": ""}, {"id": "c", "from": 20, "note": ""}]
    assert [(s["id"], s["from"], s["to"]) for s in section_ranges(scenes, 0, 30)] == [("a", 0, 10), ("b", 10, 20),
                                                                                        ("c", 20, 30)]
    # an excerpt from 12 s to 22 s shows the end of b and the start of c
    assert [(s["id"], s["from"], s["to"]) for s in section_ranges(scenes, 12, 10)] == [("b", 12, 20), ("c", 20, 22)]
    with pytest.raises(MVError, match="none of the scenes"):
        section_ranges([{"id": "late", "from": 10, "note": ""}], 0, 5)


def test_the_newest_draft_is_the_default_render(mv_ws, filed_song):
    spec_id, _ = filed_song()
    with pytest.raises(MVError, match="no draft of"):
        pick_source(mv_ws, spec_id)
    folder = mv_ws.work_for(spec_id) / "review"
    folder.mkdir(parents=True)
    versions = [{"scene": "draft", "n": 1, "kind": "video", "file": "media/draft-v1.mp4", "start": 0},
                {"scene": "draft", "n": 2, "kind": "video", "file": "media/draft-v2.mp4", "start": 0},
                {"scene": "roof", "n": 3, "kind": "video", "file": "media/roof-v3.mp4", "start": 5}]
    (folder / "versions.json").write_text(json.dumps({"video": spec_id, "versions": versions}), encoding="utf-8")
    src = pick_source(mv_ws, spec_id)
    assert src["label"] == "draft v2" and src["file"] == folder / "media" / "draft-v2.mp4"
    other = mv_ws.home / "draft-v7.mp4"
    other.write_bytes(b"")
    assert pick_source(mv_ws, spec_id, other, 3.0) == {"file": other.resolve(), "label": "draft v7", "start": 3.0}


# --- the notes -------------------------------------------------------------------------------------------------

SECS = [{"id": "street", "from": 0.0, "to": 0.8}, {"id": "roof", "from": 0.8, "to": 2.0}]


def test_notes_are_numbered_placed_in_their_section_and_kept_once_taken(tmp_path):
    store = Notes(tmp_path / "notes")
    src = {"file": tmp_path / "draft-v3.mp4", "label": "draft v3", "start": 0.0}
    a = store.add({"frame": 12, "text": " the roof is too dark "}, src, FPS, SECS)
    b = store.add({"frame": 3, "text": "", "drawing": [{"tool": "pen", "points": [[1, 2]]}]}, src, FPS, SECS)
    assert (a["id"], a["section"], a["song"], a["text"], a["render"]) == ("n1", "roof", 1.2, "the roof is too dark", "draft v3")
    assert b["id"] == "n2" and b["section"] == "street"
    with pytest.raises(MVError, match="needs words or a drawing"):
        store.add({"frame": 1, "text": "  "}, src, FPS, SECS)
    assert [x["id"] for x in store.new()] == ["n2", "n1"]       # song order
    store.edit("n1", "the roof is far too dark")
    taken = store.take(4)
    assert [x["id"] for x in taken] == ["n2", "n1"] and store.new() == []
    with pytest.raises(MVError, match="already in Round 4"):
        store.edit("n1", "changed my mind")
    with pytest.raises(MVError, match="already in Round 4"):
        store.delete("n1")
    c = store.add({"frame": 5, "text": "later"}, src, FPS, SECS)
    assert c["id"] == "n3"                                          # numbers are never reused
    store.delete("n3")
    with pytest.raises(MVError, match="no note"):
        store.delete("../notes")


def test_deleting_a_note_removes_only_its_own_frames(tmp_path):
    store = Notes(tmp_path / "notes")
    src = {"file": tmp_path / "d.mp4", "label": "d", "start": 0.0}
    note = store.add({"frame": 1, "text": "x"}, src, FPS, SECS)
    (store.folder / "frames").mkdir(parents=True)
    (store.folder / "frames" / "n1.jpg").write_bytes(b"frame")
    outside = tmp_path / "keep.txt"
    outside.write_text("mine", encoding="utf-8")
    data = json.loads(store.file.read_text(encoding="utf-8"))
    data["notes"][0]["marked"] = "../../keep.txt"          # a hand-edited notes.json
    store.file.write_text(json.dumps(data), encoding="utf-8")
    store.delete(note["id"])
    assert outside.is_file() and not (store.folder / "frames" / "n1.jpg").exists() and store.all() == []


def test_a_frame_image_must_be_a_jpeg_data_url(tmp_path):
    store = Notes(tmp_path / "notes")
    src = {"file": tmp_path / "d.mp4", "label": "d", "start": 0.0}
    with pytest.raises(MVError, match="JPEG data URL"):
        store.add({"frame": 1, "text": "x", "drawing": [{}], "marked": "data:text/html;base64,PGI+"}, src, FPS, SECS)


def test_describe_gives_claude_the_section_time_frame_and_images(tmp_path):
    folder = tmp_path / "notes"
    note = {"id": "n7", "section": "roof", "song": 66.6, "frame": 1998, "render": "draft v9",
            "render_file": "draft-v9.mp4", "text": "more sparkle", "image": "frames/n7.jpg",
            "marked": "frames/n7-marked.jpg"}
    text = describe([note], folder, [{"id": "street"}, {"id": "roof"}])
    assert text.splitlines()[0] == "n7 · 2 roof · song 1:06.6 · frame 1998 of draft v9 (draft-v9.mp4)"
    assert '"more sparkle"' in text and str(folder / "frames" / "n7-marked.jpg") in text


# --- the server ------------------------------------------------------------------------------------------------

@pytest.fixture
def sections_server(mv_ws, filed_song, tmp_path):
    spec_id, _ = filed_song(seconds=2.0)
    write_scenes(mv_ws.video_dir(spec_id))
    video = numbered_video(tmp_path / "draft.webm")
    app = Sections(mv_ws, spec_id, video, log=lambda *_: None)
    server = make_server(app, port=0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}", app
    server.shutdown()
    server.server_close()


def get(url, headers=None):
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers or {}), timeout=30) as r:
        return r.status, dict(r.headers), r.read()


def post(url, payload):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def test_state_carries_sections_filmstrip_and_posters(sections_server):
    url, app = sections_server
    status, _, body = get(url + "/api/state")
    state = json.loads(body)
    assert status == 200 and state["render"] == "draft" and state["fps"] == FPS
    assert [(s["id"], s["from"], s["to"]) for s in state["sections"]] == [("street", 0.0, 0.8), ("roof", 0.8, 1.4),
                                                                           ("sky", 1.4, state["duration"])]
    assert state["duration"] == pytest.approx(2.0, abs=0.05)
    assert len(state["thumbs"]) == 2 and state["thumbs"][1]["t"] == 1.0
    assert get(url + "/" + state["posters"][0])[0] == 200 and get(url + "/" + state["thumbs"][0]["src"])[0] == 200
    assert b"sections" in get(url + "/")[2]


def test_the_video_is_served_in_ranges_for_seeking(sections_server):
    url, app = sections_server
    status, headers, body = get(url + "/video", {"Range": "bytes=10-19"})
    size = app.source["file"].stat().st_size
    assert status == 206 and len(body) == 10 and headers["Content-Range"] == f"bytes 10-19/{size}"
    assert headers["Content-Type"] == "video/webm"
    assert body == app.source["file"].read_bytes()[10:20]


@pytest.mark.parametrize("n", [2, 7, 13])
def test_a_grabbed_frame_is_exactly_that_frame(sections_server, n):
    url, _ = sections_server
    status, headers, body = get(url + f"/frame?n={n}")
    assert status == 200 and headers["Content-Type"] == "image/png"
    assert grey(body) == pytest.approx(level(n), abs=4)     # neighbours differ by 14


def test_another_host_or_origin_is_refused(sections_server):
    url, _ = sections_server
    with pytest.raises(urllib.error.HTTPError) as e:
        get(url + "/api/state", {"Host": "evil.example"})
    assert e.value.code == 403
    req = urllib.request.Request(url + "/api/notes", data=b'{"action":"add","frame":1,"text":"x"}', method="POST",
                                 headers={"Content-Type": "application/json", "Origin": "http://evil.example"})
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(req, timeout=10)
    assert e.value.code == 403


def test_a_note_keeps_its_frame_and_drawing(sections_server, mv_ws):
    url, app = sections_server
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (160, 90), (255, 0, 0)).save(buf, "JPEG")
    marked = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    status, data = post(url + "/api/notes", {"action": "add", "frame": 9, "text": "the roof flickers here",
                                             "drawing": [{"tool": "circle", "colour": "#ff4d4d",
                                                          "points": [[100, 100], [300, 300]]}], "marked": marked})
    assert status == 200
    note = data["note"]
    assert (note["section"], note["song"], note["frame"]) == ("roof", 0.9, 9)
    folder = app.notes.folder
    assert folder == mv_ws.video_dir(app.video_id) / "notes"
    from PIL import ImageStat
    frame = Image.open(folder / note["image"]).convert("L")
    assert ImageStat.Stat(frame).mean[0] == pytest.approx(level(9), abs=5)
    assert (folder / note["marked"]).read_bytes() == buf.getvalue()
    assert get(url + "/notes/" + note["marked"])[0] == 200
    status, data = post(url + "/api/notes", {"action": "edit", "id": note["id"], "text": "it flickers"})
    assert status == 200 and data["notes"][0]["text"] == "it flickers"
    status, data = post(url + "/api/notes", {"action": "delete", "id": note["id"]})
    assert status == 200 and data["notes"] == [] and not (folder / note["image"]).exists()
    assert post(url + "/api/notes", {"action": "nope"})[0] == 400


def test_cli_notes_prints_the_new_ones_and_marks_them_taken(sections_server, capsys):
    url, app = sections_server
    post(url + "/api/notes", {"action": "add", "frame": 15, "text": "the sky needs stars"})
    capsys.readouterr()
    assert main(["notes", app.video_id]) == 0
    out = capsys.readouterr().out
    assert "1 new note(s)" in out and "n1 · 3 sky · song 0:01.5 · frame 15 of draft" in out
    assert '"the sky needs stars"' in out and "the frame: " in out
    assert main(["notes", app.video_id, "--taken", "5"]) == 0
    assert "1 note(s) marked as taken into Round 5" in capsys.readouterr().out
    assert main(["notes", app.video_id]) == 0
    assert "no new notes" in capsys.readouterr().out
    assert main(["notes", app.video_id, "--json", "--all"]) == 0
    assert json.loads(capsys.readouterr().out)["notes"][0]["round"] == 5


# --- the page --------------------------------------------------------------------------------------------------

def test_the_page_plays_the_flow_and_saves_notes_on_the_frame_shown(sections_server, browser_ok):
    from playwright.sync_api import sync_playwright
    url, app = sections_server
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(url + "/")
        page.evaluate("sections.ready")
        assert page.locator(".card").count() == 3
        # the flow: from the first card, one player carries on into the second card without stopping
        page.click("#flowBtn")
        page.wait_for_function("sections.st.cur === 1", timeout=8000)
        assert page.evaluate("!document.querySelector('.card video').paused")
        assert page.evaluate("[...document.querySelectorAll('.card')].findIndex(c => c.querySelector('video'))") == 1
        page.click("#flowBtn")
        # Opening carries on from where the card stopped, which is wherever the flow got to: past 0.9 s on a slow
        # runner, so the roof would open on frame 9 and never show frame 8 (#25). Put the card at its start first.
        scrub = page.locator(".card").nth(1).locator(".scrub")
        scrub.click(position={"x": 1, "y": scrub.bounding_box()["height"] / 2})
        # open the roof, step to a frame, write a note: it keeps that frame
        page.locator(".card").nth(1).locator("[data-a=open]").click()
        page.wait_for_function("document.querySelector('#dtime').textContent.includes('frame 8')")
        page.keyboard.press(".")
        page.keyboard.press(".")
        page.wait_for_function("document.querySelector('#dtime').textContent.includes('frame 10')")
        page.keyboard.press("n")
        page.keyboard.type("the roof is too dark")
        assert "frame 10" in page.text_content("#pin")
        page.keyboard.press("Enter")
        page.wait_for_function("sections.D.notes.length === 1")
        # draw on the next frame and save the drawing with words
        page.keyboard.press(".")
        page.wait_for_function("document.querySelector('#dtime').textContent.includes('frame 11')")
        page.keyboard.press("d")
        page.wait_for_selector("#ink:not([hidden])")
        box = page.locator("#ink").bounding_box()
        page.mouse.move(box["x"] + box["width"] * .3, box["y"] + box["height"] * .3)
        page.mouse.down()
        page.mouse.move(box["x"] + box["width"] * .6, box["y"] + box["height"] * .6, steps=5)
        page.mouse.up()
        page.keyboard.type("flicker here")
        page.keyboard.press("Enter")
        page.wait_for_function("sections.D.notes.length === 2")
        assert page.locator("#list .item").count() == 2 and page.is_hidden("#ink")
        browser.close()
    notes = app.notes.all()
    assert [(x["frame"], x["section"], x["text"]) for x in notes] == [(10, "roof", "the roof is too dark"),
                                                                      (11, "roof", "flicker here")]
    assert notes[0]["marked"] is None and notes[1]["drawing"][0]["tool"] == "pen"
    from PIL import Image
    marked = Image.open(app.notes.folder / notes[1]["marked"]).convert("RGB")
    assert marked.size == (160, 90)
    near = [marked.getpixel((x, y)) for x in range(68, 77) for y in range(36, 45)]
    assert any(r > 170 and g < 120 for r, g, _ in near)                             # the red pen line
    assert errors == []


def test_quick_frame_steps_add_up_whenever_a_seek_reports_back(sections_server, browser_ok):
    # A "seeked" can arrive after the frame it brought is on screen, so one from an earlier seek may land between two
    # quick presses of "." (seen as a rare stop on frame 9 in the flow test). It must not make the second press count
    # from the frame still on screen. The player is emptied after opening, so no new frame shows and the moment holds.
    from playwright.sync_api import sync_playwright
    url, _ = sections_server
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(url + "/#2")
        page.evaluate("sections.ready")
        page.wait_for_function("document.querySelector('#dtime').textContent.includes('frame 8')")
        page.evaluate("big.removeAttribute('src'); big.load()")
        page.keyboard.press(".")
        assert page.evaluate("[shownFrame, pendingFrame]") == [8, 9]                  # frame 9 is not on screen yet
        page.evaluate("new Promise((done) => { big.dispatchEvent(new Event('seeked')); "
                      "requestAnimationFrame(() => requestAnimationFrame(done)); })")   # the late one, from opening
        page.keyboard.press(".")
        assert page.evaluate("[shownFrame, pendingFrame, frameOf(big.currentTime)]") == [8, 10, 10]
        browser.close()
    assert errors == []


def test_each_card_keeps_its_place_and_buttons_explain_themselves(sections_server, browser_ok):
    from playwright.sync_api import sync_playwright
    url, app = sections_server
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(url + "/")
        page.evaluate("sections.ready")
        tile = "document.querySelector('.card video')"
        sky = page.locator(".card").nth(2)
        # pause the sky (1.4–2.0) at 1.6, play the street for a moment, then the sky again: it carries on from 1.6
        sky.locator("[data-a=play]").click()
        page.wait_for_function(f"!{tile}.paused")
        page.evaluate(f"{tile}.pause(); {tile}.currentTime = 1.6")
        page.wait_for_function(f"!{tile}.seeking")
        # the player is hidden as it lands on the street card (no glimpse of the sky's frame), then shows again.
        # Watched as it happens: the veil can lift before a later look, and the sky's own veil must be gone first.
        page.wait_for_function(f"{tile}.style.opacity === ''")
        page.evaluate(f"window.veiled = false; new MutationObserver(() => {{ if ({tile}.style.opacity === '0') "
                      f"window.veiled = true; }}).observe({tile}, {{ attributes: true, attributeFilter: ['style'] }})")
        page.locator(".card").nth(0).locator("[data-a=play]").click()
        page.wait_for_function("window.veiled", timeout=3000)
        page.wait_for_function(f"{tile}.style.opacity === ''", timeout=3000)
        page.wait_for_timeout(200)
        assert page.evaluate("sections.st.cur") == 0
        assert sky.locator(".screen img").get_attribute("src").startswith("data:image/jpeg")   # its paused frame
        assert sky.locator(".t").text_content() == "0:01.6"
        sky.locator("[data-a=play]").click()
        page.wait_for_function(f"!{tile}.paused")
        assert 1.59 <= page.evaluate(f"{tile}.currentTime") < 1.8
        page.evaluate(f"{tile}.pause()")
        # a tooltip says what Play on does
        page.locator(".card").nth(1).locator("[data-a=open]").click()
        page.hover("#donward")
        page.wait_for_selector("#tip:not([hidden])")
        assert "carries on into the next" in page.text_content("#tip")
        page.mouse.move(5, 5)
        page.wait_for_selector("#tip", state="hidden")
        # once seen, it comes back only when the pointer rests on the button for 5 s
        page.hover("#donward")
        page.wait_for_timeout(1500)
        assert page.is_hidden("#tip")
        page.wait_for_selector("#tip:not([hidden])", timeout=6000)
        page.mouse.move(5, 5)
        # another button's tooltip still shows right away the first time
        page.hover("#drawBtn")
        page.wait_for_selector("#tip:not([hidden])", timeout=1500)
        assert "draw on this frame" in page.text_content("#tip")
        # the scene's note is in italics, the lyrics are not
        assert page.evaluate("getComputedStyle(document.querySelector('#dnote')).fontStyle") == "italic"
        assert page.evaluate("getComputedStyle(document.querySelector('#dlyrics')).fontStyle") == "normal"
        browser.close()
    assert errors == []


# --- Compare and variants ----------------------------------------------------------------------------------------

def keep_variant(app, mv_ws, tmp_path):
    """A kept version of the roof (0.8–1.4 s) as variant b: its own numbered frames, starting at song 0.8."""
    media = mv_ws.work_for(app.video_id) / "review" / "media"
    media.mkdir(parents=True, exist_ok=True)
    numbered_video(media / "roof-v1.webm", seconds=0.6)
    versions = [{"scene": "roof", "n": 1, "kind": "video", "file": "media/roof-v1.webm", "start": 0.8, "duration": 0.6,
                 "fps": FPS, "size": [160, 90], "variant": "b", "note": "from above", "at": "2026-11-05T09:00:00"},
                {"scene": "intro", "n": 1, "kind": "video", "file": "media/intro-v1.webm", "start": 30, "duration": 5,
                 "fps": FPS, "at": "2026-11-05T09:00:00"}]                # outside the render: not offered
    (media.parent / "versions.json").write_text(json.dumps({"video": app.video_id, "versions": versions}),
                                                encoding="utf-8")


def test_state_offers_kept_versions_and_a_note_can_be_on_one(sections_server, mv_ws, tmp_path):
    url, app = sections_server
    keep_variant(app, mv_ws, tmp_path)
    state = json.loads(get(url + "/api/state")[2])
    assert [(v["key"], v["label"], v["start"]) for v in state["versions"]] == [("roof-v1.webm", "roof v1 (variant b)", 0.8)]
    assert get(url + "/versions/roof-v1.webm")[1]["Content-Type"] == "video/webm"
    for bad in ("/versions/intro-v1.webm", "/versions/..%2Fversions.json", "/versions/x.txt"):
        with pytest.raises(urllib.error.HTTPError):
            get(url + bad)
    status, data = post(url + "/api/notes", {"action": "add", "frame": 2, "text": "B is better here",
                                             "version": "roof-v1.webm"})
    assert status == 200
    note = data["note"]
    assert (note["render"], note["render_file"], note["song"], note["section"]) == ("roof v1 (variant b)",
                                                                                    "roof-v1.webm", 1.0, "roof")
    assert grey((app.notes.folder / note["image"]).read_bytes()) == pytest.approx(level(2), abs=5)
    assert post(url + "/api/notes", {"action": "add", "frame": 2, "text": "x", "version": "sky-v9.webm"})[0] == 400


def test_make_a_variant_queues_a_request_for_a_section_on_the_page(sections_server):
    url, app = sections_server
    status, data = post(url + "/api/request", {"kind": "variant", "data": {"section": "sky", "note": "more stars"}})
    assert status == 200 and data["request"]["text"] == "Make a variant of sky: more stars"
    assert json.loads(get(url + "/api/requests")[2])["requests"][0]["state"] == "new"
    assert post(url + "/api/request", {"kind": "variant", "data": {"section": "moon"}})[0] == 400
    assert post(url + "/api/request", {"kind": "message", "data": {"note": "hi"}})[0] == 400


def test_compare_plays_two_versions_and_takes_a_note_on_b(sections_server, mv_ws, tmp_path, browser_ok):
    from playwright.sync_api import sync_playwright
    url, app = sections_server
    keep_variant(app, mv_ws, tmp_path)
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(url + "/#2")
        page.evaluate("sections.ready")
        page.wait_for_selector("#detail:not([hidden])")
        page.keyboard.press("c")
        page.wait_for_selector("#cmp:not([hidden])")
        assert page.text_content("#clabelA") == "A · draft"
        assert page.text_content("#clabelB") == "B · roof v1 (variant b)"
        assert page.locator("#cstage video").count() == 2
        # side by side, then the wipe and the flip
        page.keyboard.press("2")
        assert "wipe-mode" in page.get_attribute("#cstage", "class")
        page.keyboard.press("3")
        page.keyboard.press("1")
        # play both in step for a moment, then pause and step to song 1.0 (A's frame 10, B's frame 2)
        page.click("#cplay")
        page.wait_for_timeout(400)
        page.click("#cplay")
        page.evaluate("document.querySelector('#cscrub').value = 0.8; document.querySelector('#cscrub').dispatchEvent(new Event('input'))")
        page.keyboard.press(".")
        page.keyboard.press(".")
        page.wait_for_function("document.querySelector('#ctime').textContent.includes('A frame 10 · B frame 2')")
        page.click("#cmpSide [data-side=b]")
        assert "Note on B · roof v1 (variant b)" in page.text_content("#pin")
        page.keyboard.press("n")
        page.keyboard.type("B: the view from above works")
        page.keyboard.press("Enter")
        page.wait_for_function("sections.D.notes.length === 1")
        # Make a variant of the sky
        page.keyboard.press("Escape")
        page.wait_for_selector("#cmp", state="hidden")
        page.keyboard.press("]")
        page.wait_for_function("sections.st.cur === 2")
        page.click("#variantBtn")
        page.fill("#varText", "the sky at dawn instead")
        page.keyboard.press("Enter")
        page.wait_for_selector(".vchip")
        assert "waiting for Claude" in page.text_content("#varchips")
        # the sky has no other version: Compare says so and points at Make a variant
        page.keyboard.press("c")
        page.wait_for_selector("#cnone:not([hidden])")
        assert "Make a variant" in page.text_content("#cnone")
        browser.close()
    note = app.notes.all()[0]
    assert (note["render"], note["frame"], note["section"], note["text"]) == ("roof v1 (variant b)", 2, "roof",
                                                                              "B: the view from above works")
    from musicvideo import requests as rq
    assert [r["data"] for r in rq.video_queue(mv_ws, app.video_id).all()] == [{"section": "sky",
                                                                               "note": "the sky at dawn instead"}]
    assert errors == []


# --- notes belong to a render ------------------------------------------------------------------------------------

def colour_video(path, colour, seconds=2.0):
    """A VP9 video of one flat colour (two renders of the same video that are easy to tell apart)."""
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                    f"color=c={colour}:s=160x90:r={FPS}:d={seconds}", "-c:v", "libvpx-vp9", "-crf", "20", "-b:v", "0",
                    "-pix_fmt", "yuv420p", str(path)], check=True)
    return path


def start_server(mv_ws, spec_id, video, port=0):
    app = Sections(mv_ws, spec_id, video, log=lambda *_: None)
    server = make_server(app, port=port)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return app, server, f"http://127.0.0.1:{server.server_address[1]}"


def stop_server(server):
    server.shutdown()
    server.server_close()


SHOWN_RGB = """(sel) => { const img = document.querySelector(sel); const c = document.createElement('canvas');
  c.width = c.height = 8; const g = c.getContext('2d'); g.drawImage(img, 0, 0, 8, 8);
  const d = g.getImageData(0, 0, 8, 8).data; const m = [0, 0, 0];
  for (let i = 0; i < d.length; i += 4) for (let k = 0; k < 3; k++) m[k] += d[i + k] / 64; return m; }"""


def test_a_note_on_the_next_render_shows_that_render_s_frame(mv_ws, filed_song, tmp_path, browser_ok):
    # The page ran on one render and its notes were moved aside by hand; then it ran on the next render, on the same
    # port. The new note's frame image on disk was right, but the notes panel showed the earlier render's picture.
    from playwright.sync_api import sync_playwright
    spec_id, _ = filed_song(seconds=2.0)
    write_scenes(mv_ws.video_dir(spec_id))
    red, blue = colour_video(tmp_path / "reel.webm", "red"), colour_video(tmp_path / "reel-r8.webm", "blue")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        app, server, url = start_server(mv_ws, spec_id, red)
        port = server.server_address[1]
        assert post(url + "/api/notes", {"action": "add", "frame": 9, "text": "on the red one"})[0] == 200
        page.goto(url + "/#2")
        page.evaluate("sections.ready")
        page.wait_for_function("document.querySelector('#list .item img')?.complete")
        assert page.evaluate(SHOWN_RGB, "#list .item img")[0] > 180                     # red
        stop_server(server)
        # moved aside by hand, frames and all, as was done between the two renders
        folder = app.notes.folder
        (folder / "round-8").mkdir()
        for name in ("notes.json", "frames"):
            (folder / name).rename(folder / "round-8" / name)
        app, server, url = start_server(mv_ws, spec_id, blue, port=port)
        status, data = post(url + "/api/notes", {"action": "add", "frame": 9, "text": "on the blue one"})
        assert status == 200
        assert grey((folder / data["note"]["image"]).read_bytes()) < 60                    # right on disk
        page.goto(url + "/#2")
        page.reload()
        page.evaluate("sections.ready")
        page.wait_for_function("document.querySelector('#list > .item img')?.complete")
        assert page.locator("#list > .item").count() == 1                                # only this render's note
        r, _, b = page.evaluate(SHOWN_RGB, "#list > .item img")
        assert b > 150 and r < 80                                                        # blue, not the red one
        # the red render's note is still there, read-only, folded under Earlier videos with its own picture
        assert "Earlier videos · 1" in page.text_content("#list details.earlier summary")
        page.click("#list details.earlier summary")
        page.wait_for_function("document.querySelector('#list .earlier .item img')?.complete")
        assert page.evaluate(SHOWN_RGB, "#list .earlier .item img")[0] > 180
        assert page.locator("#list .earlier [data-a=edit]").count() == 0
        stop_server(server)
        browser.close()
    assert errors == []


def test_note_numbers_never_repeat_even_after_notes_are_moved_aside(tmp_path):
    store = Notes(tmp_path / "notes")
    src = {"file": tmp_path / "reel.mp4", "label": "reel", "start": 0.0}
    for k in range(3):
        store.add({"frame": k, "text": f"note {k}"}, src, FPS, SECS)
    (store.folder / "frames").mkdir()
    (store.folder / "frames" / "n3.jpg").write_bytes(b"frame")
    store.delete("n3")
    assert store.add({"frame": 1, "text": "after a delete"}, src, FPS, SECS)["id"] == "n4"   # n3 is not reused
    # moved aside by hand, frames and all: the next note still carries on from n5, so frames/n5.jpg is new
    (store.folder / "round-8").mkdir()
    store.file.rename(store.folder / "round-8" / "notes.json")
    assert store.all() == []
    assert store.add({"frame": 1, "text": "on the next render"}, src, FPS, SECS)["id"] == "n5"
    # a frame image left behind counts too
    (store.folder / "frames" / "n9-marked.jpg").write_bytes(b"x")
    assert store.add({"frame": 1, "text": "x"}, src, FPS, SECS)["id"] == "n10"
    # the moved notes are read as archived: ids and pictures under their folder, never edited
    arch = store.archived()
    assert [x["id"] for x in arch] == ["round-8/n1", "round-8/n2", "round-8/n4"]
    assert arch[0]["folder"] == "round-8"
    with pytest.raises(MVError, match="no note"):
        store.edit("round-8/n1", "changed")


def test_a_render_key_follows_the_content_not_the_name_or_the_clock(tmp_path):
    a = tmp_path / "reel.mp4"
    a.write_bytes(b"A" * 3_000_000)
    key = sections.render_key(a)
    import os
    os.utime(a, (1, 1))
    moved = a.rename(tmp_path / "moved.mp4")
    assert sections.render_key(moved) == key                        # touched and moved: the same render
    moved.write_bytes(b"A" * 3_000_000 + b"B")
    assert sections.render_key(moved) != key                        # rendered again: another one
    assert sections.render_key(tmp_path / "gone.mp4") is None


def test_the_page_shows_only_its_render_s_notes_and_the_others_read_only(mv_ws, filed_song, tmp_path):
    spec_id, _ = filed_song(seconds=2.0)
    write_scenes(mv_ws.video_dir(spec_id))
    first = colour_video(tmp_path / "reel.webm", "red")
    app, server, url = start_server(mv_ws, spec_id, first)
    post(url + "/api/notes", {"action": "add", "frame": 9, "text": "too red"})
    old_key = app.source["key"]
    stop_server(server)
    # a note from before notes belonged to a render (no `on`), on a render of another name, still on disk
    legacy = colour_video(tmp_path / "reel-r6.webm", "green")
    data = json.loads(app.notes.file.read_text(encoding="utf-8"))
    data["notes"].append({"id": "n7", "n": 7, "at": "2026-11-01T10:00:00", "section": "sky", "song": 1.5, "frame": 15,
                          "fps": FPS, "render": "reel-r6", "render_file": legacy.name, "text": "older", "drawing": [],
                          "image": None, "marked": None, "round": 3})
    app.notes.file.write_text(json.dumps(data), encoding="utf-8")
    second = colour_video(tmp_path / "reel-r8.webm", "blue")
    app, server, url = start_server(mv_ws, spec_id, second)
    try:
        state = json.loads(get(url + "/api/state")[2])
        assert state["notes"] == [] and state["key"] == app.source["key"] != old_key
        assert [(g["render"], g["status"], [x["text"] for x in g["notes"]]) for g in state["earlier"]] == [
            ("reel", "on disk", ["too red"]), ("reel-r6", "on disk", ["older"])]
        # a note on the earlier render is read here, not changed
        assert post(url + "/api/notes", {"action": "edit", "id": "n1", "text": "x"})[0] == 400
        assert post(url + "/api/notes", {"action": "delete", "id": "n1"})[0] == 400
        # a page still open on the earlier render cannot leave a note on this one
        status, data = post(url + "/api/notes", {"action": "add", "frame": 3, "text": "x", "page": old_key})
        assert status == 400 and "another render" in data["error"]
        for stale in (f"/frame?n=3&r={old_key}", f"/video?r={old_key}"):
            with pytest.raises(urllib.error.HTTPError):
                get(url + stale)
        assert json.loads(get(url + "/api/render")[2]) == {"render": "reel-r8", "key": app.source["key"]}
        status, data = post(url + "/api/notes", {"action": "add", "frame": 3, "text": "blue now",
                                                 "page": app.source["key"]})
        assert status == 200 and [x["text"] for x in data["notes"]] == ["blue now"]
        note = data["note"]
        assert note["id"] == "n8" and note["on"] == {"render": "reel-r8", "file": str(second.resolve()),
                                                     "key": app.source["key"]}
        # the picture's address changes with the picture, and the browser checks it every time
        assert note["src"].startswith(f"/notes/{note['image']}?v=")
        _, headers, _ = get(url + note["src"])
        assert headers["Cache-Control"] == "no-cache"
        # the filmstrip's addresses carry the render's key; another key is not served
        state = json.loads(get(url + "/api/state")[2])
        assert state["posters"][0].startswith(f"a/{app.assets['key']}/")
        with pytest.raises(urllib.error.HTTPError):
            get(url + "/a/0123456789/posters/01.jpg")
    finally:
        stop_server(server)
    # rendered again under the same name: the notes on what was there are kept, as on a changed file
    colour_video(first, "yellow")
    groups = {g["render"]: g["status"] for g in sections.renders(app.notes, app.source)}
    assert groups == {"reel-r8": "showing", "reel": "changed", "reel-r6": "gone"}


def test_cli_notes_default_to_the_newest_render_and_group_the_rest(mv_ws, filed_song, tmp_path, capsys):
    spec_id, _ = filed_song(seconds=2.0)
    write_scenes(mv_ws.video_dir(spec_id))
    first, second = colour_video(tmp_path / "reel.webm", "red"), colour_video(tmp_path / "reel-r8.webm", "blue")
    store = sections.Notes(sections.notes_dir(mv_ws, spec_id))
    store.add({"frame": 9, "text": "on the red"}, {"file": first, "label": "reel", "start": 0.0}, FPS, SECS)
    # the red render's notes moved aside by hand, then one more left on it in place
    (store.folder / "round-8").mkdir()
    store.file.rename(store.folder / "round-8" / "notes.json")
    store.add({"frame": 4, "text": "red again"}, {"file": first, "label": "reel", "start": 0.0}, FPS, SECS)
    store.add({"frame": 12, "text": "on the blue"}, {"file": second, "label": "reel-r8", "start": 0.0}, FPS, SECS)
    data = json.loads(store.file.read_text(encoding="utf-8"))
    data["notes"][-1]["at"] = "2099-01-01T00:00:00"                 # surely the newest
    store.file.write_text(json.dumps(data), encoding="utf-8")
    capsys.readouterr()
    assert main(["notes", spec_id]) == 0
    out = capsys.readouterr().out
    assert "1 new note(s) for night-drive on reel-r8 (reel-r8.webm)" in out and '"on the blue"' in out
    assert "red" not in out.split("(also")[0] and "also 1 new note(s) on other renders" in out
    assert main(["notes", spec_id, "--render", "reel.webm"]) == 0
    out = capsys.readouterr().out
    assert '"red again"' in out and '"on the red"' not in out           # the archived folder is not new
    assert main(["notes", spec_id, "--all"]) == 0
    out = capsys.readouterr().out
    assert out.index("== reel-r8") < out.index("== reel (reel.webm)")
    assert '"on the red"' in out and "round-8/n1" in out and str(store.folder / "round-8" / "frames") not in out
    assert main(["notes", spec_id, "--render", "nope"]) == 2
    assert "renders with notes: reel-r8 (reel-r8.webm), reel (reel.webm)" in capsys.readouterr().err
    assert main(["notes", spec_id, "--taken", "9"]) == 0
    assert "1 note(s) marked as taken into Round 9 of NOTES.md (the notes on reel-r8)" in capsys.readouterr().out
    assert [x["text"] for x in store.new()] == ["red again"]          # the other render's note waits
    assert main(["notes", spec_id, "--json", "--render", "reel"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert [g["render"] for g in data["renders"]] == ["reel"] and [x["text"] for x in data["notes"]] == ["red again"]
