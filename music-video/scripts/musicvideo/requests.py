"""music-video requests: what the user asked for on a page, queued for Claude.

A button on the home or the sections page never runs anything itself: it writes a request into a queue, Claude in
the CLI takes it (`music-video requests`), carries it out as the make skill says, and marks it done; the page shows
its progress. One queue per video, `<video>/requests/requests.json`, and one for the home itself,
`<project>/requests/requests.json`, for videos that do not exist yet.

A request is addressed as `<video>:<id>` (`night-drive:r3`), the home's queue as `_home:<id>`.
"""
import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path

from .errors import MVError
from .workspace import Workspace

HOME_QUEUE = "_home"   # `_` cannot start a video id
STATES = ("new", "taken", "done")
MAX_TEXT = 4000
REQ_ID = "r"

# kind: (fields it takes, where it can be queued: "home" or "video")
KINDS = {
    "new-video": ({"topic", "note"}, "home"),
    "pick-lyric": ({"round", "option", "note"}, "video"),
    "lyrics-again": ({"note"}, "video"),
    "create-takes": ({"directions", "note"}, "video"),
    "use-take": ({"url", "round", "note"}, "video"),
    "approve": ({"stage", "note"}, "video"),
    "variant": ({"section", "note"}, "video"),
    "clean": ({"note"}, "video"),
    "message": ({"note"}, "video"),
}
_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_LOCK = threading.Lock()


def _lock_for(file: Path) -> threading.Lock:
    """One lock per queue file in this process: the pages' servers handle each request on its own thread, with a
    queue object of its own, and two quick clicks must not both read the old list and write over each other."""
    key = os.path.abspath(file)
    with _LOCKS_LOCK:
        return _LOCKS.setdefault(key, threading.Lock())


STAGES = ("concept", "lyrics", "song", "timing", "look", "sample", "production", "delivery", "web", "cleanup")


def _text(value, what: str, required: bool = False) -> str:
    text = str(value or "").strip()
    if required and not text:
        raise MVError(f"{what} is empty")
    if len(text) > MAX_TEXT:
        raise MVError(f"{what} is too long ({len(text)} characters; {MAX_TEXT} at most)")
    return text


def _int(value, what: str) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise MVError(f"{what} must be a whole number") from None
    if n < 0 or n > 10_000:
        raise MVError(f"{what} must be 0–10000")
    return n


def clean_data(kind: str, data: dict) -> tuple[dict, str]:
    """The request's fields, checked, and one line saying what the user asked for."""
    if kind not in KINDS:
        raise MVError(f"unknown request {kind!r}")
    if not isinstance(data, dict):
        raise MVError("a request's data must be an object")
    extra = set(data) - KINDS[kind][0]
    if extra:
        raise MVError(f"a {kind} request takes no {', '.join(sorted(extra))}")
    note = _text(data.get("note"), "the note")
    tail = f": {note}" if note else ""
    if kind == "new-video":
        topic = _text(data.get("topic"), "the topic", required=True)
        return {"topic": topic, "note": note}, f"Start a video on: {topic}" + (f" ({note})" if note else "")
    if kind == "pick-lyric":
        option = _text(data.get("option"), "the option", required=True)
        if len(option) > 8:
            raise MVError("the option is a letter, like A")
        n = _int(data.get("round", 1), "the round")
        return {"round": n, "option": option, "note": note}, f"Use lyric {option} (round {n}){tail}"
    if kind == "lyrics-again":
        return {"note": note}, f"New lyric options{tail}"
    if kind == "create-takes":
        raw = data.get("directions")
        if not isinstance(raw, list) or not raw:
            raise MVError("pick at least one direction")
        dirs = sorted({_int(d, "a direction") for d in raw})
        if any(d < 1 for d in dirs):
            raise MVError("directions are numbered from 1")
        names = ", ".join(str(d) for d in dirs)
        return {"directions": dirs, "note": note}, f"Create takes for direction{'s' if len(dirs) > 1 else ''} {names}{tail}"
    if kind == "use-take":
        url = _text(data.get("url"), "the take's address", required=True)
        if not url.startswith("https://") or any(c.isspace() for c in url):
            raise MVError("a take's address starts with https:// and has no spaces")
        n = _int(data.get("round", 0), "the round")
        return {"url": url, "round": n, "note": note}, f"Use this take: {url}{tail}"
    if kind == "approve":
        stage = _text(data.get("stage"), "the stage", required=True)
        if stage not in STAGES:
            raise MVError(f"no stage {stage!r}")
        return {"stage": stage, "note": note}, f"Approve the {stage} stage{tail}"
    if kind == "variant":
        section = _text(data.get("section"), "the section", required=True)
        if len(section) > 80:
            raise MVError("the section is a scene id, as in scenes.ts")
        return {"section": section, "note": note}, f"Make a variant of {section}{tail}"
    if kind == "clean":
        return {"note": note}, f"Free the working files{tail}"
    note = _text(data.get("note"), "the message", required=True)
    return {"note": note}, note


class Requests:
    """One queue: requests.json in its folder."""

    def __init__(self, folder: Path, name: str):
        self.folder, self.name = folder, name
        self.file = folder / "requests.json"
        self.lock = _lock_for(self.file)

    def all(self) -> list[dict]:
        if not self.file.is_file():
            return []
        try:
            data = json.loads(self.file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise MVError(f"{self.file}: not valid JSON ({e.msg}); fix or delete it") from e
        return data.get("requests", [])

    def _write(self, reqs: list[dict], top: int) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        tmp = self.file.with_name(f"requests.{os.getpid()}.{threading.get_ident()}.tmp")   # a writer's own
        tmp.write_text(json.dumps({"last": top, "requests": reqs}, indent=1, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.file)

    def _top(self) -> int:
        if not self.file.is_file():
            return 0
        data = json.loads(self.file.read_text(encoding="utf-8"))
        return max([int(data.get("last") or 0), *(int(r["n"]) for r in data.get("requests", []))])

    def add(self, kind: str, data: dict) -> dict:
        where = KINDS.get(kind, (None, None))[1]
        if where == "home" and self.name != HOME_QUEUE:
            raise MVError(f"a {kind} request goes on the home, not on a video")
        if where == "video" and self.name == HOME_QUEUE:
            raise MVError(f"a {kind} request belongs to a video")
        fields, text = clean_data(kind, data)
        with self.lock:
            reqs, n = self.all(), self._top() + 1
            req = {"id": f"{REQ_ID}{n}", "n": n, "at": datetime.now().isoformat(timespec="seconds"), "kind": kind,
                   "data": fields, "text": text, "state": "new", "taken_at": None, "done_at": None, "message": "",
                   "video": None}
            reqs.append(req)
            self._write(reqs, n)
        return req

    def _find(self, reqs: list[dict], rid: str) -> dict:
        req = next((r for r in reqs if r["id"] == rid), None)
        if req is None:
            raise MVError(f"no request {self.name}:{rid}")
        return req

    def _change(self, rid: str, fn) -> dict:
        with self.lock:
            reqs = self.all()
            req = self._find(reqs, rid)
            fn(req)
            self._write([r for r in reqs if not r.get("_drop")], self._top())
        return req

    def cancel(self, rid: str) -> None:
        def drop(req):
            if req["state"] != "new":
                raise MVError(f"Claude has already started on {rid}: tell Claude instead")
            req["_drop"] = True
        self._change(rid, drop)

    def take(self, rid: str, message: str = "") -> dict:
        def go(req):
            if req["state"] == "done":
                raise MVError(f"{self.name}:{rid} is already done")
            req["state"], req["taken_at"] = "taken", datetime.now().isoformat(timespec="seconds")
            req["message"] = _text(message, "the message") or req["message"]
        return self._change(rid, go)

    def update(self, rid: str, message: str) -> dict:
        def go(req):
            if req["state"] == "done":
                raise MVError(f"{self.name}:{rid} is already done")
            if req["state"] == "new":
                req["state"], req["taken_at"] = "taken", datetime.now().isoformat(timespec="seconds")
            req["message"] = _text(message, "the message", required=True)
        return self._change(rid, go)

    def done(self, rid: str, message: str = "", video: str | None = None) -> dict:
        def go(req):
            now = datetime.now().isoformat(timespec="seconds")
            req["taken_at"] = req["taken_at"] or now
            req["state"], req["done_at"] = "done", now
            req["message"] = _text(message, "the message") or req["message"]
            if video:
                req["video"] = video
        return self._change(rid, go)

    def pending(self) -> list[dict]:
        """New and in-progress requests, oldest first."""
        return [r for r in self.all() if r["state"] != "done"]


def home_queue(ws: Workspace) -> Requests:
    return Requests(ws.home / "requests", HOME_QUEUE)


def video_queue(ws: Workspace, video_id: str) -> Requests:
    return Requests(ws.video_dir(video_id) / "requests", video_id)


def queue(ws: Workspace, name: str) -> Requests:
    if name == HOME_QUEUE:
        return home_queue(ws)
    from .spec import ID_RE
    if not ID_RE.match(name or ""):
        raise MVError(f"'{name}' is not a video id")
    if not ws.video_dir(name).is_dir():
        raise MVError(f"no video folder {ws.video_dir(name)}")
    return video_queue(ws, name)


def parse_ref(ref: str) -> tuple[str, str]:
    name, sep, rid = str(ref).partition(":")
    if not sep or not rid.startswith(REQ_ID) or not rid[1:].isdigit():
        raise MVError(f"'{ref}' is not a request: write <video>:r<n> (or {HOME_QUEUE}:r<n>), as `requests` prints it")
    return name, rid


def queues(ws: Workspace, video_id: str | None = None) -> list[Requests]:
    if video_id:
        return [queue(ws, video_id)]
    out = [home_queue(ws)]
    if ws.videos_dir.is_dir():
        out += [video_queue(ws, d.name) for d in sorted(ws.videos_dir.iterdir())
                if d.is_dir() and (d / "requests" / "requests.json").is_file()]
    return out


def describe(items: list[tuple[str, dict]]) -> str:
    """The requests as Claude reads them: where, what, the note, and the state."""
    out = []
    for name, r in items:
        state = {"new": "NEW", "taken": "in progress", "done": "done"}[r["state"]]
        out.append(f"{name}:{r['id']} · {state} · {r['kind']} · asked {r['at'].replace('T', ' ')[:16]}")
        out.append(f"  {r['text']}")
        if r["message"]:
            out.append(f"  last message: {r['message']}")
    return "\n".join(out)


def new_requests(ws: Workspace) -> list[tuple[str, dict]]:
    return [(q.name, r) for q in queues(ws) for r in q.all() if r["state"] == "new"]


def wait_for_new(ws: Workspace, timeout: float | None = None, every: float = 1.0) -> list[tuple[str, dict]]:
    """Return the new requests (anywhere) as soon as there is one, at once if one is waiting already; [] when the
    timeout passes first. Claude takes every request it is shown, so a request never wakes it twice."""
    end = None if timeout is None else time.monotonic() + timeout
    while True:
        found = new_requests(ws)
        if found or (end is not None and time.monotonic() >= end):
            return found
        time.sleep(every)
