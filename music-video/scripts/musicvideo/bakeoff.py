"""The character-engine bake-off and the model watch.

A bake-off builds one short brief (the make skill's references/bakeoff.md) once per character engine, as
compositions <id>-bakeoff-<engine> over the same song window, kept as variants of the scene `bakeoff` on the review
page. `scaffold` starts one inside any video (or a new video borrowing a song); `record` adds the run to bakeoffs.md
next to the workspace's config.yaml; `watch` tells a later session whether its model has been checked yet.
"""
import json
import re
from datetime import date
from pathlib import Path

import yaml

from . import studio
from .characters import ENGINES, check_engines
from .errors import MVError
from .workspace import Workspace

WINDOW = 10.0        # seconds of song per take
HIT_AT = 6.0         # where the strongest hit falls inside the window (the brief's clash)
BAKEOFFS = "bakeoffs.md"
STARTERS = studio.PLUGIN_STUDIO / "bakeoff"
HEADER = ("# Bake-offs\n\n"
          "Every character-engine bake-off: the same brief (the make skill's references/bakeoff.md) built once per "
          "engine and compared on the review page. One row per run, newest last; a declined offer is a row too, so a "
          "model is offered once. `music-video bakeoff last --model <id>` reads it.\n\n"
          "| Date | Model | Engines | Video | Verdict |\n|---|---|---|---|---|\n")
ROW_RE = re.compile(r"^\|(?P<cells>.*)\|\s*$")
WINDOW_RE = re.compile(r"from: ([0-9.]+), to: ([0-9.]+),")
WIRING = """import { bakeoff } from './bakeoff';
// …inside Compositions, after the others (see the plugin's studio/template/index.tsx for the Bakeoff component):
{bakeoff.entries.map(({ engine }) => (
  <Composition key={engine} id={`${ID}-bakeoff-${engine}`} component={Bakeoff} width={1920} height={1080}
    {...common} defaultProps={{ data: null, engine }} calculateMetadata={songMetadata<Props & { engine?: string }>(bakeoff)} />
))}"""


def default_window(analysis: dict, length: float = WINDOW) -> tuple[float, float]:
    """A window of `length` s with the song's strongest hit HIT_AT s in, kept inside the song."""
    duration = float(analysis.get("duration") or length)
    if duration <= length:
        return 0.0, round(duration, 2)
    hits = analysis.get("hits") or []
    start = 0.0
    if hits:
        top = max(float(h.get("strength", 0)) for h in hits)
        first = min(float(h["t"]) for h in hits if float(h.get("strength", 0)) == top)
        start = first - HIT_AT
    start = min(max(0.0, start), duration - length)
    return round(start, 2), round(start + length, 2)


def _meta(vdir: Path) -> dict:
    path = vdir / "video.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) if path.is_file() else None
    return data if isinstance(data, dict) else {}


def _set_song(vdir: Path, song: str) -> None:
    """Add `song:` under `id:` in a fresh video.yaml, keeping its comments."""
    path = vdir / "video.yaml"
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    at = next((i + 1 for i, line in enumerate(lines) if line.startswith("id:")), 0)
    lines.insert(at, f"# The song this bake-off borrows (its timing and analysis).\nsong: {song}\n")
    path.write_text("".join(lines), encoding="utf-8")


def _written(vdir: Path) -> list[str]:
    folder = vdir / "bakeoff"
    return [e for e in ENGINES if (folder / f"{e}.tsx").is_file()]


def _bakeoff_ts(engines: list[str], window: tuple[float, float]) -> str:
    names = {e: e[:1].upper() + e[1:] for e in engines}
    imports = "".join(f"import {{ Bakeoff as {names[e]} }} from './bakeoff/{e}';\n" for e in engines)
    entries = ", ".join(f"{{ engine: '{e}', Component: {names[e]} }}" for e in engines)
    return ("import type { BakeoffEntry } from '@mv/kit';\n" + imports + "\n"
            "// Written by `music-video bakeoff new`: one take of the brief per character engine (bakeoff/<engine>.tsx),\n"
            "// each a composition <id>-bakeoff-<engine> over this song window (seconds). Edit from/to by hand, or\n"
            "// run bakeoff new again with --from; delete the takes and empty `entries` once the engine is chosen.\n"
            f"export const bakeoff: {{ from: number; to: number; entries: BakeoffEntry[] }} = {{\n"
            f"  from: {window[0]:g}, to: {window[1]:g},\n  entries: [{entries}],\n}};\n")


def _fmt(x: float) -> str:
    return f"{x:g}"


def _sources(vdir: Path) -> None:
    path = vdir / "SOURCES.md"
    text = path.read_text(encoding="utf-8") if path.is_file() else "| Asset | Source | Licence |\n|---|---|---|\n"
    if "vroid-sample" in text:
        return
    row = ("| Characters (vrm): `vroid-sample-1.vrm` … `vroid-sample-4.vrm` | VRoid β AvatarSample_1–4 by VRoid Project "
           "(pixiv Inc.), https://vroid.pixiv.help/hc/en-us/articles/4402614652569; installed by music-video avatars "
           "install | CC0 |\n")
    path.write_text(text.rstrip("\n") + "\n" + row, encoding="utf-8")


def scaffold(ws: Workspace, video_id: str, engines: list[str] | None = None, start: float | None = None,
             song: str | None = None) -> dict:
    """Start (or extend) a bake-off in a video: starters for engines not written yet, and bakeoff.ts. With `song`,
    a missing video is created from the template, borrowing that song."""
    wanted = check_engines(["raw", *(engines or ENGINES)])  # raw is always in a bake-off, first
    vdir = ws.video_dir(video_id)
    if not vdir.is_dir():
        if not song:
            raise MVError(f"no video '{video_id}': give --song <song id> to start a bake-off video that borrows that "
                          "song's timing, or use an existing video's id")
        studio.new_video(ws, video_id)
        _set_song(vdir, song)
    elif song and str(_meta(vdir).get("song") or video_id) != song:
        raise MVError(f"{video_id} already uses the song {_meta(vdir).get('song') or video_id}: leave out --song")
    old_ts = vdir / "bakeoff.ts"
    window = None
    if start is not None:
        window = (round(float(start), 2), round(float(start) + WINDOW, 2))
    elif old_ts.is_file() and (m := WINDOW_RE.search(old_ts.read_text(encoding="utf-8"))) and _written(vdir):
        window = (float(m.group(1)), float(m.group(2)))
    if window is None:
        song_id = str(_meta(vdir).get("song") or video_id)
        analysis = ws.work_for(song_id) / "public" / "analysis.json"
        if not analysis.is_file():
            raise MVError(f"no analysis.json for {song_id}: run music-video analyze {song_id}, or give --from <seconds>")
        window = default_window(json.loads(analysis.read_text(encoding="utf-8")))
    added = []
    (vdir / "bakeoff").mkdir(exist_ok=True)
    for engine in wanted:
        target = vdir / "bakeoff" / f"{engine}.tsx"
        if not target.exists():
            target.write_text((STARTERS / f"{engine}.tsx").read_text(encoding="utf-8"), encoding="utf-8")
            added.append(engine)
    takes = _written(vdir)
    old_ts.write_text(_bakeoff_ts(takes, window), encoding="utf-8")
    if "vrm" in takes:
        _sources(vdir)
    index = vdir / "index.tsx"
    wired = index.is_file() and "from './bakeoff'" in index.read_text(encoding="utf-8")
    return {"video": video_id, "dir": vdir, "engines": takes, "added": added, "window": window, "wired": wired}


def next_steps(ws: Workspace, out: dict) -> list[str]:
    """The commands that render, check and keep each take, for the skill and the user."""
    vid, (a, b) = out["video"], out["window"]
    song = str(_meta(out["dir"]).get("song") or vid)
    renders = ws.work_for(vid) / "renders"
    ex = f"{_fmt(a)}-{_fmt(b)}"
    lines = []
    for e in out["engines"]:
        silent, clip = renders / f"bakeoff-{e}-silent.mp4", renders / f"bakeoff-{e}.mp4"
        lines += [f"music-video render {vid} {vid}-bakeoff-{e} \"{silent}\" --muted",
                  f"music-video mux \"{silent}\" --spec {song} --out \"{clip}\" --excerpt {ex}",
                  f"music-video qc \"{clip}\" --spec {song} --excerpt {ex}",
                  f"music-video version {vid} \"{clip}\" --scene bakeoff --variant {e} --excerpt {ex}"]
    return lines


# ---- the record: bakeoffs.md ----

def _cell(text: str) -> str:
    return " ".join(str(text).split()).replace("|", "\\|")


def _split(cells: str) -> list[str]:
    parts = re.split(r"(?<!\\)\|", cells)
    return [p.strip().replace("\\|", "|") for p in parts]


def records(ws: Workspace) -> list[dict]:
    path = ws.home / BAKEOFFS
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = ROW_RE.match(line)
        if not m:
            continue
        cells = _split(m.group("cells"))
        if len(cells) != 5 or cells[0] in ("Date", "---") or set(cells[0]) <= {"-"}:
            continue
        day, model, engines, video, verdict = cells
        rows.append({"date": day, "model": model, "video": None if video == "-" else video, "verdict": verdict,
                     "engines": [] if engines == "-" else [e.strip() for e in engines.split(",") if e.strip()]})
    return rows


def record(ws: Workspace, video_id: str | None, model: str, verdict: str, engines: list[str] | None = None,
           declined: bool = False, today: str | None = None) -> dict:
    """Add one run (or a declined offer) to bakeoffs.md."""
    model = (model or "").strip()
    if not model:
        raise MVError("say which model ran it: --model <model id>")
    if declined:
        row = {"engines": [], "video": None, "verdict": "declined" + (f": {verdict.strip()}" if verdict.strip() else "")}
    else:
        if not verdict.strip():
            raise MVError("give the user's verdict in their words: --verdict \"…\"")
        if not video_id:
            raise MVError("say which video holds the bake-off")
        found = engines or _written(ws.video_dir(video_id))
        if not found:
            raise MVError(f"{video_id} has no bake-off takes (bakeoff/<engine>.tsx): run music-video bakeoff new first")
        row = {"engines": check_engines(found), "video": video_id, "verdict": verdict.strip()}
    row.update(date=today or date.today().isoformat(), model=model)
    path = ws.home / BAKEOFFS
    text = path.read_text(encoding="utf-8") if path.is_file() else HEADER
    line = (f"| {row['date']} | {_cell(model)} | {', '.join(row['engines']) or '-'} | {_cell(row['video'] or '-')} | "
            f"{_cell(row['verdict'])} |\n")
    path.write_text(text.rstrip("\n") + "\n" + line, encoding="utf-8")
    return row


def watch(ws: Workspace, model: str) -> dict:
    """Whether to offer the benchmark to this session's model: once per model, never when it already ran or was
    declined for it."""
    rows = records(ws)
    runs = [r for r in rows if r["engines"]]
    last = runs[-1] if runs else None
    seen = [r for r in rows if r["model"] == model]
    if seen:
        reason = (f"{model} already has a bake-off ({seen[-1]['date']})" if seen[-1]["engines"]
                  else f"{model} was offered the benchmark on {seen[-1]['date']} and the user declined")
        return {"last": last, "offer": False, "reason": reason}
    reason = (f"no bake-off recorded yet" if last is None
              else f"the last bake-off ran with {last['model']} on {last['date']}; this session runs {model}")
    return {"last": last, "offer": True, "reason": reason}
