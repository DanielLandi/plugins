"""The Remotion engine runs from a writable copy in the OS cache (the plugin folder is read-only and replaced on
update); its npm packages are installed there by `music-video doctor`. User videos stay in the workspace and are
rendered through a generated entry file."""
import hashlib
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import yaml

from .errors import MVError
from .spec import is_instrumental
from .workspace import Workspace, cache_dir, install_dir

PLUGIN_STUDIO = Path(__file__).resolve().parents[2] / "studio"
KEEP = {"node_modules", ".entries"}  # runtime-only folders, never synced or pruned
LOCK_STAMP = ".installed-lock"
SYNCED = ".synced.json"  # what the last sync copied: the only files a sync may delete
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


def runtime_dir() -> Path:
    return install_dir() / "engine"


def migrate_old_runtime() -> bool:
    """0.1.0 installed the engine in the cache folder; move it (with its packages) instead of reinstalling."""
    old, new = cache_dir() / "studio", runtime_dir()
    if not old.is_dir() or new.exists():
        return False
    new.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(old), str(new))
    return True


def sync_runtime(src: Path | None = None, dest: Path | None = None) -> Path:
    """Copy the plugin's engine into the runtime folder (only files that changed). Files a previous sync copied
    and the plugin no longer has are removed; nothing else in the folder is ever touched."""
    src = src or PLUGIN_STUDIO
    dest = dest or runtime_dir()
    wanted = set()
    for f in src.rglob("*"):
        rel = f.relative_to(src)
        if rel.parts[0] in KEEP or not f.is_file():
            continue
        wanted.add(rel.as_posix())
        target = dest / rel
        st = f.stat()
        if not target.is_file() or target.stat().st_size != st.st_size or target.stat().st_mtime_ns != st.st_mtime_ns:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, target)
    manifest = dest / SYNCED
    before = set(json.loads(manifest.read_text(encoding="utf-8"))) if manifest.is_file() else set()
    for rel in sorted(before - wanted):
        gone = dest / rel
        gone.unlink(missing_ok=True)
        for parent in gone.parents:
            if parent == dest or not parent.is_dir() or any(parent.iterdir()):
                break
            parent.rmdir()
    manifest.write_text(json.dumps(sorted(wanted)), encoding="utf-8")
    return dest


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
    # --include=dev: the build tools (tsx, typescript) are dev dependencies, which an npm set to omit them would skip.
    if subprocess.run([npm, "ci", "--include=dev", "--no-audit", "--no-fund"], cwd=rt).returncode:
        raise MVError(f"npm ci failed in {rt}")
    if subprocess.run([*tool(rt, "remotion"), "browser", "ensure"], cwd=rt).returncode:
        raise MVError("Remotion could not install its browser")
    (rt / LOCK_STAMP).write_text(lock_hash(rt), encoding="utf-8")


def ensure_ready() -> Path:
    rt = sync_runtime()
    if not is_installed(rt):
        raise MVError("the video engine's packages are not installed or are out of date: run music-video doctor")
    return rt


def write_entry(rt: Path, video_dir: Path, video_id: str) -> Path:
    index = video_dir / "index.tsx"
    if not index.is_file():
        raise MVError(f"no video '{video_id}' ({index} is missing): run music-video new-video {video_id}")
    entry = rt / ".entries" / video_id / "index.ts"
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
    return VideoContext(video_id, vdir, song, str(meta.get("gl") or "angle"), public, ws.work_for(video_id))


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
    link = rt / ".entries" / ctx.id / "src"
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
    entry = rt / ".entries" / ctx.id / "web.ts"
    entry.parent.mkdir(parents=True, exist_ok=True)
    target = (linked_video(rt, ctx) / source.name).as_posix()  # with its extension: a web/ folder may sit beside it
    # `export *`, not `export { web }`: a module without `web` then imports cleanly and the build's own check
    # (tools/web.ts) says what is missing in one line, instead of Node failing the import with a stack trace.
    entry.write_text(f"export * from {json.dumps(target)};\n", encoding="utf-8")
    return entry
