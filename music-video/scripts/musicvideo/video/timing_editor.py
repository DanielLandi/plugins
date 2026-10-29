"""music-video edit-timing: drag each word's mark on the vocal waveform to where it is sung, then save.

A local page (127.0.0.1 only) shows the song 10 s at a time like the preview's panel: the vocal waveform, 0.1 s
ticks and a mark at each word's start, which can be dragged (and the end of its bar, for the word's end). Saving
appends one timing-fixes.yaml entry per moved word, after the ones already there (hand-written entries and their
comments stay), then re-runs align and analyze. Fixes apply in file order, each to the word nearest its `at`, so an
entry's `at` is the word's start as the page showed it. If align refuses the new entries the file is put back.
"""
import json
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import yaml

from ..errors import MVError
from ..workspace import Workspace
from .align import align
from .analyze import analyze
from .paths import video_song
from .timing import MIN_WORD_S, is_show_only, too_short

PORT = 8644
TEMPLATE = Path(__file__).with_name("timing_editor.html")
LOCAL_HOSTS = {"127.0.0.1", "localhost", "[::1]"}


def clock(t: float) -> str:
    """m:ss.mmm, as the page shows times."""
    ms = round(t * 1000)
    return f"{ms // 60000}:{ms % 60000 / 1000:06.3f}"


def sung_text(text: str, fixes: list) -> str:
    """The word as sung: timing.json holds a `show:` word as shown ("9-to-5"), fixes match it as sung."""
    for fix in fixes:
        if is_show_only(fix) and str(fix["show"]) == text:
            return str(fix["word"])
    return text


def fix_entries(words: list[dict], moves: list[dict], fixes: list) -> list[dict]:
    """One entry per moved word: `at` its start as the page showed it (m:ss.mmm), and its new start and end."""
    entries = []
    for move in sorted(moves, key=lambda m: m["i"]):
        i = move["i"]
        if not (isinstance(i, int) and 0 <= i < len(words)):
            raise MVError(f"no word number {i!r} in this song's timing")
        w = words[i]
        start, end = round(float(move["start"]), 3), round(float(move["end"]), 3)
        if too_short(start, end):
            raise MVError(f"{w['text']!r} at {clock(w['start'])} would be shorter than {MIN_WORD_S} s")
        entries.append({"at": clock(float(w["start"])), "word": sung_text(w["text"], fixes),
                        "start": start, "end": end})
    return entries


def append_entries(fixes_file: Path, entries: list[dict], when: datetime) -> None:
    old = fixes_file.read_text(encoding="utf-8") if fixes_file.is_file() else ""
    block = (f"# timing editor, {when:%Y-%m-%d %H:%M}\n"
             + yaml.safe_dump(entries, sort_keys=False, allow_unicode=True, default_flow_style=False))
    fixes_file.parent.mkdir(parents=True, exist_ok=True)
    fixes_file.write_text(old + ("\n" if old and not old.endswith("\n") else "") + block, encoding="utf-8")


def landed(timing: dict, moves: list[dict]) -> list[str]:
    """Words that did not end up where the page put them (another fix or the word order won)."""
    off = []
    for move in moves:
        if move["i"] >= len(timing["words"]):
            off.append(f"word {move['i']}: missing after the re-align")
            continue
        w = timing["words"][move["i"]]
        if abs(w["start"] - move["start"]) > 0.002 or abs(w["end"] - move["end"]) > 0.002:
            off.append(f"{w['text']!r}: placed {clock(move['start'])}–{clock(move['end'])}, "
                       f"now {clock(w['start'])}–{clock(w['end'])}")
    return off


class Editor:
    def __init__(self, ws: Workspace, spec_id: str, lang: str):
        self.ws, self.spec_id, self.lang = ws, spec_id, lang
        self.song = video_song(ws, spec_id)
        p = self.song.paths
        if not p.timing.is_file():
            raise MVError(f"no timing for {spec_id}: run music-video align {spec_id} first")

    @property
    def paths(self):
        return self.song.paths

    def page(self) -> str:
        config = {"id": self.spec_id, "title": self.song.spec.get("title") or self.spec_id}
        return TEMPLATE.read_text(encoding="utf-8").replace("__CONFIG__", json.dumps(config, ensure_ascii=False))

    def fixes(self) -> list:
        f = self.paths.fixes
        return (yaml.safe_load(f.read_text(encoding="utf-8")) or []) if f.is_file() else []

    def save(self, moves: list[dict]) -> dict:
        p = self.paths
        timing = json.loads(p.timing.read_text(encoding="utf-8"))
        entries = fix_entries(timing["words"], moves, self.fixes())
        if not entries:
            return {"timing": timing, "saved": 0, "off": []}
        before = p.fixes.read_text(encoding="utf-8") if p.fixes.is_file() else None
        append_entries(p.fixes, entries, datetime.now())
        try:
            result = align(self.ws, self.spec_id, lang=self.lang)
            analyze(self.ws, self.spec_id)
        except Exception:
            if before is None:
                p.fixes.unlink(missing_ok=True)
            else:
                p.fixes.write_text(before, encoding="utf-8")
            raise
        clean = [{"i": m["i"], "start": round(float(m["start"]), 3), "end": round(float(m["end"]), 3)}
                 for m in moves]
        return {"timing": result.timing, "saved": len(entries), "off": landed(result.timing, clean)}


def trusted_host(header: str | None) -> bool:
    """Only this computer's own names: a site whose domain points here (DNS rebinding) cannot drive the editor."""
    if not header:
        return False
    host = header.rsplit(":", 1)[0] if not header.endswith("]") else header
    return host in LOCAL_HOSTS


def make_handler(editor: Editor):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def do_GET(self):
            if not trusted_host(self.headers.get("Host")):
                return self.send_error(403)
            p = editor.paths
            route = self.path.split("?", 1)[0]
            if route == "/":
                return self.send_bytes(editor.page().encode("utf-8"), "text/html; charset=utf-8")
            files = {"/timing.json": (p.timing, "application/json"),
                     "/analysis.json": (p.analysis, "application/json"),
                     "/audio/song": (p.song, "audio/mpeg"),
                     "/audio/vocals": (p.vocals if p.vocals.is_file() else p.song,
                                       "audio/wav" if p.vocals.is_file() else "audio/mpeg")}
            if route not in files or not files[route][0].is_file():
                return self.send_error(404)
            file, kind = files[route]
            self.send_bytes(file.read_bytes(), kind)

        def do_POST(self):
            if not trusted_host(self.headers.get("Host")) or self.path != "/save":
                return self.send_error(403)
            origin = self.headers.get("Origin")
            if origin and not trusted_host(origin.split("://", 1)[-1]):
                return self.send_error(403)
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
                answer, status = editor.save(body.get("moves") or []), 200
            except (MVError, ValueError, KeyError, TypeError) as e:
                answer, status = {"error": str(e)}, 400
            except Exception as e:  # the re-align failed some other way: say so on the page, keep serving
                answer, status = {"error": f"{type(e).__name__}: {e}"}, 500
            self.send_bytes(json.dumps(answer, ensure_ascii=False).encode("utf-8"), "application/json", status)

        def send_bytes(self, body: bytes, kind: str, status: int = 200) -> None:
            self.send_response(status)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

    return Handler


def make_server(editor: Editor, port: int = PORT) -> ThreadingHTTPServer:
    try:
        return ThreadingHTTPServer(("127.0.0.1", port), make_handler(editor))
    except OSError as e:
        raise MVError(f"port {port} is busy ({e.strerror}): pass --port <another>") from e


def serve(ws: Workspace, spec_id: str, lang: str, port: int = PORT, open_page: bool = False) -> None:
    server = make_server(Editor(ws, spec_id, lang), port)
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print(f"timing editor for {spec_id}: {url} (Ctrl-C stops it)", flush=True)
    if open_page:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
