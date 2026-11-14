"""A silent placeholder song: work on a video's picture before (or without) its song.

`placeholder: {seconds, bpm}` in video.yaml stands in for the song. It writes the video's public folder as align and
analyze would: a silent song.mp3, a timing.json with no words and an analysis.json with a steady beat grid and
8-bar parts, each marked `"placeholder": true`. The work folder is regenerable, so the files come back on their own
after `clean`. Once the real song is filed under the video's id, the first command that reads it (align, analyze,
mux, qc) removes the stand-in and sets video.yaml back to `placeholder: null`.
"""
import json
import math
from pathlib import Path

import yaml

from ..errors import MVError
from .media import need, run

DEFAULT_BPM = 120.0
FPS = 30
BEATS_PER_BAR = 4
PART_BARS = 8          # one section every 8 bars
MIN_PART_BARS = 4      # a shorter last part joins the one before it
ENERGY = 0.5           # a flat, middling energy, so energy-driven visuals show something
MAX_SECONDS = 20 * 60
FILES = ("song.mp3", "timing.json", "analysis.json")
COMMENT = ("# A silent placeholder song for working on the picture before the song exists ({seconds, bpm}), set by\n"
           "# `music-video placeholder`. Filing the real song and running align replaces it (and sets this to null).\n")


def declared(meta: dict) -> dict | None:
    """`placeholder:` in a parsed video.yaml: {seconds, bpm}, or None. A bare number is the seconds."""
    raw = meta.get("placeholder") if isinstance(meta, dict) else None
    if raw is None or raw is False:
        return None
    if isinstance(raw, bool) or not isinstance(raw, (int, float, dict)):
        raise MVError(f"placeholder: {raw!r} in video.yaml: use {{seconds: 10, bpm: 120}} or null")
    seconds, bpm = (raw, DEFAULT_BPM) if not isinstance(raw, dict) else (raw.get("seconds"), raw.get("bpm") or DEFAULT_BPM)
    return check(seconds, bpm)


def check(seconds, bpm) -> dict:
    try:
        seconds, bpm = float(seconds), float(bpm)
    except (TypeError, ValueError) as e:
        raise MVError("a placeholder needs its length in seconds and a tempo in bpm") from e
    if not 0 < seconds <= MAX_SECONDS:
        raise MVError(f"placeholder seconds {seconds:g}: give a length between 0 and {MAX_SECONDS} s")
    if not 40 <= bpm <= 240:
        raise MVError(f"placeholder bpm {bpm:g}: give a tempo between 40 and 240 bpm")
    return {"seconds": seconds, "bpm": bpm}


def read_meta(vdir: Path) -> dict:
    path = vdir / "video.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) if path.is_file() else None
    return data if isinstance(data, dict) else {}


def set_declared(vdir: Path, value: dict | None) -> None:
    """Write `placeholder:` into video.yaml in place, keeping every other line and comment."""
    path = vdir / "video.yaml"
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    text = "null" if value is None else f"{{seconds: {value['seconds']:g}, bpm: {value['bpm']:g}}}"
    new = f"placeholder: {text}\n"
    at = next((i for i, line in enumerate(lines) if line.startswith("placeholder:")), None)
    if at is None:
        if lines and not lines[-1].endswith("\n"):
            lines[-1] += "\n"
        lines += [COMMENT, new]
    else:
        end = at + 1
        while end < len(lines) and lines[end].startswith((" ", "\t")):   # a block mapping written by hand
            end += 1
        lines[at:end] = [new]
    path.write_text("".join(lines), encoding="utf-8")


def is_placeholder(public: Path) -> bool:
    """The public folder holds a placeholder's files (not a real song's timings)."""
    for name in ("analysis.json", "timing.json"):
        f = public / name
        if f.is_file():
            try:
                if json.loads(f.read_text(encoding="utf-8")).get("placeholder") is True:
                    return True
            except (ValueError, AttributeError):
                pass
    return False


def analysis(seconds: float, bpm: float) -> dict:
    step = 60.0 / bpm
    beats = [round(i * step, 3) for i in range(math.ceil(seconds / step - 1e-9))]
    downbeats = beats[::BEATS_PER_BAR]
    part = PART_BARS * BEATS_PER_BAR * step
    starts = [0.0]
    while starts[-1] + part < seconds - 1e-9:
        starts.append(starts[-1] + part)
    if len(starts) > 1 and seconds - starts[-1] < MIN_PART_BARS * BEATS_PER_BAR * step - 1e-9:
        starts.pop()
    sections = [{"id": f"part-{i + 1}", "name": f"Part {i + 1}", "start": round(s, 3),
                 "end": round(starts[i + 1] if i + 1 < len(starts) else seconds, 3), "sung": False}
                for i, s in enumerate(starts)]
    n = math.ceil(seconds * FPS)
    return {"version": 1, "duration": round(seconds, 3), "fps": FPS, "tempo": round(bpm, 1), "beats": beats,
            "downbeats": downbeats, "sections": sections,
            "energy": {k: [ENERGY] * n for k in ("rms", "low", "mid", "high")}, "hits": [], "placeholder": True}


def write_files(public: Path, seconds: float, bpm: float) -> None:
    public.mkdir(parents=True, exist_ok=True)
    run([need("ffmpeg"), "-nostdin", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
         "-t", f"{seconds:.3f}", "-c:a", "libmp3lame", "-b:a", "128k", str(public / "song.mp3")], "placeholder song")
    timing = {"version": 1, "duration": round(seconds, 3), "words": [], "lines": [], "sections": [], "placeholder": True}
    (public / "timing.json").write_text(json.dumps(timing, indent=1), encoding="utf-8")
    (public / "analysis.json").write_text(json.dumps(analysis(seconds, bpm)), encoding="utf-8")


def ensure(public: Path, meta: dict) -> bool:
    """Write the declared placeholder's files when they are missing or stale; a real song's files are left alone."""
    value = declared(meta)
    if value is None:
        return False
    current = public / "analysis.json"
    if current.is_file():
        if not is_placeholder(public):
            return False
        data = json.loads(current.read_text(encoding="utf-8"))
        if (data.get("duration") == round(value["seconds"], 3) and data.get("tempo") == round(value["bpm"], 1)
                and all((public / f).is_file() for f in FILES)):
            return False
    write_files(public, value["seconds"], value["bpm"])
    return True


def drop(public: Path, vdir: Path) -> bool:
    """The real song is here: remove the placeholder's files and set video.yaml back to `placeholder: null`."""
    dropped = False
    if is_placeholder(public):
        for name in FILES:
            (public / name).unlink(missing_ok=True)
        dropped = True
    if declared(read_meta(vdir)) is not None:
        set_declared(vdir, None)
        dropped = True
    return dropped


def describe(value: dict) -> str:
    return f"{value['seconds']:g} s at {value['bpm']:g} bpm"


def make(ws, video_id: str, seconds, bpm=None) -> dict:
    """`music-video placeholder <id> --seconds S [--bpm B]`: declare it in video.yaml and write its files."""
    vdir = ws.video_dir(video_id)
    if not (vdir / "video.yaml").is_file():
        raise MVError(f"no video '{video_id}' ({vdir} has no video.yaml): run music-video new-video {video_id} first")
    meta = read_meta(vdir)
    if meta.get("song"):
        raise MVError(f"{video_id} borrows the song {meta['song']} (song: in video.yaml): it has that song's timings")
    if song_filed(ws, video_id):
        raise MVError(f"the song {video_id} is filed: run music-video align {video_id} and analyze {video_id} instead")
    old = declared(meta)
    value = check(seconds if seconds is not None else (old or {}).get("seconds"),
                  bpm if bpm is not None else (old or {}).get("bpm", DEFAULT_BPM))
    public = ws.work_for(video_id) / "public"
    if public.is_dir() and any((public / f).is_file() for f in FILES) and not is_placeholder(public):
        raise MVError(f"{public} holds a song's timings: a placeholder would replace them")
    set_declared(vdir, value)
    write_files(public, value["seconds"], value["bpm"])
    return value


def song_filed(ws, song_id: str) -> bool:
    from ..spec import load_spec
    spec = ws.specs_dir / f"{song_id}.yaml"
    return spec.is_file() and load_spec(spec).get("status") == "filed"
