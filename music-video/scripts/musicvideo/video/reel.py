"""A reel: a video's finished clips chained by joins and spliced into one file (`music-video reel`).

The reel is described by `reel.yaml` in the video's folder:

    out: my-reel.mp4                 # the final file, in the video's results folder
    fps: 30
    join: {seconds: 1.5, transition: passage, params: {}}   # every join, unless a clip or a pair says otherwise
    render: {file: "{clip}.mp4", composition: "{video}-{clip}", samples: 8}   # where a clip is, how to render it
    search: []                       # more folders to look for clip files in, before the renders folder
    head: [intro]                    # always first, in this order
    clips: [a, {id: b, title: "B", exit: [0.5, 0.4]}, c]   # the middle: insert, remove or reorder freely
    tail: [outro]                    # always last
    joins: {"a>b": {seconds: 2}}     # optional overrides for one pair

Each clip is played whole, except that every join takes the last `seconds` of the clip before it and the first
`seconds` of the clip after it. The pieces are cached in <work>/reel/ under a key of what they are made from: a
clip's body (its frames between its joins) and each join (a short render of the `<video>-join` composition, see
kit/reel.tsx). Adding a clip renders that clip (when it has no file yet), its body and its two joins; everything
else is reused, and the final file is a stream copy of the pieces, so nothing else is encoded again.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from ..errors import MVError
from . import media

JOIN_VERSION = 1  # bump when a join is put together differently here: every join is rendered again


def _join_source() -> str:
    """What draws a join (kit/reel.tsx and the transition library's registry): a change there remakes every join."""
    studio = Path(__file__).resolve().parents[3] / "studio"
    h = hashlib.sha1()
    for f in (studio / "kit" / "reel.tsx", studio / "transitions" / "src" / "registry.ts"):
        if f.is_file():
            h.update(f.read_bytes())
    return h.hexdigest()[:12]
ENCODE_VERSION = 1


def encode_args(fps: int) -> list[str]:
    """One encoding for every piece, so the pieces join by stream copy (H.264 High, 4:2:0, closed GOPs)."""
    return ["-c:v", "libx264", "-preset", "medium", "-crf", "14", "-pix_fmt", "yuv420p", "-profile:v", "high",
            "-level:v", "4.2", "-r", str(fps), "-g", str(2 * fps), "-keyint_min", str(2 * fps), "-sc_threshold", "0",
            "-video_track_timescale", str(fps * 512), "-an", "-movflags", "+faststart"]


@dataclass
class Clip:
    id: str
    title: str
    file: Path | None = None
    exit: list | None = None  # [x, y], or keys [[t, x, y] or [t, x, y, height], …] in seconds before the clip's end
    frames: int = 0
    stamp: str = ""  # what the clip file is: path, size, modification time


@dataclass
class Piece:
    kind: str  # body | join
    name: str
    key: str
    frames: int
    file: Path
    clip: Clip | None = None  # body: its clip
    a: Clip | None = None  # join: the clips on each side
    b: Clip | None = None
    start: int = 0  # body: first frame of the clip used; join: A's first frame used
    spec: dict = field(default_factory=dict)  # join: transition and params


@dataclass
class Reel:
    video: str
    fps: int
    out: str
    join: dict
    render: dict
    search: list[Path]
    clips: list[Clip]
    fixed_head: int
    fixed_tail: int
    joins: dict


def _clip(item, where: str) -> Clip:
    if isinstance(item, str):
        return Clip(id=item, title=item)
    if not isinstance(item, dict) or not isinstance(item.get("id"), str):
        raise MVError(f"reel.yaml {where}: each clip is an id or {{id: …}}")
    exit_ = item.get("exit")
    point = isinstance(exit_, list) and len(exit_) == 2 and all(isinstance(v, (int, float)) for v in exit_)
    keys = isinstance(exit_, list) and len(exit_) > 0 and all(
        isinstance(k, list) and len(k) in (3, 4) and all(isinstance(v, (int, float)) for v in k) and k[0] <= 0
        for k in exit_)
    if exit_ is not None and not (point or keys):
        raise MVError(f"reel.yaml {where} {item['id']}: exit is [x, y] as fractions of the frame, or keys "
                      "[[t, x, y], …] (t in seconds before the clip's end, ≤ 0; an optional 4th value is the "
                      "opening's height)")
    return Clip(id=item["id"], title=str(item.get("title") or item["id"]),
                file=Path(item["file"]).expanduser() if item.get("file") else None,
                exit=[float(v) for v in exit_] if point else [[float(v) for v in k] for k in exit_] if keys else None)


def load(path: Path, video_id: str) -> Reel:
    if not path.is_file():
        raise MVError(f"no {path.name} in {path.parent}: write one (see the top of scripts/musicvideo/video/reel.py)")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise MVError("reel.yaml: expected a mapping")
    lists = {k: data.get(k) or [] for k in ("head", "clips", "tail")}
    for k, v in lists.items():
        if not isinstance(v, list):
            raise MVError(f"reel.yaml: {k} is a list")
    clips = [_clip(c, k) for k in ("head", "clips", "tail") for c in lists[k]]
    if len(clips) < 2:
        raise MVError("reel.yaml: a reel needs at least two clips")
    ids = [c.id for c in clips]
    if len(set(ids)) != len(ids):
        dup = sorted({i for i in ids if ids.count(i) > 1})
        raise MVError(f"reel.yaml: a clip appears twice: {', '.join(dup)}")
    join = {"seconds": 1.5, "transition": "passage", "params": {}, **(data.get("join") or {})}
    render = {"file": "{clip}.mp4", "composition": "{video}-{clip}", "samples": 8, **(data.get("render") or {})}
    return Reel(video=video_id, fps=int(data.get("fps", 30)), out=str(data.get("out") or f"{video_id}-reel.mp4"),
                join=join, render=render, search=[Path(p).expanduser() for p in data.get("search") or []],
                clips=clips, fixed_head=len(lists["head"]), fixed_tail=len(lists["tail"]),
                joins=data.get("joins") or {})


def _key(*parts) -> str:
    return hashlib.sha1(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()[:12]


def find_clip(reel: Reel, clip: Clip, renders: Path) -> Path:
    """Where the clip's file is: its own `file`, else the first search folder (then renders) that has it."""
    name = reel.render["file"].format(clip=clip.id, video=reel.video)
    if clip.file is not None:
        return clip.file if clip.file.is_absolute() else renders / clip.file
    for folder in [*reel.search, renders]:
        if (folder / name).is_file():
            return folder / name
    return renders / name


def stamp(path: Path) -> str:
    st = path.stat()
    return f"{path.resolve()}|{st.st_size}|{st.st_mtime_ns}"


def join_spec(reel: Reel, a: Clip, b: Clip) -> dict:
    """The join between a and b: the reel's join, A's exit point (where the opening grows from), the pair's own."""
    spec = {**reel.join, "params": dict(reel.join.get("params") or {})}
    own = reel.joins.get(f"{a.id}>{b.id}") or {}
    spec.update({k: v for k, v in own.items() if k != "params"})
    if a.exit is not None and isinstance(a.exit[0], list):
        # keys in seconds before A's end → join progress; the first key's height sizes the opening
        secs = float(spec["seconds"])
        keys = sorted(a.exit)
        spec["params"]["track"] = [[round(min(1.0, max(0.0, 1 + k[0] / secs)), 4), k[1], k[2]] for k in keys]
        inside = [k for k in keys if k[0] >= -secs and len(k) == 4]
        if inside:
            spec["params"]["size"] = inside[0][3]
    elif a.exit is not None:
        spec["params"].update({"x": a.exit[0], "y": a.exit[1]})
    spec["params"].update(own.get("params") or {})
    return spec


def plan(reel: Reel, cache: Path) -> list[Piece]:
    """The pieces in order: body, join, body, join … body. Every clip's frames and stamp must be known."""
    pieces: list[Piece] = []
    n = len(reel.clips)
    specs = [join_spec(reel, reel.clips[i], reel.clips[i + 1]) for i in range(n - 1)]
    lens = [round(float(s["seconds"]) * reel.fps) for s in specs]
    for i, c in enumerate(reel.clips):
        lead = lens[i - 1] if i > 0 else 0
        trail = lens[i] if i < n - 1 else 0
        if c.frames - lead - trail < 1:
            raise MVError(f"clip {c.id} has {c.frames} frames: too short for its joins ({lead} + {trail} frames)")
        key = _key("body", c.stamp, lead, c.frames - trail, reel.fps, ENCODE_VERSION)
        pieces.append(Piece("body", c.id, key, c.frames - lead - trail, cache / f"body-{c.id}-{key}.mp4",
                            clip=c, start=lead))
        if i < n - 1:
            b, spec, d = reel.clips[i + 1], specs[i], lens[i]
            key = _key("join", c.stamp, b.stamp, d, spec.get("transition"), spec.get("params"), reel.fps,
                       JOIN_VERSION, ENCODE_VERSION, _join_source())
            pieces.append(Piece("join", f"{c.id}>{b.id}", key, d, cache / f"join-{c.id}--{b.id}-{key}.mp4",
                                a=c, b=b, start=c.frames - d, spec=spec))
    return pieces


def chapters(reel: Reel, pieces: list[Piece], min_s: float = 10.0) -> list[tuple[float, str]]:
    """YouTube chapters: each clip starts where the join into it starts (the first at 0). A chapter shorter than
    min_s is folded into the next one, both titles kept (YouTube ignores chapters under 10 s)."""
    starts, t = {}, 0
    for p in pieces:
        if p.kind == "join":
            starts[p.b.id] = t
        t += p.frames
    marks = [(0.0 if i == 0 else starts[c.id] / reel.fps, c.title) for i, c in enumerate(reel.clips)]
    total = t / reel.fps
    out: list[tuple[float, str]] = []
    carried: tuple[float, list[str]] | None = None  # a too-short chapter, handed on to the next one
    for i, (s, title) in enumerate(marks):
        start, titles = (s, [title]) if carried is None else (carried[0], [*carried[1], title])
        end = marks[i + 1][0] if i + 1 < len(marks) else total
        if end - start < min_s and i + 1 < len(marks):
            carried = (start, titles)
            continue
        carried = None
        out.append((start, " · ".join(titles)))
    if len(out) > 1 and total - out[-1][0] < min_s:
        last = out.pop()  # a too-short last chapter belongs to the one before it
        out[-1] = (out[-1][0], f"{out[-1][1]} · {last[1]}")
    return [(0.0, out[0][1]), *out[1:]] if out else out


def timestamp(s: float) -> str:
    s = int(s)
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


def count_frames(path: Path) -> int:
    out = media.run([media.need("ffprobe"), "-v", "error", "-select_streams", "v:0", "-count_packets",
                     "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", str(path)], f"counting {path.name}")
    return int(out.stdout.decode().strip().split(",")[0])


def _cli(*args: str) -> list[str]:
    return [sys.executable, str(Path(__file__).resolve().parents[2] / "music-video.py"), *args]


def _call(cmd: list[str], what: str) -> None:
    print(f"  $ {' '.join(cmd[1:])}", flush=True)
    if subprocess.run(cmd).returncode:
        raise MVError(f"{what} failed")


def _place(src: Path, dest: Path) -> None:
    """dest as a hard link to src (a copy across volumes)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        return
    try:
        os.link(src, dest)
    except OSError:
        shutil.copy2(src, dest)


def build_body(p: Piece, fps: int) -> None:
    tmp = p.file.with_suffix(".part.mp4")
    end = p.start + p.frames
    media.run([media.need("ffmpeg"), "-nostdin", "-y", "-loglevel", "error", "-i", str(p.clip.file),
               "-vf", f"trim=start_frame={p.start}:end_frame={end},setpts=PTS-STARTPTS", *encode_args(fps), str(tmp)],
              f"cutting the body of {p.name}")
    got = count_frames(tmp)
    if got != p.frames:
        tmp.unlink(missing_ok=True)
        raise MVError(f"the body of {p.name} came out with {got} frames, not {p.frames}")
    tmp.replace(p.file)


def build_join(p: Piece, reel: Reel, public: Path, extra: list[str]) -> None:
    names = {}
    for c in (p.a, p.b):
        names[c.id] = f"reel/{c.id}-{_key(c.stamp)}.mp4"
        _place(c.file, public / names[c.id])
    props = {"a": names[p.a.id], "b": names[p.b.id], "aFrom": p.start, "frames": p.frames,
             "transition": p.spec.get("transition") or "passage", "params": p.spec.get("params") or {}}
    props_file = p.file.with_suffix(".props.json")
    props_file.write_text(json.dumps(props, indent=1), encoding="utf-8")
    raw = p.file.with_suffix(".raw.mp4")
    _call(_cli("render", reel.video, f"{reel.video}-join", str(raw), f"--props={props_file}", "--codec=h264",
               "--crf=10", *extra), f"rendering the join {p.name}")
    tmp = p.file.with_suffix(".part.mp4")
    media.run([media.need("ffmpeg"), "-nostdin", "-y", "-loglevel", "error", "-i", str(raw), *encode_args(reel.fps),
               str(tmp)], f"encoding the join {p.name}")
    got = count_frames(tmp)
    if got != p.frames:
        raise MVError(f"the join {p.name} came out with {got} frames, not {p.frames}")
    tmp.replace(p.file)
    raw.unlink(missing_ok=True)


def splice(pieces: list[Piece], out: Path, fps: int) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    listing = out.with_suffix(".concat.txt")
    listing.write_text("".join(f"file '{p.file}'\n" for p in pieces), encoding="utf-8")
    total = sum(p.frames for p in pieces)
    tmp = out.with_suffix(".part.mp4")
    media.run([media.need("ffmpeg"), "-nostdin", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
               "-i", str(listing), "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-map", "0:v", "-map", "1:a",
               "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-t", f"{total / fps:.6f}", "-movflags", "+faststart",
               str(tmp)], "splicing the reel")
    got = count_frames(tmp)
    if got != total:
        raise MVError(f"the reel came out with {got} frames, not {total}")
    tmp.replace(out)
    listing.unlink(missing_ok=True)


def run(reel: Reel, *, renders: Path, cache: Path, public: Path, results: Path, dry_run: bool = False,
        render_missing: bool = True, prune: bool = False, extra: list[str] | None = None) -> Path | None:
    cache.mkdir(parents=True, exist_ok=True)
    for c in reel.clips:
        c.file = find_clip(reel, c, renders)
        if not c.file.is_file():
            comp = reel.render["composition"].format(clip=c.id, video=reel.video)
            if dry_run or not render_missing:
                print(f"missing clip {c.id}: {c.file} (would render {comp})")
                continue
            print(f"rendering the missing clip {c.id} ({comp})", flush=True)
            _call(_cli("blur", reel.video, comp, str(c.file), f"--samples={reel.render['samples']}"),
                  f"rendering {c.id}")
        c.frames = count_frames(c.file)
        c.stamp = stamp(c.file)
    if any(not c.stamp for c in reel.clips):
        return None
    pieces = plan(reel, cache)
    todo = [p for p in pieces if not p.file.is_file()]
    total = sum(p.frames for p in pieces)
    print(f"{len(reel.clips)} clips, {len(pieces) - len(reel.clips)} joins, {total} frames "
          f"({timestamp(total / reel.fps)}); {len(todo)} piece(s) to make")
    for p in todo:
        print(f"  to make: {p.kind} {p.name} ({p.frames} frames)")
    if dry_run:
        return None
    for i, p in enumerate(todo, 1):
        print(f"[{i}/{len(todo)}] {p.kind} {p.name}", flush=True)
        if p.kind == "body":
            build_body(p, reel.fps)
        else:
            build_join(p, reel, public, extra or [])
    out = results / reel.out
    splice(pieces, out, reel.fps)
    marks = chapters(reel, pieces)
    out.with_suffix(".chapters.txt").write_text("".join(f"{timestamp(s)} {t}\n" for s, t in marks), encoding="utf-8")
    t = 0
    layout = []
    for p in pieces:
        layout.append({"kind": p.kind, "name": p.name, "from": round(t / reel.fps, 3), "frames": p.frames,
                       "file": str(p.file)})
        t += p.frames
    out.with_suffix(".reel.json").write_text(json.dumps({"fps": reel.fps, "frames": t, "pieces": layout}, indent=1),
                                             encoding="utf-8")
    if prune:
        keep = {p.file.name for p in pieces}
        for f in cache.glob("*.mp4"):
            if f.name not in keep:
                f.unlink()
    print(out)
    return out
