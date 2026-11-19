"""music-video sections and notes: every scene of a render on one page, and notes left on its frames.

The page (127.0.0.1 only) lays the render out by the scenes in the video's scenes.ts: a strip with every section to
scale on the song, and a card per section that plays just that section. Opening a section gives a large player with
frame stepping, a filmstrip (a frame a second), its lyrics and its storyboard note, and a notes panel: a note takes
the frame on screen (song time, frame number, which render), and can carry a drawing on that frame at full size.

Notes live with the video's code, in <video>/notes/ (notes.json and the frame images), until Claude takes them into
a round of NOTES.md (`music-video notes <id>`, then `--taken <round>`).

A note belongs to the render it was left on (`on`: its label, its file and a fingerprint of the file's content). The
page shows, editable, only the notes on the render it is showing; notes on earlier renders are read-only, grouped by
render, and stay where they are (nothing is moved or deleted for being old). A notes.json moved by hand into a folder
under notes/ (notes/round-8/) is read as archived. Note numbers never repeat within a video, archived folders
included, so a frame image's name (frames/n<N>.jpg) and its address on the page always mean one picture.
"""
import base64
import hashlib
import json
import re
import shutil
import threading
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import yaml

from ..errors import MVError
from ..spec import find_spec, load_spec
from ..workspace import Workspace
from .media import need, run
from .review import load_versions, review_dir, version_label
from .timing_editor import trusted_host

PORT = 8645
TEMPLATE = Path(__file__).with_name("sections.html")
THUMB_STEP = 1.0     # seconds between filmstrip frames
THUMB_WIDTH = 320
POSTER_WIDTH = 960
MAX_BODY = 40 * 1024 * 1024
ENTRY_RE = re.compile(r"\{\s*id:\s*['\"]([a-z0-9-]+)['\"]\s*,\s*from:\s*([^,}\s]+)")
NOTE_ID_RE = re.compile(r"^n[0-9]+$")
NOTE_IMAGE_RE = re.compile(r"^((?:[A-Za-z0-9_][A-Za-z0-9._-]*/)?frames/n[0-9]+(?:-marked)?\.jpg)$")
KEY_BYTES = 1 << 20  # a render's fingerprint reads this much from each end of the file
VERSION_FILE_RE = re.compile(r"^[a-z0-9-]+-v[0-9]+\.(mp4|mov|webm|png|jpg|jpeg|webp)$")


def clock(t: float) -> str:
    """m:ss.s, as the page shows song times."""
    t = max(0.0, t)
    m = int(t // 60)
    return f"{m}:{t - m * 60:04.1f}"


# --- the sections -----------------------------------------------------------------------------------------------

def read_scenes(video_dir: Path) -> list[dict]:
    """[{id, from, note}] from scenes.ts: each `{ id: '…', from: <seconds>` entry, with the // comment lines right
    above it as its note."""
    file = video_dir / "scenes.ts"
    if not file.is_file():
        raise MVError(f"no scenes.ts in {video_dir}: the sections come from the video's code (music-video new-video)")
    scenes, notes = [], []
    for line in file.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith("//"):
            notes.append(s[2:].strip())
            continue
        for k, m in enumerate(ENTRY_RE.finditer(s)):
            try:
                start = float(m[2])
            except ValueError:
                raise MVError(f"scenes.ts: scene '{m[1]}' starts at `{m[2]}`; the sections page needs a number "
                              "of seconds there") from None
            scenes.append({"id": m[1], "from": start, "note": " ".join(notes) if k == 0 else ""})
        notes = []
    if not scenes:
        raise MVError(f"no scenes found in {file} (entries look like {{ id: 'verse', from: 0, Component: Verse }})")
    scenes.sort(key=lambda s: s["from"])
    return scenes


def section_ranges(scenes: list[dict], start: float, duration: float) -> list[dict]:
    """Each scene runs to the next one's start, the last to the end of the render; only what the render shows."""
    end = start + duration
    out = []
    for i, s in enumerate(scenes):
        to = scenes[i + 1]["from"] if i + 1 < len(scenes) else end
        a, b = max(s["from"], start), min(to, end)
        if b - a > 0.05:
            out.append({**s, "from": round(a, 3), "to": round(b, 3)})
    if not out:
        raise MVError("the render shows none of the scenes in scenes.ts (check --start)")
    return out


def song_of(ws: Workspace, video_id: str) -> str:
    meta = ws.video_dir(video_id) / "video.yaml"
    data = (yaml.safe_load(meta.read_text(encoding="utf-8")) or {}) if meta.is_file() else {}
    return str(data.get("song") or video_id)


def video_title(ws: Workspace, video_id: str) -> str:
    """The song's title (its spec), else the video's id."""
    try:
        return str(load_spec(find_spec(ws, song_of(ws, video_id))).get("title") or video_id)
    except (MVError, OSError, ValueError):
        return video_id


def lyric_lines(ws: Workspace, video_id: str) -> list[dict]:
    """[{t, words: [{t, w}]}] in song time from the song's timing.json; [] when there is none yet."""
    song = song_of(ws, video_id)
    timing = ws.work_for(song) / "public" / "timing.json"
    if not timing.is_file():
        return []
    t = json.loads(timing.read_text(encoding="utf-8"))
    words = t.get("words", [])
    lines = []
    for ln in t.get("lines", []):
        a, b = ln["words"]
        ws_ = [{"t": round(float(w["start"]), 2), "w": w["text"]} for w in words[a:b + 1]]
        if ws_:
            lines.append({"t": ws_[0]["t"], "words": ws_})
    return lines


# --- the render -------------------------------------------------------------------------------------------------

def pick_source(ws: Workspace, video_id: str, video: Path | None = None, start: float | None = None) -> dict:
    """{file, label, start}: the given render, else the newest draft kept on the review page."""
    if video is not None:
        file = video.expanduser().resolve()
        if not file.is_file():
            raise MVError(f"{file} does not exist")
        label = re.sub(r"-v([0-9]+)$", r" v\1", file.stem)        # draft-v3.mp4 → draft v3, as kept versions read
        return {"file": file, "label": label, "start": float(start or 0.0)}
    drafts = [v for v in load_versions(ws, video_id) if v["scene"] == "draft" and v.get("kind") == "video"]
    if not drafts:
        raise MVError(f"no draft of {video_id} kept yet: keep one (music-video version {video_id} <draft.mp4> "
                      "--scene draft), or pass --video <render.mp4>")
    v = max(drafts, key=lambda v: v["n"])
    return {"file": review_dir(ws, video_id) / v["file"], "label": f"draft v{v['n']}", "start": float(v.get("start") or 0)}


def render_key(file: Path) -> str | None:
    """A fingerprint of a render's content: its size and its first and last MiB (where an MP4 keeps its index), so a
    render keeps its key when moved or touched and gets a new one when rendered again. None when the file is gone."""
    try:
        size = file.stat().st_size
        h = hashlib.sha1(str(size).encode())
        with file.open("rb") as f:
            h.update(f.read(KEY_BYTES))
            if size > 2 * KEY_BYTES:
                f.seek(size - KEY_BYTES)
            h.update(f.read(KEY_BYTES))
    except OSError:
        return None
    return h.hexdigest()[:12]


def video_facts(file: Path) -> dict:
    from .media import probe
    info = probe(file)
    video = next((s for s in info["streams"] if s.get("codec_type") == "video"), None)
    if video is None:
        raise MVError(f"{file.name} has no video stream")
    num, den = (int(x) for x in video.get("avg_frame_rate", "30/1").split("/"))
    return {"duration": round(float(info["format"]["duration"]), 3), "fps": round(num / den, 3) if den else 30.0,
            "size": [int(video["width"]), int(video["height"])]}


def build_assets(folder: Path, file: Path, sections: list[dict], start: float) -> dict:
    """The filmstrip (a frame every THUMB_STEP s of the render) and a poster per section, made once per render."""
    stat = file.stat()
    key = hashlib.sha1(f"{file}|{stat.st_size}|{stat.st_mtime_ns}|{[s['from'] for s in sections]}".encode()).hexdigest()[:10]
    out = folder / key
    done = out / "ready.json"
    if done.is_file() and all(str(x).startswith("a/") for x in
                              json.loads(done.read_text(encoding="utf-8")).get("posters") or [""]):
        return json.loads(done.read_text(encoding="utf-8"))
    if out.exists():
        shutil.rmtree(out)
    (out / "thumbs").mkdir(parents=True)
    (out / "posters").mkdir()
    ffmpeg = need("ffmpeg")
    run([ffmpeg, "-nostdin", "-loglevel", "error", "-y", "-i", str(file), "-an",
         "-vf", f"fps=1/{THUMB_STEP},scale={THUMB_WIDTH}:-2", "-q:v", "5", str(out / "thumbs" / "%05d.jpg")],
        f"filmstrip for {file.name}")
    thumbs = sorted(p.name for p in (out / "thumbs").glob("*.jpg"))
    for i, s in enumerate(sections):
        mid = (s["from"] + s["to"]) / 2 - start
        run([ffmpeg, "-nostdin", "-loglevel", "error", "-y", "-ss", f"{mid:.3f}", "-i", str(file), "-frames:v", "1",
             "-vf", f"scale={POSTER_WIDTH}:-2", "-q:v", "4", str(out / "posters" / f"{i + 1:02d}.jpg")],
            f"poster for {s['id']}")
    # the addresses carry the key: a filmstrip of another render never answers for this one from the browser's cache
    assets = {"key": key, "thumbs": [{"t": round(k * THUMB_STEP, 3), "src": f"a/{key}/thumbs/{name}"}
                                     for k, name in enumerate(thumbs)],
              "posters": [f"a/{key}/posters/{i + 1:02d}.jpg" for i in range(len(sections))]}
    done.write_text(json.dumps(assets), encoding="utf-8")
    for old in folder.iterdir():   # one render's assets at a time
        if old.is_dir() and old.name != key:
            shutil.rmtree(old, ignore_errors=True)
    return assets


def grab_frame(file: Path, n: int, fps: float, out: Path) -> Path:
    """Frame n of the render, full size, as PNG (the first frame at or after a quarter frame before n's time)."""
    if not out.is_file():
        out.parent.mkdir(parents=True, exist_ok=True)
        at = max(0.0, (n - 0.25) / fps)
        run([need("ffmpeg"), "-nostdin", "-loglevel", "error", "-y", "-ss", f"{at:.4f}", "-i", str(file),
             "-frames:v", "1", str(out)], f"frame {n} of {file.name}")
    return out


# --- the notes --------------------------------------------------------------------------------------------------

def notes_dir(ws: Workspace, video_id: str) -> Path:
    return ws.video_dir(video_id) / "notes"


def on_of(note: dict) -> dict:
    """The render a note belongs to: {render, file, key}. A note from before 0.14.1 has no `on`: its own render (the
    file name only, no key) stands in."""
    on = note.get("on")
    if isinstance(on, dict):
        return {"render": on.get("render") or note.get("render"), "file": on.get("file") or note.get("render_file"),
                "key": on.get("key")}
    return {"render": note.get("render"), "file": note.get("render_file"), "key": None}


def group_of(note: dict) -> str:
    on = on_of(note)
    return f"key:{on['key']}" if on["key"] else f"file:{Path(str(on['file'] or on['render'] or '?')).name}"


def ref_of(source: dict) -> dict:
    """The `on` of a note left while the page shows source ({file, label[, key]})."""
    file = Path(source["file"])
    key = source.get("key") if "key" in source else render_key(file)
    return {"render": source["label"], "file": str(file), "key": key}


class Notes:
    """<video>/notes/notes.json and its frame images. A note taken into a round of NOTES.md is kept, read-only;
    notes.json files moved by hand into a folder under notes/ are read, never written (`archived()`)."""

    def __init__(self, folder: Path):
        self.folder = folder
        self.file = folder / "notes.json"
        self.lock = threading.Lock()

    def _data(self) -> dict:
        if not self.file.is_file():
            return {}
        return json.loads(self.file.read_text(encoding="utf-8"))

    def all(self) -> list[dict]:
        return self._data().get("notes", [])

    def archived(self) -> list[dict]:
        """Notes in notes/<folder>/notes.json (moved there by hand), read-only: their ids and image paths carry the
        folder (round-8/n3, round-8/frames/n3.jpg)."""
        out = []
        for file in sorted(self.folder.glob("*/notes.json")):
            sub = file.parent.name
            try:
                notes = json.loads(file.read_text(encoding="utf-8")).get("notes", [])
            except (OSError, ValueError):
                continue
            for x in notes:
                x = {**x, "id": f"{sub}/{x.get('id')}", "folder": sub}
                for k in ("image", "marked"):
                    if x.get(k):
                        x[k] = f"{sub}/{x[k]}"
                out.append(x)
        return out

    def _next(self, notes: list[dict]) -> int:
        """The next note number: past every number used in this video, in notes.json, in archived folders, in any
        frame image left under notes/, and past the stored counter (so a deleted note's number is not reused)."""
        seen = [int(x.get("n") or 0) for x in notes] + [int(self._data().get("next") or 1) - 1]
        for file in self.folder.glob("*/notes.json"):
            try:
                seen += [int(x.get("n") or 0) for x in json.loads(file.read_text(encoding="utf-8")).get("notes", [])]
            except (OSError, ValueError, TypeError):
                pass
        seen += [int(m[1]) for f in self.folder.rglob("n*.jpg") if (m := re.match(r"^n([0-9]+)", f.name))]
        return 1 + max(seen, default=0)

    def _write(self, notes: list[dict], next_n: int | None = None) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        stored = int(self._data().get("next") or 1)
        next_n = max(next_n or 1, stored, 1 + max((int(x.get("n") or 0) for x in notes), default=0))
        tmp = self.file.with_suffix(".tmp")
        tmp.write_text(json.dumps({"notes": notes, "next": next_n}, indent=1, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.file)

    def _image(self, name: str, data_url: str | None) -> str | None:
        if not data_url:
            return None
        head, _, b64 = data_url.partition(",")
        if head != "data:image/jpeg;base64":
            raise MVError("a frame image must be a JPEG data URL")
        (self.folder / "frames").mkdir(parents=True, exist_ok=True)
        (self.folder / "frames" / name).write_bytes(base64.b64decode(b64, validate=True))
        return f"frames/{name}"

    def _grabbed(self, nid: str, frame: int, grab) -> str:
        """The frame alone, full size, as JPEG (grab(n) gives its PNG)."""
        (self.folder / "frames").mkdir(parents=True, exist_ok=True)
        out = self.folder / "frames" / f"{nid}.jpg"
        run([need("ffmpeg"), "-nostdin", "-loglevel", "error", "-y", "-i", str(grab(frame)), "-q:v", "3", str(out)],
            f"frame image for note {nid}")
        return f"frames/{nid}.jpg"

    def add(self, body: dict, source: dict, fps: float, sections: list[dict], grab=None, on: dict | None = None) -> dict:
        """A note on the frame `body["frame"]` of source (the render on the page, or a version shown in Compare);
        `on` is the render the page shows, which the note belongs to (default: source itself)."""
        text = str(body.get("text") or "").strip()
        drawing = body.get("drawing") or []
        if not text and not drawing:
            raise MVError("a note needs words or a drawing")
        frame = int(body["frame"])
        if frame < 0:
            raise MVError("frame must be 0 or more")
        song = round(source["start"] + frame / fps, 3)
        section = next((s["id"] for s in sections if s["from"] <= song < s["to"]), sections[-1]["id"])
        on = on or ref_of(source)
        with self.lock:
            notes = self.all()
            n = self._next(notes)
            nid = f"n{n}"
            note = {"id": nid, "n": n, "at": datetime.now().isoformat(timespec="seconds"), "section": section,
                    "song": song, "frame": frame, "fps": fps, "render": source["label"],
                    "render_file": source["file"].name, "text": text, "drawing": drawing,
                    "image": self._grabbed(nid, frame, grab) if grab else None,
                    "marked": self._image(f"{nid}-marked.jpg", body.get("marked")), "round": None, "on": on}
            notes.append(note)
            self._write(notes, n + 1)
        return note

    def _find(self, notes: list[dict], nid: str) -> dict:
        if not NOTE_ID_RE.match(str(nid)):
            raise MVError(f"no note {nid!r}")
        note = next((x for x in notes if x["id"] == nid), None)
        if note is None:
            raise MVError(f"no note {nid!r}")
        if note["round"] is not None:
            raise MVError(f"note {nid} is already in Round {note['round']} of NOTES.md; leave a new note instead")
        return note

    def edit(self, nid: str, text: str) -> dict:
        with self.lock:
            notes = self.all()
            note = self._find(notes, nid)
            if not str(text).strip() and not note["drawing"]:
                raise MVError("a note needs words or a drawing")
            note["text"] = str(text).strip()
            self._write(notes)
        return note

    def delete(self, nid: str) -> None:
        with self.lock:
            notes = self.all()
            note = self._find(notes, nid)
            # the file names come from the note's id (checked by _find), never from paths stored in notes.json
            for name in (f"{note['id']}.jpg", f"{note['id']}-marked.jpg"):
                (self.folder / "frames" / name).unlink(missing_ok=True)
            self._write([x for x in notes if x["id"] != nid])

    def new(self, group: str | None = None) -> list[dict]:
        """The notes not yet taken into a round: of one render (a group_of key), or of every render."""
        return sorted((x for x in self.all() if x["round"] is None and (group is None or group_of(x) == group)),
                      key=lambda x: (x["song"], x["n"]))

    def take(self, round_n: int, groups: set[str] | None = None) -> list[dict]:
        """Mark the new notes (of these renders, or of every one) as taken into Round round_n of NOTES.md."""
        with self.lock:
            notes = self.all()
            taken = [x for x in notes if x["round"] is None and (groups is None or group_of(x) in groups)]
            for x in taken:
                x["round"] = round_n
            if taken:
                self._write(notes)
        return sorted(taken, key=lambda x: (x["song"], x["n"]))


def renders(store: Notes, current: dict | None = None, look_in: list[Path] | None = None,
            archived: bool = True) -> list[dict]:
    """The notes grouped by the render they belong to, newest first (by its latest note): [{group, render, file,
    key, status, path, notes}]. status: "showing" (the render on the page, `current`), "on disk" (its file is still
    there: the same content, or for a note from before 0.14.1 a file of that name in one of look_in), "changed"
    (the file was rendered again since) or "gone"."""
    groups: dict[str, dict] = {}
    for x in store.all() + (store.archived() if archived else []):
        g = group_of(x)
        on = on_of(x)
        grp = groups.setdefault(g, {"group": g, "render": on["render"], "file": on["file"], "key": on["key"],
                                    "notes": []})
        grp["notes"].append(x)
    cur = ref_of(current) if current else None
    keys: dict[str, str | None] = {}
    for grp in groups.values():
        grp["notes"].sort(key=lambda x: (x.get("round") is not None, x.get("song", 0), x.get("n", 0)))
        grp["last"] = max(str(x.get("at") or "") for x in grp["notes"])
        file = Path(str(grp["file"] or ""))
        path = None
        if grp["key"]:
            if cur and grp["key"] == cur["key"]:
                status, path = "showing", cur["file"]
            elif file.is_absolute() and file.is_file():
                if str(file) not in keys:
                    keys[str(file)] = render_key(file)
                status = "on disk" if keys[str(file)] == grp["key"] else "changed"
                path = str(file)
            else:
                status = "gone"
        else:
            if cur and file.name == Path(cur["file"]).name:
                status, path = "showing", cur["file"]
            else:
                hit = next((d / file.name for d in (look_in or []) if file.name and (d / file.name).is_file()), None)
                status, path = ("on disk", str(hit)) if hit else ("gone", None)
        grp["status"], grp["path"] = status, path
        grp["name"] = file.name
    return sorted(groups.values(), key=lambda g: g["last"], reverse=True)


def describe(notes: list[dict], folder: Path, sections: list[dict] | None = None) -> str:
    """The notes as Claude reads them: section, song time, frame of which render, the words, the images."""
    order = {s["id"]: i + 1 for i, s in enumerate(sections or [])}
    out = []
    for x in notes:
        num = f"{order[x['section']]} " if x["section"] in order else ""
        out.append(f"{x['id']} · {num}{x['section']} · song {clock(x['song'])} · frame {x['frame']} of "
                   f"{x['render']} ({x['render_file']})")
        out.append(f"  {json.dumps(x['text'], ensure_ascii=False)}" if x["text"] else "  (a drawing, no words)")
        if x.get("marked"):
            out.append(f"  drawn on: {folder / x['marked']}")
        if x.get("image"):
            out.append(f"  the frame: {folder / x['image']}")
    return "\n".join(out)


# --- the server -------------------------------------------------------------------------------------------------

class Sections:
    def __init__(self, ws: Workspace, video_id: str, video: Path | None = None, start: float | None = None,
                 log=print):
        self.ws, self.video_id = ws, video_id
        self.source = pick_source(ws, video_id, video, start)
        self.source["key"] = render_key(self.source["file"])
        self.facts = video_facts(self.source["file"])
        self.sections = section_ranges(read_scenes(ws.video_dir(video_id)), self.source["start"],
                                       self.facts["duration"])
        self.build = ws.work_for(video_id) / "sections"
        log(f"preparing the filmstrip of {self.source['label']} ({len(self.sections)} sections)…")
        self.assets = build_assets(self.build, self.source["file"], self.sections, self.source["start"])
        self.notes = Notes(notes_dir(ws, video_id))
        self.lines = lyric_lines(ws, video_id)
        self.title = video_title(ws, video_id)

    def versions(self) -> list[dict]:
        """Every kept version that shows part of these sections (earlier drafts, scene clips, variants, stills), but
        not the render on the page: the second side of Compare."""
        media = review_dir(self.ws, self.video_id) / "media"
        lo, hi = self.sections[0]["from"], self.sections[-1]["to"]
        out = []
        for v in load_versions(self.ws, self.video_id):
            name = Path(v.get("file", "")).name
            if not VERSION_FILE_RE.match(name) or not (media / name).is_file():
                continue
            if (media / name).resolve() == Path(self.source["file"]).resolve():
                continue
            start = float(v.get("start") or 0.0)
            if v.get("kind") == "video":
                end = start + float(v.get("duration") or 0)
                if end <= lo or start >= hi:
                    continue
            elif v.get("start") is None or not lo <= start < hi:
                continue
            out.append({"key": name, "label": version_label(v), "scene": v["scene"], "n": v["n"],
                        "variant": v.get("variant"), "kind": v.get("kind"), "start": start,
                        "duration": float(v.get("duration") or 0), "fps": float(v.get("fps") or self.facts["fps"]),
                        "size": v.get("size"), "note": v.get("note", ""), "at": v.get("at", ""),
                        "src": f"/versions/{name}"})
        return out

    def version(self, key: str) -> dict:
        v = next((x for x in self.versions() if x["key"] == key), None)
        if v is None:
            raise MVError(f"no kept version {key!r} covers these sections")
        return v

    def requests(self) -> list[dict]:
        from ..requests import video_queue
        return [r for r in video_queue(self.ws, self.video_id).all() if r["kind"] == "variant"]

    def _shown(self, note: dict) -> dict:
        """A note as the page shows it: `src` is its picture's address, which changes whenever the picture does."""
        img = note.get("marked") or note.get("image")
        src = None
        if img and NOTE_IMAGE_RE.match(img):
            file = self.notes.folder / img
            v = file.stat().st_mtime_ns if file.is_file() else 0
            src = f"/notes/{img}?v={v}"
        return {**note, "src": src}

    def _mine(self, note: dict, offered: set[str] | None = None) -> bool:
        """On the render this page shows (a note from before 0.14.1: by its file name, or a version Compare offers)."""
        on = on_of(note)
        if on["key"]:
            return on["key"] == self.source["key"]
        name = Path(str(on["file"] or "")).name
        if offered is None:
            offered = {v["key"] for v in self.versions()}
        return name == Path(self.source["file"]).name or name in offered

    def my_notes(self) -> list[dict]:
        """The notes this page shows and edits: those left on its render (and on versions compared with it)."""
        offered = {v["key"] for v in self.versions()}
        return [self._shown(x) for x in self.notes.all() if self._mine(x, offered)]

    def earlier(self) -> list[dict]:
        """Notes on other renders of this video (and any moved into a folder under notes/), read-only, by render."""
        out = []
        look_in = [Path(self.source["file"]).parent, review_dir(self.ws, self.video_id) / "media"]
        offered = {v["key"] for v in self.versions()}
        for g in renders(self.notes, self.source, look_in):
            notes = [x for x in g["notes"] if x.get("folder") or not self._mine(x, offered)]
            if notes:
                out.append({"render": g["render"], "name": g["name"], "status": g["status"], "path": g["path"],
                            "notes": [self._shown(x) for x in notes]})
        return out

    def state(self) -> dict:
        return {"id": self.video_id, "title": self.title, "render": self.source["label"], "key": self.source["key"],
                "start": self.source["start"], **self.facts, "sections": self.sections, "lines": self.lines,
                "thumbs": self.assets["thumbs"], "posters": self.assets["posters"], "notes": self.my_notes(),
                "earlier": self.earlier(), "versions": self.versions(), "requests": self.requests()}

    def page(self) -> str:
        return TEMPLATE.read_text(encoding="utf-8").replace("{{TITLE}}", self.title.replace("<", "&lt;"))

    def frame(self, n: int) -> Path:
        if not 0 <= n <= round(self.facts["duration"] * self.facts["fps"]):
            raise MVError(f"no frame {n} in {self.source['label']}")
        return grab_frame(self.source["file"], n, self.facts["fps"], self.build / self.assets["key"] / "frames" / f"{n}.png")

    def version_frame(self, v: dict, n: int) -> Path:
        """Frame n of a kept version, full size (a still is its one frame)."""
        file = review_dir(self.ws, self.video_id) / "media" / v["key"]
        if v["kind"] != "video":
            return grab_frame(file, 0, 1.0, self.build / self.assets["key"] / "vframes" / f"{Path(v['key']).stem}.png")
        if not 0 <= n <= round(v["duration"] * v["fps"]):
            raise MVError(f"no frame {n} in {v['label']}")
        return grab_frame(file, n, v["fps"], self.build / self.assets["key"] / "vframes" / Path(v["key"]).stem / f"{n}.png")

    def ask(self, body: dict) -> dict:
        """A request from this page: only Make a variant, of one of its sections."""
        from ..requests import video_queue
        if body.get("kind") != "variant":
            raise MVError("this page only asks for variants")
        data = body.get("data") or {}
        if not isinstance(data, dict) or data.get("section") not in {s["id"] for s in self.sections}:
            raise MVError("no such section on this page")
        req = video_queue(self.ws, self.video_id).add("variant", data)
        return {"request": req, "requests": self.requests()}

    def act(self, body: dict) -> dict:
        action = body.get("action")
        if body.get("page") and body["page"] != self.source["key"]:
            raise MVError(f"this page was opened on another render; the page now shows {self.source['label']} "
                          "(reload it)")
        if action in ("edit", "delete") and not any(x["id"] == body.get("id") and self._mine(x)
                                                    for x in self.notes.all()):
            raise MVError(f"note {body.get('id')!r} is not on {self.source['label']}: it can be read here, not changed")
        on = ref_of(self.source)
        if action == "add" and body.get("version"):
            v = self.version(str(body["version"]))
            source = {"file": review_dir(self.ws, self.video_id) / "media" / v["key"], "label": v["label"],
                      "start": v["start"]}
            if v["kind"] != "video":
                body = {**body, "frame": 0}
            note = self.notes.add(body, source, v["fps"], self.sections, grab=lambda n: self.version_frame(v, n), on=on)
            return {"note": self._shown(note), "notes": self.my_notes()}
        if action == "add":
            note = self.notes.add(body, self.source, self.facts["fps"], self.sections, grab=self.frame, on=on)
            return {"note": self._shown(note), "notes": self.my_notes()}
        if action == "edit":
            self.notes.edit(body.get("id"), body.get("text", ""))
        elif action == "delete":
            self.notes.delete(body.get("id"))
        else:
            raise MVError(f"unknown action {action!r}")
        return {"notes": self.my_notes()}


def _range_of(header: str | None, size: int) -> tuple[int, int] | None:
    m = re.match(r"bytes=(\d*)-(\d*)$", header or "")
    if not m or (not m[1] and not m[2]):
        return None
    if m[1]:
        a, b = int(m[1]), int(m[2]) if m[2] else size - 1
    else:
        a, b = max(0, size - int(m[2])), size - 1
    return (a, min(b, size - 1)) if a < size else None


def send_file(handler: BaseHTTPRequestHandler, file: Path, kind: str, cache: str = "no-store") -> None:
    """A file, in byte ranges when asked (players seek with them). Only addresses that can never mean another file
    (the filmstrip's, which carry the render's key) are cached."""
    if not file.is_file():
        return handler.send_error(404)
    size = file.stat().st_size
    span = _range_of(handler.headers.get("Range"), size)
    a, b = span if span else (0, size - 1)
    handler.send_response(206 if span else 200)
    handler.send_header("Content-Type", kind)
    handler.send_header("Accept-Ranges", "bytes")
    handler.send_header("Content-Length", str(b - a + 1))
    if span:
        handler.send_header("Content-Range", f"bytes {a}-{b}/{size}")
    handler.send_header("Cache-Control", cache)
    handler.end_headers()
    try:
        with file.open("rb") as f:
            f.seek(a)
            left = b - a + 1
            while left > 0:
                chunk = f.read(min(1 << 20, left))
                if not chunk:
                    break
                handler.wfile.write(chunk)
                left -= len(chunk)
    except (BrokenPipeError, ConnectionResetError):
        pass   # the player moved on and dropped the request


def make_handler(app: Sections):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def do_GET(self):
            if not trusted_host(self.headers.get("Host")):
                return self.send_error(403)
            route, _, query = self.path.partition("?")
            try:
                if route == "/":
                    return self.send_bytes(app.page().encode("utf-8"), "text/html; charset=utf-8")
                if route == "/api/state":
                    return self.send_json(app.state())
                if route == "/api/render":         # the page checks it when it comes back into view
                    return self.send_json({"render": app.source["label"], "key": app.source["key"]})
                if route == "/video":
                    if dict(p.split("=", 1) for p in query.split("&") if "=" in p).get("r", app.source["key"]) \
                            != app.source["key"]:
                        return self.send_error(409, "this page was opened on another render (reload it)")
                    return self.send_file(app.source["file"], "video/mp4" if app.source["file"].suffix != ".webm"
                                          else "video/webm")
                if route == "/frame":
                    q = dict(p.split("=", 1) for p in query.split("&") if "=" in p)
                    if q.get("r", app.source["key"]) != app.source["key"]:
                        raise MVError("this page was opened on another render (reload it)")
                    return self.send_file(app.frame(int(q.get("n", "-1"))), "image/png")
                m = re.match(r"^/a/([0-9a-f]+)/(thumbs|posters)/([0-9]+\.jpg)$", route)
                if m and m[1] == app.assets["key"]:
                    return self.send_file(app.build / m[1] / m[2] / m[3], "image/jpeg", "max-age=3600, immutable")
                m = NOTE_IMAGE_RE.match(route.removeprefix("/notes/")) if route.startswith("/notes/") else None
                if m and ".." not in m[1]:
                    return self.send_file(app.notes.folder / m[1], "image/jpeg", "no-cache")
                m = re.match(r"^/versions/([^/]+)$", route)
                if m and VERSION_FILE_RE.match(m[1]):
                    v = app.version(m[1])
                    ext = Path(v["key"]).suffix.lower()
                    kind = {".webm": "video/webm", ".mov": "video/quicktime", ".png": "image/png",
                            ".webp": "image/webp"}.get(ext, "image/jpeg" if ext in (".jpg", ".jpeg") else "video/mp4")
                    return self.send_file(review_dir(app.ws, app.video_id) / "media" / v["key"], kind)
                if route == "/api/requests":
                    return self.send_json({"requests": app.requests()})
            except (MVError, ValueError) as e:
                return self.send_json({"error": str(e)}, 400)
            self.send_error(404)

        def do_POST(self):
            if not trusted_host(self.headers.get("Host")) or self.path not in ("/api/notes", "/api/request"):
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
                answer, status = (app.act(body) if self.path == "/api/notes" else app.ask(body)), 200
            except (MVError, ValueError, KeyError, TypeError) as e:
                answer, status = {"error": str(e)}, 400
            self.send_json(answer, status)

        def send_json(self, data, status: int = 200) -> None:
            self.send_bytes(json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json", status)

        def send_file(self, file: Path, kind: str, cache: str = "no-store") -> None:
            send_file(self, file, kind, cache)

        def send_bytes(self, body: bytes, kind: str, status: int = 200) -> None:
            self.send_response(status)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

    return Handler


def make_server(app: Sections, port: int = PORT) -> ThreadingHTTPServer:
    try:
        server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(app))
    except OSError as e:
        raise MVError(f"port {port} is busy ({e.strerror}): pass --port <another>") from e
    server.daemon_threads = True
    return server


def serve(ws: Workspace, video_id: str, video: Path | None = None, start: float | None = None, port: int = PORT,
          open_page: bool = False) -> None:
    app = Sections(ws, video_id, video, start)
    server = make_server(app, port)
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print(f"sections of {app.title} ({app.source['label']}): {url} (Ctrl-C stops it)", flush=True)
    print(f"notes go to {app.notes.folder}", flush=True)
    if open_page:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
