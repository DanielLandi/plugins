"""music-video version and review: keep every checked render of a scene, and compare any two in a local page.

A version is a copy of a render (or a still) in <work>/review/media/, numbered per scene (relay v1, v2, …), with the
song time its first frame shows, so a scene clip lines up with a full draft. The page plays two versions in sync on
the song clock: side by side, with a wipe, or flipping between them.
"""
import html
import json
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import yaml

from ..errors import MVError
from ..workspace import Workspace
from .media import need, probe, run

SCENE_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
VIDEO_EXT = {".mp4", ".mov", ".webm"}
STILL_EXT = {".png", ".jpg", ".jpeg", ".webp"}
POSTER_WIDTH = 320
TEMPLATE = Path(__file__).with_name("review.html")


def review_dir(ws: Workspace, video_id: str) -> Path:
    return ws.work_for(video_id) / "review"


def load_versions(ws: Workspace, video_id: str) -> list[dict]:
    index = review_dir(ws, video_id) / "versions.json"
    if not index.is_file():
        return []
    return json.loads(index.read_text(encoding="utf-8"))["versions"]


def _song_of(ws: Workspace, video_id: str) -> str:
    meta = ws.video_dir(video_id) / "video.yaml"
    data = (yaml.safe_load(meta.read_text(encoding="utf-8")) or {}) if meta.is_file() else {}
    return str(data.get("song") or video_id)


def _qc_report(ws: Workspace, video_id: str, file: Path) -> dict:
    """The qc report for exactly this file, newer than it: a version is only kept once it passed qc."""
    folders = {ws.work_for(video_id) / "qc", ws.work_for(_song_of(ws, video_id)) / "qc"}
    for folder in folders:
        report = folder / f"qc-{file.stem}.json"
        if not report.is_file():
            continue
        data = json.loads(report.read_text(encoding="utf-8"))
        if Path(data.get("video", "")).resolve() != file.resolve():
            continue
        if file.stat().st_mtime > report.stat().st_mtime:
            raise MVError(f"{file.name} changed after its qc: run music-video qc on it again first")
        if data.get("result") != "PASS":
            raise MVError(f"{file.name} failed qc: fix it before keeping it as a version")
        return data
    raise MVError(f"no qc report for {file.name}: run music-video qc on it first (a version must have passed qc)")


def _code_stamp(folder: Path) -> str | None:
    """The video code's last commit, with + when the folder has uncommitted changes (None outside git)."""
    git = shutil.which("git")
    if not git or not folder.is_dir():
        return None
    head = subprocess.run([git, "-C", str(folder), "log", "-1", "--format=%h", "--", "."],
                          capture_output=True, text=True, encoding="utf-8")
    if head.returncode or not head.stdout.strip():
        return None
    dirty = subprocess.run([git, "-C", str(folder), "status", "--porcelain", "--", "."],
                           capture_output=True, text=True, encoding="utf-8")
    return head.stdout.strip() + ("+" if dirty.stdout.strip() else "")


def _video_facts(file: Path) -> dict:
    info = probe(file)
    video = next((s for s in info["streams"] if s.get("codec_type") == "video"), None)
    if video is None:
        raise MVError(f"{file.name} has no video stream")
    num, den = (int(x) for x in video.get("avg_frame_rate", "30/1").split("/"))
    return {"duration": round(float(info["format"]["duration"]), 3), "size": [int(video["width"]), int(video["height"])],
            "fps": round(num / den, 3) if den else 30.0,
            "audio": any(s.get("codec_type") == "audio" for s in info["streams"])}


def _poster(file: Path, out: Path, at: float) -> None:
    run([need("ffmpeg"), "-nostdin", "-loglevel", "error", "-y", "-ss", f"{max(at, 0):.3f}", "-i", str(file),
         "-frames:v", "1", "-vf", f"scale={POSTER_WIDTH}:-2", "-q:v", "4", str(out)], f"poster for {file.name}")


def record_version(ws: Workspace, video_id: str, file: Path, scene: str, *, start: float | None = None,
                   note: str = "") -> dict:
    if not SCENE_RE.match(scene):
        raise MVError(f"'{scene}' is not a scene name: lowercase words joined by hyphens, as in scenes.ts "
                      "(or draft, sample, vertical)")
    file = file.expanduser().resolve()
    if not file.is_file():
        raise MVError(f"{file} does not exist")
    ext = file.suffix.lower()
    if ext not in VIDEO_EXT | STILL_EXT:
        raise MVError(f"{file.name}: a version is a video ({', '.join(sorted(VIDEO_EXT))}) "
                      f"or a still ({', '.join(sorted(STILL_EXT))})")
    folder = review_dir(ws, video_id)
    media = folder / "media"
    media.mkdir(parents=True, exist_ok=True)
    versions = load_versions(ws, video_id)
    n = 1 + max((v["n"] for v in versions if v["scene"] == scene), default=0)
    name = f"{scene}-v{n}"
    entry = {"scene": scene, "n": n, "at": datetime.now().isoformat(timespec="seconds"), "note": note,
             "code": _code_stamp(ws.video_dir(video_id)), "source": file.name, "start": start}
    if ext in VIDEO_EXT:
        qc = _qc_report(ws, video_id, file)
        facts = _video_facts(file)
        entry.update(kind="video", qc=qc["result"], start=start or 0.0, **facts)
        _poster(file, media / f"{name}.jpg", facts["duration"] / 2)
        entry["poster"] = f"media/{name}.jpg"
    else:
        entry.update(kind="still")
    target = media / f"{name}{ext}"
    shutil.copy2(file, target)
    entry["file"] = f"media/{target.name}"
    versions.append(entry)
    write_index(ws, video_id, versions)
    return entry


def write_index(ws: Workspace, video_id: str, versions: list[dict]) -> Path:
    folder = review_dir(ws, video_id)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "versions.json").write_text(json.dumps({"video": video_id, "versions": versions}, indent=1,
                                                     ensure_ascii=False), encoding="utf-8")
    return build_page(ws, video_id, versions)


def build_page(ws: Workspace, video_id: str, versions: list[dict] | None = None) -> Path:
    """The page reads nothing at run time: the versions are written into it, the media sit next to it."""
    versions = load_versions(ws, video_id) if versions is None else versions
    data = json.dumps({"video": video_id, "versions": versions}, ensure_ascii=False).replace("</", "<\\/")
    page = review_dir(ws, video_id) / "index.html"
    page.parent.mkdir(parents=True, exist_ok=True)
    template = TEMPLATE.read_text(encoding="utf-8")
    page.write_text(template.replace("/*VERSIONS*/null", data).replace("{{TITLE}}", html.escape(video_id)), encoding="utf-8")
    return page
