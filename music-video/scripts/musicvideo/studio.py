"""The Remotion engine runs from a writable copy in the OS cache (the plugin folder is read-only and replaced on
update); its npm packages are installed there by `music-video doctor`. User videos stay in the workspace and are
rendered through a generated entry file."""
import contextlib
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import yaml

from . import __version__
from .errors import MVError
from .filelock import file_lock
from .spec import is_instrumental
from .workspace import Workspace, cache_dir, folder_key, install_dir

PLUGIN_STUDIO = Path(__file__).resolve().parents[2] / "studio"
KEEP = {"node_modules", ".entries"}  # runtime-only folders, never synced or pruned
LOCK_STAMP = ".installed-lock"
SYNCED = ".synced.json"  # what the last sync copied: the only files a sync may delete
SEED_SKIP = {".cache", ".vite", ".vite-temp"}  # tool caches written in place: never shared between engines
SEED_COPY = {".package-lock.json"}  # npm's hidden lockfile, rewritten in place by npm: each engine gets its own copy
LEASES = ".leases"  # one file per command using the engine (removed when it ends)
LEASE_MAX_AGE = 48 * 3600  # a lease older than this is stale whatever its pid says (pids get reused)
OWNER = ".owner.json"  # a checkout's engine: which checkout it serves, when it was last used
ID_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
WEB_MARK = "<!-- built by music-video web -->"  # first line of a web build's README (tools/web-out.ts)


def check_web_out(out: Path) -> None:
    """The web build empties its output first: refuse anything but a missing or empty folder, or an earlier build."""
    if out.exists() and not out.is_dir():
        raise MVError(f"{out} is not a folder: give --out a folder for the page")
    if out.is_dir() and any(out.iterdir()):
        readme = out / "README.md"
        if not (readme.is_file() and readme.read_bytes().startswith(WEB_MARK.encode("utf-8"))):
            raise MVError(f"{out} is not empty and is not a web build (no README.md from music-video web): "
                          "refusing to empty it; pick an empty folder")


def plugin_checkout(studio_dir: Path | None = None) -> Path | None:
    """The git working tree this plugin copy runs from, or None for the installed plugin. Claude Code runs a plugin
    from its cache copy, which is in no git repo; only the plugin root and the repo root above it are looked at, so
    a home folder kept in git never makes the installed plugin look like a checkout."""
    studio_dir = studio_dir or PLUGIN_STUDIO
    return next((d for d in (studio_dir.parent, studio_dir.parents[1]) if (d / ".git").exists()), None)


def runtime_dir() -> Path:
    """The installed plugin's engine is install/engine, as always; each git checkout of the plugin (a clone, a
    worktree) gets install/engines/<checkout>, so two copies never sync over each other's engine."""
    if value := os.environ.get("MV_ENGINE_DIR"):
        return Path(value).expanduser().resolve()
    checkout = plugin_checkout()
    return install_dir() / "engine" if checkout is None else install_dir() / "engines" / folder_key(checkout)


def touch_owner(rt: Path) -> None:
    """A checkout's engine records which checkout it serves and when it was last used (at most hourly), so stale
    engines can be found later. The installed engine has none."""
    checkout = plugin_checkout()
    if checkout is None:
        return
    path, now = rt / OWNER, time.time()
    try:
        owner = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        owner = {"created": _iso(now)}
    if owner.get("checkout") == str(checkout) and now - owner.get("used_at", 0) < 3600:
        return
    owner.update(checkout=str(checkout), last_used=_iso(now), used_at=now)
    rt.mkdir(parents=True, exist_ok=True)
    # Written beside it and moved over it, so a reader never sees half a record. The record is only a hint for
    # finding stale engines: if it cannot be written, the old one stays and the command goes on.
    tmp = path.with_name(f"{OWNER}.{os.getpid()}-{secrets.token_hex(4)}.tmp")
    try:
        tmp.write_text(json.dumps(owner), encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        tmp.unlink(missing_ok=True)


def _iso(t: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


def migrate_old_runtime() -> bool:
    """0.1.0 installed the engine in the cache folder; move it (with its packages) instead of reinstalling."""
    old, new = cache_dir() / "studio", install_dir() / "engine"
    if not old.is_dir() or new.exists():
        return False
    new.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(old), str(new))
    return True


def _plan(src: Path, dest: Path) -> tuple[list[str], list[str], list[str]]:
    wanted, copy = [], []
    for f in sorted(src.rglob("*")):
        rel = f.relative_to(src)
        if rel.parts[0] in KEEP or not f.is_file():
            continue
        wanted.append(rel.as_posix())
        target, st = dest / rel, f.stat()
        if not target.is_file() or target.stat().st_size != st.st_size or target.stat().st_mtime_ns != st.st_mtime_ns:
            copy.append(rel.as_posix())
    manifest = dest / SYNCED
    before = set(json.loads(manifest.read_text(encoding="utf-8"))) if manifest.is_file() else set()
    return wanted, copy, sorted(before - set(wanted))


def sync_plan(src: Path, dest: Path) -> tuple[list[str], list[str]]:
    """What a sync of src into dest would copy and delete (relative POSIX paths)."""
    _, copy, delete = _plan(src, dest)
    return copy, delete


def sync_runtime(src: Path | None = None, dest: Path | None = None) -> Path:
    """Copy the plugin's engine into the runtime folder (only files that changed). Files a previous sync copied
    and the plugin no longer has are removed; nothing else in the folder is ever touched."""
    src = src or PLUGIN_STUDIO
    dest = dest or runtime_dir()
    wanted, copy, delete = _plan(src, dest)
    for rel in copy:
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src / rel, target)
    for rel in delete:
        gone = dest / rel
        gone.unlink(missing_ok=True)
        for parent in gone.parents:
            if parent == dest or not parent.is_dir() or any(parent.iterdir()):
                break
            parent.rmdir()
    dest.mkdir(parents=True, exist_ok=True)
    (dest / SYNCED).write_text(json.dumps(wanted), encoding="utf-8")
    return dest


def pid_alive(pid: int) -> bool:
    if sys.platform == "win32":  # never os.kill here: on Windows it terminates the process
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            return bool(kernel32.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259  # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def process_started(pid: int) -> float | None:
    """When the process with this pid started (epoch seconds), or None when that cannot be told."""
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return None
        try:
            times = [wintypes.FILETIME() for _ in range(4)]  # creation, exit, kernel, user
            if not kernel32.GetProcessTimes(handle, *(ctypes.byref(t) for t in times)):
                return None
            created = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime  # 100 ns steps since 1601
            return created / 1e7 - 11644473600
        finally:
            kernel32.CloseHandle(handle)
    try:  # elapsed time as [[dd-]hh:]mm:ss, the same on macOS and Linux and in every locale
        out = subprocess.run(["ps", "-o", "etime=", "-p", str(pid)], capture_output=True, text=True,
                             encoding="utf-8", timeout=5).stdout.strip()
        days, _, clock = out.rpartition("-")
        seconds = 0
        for part in clock.split(":"):
            seconds = seconds * 60 + int(part)
        return time.time() - seconds - int(days or 0) * 86400
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


_held: list[Path] = []  # the leases this process holds: release_leases() removes them when the command ends


def take_lease(rt: Path, video_id: str, lane: str | None = None) -> Path:
    """Mark the engine as in use by this command until it ends (release_leases), so that another plugin copy does
    not sync over it or reinstall its packages mid-render."""
    folder = rt / LEASES
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{os.getpid()}-{secrets.token_hex(4)}.json"
    path.write_text(json.dumps({"pid": os.getpid(), "started": time.time(), "version": __version__,
                                "source": str(PLUGIN_STUDIO), "video": video_id, "lane": lane}), encoding="utf-8")
    _held.append(path)
    return path


def release_leases() -> None:
    while _held:
        _held.pop().unlink(missing_ok=True)


def _lease_holds(lease: dict) -> bool:
    started, pid = float(lease["started"]), int(lease["pid"])
    if time.time() - started >= LEASE_MAX_AGE or not pid_alive(pid):
        return False
    # A process that started after the lease was written did not write it: its pid was reused.
    born = process_started(pid)
    return born is None or born <= started + 5


def live_leases(rt: Path) -> list[dict]:
    """Leases of commands still running, each with its "file"; dead, stale or unreadable ones are deleted on sight."""
    live = []
    for path in sorted((rt / LEASES).glob("*.json")) if (rt / LEASES).is_dir() else []:
        try:
            lease = json.loads(path.read_text(encoding="utf-8"))
            ok = _lease_holds(lease)
        except (OSError, ValueError, KeyError, TypeError):
            ok = False
        if ok:
            live.append({**lease, "file": str(path)})
        else:
            path.unlink(missing_ok=True)
    return live


def _in_use(lease: dict) -> str:
    lane = f", worktree {lease['lane']}" if lease.get("lane") else ""
    return (f"the engine is in use by music-video {lease.get('version')} (pid {lease.get('pid')}, "
            f"video {lease.get('video')}{lane}): wait for it to finish, then run again. If no music-video command is "
            f"running, delete {lease.get('file')}")


def lock_hash(rt: Path) -> str:
    lock = rt / "package-lock.json"
    return hashlib.sha256(lock.read_bytes()).hexdigest() if lock.is_file() else "none"


def is_installed(rt: Path) -> bool:
    stamp = rt / LOCK_STAMP
    return (rt / "node_modules").is_dir() and stamp.is_file() and stamp.read_text(encoding="utf-8") == lock_hash(rt)


def node() -> str:
    found = shutil.which("node")
    if not found:
        raise MVError("Node.js not found: install Node 20 or newer, then run music-video doctor")
    return found


# Each tool's own entry script, run by node itself: no npx, so no .cmd shim on Windows re-parsing the arguments
# (a JSON --props value survives intact).
SCRIPTS = {"remotion": "node_modules/@remotion/cli/remotion-cli.js", "tsx": "node_modules/tsx/dist/cli.mjs",
           "tsc": "node_modules/typescript/bin/tsc"}


def tool(rt: Path, name: str) -> list[str]:
    script = rt / SCRIPTS[name]
    if not script.is_file():
        raise MVError(f"the video engine is missing {name} ({script}): run music-video doctor")
    return [node(), str(script)]


def install(rt: Path) -> None:
    npm = shutil.which("npm")
    if not npm:
        raise MVError("Node.js (npm) not found: install Node 20 or newer, then run music-video doctor")
    if leases := live_leases(rt):
        raise MVError(_in_use(leases[0]))
    # npm ci deletes and re-extracts node_modules: until it is done, the engine must not look installed (a checkout
    # seeding from it then would link a half-extracted tree).
    (rt / LOCK_STAMP).unlink(missing_ok=True)
    # --include=dev: the build tools (tsx, typescript) are dev dependencies, which an npm set to omit them would skip.
    if subprocess.run([npm, "ci", "--include=dev", "--no-audit", "--no-fund"], cwd=rt).returncode:
        raise MVError(f"npm ci failed in {rt}")
    if subprocess.run([*tool(rt, "remotion"), "browser", "ensure"], cwd=rt).returncode:
        raise MVError("Remotion could not install its browser")
    (rt / LOCK_STAMP).write_text(lock_hash(rt), encoding="utf-8")


def find_seed(rt: Path) -> Path | None:
    """An installed engine with the same packages as rt (same lock), to seed rt's node_modules from."""
    others = install_dir() / "engines"
    candidates = [install_dir() / "engine", *(sorted(others.iterdir()) if others.is_dir() else [])]
    want = lock_hash(rt)
    return next((c for c in candidates if c != rt and is_installed(c)
                 and (c / LOCK_STAMP).read_text(encoding="utf-8") == want), None)


def link_tree(src: Path, dest: Path, skip: frozenset[str] | set[str] = frozenset(),
              copy: frozenset[str] | set[str] = frozenset()) -> None:
    """dest as a tree of hard links to src's files (symlinks re-created), leaving out the top-level names in skip and
    copying the top-level files in copy. npm ci replaces files rather than rewriting them, so a later install in src
    never changes dest. Where hard links fail (another volume, an odd file system) the files are copied instead, and
    it says so; where a symlink cannot be made (Windows without Developer Mode) what it points to stands in for it."""
    linking = True

    def place(s: str, d: Path) -> None:
        nonlocal linking
        if linking:
            try:
                os.link(s, d)
                return
            except OSError as e:
                linking = False
                print(f"hard links from {src} to {dest} are not possible ({e}): copying the packages instead "
                      "(about 1.7 GB, once)…", file=sys.stderr, flush=True)
        shutil.copy2(s, d)

    def walk(s: Path, d: Path, top: bool) -> None:
        d.mkdir(parents=True, exist_ok=True)
        with os.scandir(s) as entries:
            for e in entries:
                if top and e.name in skip:
                    continue
                target = d / e.name
                if e.is_symlink():
                    try:
                        os.symlink(os.readlink(e.path), target, target_is_directory=e.is_dir())
                        continue
                    except OSError:
                        real = Path(e.path).resolve()
                    if real.is_dir() and not Path(s).resolve().is_relative_to(real):  # never a loop upwards
                        walk(real, target, False)
                    elif real.is_file():
                        place(str(real), target)
                elif e.is_dir():
                    walk(Path(e.path), target, False)
                elif top and e.name in copy:
                    shutil.copy2(e.path, target)
                else:
                    place(e.path, target)
    walk(src, dest, True)


def seed_modules(rt: Path) -> Path | None:
    """Give rt the packages of an engine with the same lock, by hard links: seconds, and almost no disk. Returns the
    engine it seeded from, or None when there is none (then doctor installs them)."""
    seed = find_seed(rt)
    if seed is None:
        return None
    if leases := live_leases(rt):  # replacing node_modules under a running command breaks it, as npm ci would
        raise MVError(_in_use(leases[0]))
    shutil.rmtree(rt / "node_modules", ignore_errors=True)  # an earlier seed may have stopped half-way
    link_tree(seed / "node_modules", rt / "node_modules", SEED_SKIP, SEED_COPY)
    (rt / LOCK_STAMP).write_text(lock_hash(rt), encoding="utf-8")
    return seed


def refuse_other_source(rt: Path) -> None:
    """Before a sync that would change files: another plugin copy (another version, across an update) may be
    rendering from them. The same copy's own edits proceed, as always. Dead leases are swept every time, so a
    stale one never waits for the next update to be found. Call under engine_lock."""
    leases = live_leases(rt)
    if leases and any(sync_plan(PLUGIN_STUDIO, rt)):
        for lease in leases:
            if lease.get("source") != str(PLUGIN_STUDIO):
                raise MVError(_in_use(lease))


@contextlib.contextmanager
def engine_lock(rt: Path, timeout: float = 600.0, notice_after: float = 2.0):
    """Only one command at a time changes an engine (sync, seed, install). Renders do not hold it, so they still
    run side by side. Not re-entrant: taken by ensure_ready() and doctor only."""
    rt.mkdir(parents=True, exist_ok=True)
    with file_lock(rt / ".lock", timeout,
                   busy=f"another music-video command has been updating the engine in {rt} for "
                        f"{max(1, round(timeout / 60))} minutes: try again when it ends",
                   notice="waiting for another music-video command to finish updating the engine…",
                   notice_after=notice_after):
        yield rt


def ensure_ready(video_id: str | None = None, lane: str | None = None) -> Path:
    """The engine, synced and installed. With a video id, this command's lease on it is taken before the engine
    lock is let go, so no other plugin copy can sync over it in between."""
    with engine_lock(runtime_dir()) as rt:
        refuse_other_source(rt)
        sync_runtime(dest=rt)
        if not is_installed(rt) and (seed := seed_modules(rt)):
            print(f"seeded the engine's packages in {rt} from {seed}", file=sys.stderr)
        if not is_installed(rt):
            raise MVError("the video engine's packages are not installed or are out of date: run music-video doctor")
        if video_id is not None:
            take_lease(rt, video_id, lane)  # released when the command ends (cli.main)
    touch_owner(rt)
    return rt


def entry_dir(rt: Path, video_id: str, lane: str | None = None) -> Path:
    """A video's folder inside the engine: .entries/<id>, or .entries/.lane-<key>/<id> for a git worktree of the
    project (a video id never starts with a dot, so the two never collide)."""
    return rt / ".entries" / video_id if lane is None else rt / ".entries" / f".lane-{lane}" / video_id


def write_entry(rt: Path, video_dir: Path, video_id: str, lane: str | None = None) -> Path:
    index = video_dir / "index.tsx"
    if not index.is_file():
        raise MVError(f"no video '{video_id}' ({index} is missing): run music-video new-video {video_id}")
    entry = entry_dir(rt, video_id, lane) / "index.ts"
    entry.parent.mkdir(parents=True, exist_ok=True)
    text = ("import { registerRoot } from 'remotion';\n"
            f"import {{ Compositions }} from {json.dumps(index.as_posix())};\n\n"
            "registerRoot(Compositions);\n")
    if not entry.is_file() or entry.read_text(encoding="utf-8") != text:
        entry.write_text(text, encoding="utf-8")
    return entry


@dataclass(frozen=True)
class VideoContext:
    id: str
    dir: Path
    song: str
    gl: str
    public: Path
    work: Path
    lane: str | None = None  # the project's git worktree key (Workspace.lane): its own engine entries


def _instrumental(ws: Workspace, song: str) -> bool:
    """An instrumental has no words to time, so it never gets a timing.json."""
    path = ws.specs_dir / f"{song}.yaml"
    if not path.is_file():
        return False
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return is_instrumental(data)


def video_context(ws: Workspace, video_id: str) -> VideoContext:
    vdir = ws.video_dir(video_id)
    meta_file = vdir / "video.yaml"
    meta = (yaml.safe_load(meta_file.read_text(encoding="utf-8")) or {}) if meta_file.is_file() else {}
    song = str(meta.get("song") or video_id)  # a test-bed video can borrow another video's song
    public = ws.work_for(song) / "public"
    if not (public / "timing.json").is_file() and not _instrumental(ws, song):
        raise MVError(f"no timing.json in {public}: run music-video align {song}, then music-video analyze {song}")
    if not (public / "analysis.json").is_file():
        raise MVError(f"no analysis.json in {public}: run music-video analyze {song}")
    return VideoContext(video_id, vdir, song, str(meta.get("gl") or "angle"), public, ws.work_for(video_id),
                        lane=ws.lane)


def tool_env(rt: Path, ctx: VideoContext, entry: Path) -> dict[str, str]:
    """The environment for the engine's Node tools. The board imports the video's own files in Node, so they are
    reached through the link inside the engine (`linked_video`) with --preserve-symlinks: their packages and
    `@mv/kit` (the engine's tsconfig paths, which tsx applies) resolve from the engine."""
    node_options = " ".join(filter(None, [os.environ.get("NODE_OPTIONS", ""), "--preserve-symlinks"]))
    return {**os.environ, "MV_STUDIO": str(rt), "MV_ENTRY": str(entry), "MV_PUBLIC": str(ctx.public),
            "MV_WORK": str(ctx.work), "MV_VIDEO": ctx.id, "MV_VIDEO_DIR": str(linked_video(rt, ctx)),
            "MV_GL": ctx.gl, "NODE_OPTIONS": node_options, "INIT_CWD": os.getcwd()}


def run_node(cmd: list[str], cwd: Path, env: dict[str, str]) -> int:
    return subprocess.run(cmd, cwd=cwd, env=env).returncode


def new_video(ws: Workspace, video_id: str, template: Path | None = None) -> Path:
    if not ID_RE.match(video_id):
        raise MVError(f"'{video_id}': use lowercase words joined by hyphens, as in the song spec id")
    dest = ws.video_dir(video_id)
    if dest.exists():
        raise MVError(f"{dest} already exists")
    shutil.copytree(template or PLUGIN_STUDIO / "template", dest)
    for f in dest.rglob("*"):
        if f.is_file():
            f.write_text(f.read_text(encoding="utf-8").replace("__ID__", video_id), encoding="utf-8")
    ws.work_for(video_id).mkdir(parents=True, exist_ok=True)
    return dest


def _link_dir(link: Path, target: Path) -> None:
    """A directory link (a junction on Windows, which needs no admin rights)."""
    if link.is_symlink() or link.exists():
        if link.resolve() == target.resolve():
            return
        link.unlink()
    if os.name == "nt":
        import _winapi
        _winapi.CreateJunction(str(target), str(link))
    else:
        link.symlink_to(target, target_is_directory=True)


def linked_video(rt: Path, ctx: VideoContext) -> Path:
    """The video folder as seen from inside the engine: <rt>/.entries/<id>/src, a link to the workspace folder."""
    link = entry_dir(rt, ctx.id, ctx.lane) / "src"
    link.parent.mkdir(parents=True, exist_ok=True)
    _link_dir(link, ctx.dir)
    return link


def typecheck_config(rt: Path, ctx: VideoContext) -> Path:
    """A tsconfig that checks one workspace video against the engine. The video folder is linked inside the engine
    folder and checked through the link (preserveSymlinks), so packages resolve from the engine's node_modules
    exactly as for engine files, `exports` subpaths included."""
    r = rt.as_posix()
    entry_dir = linked_video(rt, ctx).parent
    cfg = {
        "extends": f"{r}/tsconfig.json",
        "compilerOptions": {
            "baseUrl": r,
            "noEmit": True,
            "preserveSymlinks": True,
            "paths": {"@mv/kit": [f"{r}/kit"], "@mv/kit/*": [f"{r}/kit/*"], "@mv/assets/*": [f"{r}/assets/*"]},
        },
        "include": ["src/**/*.ts", "src/**/*.tsx", f"{r}/types/**/*.d.ts"],
    }
    path = entry_dir / "tsconfig.json"
    path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    return path


def web_entry(rt: Path, ctx: VideoContext) -> Path:
    """The module the web page imports as `@mv/web-entry`: the video's own web.tsx, reached through its link."""
    source = next((ctx.dir / n for n in ("web.tsx", "web.ts") if (ctx.dir / n).is_file()), None)
    how = ("add `export const web: WebEntry = { Component, fps, frames }` (the template's web.tsx is a starting "
           "point) to publish this video as a web page")
    if source is None:
        raise MVError(f"{ctx.dir} has no web.tsx: {how}")
    entry = entry_dir(rt, ctx.id, ctx.lane) / "web.ts"
    entry.parent.mkdir(parents=True, exist_ok=True)
    target = (linked_video(rt, ctx) / source.name).as_posix()  # with its extension: a web/ folder may sit beside it
    # `export *`, not `export { web }`: a module without `web` then imports cleanly and the build's own check
    # (tools/web.ts) says what is missing in one line, instead of Node failing the import with a stack trace.
    entry.write_text(f"export * from {json.dumps(target)};\n", encoding="utf-8")
    return entry
