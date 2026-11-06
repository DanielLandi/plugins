"""music-video home: every song and video on one local page, each with its ten stages, and buttons that queue
requests for Claude.

The page reads the project as it is (video.yaml, the spec, lyric-options.yaml, directions.yaml, the review versions,
the notes, the finals) and writes nothing but requests (`..requests`): Claude in the CLI carries them out. It also
starts the sections page and the timing editor for a video, inside this process, on free ports.
"""
import json
import mimetypes
import re
import threading
import webbrowser
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import yaml

from .. import requests as rq
from ..budget import cycle_start, downloads_in_cycle
from ..errors import MVError
from ..spec import ID_RE, iter_specs, load_spec
from ..spec import lyrics as spec_lyrics
from ..workspace import Workspace
from .review import load_versions, review_dir
from .sections import Notes, notes_dir, send_file
from .timing_editor import trusted_host

PORT = 8646
TEMPLATE = Path(__file__).with_name("home.html")
MAX_BODY = 256 * 1024
MAX_TEXT_FILE = 20_000

# (key, name, the video.yaml step that is this stage, the user decides at the end (✋))
STAGES = [
    ("concept", "Concept", "concept", True),
    ("lyrics", "Lyrics", "lyrics", True),
    ("song", "Song", "song", True),
    ("timing", "Timing", "timing", True),
    ("look", "Look", "look", True),
    ("sample", "Sample", "sample", True),
    ("production", "Production", "production", True),
    ("delivery", "Delivery", "delivery", False),
    ("web", "Web page", None, True),
    ("cleanup", "Clean up", None, False),
]
STEP_INDEX = {step: i for i, (_, _, step, _) in enumerate(STAGES) if step}
FINALS = {".mp4", ".mov", ".webm", ".png", ".jpg", ".jpeg", ".mp3", ".srt", ".vtt", ".lrc", ".md"}
TYPES = {".vtt": "text/vtt", ".srt": "text/plain; charset=utf-8", ".lrc": "text/plain; charset=utf-8",
         ".md": "text/plain; charset=utf-8", ".mjs": "text/javascript", ".js": "text/javascript",
         ".wasm": "application/wasm", ".glb": "model/gltf-binary", ".webp": "image/webp", ".woff2": "font/woff2",
         ".m4a": "audio/mp4"}


def _yaml(file: Path) -> dict | list | None:
    if not file.is_file():
        return None
    try:
        return yaml.safe_load(file.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise MVError(f"{file.name}: not valid YAML ({str(e).splitlines()[0]})") from e


def _meta(ws: Workspace, video_id: str) -> dict:
    data = _yaml(ws.video_dir(video_id) / "video.yaml")
    return data if isinstance(data, dict) else {}


def _spec(ws: Workspace, spec_id: str) -> dict | None:
    path = ws.specs_dir / f"{spec_id}.yaml"
    try:
        return load_spec(path) if path.is_file() else None
    except MVError:
        return None


def _mtime(*files: Path) -> float:
    return max((f.stat().st_mtime for f in files if f.exists()), default=0.0)


def _read(file: Path) -> str:
    if not file.is_file():
        return ""
    text = file.read_text(encoding="utf-8")
    return text if len(text) <= MAX_TEXT_FILE else text[:MAX_TEXT_FILE] + "\n…"


def generator_name(spec: dict | None) -> str:
    return str((spec or {}).get("generator") or "suno").capitalize()


# --- what each video has ------------------------------------------------------------------------------------------

def read_lyric_options(file: Path) -> dict:
    """{rounds: [{n, at, note, options: [{key, title, angle, lyrics}]}], final, error} from lyric-options.yaml."""
    out = {"rounds": [], "final": None, "error": None}
    try:
        data = _yaml(file)
    except MVError as e:
        return {**out, "error": str(e)}
    if data is None:
        return out
    if not isinstance(data, dict) or not isinstance(data.get("rounds", []), list):
        return {**out, "error": f"{file.name}: expected `rounds:` (a list) and `final:`"}
    for k, rnd in enumerate(data.get("rounds") or [], 1):
        if not isinstance(rnd, dict):
            continue
        options = []
        for j, o in enumerate(rnd.get("options") or []):
            if isinstance(o, dict):
                options.append({"key": str(o.get("key") or chr(65 + j)), "title": str(o.get("title") or ""),
                                "angle": str(o.get("angle") or ""), "lyrics": str(o.get("lyrics") or "")})
        out["rounds"].append({"n": int(rnd.get("n") or k), "at": str(rnd.get("at") or ""),
                              "note": str(rnd.get("note") or ""), "options": options})
    final = data.get("final")
    if isinstance(final, dict) and final.get("lyrics"):
        out["final"] = {"title": str(final.get("title") or ""), "from": str(final.get("from") or ""),
                        "lyrics": str(final["lyrics"])}
    return out


def video_lyrics(folder: Path, spec: dict | None) -> dict:
    """The lyric options, with the song's own lyrics as the final ones when no option was picked on the home.

    Videos made before the home (or songs written outside it) have no lyric-options.yaml, but their spec holds the
    lyrics that were sent to the song generator: those are the final lyrics."""
    out = read_lyric_options(folder / "lyric-options.yaml")
    text = spec_lyrics(spec).strip() if spec else ""
    if not out["final"] and text:
        out["final"] = {"title": str(spec.get("title") or ""), "from": "as sent to the song generator", "lyrics": text}
    return out


def read_directions(file: Path, generator: str) -> list[dict]:
    """[{n, name, why, styles}] from directions.yaml (a list, or `directions:` holding one)."""
    try:
        data = _yaml(file)
    except MVError:
        return []
    if isinstance(data, dict):
        data = data.get("directions")
    out = []
    for k, d in enumerate(data if isinstance(data, list) else [], 1):
        if not isinstance(d, dict):
            continue
        block = d.get(generator.lower())
        block = block if isinstance(block, dict) else next((v for v in d.values() if isinstance(v, dict)), {})
        out.append({"n": k, "name": str(d.get("name") or f"direction {k}"), "why": str(d.get("why") or ""),
                    "styles": str(block.get("styles") or "")})
    return out


DIRECTION_RE = re.compile(r"direction\s+(\d+)", re.I)


def read_takes(spec: dict | None) -> list[dict]:
    """[{round, changes, direction, url, kept}] from the spec's rounds, newest round first."""
    if not spec:
        return []
    kept = (spec.get("kept") or {}).get("take_url")
    rows = []
    for k, rnd in enumerate(spec.get("rounds") or [], 1):
        if not isinstance(rnd, dict):
            continue
        m = DIRECTION_RE.search(str(rnd.get("changes") or ""))
        for url in rnd.get("suno_urls") or []:
            url = str(url)
            if not url.startswith("https://"):
                continue
            rows.append({"round": k, "changes": str(rnd.get("changes") or ""), "direction": int(m[1]) if m else None,
                         "url": url, "kept": url == kept})
    return sorted(rows, key=lambda r: -r["round"])


def downloads(ws: Workspace) -> dict | None:
    if ws.billing_day is None or ws.download_budget is None:
        return None
    today = date.today()
    used = downloads_in_cycle((d for _, d in _specs(ws)), today, ws.billing_day)
    return {"used": used, "budget": ws.download_budget, "left": max(ws.download_budget - used, 0),
            "since": cycle_start(today, ws.billing_day).isoformat()}


def _specs(ws: Workspace):
    try:
        yield from iter_specs(ws)
    except MVError:
        return


def stage_index(meta: dict) -> int:
    """0-based index of the stage the video is at: its `step:`, and after `done` the web page, then clean up."""
    step = str(meta.get("step") or "concept")
    if step == "done":
        return 9
    return STEP_INDEX.get(step, 0)


def _waiting(meta: dict, at: str, lyrics: dict, directions: list, takes: list, spec: dict | None,
             open_reqs: list[dict]) -> str:
    said = str(meta.get("waiting") or "").strip()
    if said:
        return said
    kinds = {r["kind"] for r in open_reqs}
    if at == "lyrics" and lyrics["rounds"] and not lyrics["final"] and not kinds & {"pick-lyric", "lyrics-again"}:
        return "pick a lyric (or ask for new options)"
    if at == "song" and not kinds & {"create-takes", "use-take"}:
        if takes and not (spec or {}).get("kept"):
            return "listen to the takes and pick one"
        if directions and not takes:
            return "choose the directions to create"
    return ""


def _queue(ws: Workspace, video_id: str) -> list[dict]:
    try:
        return rq.video_queue(ws, video_id).all()
    except MVError:
        return []


def _new_notes(ws: Workspace, video_id: str) -> int:
    try:
        return len(Notes(notes_dir(ws, video_id)).new())
    except (MVError, ValueError, KeyError):
        return 0


def summary(ws: Workspace, video_id: str) -> dict:
    """One card on the home."""
    folder = ws.video_dir(video_id)
    meta = _meta(ws, video_id)
    song = str(meta.get("song") or video_id)
    spec = _spec(ws, song)
    i = stage_index(meta)
    reqs = _queue(ws, video_id)
    open_reqs = [r for r in reqs if r["state"] != "done"]
    lyrics = video_lyrics(folder, spec)
    gen = generator_name(spec)
    waiting = _waiting(meta, STAGES[i][0], lyrics, read_directions(folder / "directions.yaml", gen),
                       read_takes(spec), spec, open_reqs)
    title = str((spec or {}).get("title") or (lyrics["final"] or {}).get("title") or meta.get("title")
                or video_id.replace("-", " ").title())
    return {"id": video_id, "kind": "video", "title": title, "topic": str(meta.get("topic") or ""),
            "stage": i + 1, "stage_key": STAGES[i][0], "stage_name": STAGES[i][1], "done": meta.get("step") == "done",
            "waiting": waiting, "requests": len(open_reqs), "notes": _new_notes(ws, video_id),
            "updated": _mtime(folder / "video.yaml", folder / "JOURNAL.md", folder / "lyric-options.yaml",
                              folder / "requests" / "requests.json", folder / "notes" / "notes.json")}


def projects(ws: Workspace) -> dict:
    """Every video (folders with a video.yaml), every song with no video, and the topics queued for new videos."""
    videos = []
    if ws.videos_dir.is_dir():
        for d in sorted(ws.videos_dir.iterdir()):
            if d.is_dir() and ID_RE.match(d.name) and (d / "video.yaml").is_file():
                try:
                    videos.append(summary(ws, d.name))
                except MVError as e:
                    videos.append({"id": d.name, "kind": "video", "title": d.name, "error": str(e), "stage": 1,
                                   "stage_key": "concept", "stage_name": "Concept", "waiting": "", "requests": 0,
                                   "notes": 0, "updated": 0, "topic": "", "done": False})
    taken = {v["id"] for v in videos}
    songs = []
    for path, spec in _specs(ws):
        if path.stem in taken:
            continue
        songs.append({"id": path.stem, "kind": "song", "title": str(spec.get("title") or path.stem),
                      "status": str(spec.get("status") or "drafted"), "takes": len(read_takes(spec)),
                      "generator": generator_name(spec), "updated": _mtime(path)})
    videos.sort(key=lambda v: -v["updated"])
    songs.sort(key=lambda s: -s["updated"])
    home = rq.home_queue(ws).all()
    return {"artist": ws.artist, "videos": videos, "songs": songs, "downloads": downloads(ws),
            "queued": [r for r in home if r["state"] != "done"],
            "started": [r for r in home if r["state"] == "done"][-5:][::-1]}


def _look_sheets(ws: Workspace, video_id: str) -> list[dict]:
    frames = ws.work_for(video_id) / "renders" / "frames"
    if not frames.is_dir():
        return []
    out = []
    for d in sorted(frames.iterdir()):
        if d.is_dir() and ID_RE.match(d.name):
            for f in sorted(d.glob("*-sheet.png")):
                out.append({"look": d.name, "name": f.name, "src": f"/v/{video_id}/look/{d.name}/{f.name}"})
    return out


def _finals(ws: Workspace, video_id: str) -> list[dict]:
    folder = ws.results_for(video_id)
    if not folder.is_dir():
        return []
    return [{"name": f.name, "src": f"/v/{video_id}/results/{f.name}", "size": f.stat().st_size}
            for f in sorted(folder.iterdir())
            if f.is_file() and f.suffix.lower() in FINALS and not f.name.startswith((".", "_"))]


def _folder_size(folder: Path) -> int:
    return sum(f.stat().st_size for f in folder.rglob("*") if f.is_file()) if folder.is_dir() else 0


def detail(ws: Workspace, video_id: str) -> dict:
    """Everything the video's own view shows."""
    folder = ws.video_dir(video_id)
    if not ID_RE.match(video_id or "") or not (folder / "video.yaml").is_file():
        raise MVError(f"no video {video_id!r}")
    meta = _meta(ws, video_id)
    song = str(meta.get("song") or video_id)
    spec = _spec(ws, song)
    gen = generator_name(spec)
    card = summary(ws, video_id)
    i = card["stage"] - 1
    work, results = ws.work_for(video_id), ws.results_for(video_id)
    song_work = ws.work_for(song)
    versions = load_versions(ws, video_id)
    drafts = [v for v in versions if v["scene"] == "draft" and v.get("kind") == "video"]
    has_web = (results / "web" / "index.html").is_file()
    cleaned = meta.get("step") == "done" and not work.exists()
    review_page = review_dir(ws, video_id) / "index.html"

    links: dict[str, list[dict]] = {k: [] for k, *_ in STAGES}
    if (song_work / "preview.mp4").is_file():
        links["timing"].append({"label": "Karaoke preview", "kind": "video", "href": f"/v/{video_id}/preview.mp4"})
    if (song_work / "public" / "timing.json").is_file() and spec and spec.get("status") == "filed":
        links["timing"].append({"label": "timing editor", "kind": "open", "page": "timing"})
    if review_page.is_file():
        links["sample"].append({"label": "Review page (every version)", "kind": "link",
                                "href": f"/v/{video_id}/review/index.html"})
    if drafts:
        links["production"].append({"label": f"sections page (draft v{max(v['n'] for v in drafts)})",
                                    "kind": "open", "page": "sections"})
    if review_page.is_file():
        links["production"].append({"label": "Review page (every version)", "kind": "link",
                                    "href": f"/v/{video_id}/review/index.html"})
    if has_web:
        links["web"].append({"label": "The live page", "kind": "link", "href": f"/v/{video_id}/web/index.html"})

    stages = []
    for k, (key, name, _, hand) in enumerate(STAGES):
        if key == "web":
            state = "done" if has_web else ("optional" if k <= i else "later")
        elif key == "cleanup":
            state = "done" if cleaned else ("now" if k == i else "later")
        else:
            state = "done" if k < i else ("now" if k == i else "later")
        stages.append({"n": k + 1, "key": key, "name": name, "hand": hand, "state": state, "links": links[key]})

    return {**card, "generator": gen, "lang": str(meta.get("lang") or "en"), "song": song,
            "spec": {"status": spec.get("status"), "kept": (spec.get("kept") or {}).get("take_url")} if spec else None,
            "stages": stages, "concept": _read(folder / "CONCEPT.md"),
            "lyrics": video_lyrics(folder, spec),
            "directions": read_directions(folder / "directions.yaml", gen), "takes": read_takes(spec),
            "downloads": downloads(ws), "looks": _look_sheets(ws, video_id),
            "versions": [{"scene": v["scene"], "n": v["n"], "kind": v.get("kind"), "note": v.get("note", ""),
                          "variant": v.get("variant"), "at": v.get("at")} for v in versions],
            "finals": _finals(ws, video_id), "work_size": _folder_size(work) if work.exists() else 0,
            "requests": list(reversed(_queue(ws, video_id)))[:40], "checklist": meta.get("checklist") or []}


# --- files a video's view links to --------------------------------------------------------------------------------

def _inside(base: Path, rel: str) -> Path | None:
    """base/rel when no part starts with a dot or an underscore (hidden and working files, `..`) and it stays
    inside base."""
    parts = [p for p in rel.split("/") if p]
    if not parts or any(p.startswith((".", "_")) or "\\" in p or "\x00" in p or ":" in p for p in parts):
        return None
    target = base.joinpath(*parts)
    try:
        if not target.resolve().is_relative_to(base.resolve()):
            return None
    except OSError:
        return None
    return target if target.is_file() else None


def video_file(ws: Workspace, video_id: str, kind: str, rel: str) -> Path | None:
    if not ID_RE.match(video_id) or not ws.video_dir(video_id).is_dir():
        return None
    song = str(_meta(ws, video_id).get("song") or video_id)
    if kind == "preview.mp4" and not rel:
        f = ws.work_for(song) / "preview.mp4"
        return f if f.is_file() else None
    if kind == "look":
        f = _inside(ws.work_for(video_id) / "renders" / "frames", rel)
        return f if f and f.name.endswith("-sheet.png") else None
    if kind == "review":
        return _inside(review_dir(ws, video_id), rel or "index.html")
    if kind == "results":
        f = _inside(ws.results_for(video_id), rel)
        return f if f and "/" not in rel and f.suffix.lower() in FINALS else None
    if kind == "web":
        return _inside(ws.results_for(video_id) / "web", rel or "index.html")
    return None


def content_type(file: Path) -> str:
    ext = file.suffix.lower()
    if ext in TYPES:
        return TYPES[ext]
    kind = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
    return kind + ("; charset=utf-8" if kind.startswith("text/") or kind.endswith(("json", "javascript")) else "")


# --- the pages it starts ------------------------------------------------------------------------------------------

class Pages:
    """The sections page and the timing editor of each video, started on demand inside this process."""

    def __init__(self, ws: Workspace):
        self.ws = ws
        self.lock = threading.Lock()
        self.running: dict[tuple[str, str], tuple[ThreadingHTTPServer, str]] = {}

    def start(self, page: str, video_id: str) -> str:
        if not ID_RE.match(video_id or "") or not (self.ws.video_dir(video_id) / "video.yaml").is_file():
            raise MVError(f"no video {video_id!r}")
        with self.lock:
            if page == "sections":
                from . import sections
                stamp = sections.pick_source(self.ws, video_id)["label"]
            elif page == "timing":
                stamp = ""
            else:
                raise MVError(f"no page {page!r}")
            old = self.running.get((page, video_id))
            if old and old[1] == stamp:
                return f"http://127.0.0.1:{old[0].server_address[1]}/"
            if old:   # a newer draft: show that one
                old[0].shutdown()
                old[0].server_close()
            server = self._start(page, video_id)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            self.running[(page, video_id)] = (server, stamp)
            return f"http://127.0.0.1:{server.server_address[1]}/"

    def _start(self, page: str, video_id: str) -> ThreadingHTTPServer:
        meta = _meta(self.ws, video_id)
        if page == "sections":
            from . import sections
            return sections.make_server(sections.Sections(self.ws, video_id, log=lambda *_: None), port=0)
        from . import timing_editor
        song = str(meta.get("song") or video_id)
        return timing_editor.make_server(timing_editor.Editor(self.ws, song, str(meta.get("lang") or "en")), port=0)

    def close(self) -> None:
        with self.lock:
            for server, _ in self.running.values():
                server.shutdown()
                server.server_close()
            self.running.clear()


# --- the server ---------------------------------------------------------------------------------------------------

class Home:
    def __init__(self, ws: Workspace):
        self.ws = ws
        self.pages = Pages(ws)

    def page(self) -> str:
        return TEMPLATE.read_text(encoding="utf-8")

    def request(self, body: dict) -> dict:
        video = body.get("video")
        if video is None:
            q = rq.home_queue(self.ws)
        else:
            if not ID_RE.match(str(video)) or not (self.ws.video_dir(str(video)) / "video.yaml").is_file():
                raise MVError(f"no video {video!r}")
            q = rq.video_queue(self.ws, str(video))
        action = body.get("action", "add")
        if action == "add":
            return {"request": q.add(str(body.get("kind") or ""), body.get("data") or {})}
        if action == "cancel":
            q.cancel(str(body.get("id") or ""))
            return {"ok": True}
        raise MVError(f"unknown action {action!r}")


VIDEO_ROUTE = re.compile(r"^/v/([a-z0-9-]+)/(preview\.mp4|look|review|results|web)(?:/(.*))?$")


def make_handler(app: Home):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def do_GET(self):
            if not trusted_host(self.headers.get("Host")):
                return self.send_error(403)
            route = self.path.split("?", 1)[0]
            try:
                if route == "/":
                    return self.send_bytes(app.page().encode("utf-8"), "text/html; charset=utf-8")
                if route == "/api/state":
                    return self.send_json(projects(app.ws))
                m = re.match(r"^/api/video/([a-z0-9-]+)$", route)
                if m:
                    return self.send_json(detail(app.ws, m[1]))
                m = VIDEO_ROUTE.match(route)
                if m:
                    from urllib.parse import unquote
                    f = video_file(app.ws, m[1], m[2], unquote(m[3] or ""))
                    if f is None:
                        return self.send_error(404)
                    return send_file(self, f, content_type(f))
            except MVError as e:
                return self.send_json({"error": str(e)}, 400)
            self.send_error(404)

        def do_POST(self):
            if not trusted_host(self.headers.get("Host")) or self.path not in ("/api/request", "/api/open"):
                return self.send_error(403)
            origin = self.headers.get("Origin")
            if origin and not trusted_host(origin.split("://", 1)[-1]):
                return self.send_error(403)
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY:
                return self.send_json({"error": "too large"}, 413)
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
                if not isinstance(body, dict):
                    raise MVError("expected a JSON object")
                if self.path == "/api/open":
                    answer = {"url": app.pages.start(str(body.get("page") or ""), str(body.get("video") or ""))}
                else:
                    answer = app.request(body)
                status = 200
            except (MVError, ValueError, KeyError, TypeError) as e:
                answer, status = {"error": str(e)}, 400
            self.send_json(answer, status)

        def send_json(self, data, status: int = 200) -> None:
            self.send_bytes(json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json", status)

        def send_bytes(self, body: bytes, kind: str, status: int = 200) -> None:
            self.send_response(status)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

    return Handler


def make_server(app: Home, port: int = PORT) -> ThreadingHTTPServer:
    try:
        server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(app))
    except OSError as e:
        raise MVError(f"port {port} is busy ({e.strerror}): pass --port <another>") from e
    server.daemon_threads = True
    return server


def serve(ws: Workspace, port: int = PORT, open_page: bool = False) -> None:
    app = Home(ws)
    server = make_server(app, port)
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print(f"home of {ws.home}: {url} (Ctrl-C stops it)", flush=True)
    print("its buttons queue requests: music-video requests lists them", flush=True)
    if open_page:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        app.pages.close()
        server.server_close()
