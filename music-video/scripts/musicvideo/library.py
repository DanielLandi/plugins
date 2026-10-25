"""The library: every finished video, song and lesson in the results folder as one page that any phone, tablet or TV
browser on the home network can open and play from. Read-only, and the Python standard library only: `music-video
library install` copies this file into the install folder and runs it on its own at login.

    python library.py --root <results folder> [--port 8642] [--host 0.0.0.0] [--cache <folder>]

What it shows: every folder under the root that holds videos or songs (a project, an album, a lesson unit),
newest first, titled by the first heading of its README.md. Folders whose name starts with `_` or `.` (paid
source media, working files) are never listed or served; a `web/` folder is linked as the project's live page.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import mimetypes
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
from dataclasses import asdict, dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

PORT = 8642
LABEL = "dev.music-video.library"  # the macOS login item (launchd agent)
VIDEO = {".mp4", ".m4v", ".mov", ".webm"}
AUDIO = {".mp3", ".m4a", ".aac", ".flac", ".ogg"}  # not .wav: a master copy beside its MP3
IMAGE = {".png", ".jpg", ".jpeg", ".webp"}
TRACK = {".vtt"}
# A live page (a project's web/ folder) may load these too.
WEB = {".html", ".js", ".mjs", ".css", ".json", ".svg", ".woff", ".woff2", ".ttf", ".wasm", ".glb"}
ART_NAMES = ("thumbnail", "cover", "poster")
TYPES = {".vtt": "text/vtt", ".m4v": "video/mp4", ".mjs": "text/javascript", ".glb": "model/gltf-binary",
         ".wasm": "application/wasm", ".webp": "image/webp", ".woff2": "font/woff2", ".flac": "audio/flac"}
CHUNK = 1 << 20


@dataclass
class Item:
    rel: str  # path from the root, with forward slashes
    title: str
    art: str | None = None  # an image beside it, or None (a poster frame is made on request)
    subs: str | None = None  # a .vtt beside it
    vertical: bool = False
    seconds: float | None = None


@dataclass
class Shelf:
    rel: str
    title: str
    updated: float
    videos: list[Item] = field(default_factory=list)
    songs: list[Item] = field(default_factory=list)
    live: str | None = None  # web/index.html
    art: str | None = None


def hidden(name: str) -> bool:
    """Working folders and files that are never listed or served: `_source`, `.git`, `.plexignore`…"""
    return name.startswith(("_", "."))


def natural(text: str) -> list:
    """Sort key that puts "Chapter 2" before "Chapter 10"."""
    return [int(p) if p.isdigit() else p for p in re.split(r"(\d+)", text.lower())]


def humanize(name: str) -> str:
    words = re.sub(r"[-_]+", " ", name).strip()
    return " ".join(w if any(c.isupper() for c in w) else w.capitalize() for w in words.split())


def readme_title(folder: Path) -> str | None:
    """The first heading of the folder's README.md, without a trailing "(<folder name>)"."""
    readme = folder / "README.md"
    if not readme.is_file():
        return None
    try:
        for line in readme.read_text(encoding="utf-8").splitlines():
            if line.startswith("# "):
                title = line[2:].strip().removesuffix(f"({folder.name})").strip()
                return title or None
    except (OSError, UnicodeDecodeError):
        return None
    return None


def drop_copies(names: list[str]) -> list[str]:
    """A song filed as "<artist> - <title>.mp3" next to a plain "<title>.mp3" copy: keep the filed one."""
    stems = {Path(n).stem for n in names}
    return [n for n in names if not any(other.endswith(" - " + Path(n).stem) for other in stems)]


def _art_for(folder: Path, stem: str, files: dict[str, str]) -> str | None:
    """An image beside a video: one with the video's own name, else thumbnail/cover/poster (the "(vertical)"
    variant for a vertical cut)."""
    lower = {name.lower(): name for name in files}
    vertical = "(vertical)" in stem.lower()
    candidates = [stem] + [f"{a} (vertical)" if vertical else a for a in ART_NAMES]
    for base in candidates:
        for ext in (".jpg", ".jpeg", ".png", ".webp"):
            hit = lower.get((base + ext).lower())
            if hit:
                return files[hit]
    return None


class Prober:
    """Video and song lengths, cached by file and modification time (ffprobe; none when it is missing)."""

    def __init__(self) -> None:
        self.cache: dict[tuple[str, float], float | None] = {}
        self.ffprobe = shutil.which("ffprobe")

    def seconds(self, path: Path) -> float | None:
        if not self.ffprobe:
            return None
        key = (str(path), path.stat().st_mtime)
        if key not in self.cache:
            try:
                out = subprocess.run([self.ffprobe, "-v", "error", "-show_entries", "format=duration", "-of",
                                      "csv=p=0", str(path)], capture_output=True, text=True, encoding="utf-8", timeout=20)
                self.cache[key] = float(out.stdout.strip())
            except (ValueError, subprocess.SubprocessError, OSError):
                self.cache[key] = None
        return self.cache[key]


def scan(root: Path, prober: Prober | None = None) -> list[Shelf]:
    """Every folder under root that holds videos or songs, newest first."""
    shelves: list[Shelf] = []
    root = root.resolve()
    for here, dirs, names in os.walk(root):
        folder = Path(here)
        dirs[:] = sorted(d for d in dirs if not hidden(d) and d != "web")
        visible = {n: (folder / n).relative_to(root).as_posix() for n in names if not hidden(n)}
        videos = [n for n in visible if Path(n).suffix.lower() in VIDEO]
        songs = [n for n in visible if Path(n).suffix.lower() in AUDIO]
        if not videos and not songs:
            continue
        rel = folder.relative_to(root).as_posix()
        if rel == ".":
            rel = ""
        title = readme_title(folder) or " · ".join(humanize(p) for p in rel.split("/") if p) or "Library"
        stamps = [(folder / n).stat().st_mtime for n in videos + songs]
        shelf = Shelf(rel=rel, title=title, updated=max(stamps))
        tracks = {Path(n).stem.lower(): visible[n] for n in visible if Path(n).suffix.lower() in TRACK}
        for name in sorted(videos, key=lambda n: ("(vertical)" in n.lower(), natural(n))):
            stem = Path(name).stem
            item = Item(rel=visible[name], title=stem, art=_art_for(folder, stem, visible),
                        subs=tracks.get(stem.lower()), vertical="(vertical)" in stem.lower())
            if prober:
                item.seconds = prober.seconds(folder / name)
            shelf.videos.append(item)
        for name in sorted(drop_copies(songs), key=natural):
            item = Item(rel=visible[name], title=Path(name).stem)
            if prober:
                item.seconds = prober.seconds(folder / name)
            shelf.songs.append(item)
        live = folder / "web" / "index.html"
        if live.is_file():
            shelf.live = live.relative_to(root).as_posix()
        shelf.art = _art_for(folder, "", visible) or next((v.art for v in shelf.videos if v.art), None)
        shelves.append(shelf)
    shelves.sort(key=lambda s: -s.updated)
    return shelves


def safe_file(root: Path, rel: str) -> Path | None:
    """The file `rel` names under root, or None when it is outside root, hidden, or not a kind the library serves."""
    parts = rel.split("/")
    if not rel or any(p in ("", ".", "..") or hidden(p) for p in parts):
        return None
    ext = Path(rel).suffix.lower()
    in_web = "web" in parts[:-1]
    if ext not in VIDEO | AUDIO | IMAGE | TRACK and not (in_web and ext in WEB):
        return None
    root = root.resolve()
    path = (root / rel).resolve()
    if root not in path.parents or not path.is_file():
        return None
    return path


def parse_range(header: str | None, size: int) -> tuple[int, int] | None | bool:
    """(start, end) inclusive for a single `bytes=` range; None for no range; False when it cannot be satisfied."""
    if not header or not header.startswith("bytes=") or "," in header:
        return None
    first, _, last = header[6:].strip().partition("-")
    try:
        if first == "":
            n = int(last)
            if n <= 0:
                return False
            return max(0, size - n), size - 1
        start = int(first)
        end = int(last) if last else size - 1
    except ValueError:
        return None
    if start >= size or end < start:
        return False
    return start, min(end, size - 1)


def content_type(path: Path) -> str:
    ext = path.suffix.lower()
    return TYPES.get(ext) or mimetypes.guess_type(path.name)[0] or "application/octet-stream"


def clock(seconds: float | None) -> str:
    if not seconds:
        return ""
    s = int(round(seconds))
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


def url(rel: str) -> str:
    return "/m/" + quote(rel)


def poster_url(rel: str) -> str:
    return "/poster/" + quote(rel)


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes"><meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="theme-color" content="#0f1216"><title>Library</title>
<style>
:root{--bg:#0f1216;--card:#181d23;--ink:#e8ecf0;--dim:#8f9aa6;--accent:#f5c542}
*{box-sizing:border-box}html,body{overflow-x:hidden}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.4 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
header{padding:28px 16px 8px;max-width:1400px;margin:auto}h1{margin:0;font-size:28px;letter-spacing:.5px}
header p{margin:4px 0 0;color:var(--dim);font-size:14px}
main{max-width:1400px;margin:auto;padding:0 16px 60px}
section{margin-top:28px}h2{font-size:19px;margin:0 0 10px;display:flex;gap:12px;align-items:baseline;flex-wrap:wrap}
h2 a{font-size:13px;font-weight:500;color:var(--accent);text-decoration:none}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(260px,100%),1fr));gap:14px}
.card{background:var(--card);border:0;border-radius:12px;overflow:hidden;padding:0;color:inherit;text-align:left;cursor:pointer;font:inherit}
.card:focus-visible{outline:3px solid var(--accent)}
.thumb{aspect-ratio:16/9;background:#222a33 center/cover no-repeat;position:relative}
.card.v .thumb{background-size:contain}
.thumb span{position:absolute;right:8px;bottom:8px;background:rgba(0,0,0,.7);padding:2px 7px;border-radius:6px;font-size:12px}
.card div.t{padding:9px 12px 11px;font-size:14px}
ul.songs{list-style:none;margin:10px 0 0;padding:0;display:grid;gap:8px}
ul.songs li{background:var(--card);border-radius:10px;padding:8px 12px;display:grid;gap:4px}
ul.songs small{color:var(--dim)}audio{width:100%;height:36px}
dialog{border:0;padding:0;background:#000;color:var(--ink);width:100vw;height:100vh;max-width:none;max-height:none}
dialog::backdrop{background:#000}
dialog video{width:100%;height:calc(100% - 52px);background:#000;display:block}
dialog nav{height:52px;display:flex;gap:8px;align-items:center;padding:0 12px}
dialog nav b{flex:1;font-weight:500;overflow:hidden;white-space:nowrap;text-overflow:ellipsis}
dialog button{background:#222a33;color:var(--ink);border:0;border-radius:8px;padding:8px 12px;font:inherit;cursor:pointer}
dialog button[aria-pressed=true]{background:var(--accent);color:#111}
.empty{color:var(--dim);margin-top:40px}
</style></head><body>
<header><h1>Library</h1><p>__COUNT__ · tap a video to play; AirPlay or cast it to the TV from the player</p></header>
<main>__SHELVES__</main>
<dialog id="player"><nav><b id="ptitle"></b>
<button id="loop" aria-pressed="false" title="Play this video on repeat">Loop</button>
<button id="next" aria-pressed="false" title="Play the next video in this project when one ends">Play all</button>
<button id="close">Close</button></nav>
<video id="video" controls playsinline x-webkit-airplay="allow" preload="metadata"></video></dialog>
<script>
const LIB = __DATA__;
const dlg = document.getElementById('player'), v = document.getElementById('video');
const loopBtn = document.getElementById('loop'), nextBtn = document.getElementById('next');
const pref = (k, d) => { try { return localStorage.getItem(k) ?? d; } catch { return d; } };
const keep = (k, x) => { try { localStorage.setItem(k, x); } catch {} };
let loop = pref('loop', '0') === '1', all = pref('all', '0') === '1', cur = null;
const paint = () => { loopBtn.setAttribute('aria-pressed', loop); nextBtn.setAttribute('aria-pressed', all); v.loop = loop; };
function play(s, i) {
  cur = [s, i]; const it = LIB[s].videos[i];
  v.innerHTML = ''; v.src = it.src; v.poster = it.poster;
  if (it.subs) { const t = document.createElement('track'); t.kind = 'subtitles'; t.src = it.subs; t.srclang = 'en'; t.label = 'Subtitles'; v.appendChild(t); }
  document.getElementById('ptitle').textContent = it.title;
  paint(); if (!dlg.open) dlg.showModal(); v.play().catch(() => {});
}
v.addEventListener('ended', () => { if (!loop && all && cur) { const [s, i] = cur; const n = LIB[s].videos; if (i + 1 < n.length) play(s, i + 1); } });
loopBtn.onclick = () => { loop = !loop; keep('loop', loop ? '1' : '0'); paint(); };
nextBtn.onclick = () => { all = !all; keep('all', all ? '1' : '0'); paint(); };
document.getElementById('close').onclick = () => dlg.close();
dlg.addEventListener('close', () => { v.pause(); v.removeAttribute('src'); v.load(); });
document.querySelectorAll('.card').forEach(c => c.onclick = () => play(+c.dataset.s, +c.dataset.i));
</script></body></html>
"""


def render_page(shelves: list[Shelf]) -> str:
    parts, data = [], []
    videos = sum(len(s.videos) for s in shelves)
    songs = sum(len(s.songs) for s in shelves)
    for si, s in enumerate(shelves):
        e = html.escape
        live = f' <a href="{e(url(s.live))}" target="_blank" rel="noopener">Live page ↗</a>' if s.live else ""
        block = [f"<section><h2>{e(s.title)}{live}</h2>"]
        if s.videos:
            block.append('<div class="grid">')
            for vi, item in enumerate(s.videos):
                art = url(item.art) if item.art else poster_url(item.rel)
                length = f"<span>{clock(item.seconds)}</span>" if item.seconds else ""
                block.append(f'<button class="card{" v" if item.vertical else ""}" data-s="{si}" data-i="{vi}">'
                             f'<div class="thumb" style="background-image:url(&quot;{e(art)}&quot;)">{length}</div>'
                             f'<div class="t">{e(item.title)}</div></button>')
            block.append("</div>")
        if s.songs:
            block.append('<ul class="songs">')
            for item in s.songs:
                length = f" <small>{clock(item.seconds)}</small>" if item.seconds else ""
                block.append(f"<li><div>{e(item.title)}{length}</div>"
                             f'<audio controls preload="none" src="{e(url(item.rel))}"></audio></li>')
            block.append("</ul>")
        block.append("</section>")
        parts.append("".join(block))
        data.append({"videos": [{"title": i.title, "src": url(i.rel),
                                 "poster": url(i.art) if i.art else poster_url(i.rel),
                                 "subs": url(i.subs) if i.subs else None} for i in s.videos]})
    count = f"{videos} video{'' if videos == 1 else 's'}, {songs} song{'' if songs == 1 else 's'}"
    body = "".join(parts) or '<p class="empty">Nothing here yet: finished videos and songs appear on their own.</p>'
    script_data = json.dumps(data).replace("</", "<\\/")
    return PAGE.replace("__COUNT__", count).replace("__SHELVES__", body).replace("__DATA__", script_data)


class Library:
    def __init__(self, root: Path, cache: Path | None = None) -> None:
        self.root = root.expanduser().resolve()
        self.cache = (cache or self.root / ".library-cache").expanduser()
        self.prober = Prober()
        self.ffmpeg = shutil.which("ffmpeg")
        self.lock = threading.Lock()

    def shelves(self) -> list[Shelf]:
        return scan(self.root, self.prober) if self.root.is_dir() else []

    def poster(self, rel: str) -> Path | None:
        """A frame from a video with no picture beside it, made once with ffmpeg and kept in the cache."""
        path = safe_file(self.root, rel)
        if path is None or path.suffix.lower() not in VIDEO or not self.ffmpeg:
            return None
        st = path.stat()
        key = hashlib.sha1(f"{rel}|{st.st_size}|{st.st_mtime}".encode()).hexdigest()[:20]
        out = self.cache / "posters" / f"{key}.jpg"
        with self.lock:
            if not out.is_file():
                out.parent.mkdir(parents=True, exist_ok=True)
                seconds = self.prober.seconds(path) or 0
                at = min(max(seconds * 0.2, 0), 30)
                tmp = out.with_suffix(".part.jpg")
                subprocess.run([self.ffmpeg, "-v", "error", "-y", "-ss", f"{at:.2f}", "-i", str(path), "-frames:v",
                                "1", "-vf", "scale=640:-2", "-q:v", "4", str(tmp)], capture_output=True, timeout=60)
                if not tmp.is_file():
                    return None
                tmp.replace(out)
        return out


def make_handler(lib: Library, verbose: bool = False):
    class Handler(BaseHTTPRequestHandler):
        server_version = "music-video-library"

        def log_message(self, fmt, *args):  # quiet unless asked
            if verbose:
                sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

        def do_HEAD(self):
            self.route(head=True)

        def do_GET(self):
            self.route(head=False)

        def route(self, head: bool) -> None:
            path = unquote(urlsplit(self.path).path)
            try:
                if path in ("/", "/index.html"):
                    self.send_bytes(render_page(lib.shelves()).encode("utf-8"), "text/html; charset=utf-8", head)
                elif path == "/library.json":
                    body = json.dumps([asdict(s) for s in lib.shelves()], indent=1).encode("utf-8")
                    self.send_bytes(body, "application/json", head)
                elif path.startswith("/m/"):
                    file = safe_file(lib.root, path[3:])
                    self.send_file(file, head) if file else self.send_error(HTTPStatus.NOT_FOUND)
                elif path.startswith("/poster/"):
                    file = lib.poster(path[8:])
                    self.send_file(file, head) if file else self.send_error(HTTPStatus.NOT_FOUND)
                else:
                    self.send_error(HTTPStatus.NOT_FOUND)
            except (BrokenPipeError, ConnectionResetError):
                pass  # the phone moved on (seeking closes connections all the time)

        def send_bytes(self, body: bytes, kind: str, head: bool) -> None:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            if not head:
                self.wfile.write(body)

        def send_file(self, file: Path, head: bool) -> None:
            size = file.stat().st_size
            span = parse_range(self.headers.get("Range"), size)
            if span is False:
                self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                self.send_header("Content-Range", f"bytes */{size}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            start, end = span if span else (0, size - 1)
            length = max(0, end - start + 1)
            self.send_response(HTTPStatus.PARTIAL_CONTENT if span else HTTPStatus.OK)
            self.send_header("Content-Type", content_type(file))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(length))
            if span:
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            if head or length == 0:
                return
            with file.open("rb") as f:
                f.seek(start)
                left = length
                while left > 0:
                    chunk = f.read(min(CHUNK, left))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)

    return Handler


def make_server(root: Path, port: int = PORT, host: str = "0.0.0.0", cache: Path | None = None,
                verbose: bool = False) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), make_handler(Library(root, cache), verbose))
    server.daemon_threads = True
    return server


def lan_urls(port: int) -> list[str]:
    """How other devices on the network reach this computer: its local name (Bonjour on macOS) and its address."""
    names: list[str] = []
    if sys.platform == "darwin":
        try:
            local = subprocess.run(["scutil", "--get", "LocalHostName"], capture_output=True, text=True, encoding="utf-8",
                                   timeout=5).stdout.strip()
            if local:
                names.append(f"{local}.local")
        except (OSError, subprocess.SubprocessError):
            pass
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 9))  # no packet is sent: this only picks the outgoing interface
            names.append(s.getsockname()[0])
    except OSError:
        pass
    return [f"http://{n}:{port}/" for n in names] or [f"http://localhost:{port}/"]


def agent_plist(program: list[str], path_env: str, log: Path) -> bytes:
    """The launchd agent that keeps the library running from login (macOS)."""
    import plistlib
    return plistlib.dumps({
        "Label": LABEL,
        "ProgramArguments": program,
        "EnvironmentVariables": {"PATH": path_env},  # launchd's own PATH has no Homebrew: ffmpeg would be missing
        "RunAtLoad": True,
        "KeepAlive": True,
        "ProcessType": "Background",
        "StandardOutPath": str(log),
        "StandardErrorPath": str(log),
    })


def agent_file() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def answering(port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout) as s:
            s.sendall(b"HEAD /library.json HTTP/1.0\r\n\r\n")
            return s.recv(12).startswith(b"HTTP/1.")
    except OSError:
        return False


def install_agent(root: Path, port: int, cache: Path, folder: Path, run=subprocess.run) -> Path:
    """Copy this file into `folder` (the install folder: plugin updates replace the plugin's own folder) and start it
    at every login through launchd. Returns the agent's plist. Run again after a plugin update to refresh the copy."""
    uv = shutil.which("uv")
    if not uv:
        raise RuntimeError("uv is not on PATH")
    folder.mkdir(parents=True, exist_ok=True)
    cache.mkdir(parents=True, exist_ok=True)
    script = folder / "library.py"
    shutil.copy2(Path(__file__), script)
    tools = [shutil.which(t) for t in ("ffmpeg", "ffprobe")] + [uv]
    dirs = list(dict.fromkeys(str(Path(t).parent) for t in tools if t))
    path_env = ":".join(dirs + ["/usr/bin", "/bin", "/usr/sbin", "/sbin"])
    program = [uv, "run", "--no-project", "--quiet", str(script), "--root", str(root), "--port", str(port),
               "--cache", str(cache)]
    plist = agent_file()
    plist.parent.mkdir(parents=True, exist_ok=True)
    domain = f"gui/{os.getuid()}"
    run(["launchctl", "bootout", f"{domain}/{LABEL}"], capture_output=True)  # an older copy, if any
    plist.write_bytes(agent_plist(program, path_env, cache / "library.log"))
    run(["launchctl", "bootstrap", domain, str(plist)], check=True, capture_output=True)
    return plist


def uninstall_agent(folder: Path, run=subprocess.run) -> bool:
    plist = agent_file()
    existed = plist.is_file()
    run(["launchctl", "bootout", f"gui/{os.getuid()}/{LABEL}"], capture_output=True)
    plist.unlink(missing_ok=True)
    (folder / "library.py").unlink(missing_ok=True)
    return existed


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Serve the results folder as a library page on the home network.")
    ap.add_argument("--root", required=True, help="the results folder")
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--host", default="0.0.0.0", help="0.0.0.0: the home network; 127.0.0.1: this computer only")
    ap.add_argument("--cache", help="where poster frames are kept")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)
    server = make_server(Path(args.root), args.port, args.host, Path(args.cache) if args.cache else None,
                         args.verbose)
    for u in lan_urls(args.port) if args.host == "0.0.0.0" else [f"http://{args.host}:{args.port}/"]:
        print(f"library: {u}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
