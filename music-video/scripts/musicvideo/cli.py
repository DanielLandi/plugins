import argparse
import json
import shutil
import sys
from collections import Counter
from datetime import date
from pathlib import Path

import yaml

from . import __version__
from . import studio
from .doctor import run_doctor
from .albums import load_album, write_manifest
from .errors import MVError
from .ingest import ingest
from .budget import cycle_start, downloads_in_cycle
from .spec import STATUSES, find_spec, iter_specs, load_spec, now_iso, save_spec, slugify, validate
from .video.align import align
from .video.analyze import analyze
from .video.loop import make_loop
from .video.mux import mux
from .video.paths import VideoPaths, open_file, video_song
from .video.preview import preview
from .video.qc import run_qc
from .video.timing import clock
from .workspace import init_workspace, install_dir, load_private_names, load_workspace, workspace_home



def cmd_init(args) -> int:
    home = Path(args.path).expanduser() if args.path else workspace_home()
    if not (home / "config.yaml").is_file() and not args.artist:
        raise MVError("a new workspace needs --artist (the name your songs are credited to)")
    home, created = init_workspace(home, args.artist or "", args.billing_day, args.download_budget,
                                   Path(args.results_dir).expanduser() if args.results_dir else None)
    print(f"{'created' if created else 'using existing'} workspace {home}")
    return 0


def _budget(ws):
    if ws.billing_day is None or ws.download_budget is None:
        raise MVError(f"set billing_day and download_budget in {ws.home / 'config.yaml'} "
                      "(read them from your song generator account's billing page) before recording a download")
    return ws.billing_day, ws.download_budget


def cmd_new(args) -> int:
    ws = load_workspace()
    spec_id = args.id or slugify(args.title)
    path = ws.specs_dir / f"{spec_id}.yaml"
    if path.exists():
        raise MVError(f"{path} already exists: pick another title or pass --id")
    save_spec(path, {"id": spec_id, "title": args.title, "kind": "original", "generator": "suno",
                     "suno": {"model": "v6", "styles": "", "exclude_styles": "", "lyrics": ""}, "status": "drafted"})
    print(path)
    return 0


def cmd_validate(args) -> int:
    if not args.id and not args.all:
        raise MVError("give a spec id or --all")
    ws = load_workspace()
    names = load_private_names(ws)
    paths = [p for p, _ in iter_specs(ws)] if args.all else [find_spec(ws, args.id)]
    failed = 0
    for path in paths:
        data = load_spec(path)
        try:
            album = load_album(ws, data["album"]) if data.get("album") else None
        except MVError as e:
            album, data_errors = None, [str(e)]
        else:
            data_errors = []
        errors = data_errors + validate(data, names, album)
        if errors:
            failed += 1
            print(f"{path.stem}: FAIL")
            for error in errors:
                print(f"  - {error}")
        else:
            print(f"{path.stem}: ok")
    return 1 if failed else 0


def cmd_round(args) -> int:
    ws = load_workspace()
    path = find_spec(ws, args.id)
    data = load_spec(path)
    rounds = data.get("rounds") or []
    rounds.append({"at": now_iso(), "changes": args.changes, "suno_urls": args.url or []})
    data["rounds"] = rounds
    if args.url and data.get("status") == "drafted":
        data["status"] = "generated"
    save_spec(path, data)
    print(f"round {len(rounds)} recorded for {args.id}")
    return 0


def cmd_downloaded(args) -> int:
    ws = load_workspace()
    path = find_spec(ws, args.id)
    data = load_spec(path)
    kept = data.get("kept") or {}
    if args.undo:
        if data.get("status") == "filed":
            raise MVError(f"{args.id} is already filed; nothing to undo")
        data.pop("kept", None)
        data["status"] = "generated"
        save_spec(path, data)
        print(f"download record removed for {args.id}")
        return 0
    if not args.take_url:
        raise MVError("--take-url is required")
    if kept.get("downloaded_at"):
        raise MVError(f"{args.id} already downloaded at {kept['downloaded_at']}; use --undo first")
    billing_day, budget = _budget(ws)
    today = date.today()
    start = cycle_start(today, billing_day)
    used = downloads_in_cycle((d for _, d in iter_specs(ws)), today, billing_day)
    if used >= budget and not args.paid_extra:
        raise MVError(f"download budget used up: {used} of {budget} since {start}; "
                      "pass --paid-extra only if the user confirmed buying an extra download")
    data["kept"] = {"take_url": args.take_url, "downloaded_at": now_iso()}
    data["status"] = "downloaded"
    save_spec(path, data)
    extra = " (paid extra)" if used >= budget else ""
    print(f"recorded download {used + 1} of {budget} for the cycle starting {start}{extra}")
    return 0


def cmd_status(args) -> int:
    ws = load_workspace()
    specs = [d for _, d in iter_specs(ws)]
    if ws.billing_day is None or ws.download_budget is None:
        print("Downloads: not tracked (set billing_day and download_budget in config.yaml)")
    else:
        today = date.today()
        used = downloads_in_cycle(specs, today, ws.billing_day)
        left = max(ws.download_budget - used, 0)
        start = cycle_start(today, ws.billing_day)
        print(f"Downloads: {used} of {ws.download_budget} used since {start} ({left} left)")
    counts = Counter(d.get("status") for d in specs)
    print("Songs: " + " · ".join(f"{s} {counts[s]}" for s in STATUSES))
    return 0


def cmd_ingest(args) -> int:
    print(ingest(load_workspace(), args.id, Path(args.file).expanduser() if args.file else None))
    return 0


def cmd_align(args) -> int:
    r = align(load_workspace(), args.id, lang=args.lang, force=args.force)
    t = r.timing
    print(f"timing: {r.timing_path} ({len(t['words'])} words, {len(t['lines'])} lines; "
          f"lyrics from the {r.lyrics_source})")
    print(f"repaired: {r.counts.get('transcript', 0)} from the transcription, "
          f"{r.counts.get('snapped', 0)} moved onto the voice, {r.counts.get('fixed', 0)} fixed by you")
    unsure = " · ".join(f"{clock(w['start'])} {w['text']} ({w['conf']:.2f})" for w in r.suspects)
    print(f"unsure words ({len(r.suspects)}): {unsure or 'none'}")
    missing = "; ".join(repr(m["text"]) for m in r.missing)
    print(f"possibly missing lines ({len(r.missing)}): {missing or 'none'}")
    return 0


def cmd_analyze(args) -> int:
    data = analyze(load_workspace(), args.id)
    print(f"tempo {data['tempo']} bpm · {len(data['beats'])} beats · {len(data['downbeats'])} bars")
    for s in data["sections"]:
        print(f"  {clock(s['start'])}–{clock(s['end'])}  {s['name']} ({s['id']}){'' if s['sung'] else ' · no vocals'}")
    print("big moments: " + (", ".join(clock(h["t"]) for h in data["hits"]) or "none"))
    return 0


def cmd_preview(args) -> int:
    path, beats = preview(load_workspace(), args.id)
    print(path)
    if not beats:
        print("no beat dots: run music-video analyze first to see them")
    if args.open:
        open_file(path)
    return 0


def _range(text: str) -> tuple[float, float]:
    try:
        start, end = (float(x) for x in text.split("-", 1))
    except ValueError as e:
        raise MVError(f"bad range {text!r}: use start-end in seconds, e.g. 44.0-54.0") from e
    if end <= start:
        raise MVError(f"bad range {text!r}: the end must come after the start")
    return start, end


def _size(text: str) -> tuple[int, int]:
    try:
        w, h = (int(x) for x in text.lower().split("x"))
    except ValueError as e:
        raise MVError(f"bad size {text!r}: use WIDTHxHEIGHT, e.g. 1920x1080") from e
    return w, h


def cmd_mux(args) -> int:
    song = video_song(load_workspace(), args.spec)
    print(mux(Path(args.video), song.paths.song, Path(args.out), _range(args.excerpt) if args.excerpt else None))
    return 0


def cmd_loop(args) -> int:
    song = video_song(load_workspace(), args.id)
    analysis = song.paths.analysis
    downbeats = json.loads(analysis.read_text(encoding="utf-8"))["downbeats"] if analysis.is_file() else None
    out = song.paths.root / "loop"
    meta = make_loop(song.paths.song, out, downbeats, args.end)
    print(f"loop {meta['start_s']:.2f}–{meta['end_s']:.2f} s ({meta['loopSamples'] / meta['rate']:.1f} s"
          f"{', on downbeats' if meta['onDownbeats'] else ', no beat grid'}) → {out}")
    if meta["clipped"]:
        print(f"warning: the crossfade clipped {meta['clipped']} samples; try another --end, or a quieter take")
    print(f"listen to the seam: {out / 'seam-preview.m4a'}")
    return 0


def cmd_qc(args) -> int:
    song = video_song(load_workspace(), args.spec)
    report = run_qc(Path(args.video), song.paths.song, song.paths.qc,
                    size=_size(args.size) if args.size else None, fps=args.fps,
                    excerpt=_range(args.excerpt) if args.excerpt else None,
                    holds=[_range(h) for h in args.hold or []])
    for check in report["checks"]:
        print(f"{'PASS' if check['ok'] else 'FAIL'}  {check['id']:<9} {check['detail']}")
    print(f"sheet: {report['sheet']} (look at it)")
    return 0 if report["result"] == "PASS" else 1


def cmd_paths(args) -> int:
    ws = load_workspace()
    meta_file = ws.video_dir(args.id) / "video.yaml"
    meta = (yaml.safe_load(meta_file.read_text(encoding="utf-8")) or {}) if meta_file.is_file() else {}
    song = str(meta.get("song") or args.id)  # a video can borrow another song's timings
    p = VideoPaths(ws.work_for(args.id), ws.results_for(args.id))
    print(json.dumps({"video": str(ws.video_dir(args.id)), "work": str(p.root),
                      "public": str(ws.work_for(song) / "public"), "renders": str(p.renders), "qc": str(p.qc),
                      "results": str(p.deliver), "web": str(p.deliver / "web")}, indent=2))
    return 0


def _overlaps(a: Path, b: Path) -> bool:
    return a == b or a.is_relative_to(b) or b.is_relative_to(a)


def cmd_clean(args) -> int:
    """Delete one video's work folder, and nothing else: it asks nothing, so the target is checked first."""
    if not studio.ID_RE.match(args.id or ""):
        raise MVError(f"'{args.id}' is not a video id (lowercase words joined by hyphens): nothing was deleted")
    ws = load_workspace()
    work_dir = ws.work_dir.expanduser().resolve()
    work = (work_dir / args.id).resolve()
    if work.parent != work_dir:
        raise MVError(f"{work} is not inside the work folder {work_dir}: nothing was deleted")
    for name, other in (("results", ws.results_dir), ("project", ws.home), ("install", install_dir())):
        if _overlaps(work, other.expanduser().resolve()):
            raise MVError(f"work_dir {work_dir} overlaps the {name} folder {other}: set its own work_dir in "
                          "config.yaml (default: the OS cache); nothing was deleted")
    if not work.exists():
        print(f"nothing to clean: {work} does not exist")
        return 0
    size = sum(f.stat().st_size for f in work.rglob("*") if f.is_file())
    shutil.rmtree(work)
    print(f"freed {size / 1e6:.0f} MB: removed {work} (finals are untouched)")
    return 0


def cmd_album(args) -> int:
    path, count = write_manifest(load_workspace(), args.album)
    print(f"{path} ({count} song{'' if count == 1 else 's'})")
    return 0


def cmd_doctor(args) -> int:
    return run_doctor(not args.no_install)


def _prepare(video_id):
    ws = load_workspace()
    rt = studio.ensure_ready()
    ctx = studio.video_context(ws, video_id)
    entry = studio.write_entry(rt, ctx.dir, video_id)
    return rt, ctx, entry, studio.tool_env(rt, ctx, entry)


def _resolve_output(rest: list[str], index: int) -> list[str]:
    """The tools run inside the engine folder: make the index-th positional argument (an output path) absolute
    against the caller's folder, so a relative output never lands in the engine's cache."""
    rest = list(rest)
    positions = [i for i, a in enumerate(rest) if not a.startswith("--")]
    if len(positions) > index:
        i = positions[index]
        rest[i] = str(Path(rest[i]).expanduser().resolve())
    return rest


def _remotion(command):
    def run(args) -> int:
        rest = list(args.rest)
        if command in ("render", "still") and len(rest) < 2:
            raise MVError(f"usage: music-video {command} <id> <composition> <out> [flags]")
        rt, ctx, entry, env = _prepare(args.id)
        if command in ("render", "still"):
            rest = _resolve_output(rest, 1)
        cmd = [*studio.tool(rt, "remotion"), command, str(entry), *rest, f"--public-dir={ctx.public}"]
        if command != "studio":
            cmd.append(f"--gl={ctx.gl}")
        return studio.run_node(cmd, rt, env)
    return run


def _tool(script, output_index=None):
    def run(args) -> int:
        rt, ctx, entry, env = _prepare(args.id)
        rest = _resolve_output(args.rest, output_index) if output_index is not None else list(args.rest)
        return studio.run_node([*studio.tool(rt, "tsx"), f"tools/{script}", args.id, *rest], rt, env)
    return run


def cmd_web(args) -> int:
    rt, ctx, entry, env = _prepare(args.id)
    ws = load_workspace()
    env["MV_WEB_ENTRY"] = str(studio.web_entry(rt, ctx))
    out = Path(args.out).expanduser().resolve() if args.out else ws.results_for(args.id) / "web"
    studio.check_web_out(out)
    cmd = [*studio.tool(rt, "tsx"), "tools/web.ts", args.id, "--out", str(out)]
    if args.audio_loop:
        loop = ws.work_for(args.audio_loop) / "loop"
        if not (loop / "loop.m4a").is_file() or not (loop / "loop.json").is_file():
            raise MVError(f"no audio loop in {loop}: run music-video loop {args.audio_loop} first")
        cmd += ["--audio", str(loop)]
    for flag in ("title", "description", "label", "background"):
        if getattr(args, flag):
            cmd += [f"--{flag}", getattr(args, flag)]
    return studio.run_node(cmd, rt, env)


def cmd_new_video(args) -> int:
    print(studio.new_video(load_workspace(), args.id))
    return 0


def cmd_typecheck(args) -> int:
    rt, ctx, entry, env = _prepare(args.id)
    return studio.run_node([*studio.tool(rt, "tsc"), "-p", str(studio.typecheck_config(rt, ctx))], rt, env)


HANDLERS: dict = {"web": cmd_web, "album": cmd_album, "loop": cmd_loop, "clean": cmd_clean, "new-video": cmd_new_video, "typecheck": cmd_typecheck, "studio": _remotion("studio"),
                  "render": _remotion("render"), "still": _remotion("still"), "stills": _tool("stills.ts", 1),
                  "blur": _tool("blur.ts", 1), "board": _tool("board.ts"), "doctor": cmd_doctor, "align": cmd_align, "analyze": cmd_analyze, "preview": cmd_preview, "mux": cmd_mux,
                  "qc": cmd_qc, "paths": cmd_paths, "ingest": cmd_ingest, "init": cmd_init, "new": cmd_new, "validate": cmd_validate, "round": cmd_round,
                  "downloaded": cmd_downloaded, "status": cmd_status}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="music-video", description="Songs (from your own song generator account) and the music videos made from them.")
    parser.add_argument("--version", action="version", version=f"music-video {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("doctor", help="check the tools and install the video engine (once, about 1.7 GB)")
    p.add_argument("--no-install", action="store_true", help="only check; do not install the engine's packages")
    p = sub.add_parser("init", help="create (or point at) your workspace")
    p.add_argument("--path", help="workspace folder (default: ~/Movies/Music Videos)")
    p.add_argument("--artist", help="the name your songs are credited to")
    p.add_argument("--billing-day", type=int, help="the day your song generator plan renews (from your account page)")
    p.add_argument("--download-budget", type=int, help="downloads included per billing cycle")
    p.add_argument("--results-dir", help="where finals go (default: ~/Movies/Music Videos)")
    p = sub.add_parser("new", help="create a song spec skeleton in the workspace")
    p.add_argument("--title", required=True)
    p.add_argument("--id", help="spec id (default: the title, slugified)")
    p = sub.add_parser("validate", help="check a spec (or --all) against the schema and private names")
    p.add_argument("id", nargs="?")
    p.add_argument("--all", action="store_true")
    p = sub.add_parser("round", help="record one create round with the song generator")
    p.add_argument("id")
    p.add_argument("--changes", required=True, help="what changed this round, or why it was rejected")
    p.add_argument("--url", action="append", help="a take's URL (repeat for each take)")
    p = sub.add_parser("downloaded", help="record a download before clicking Download (counts against the budget)")
    p.add_argument("id")
    p.add_argument("--take-url")
    p.add_argument("--paid-extra", action="store_true", help="the user confirmed buying an extra download")
    p.add_argument("--undo", action="store_true")
    sub.add_parser("status", help="downloads used this cycle and songs by status")
    p = sub.add_parser("album", help="rewrite an album's manifest.json from its filed songs")
    p.add_argument("album")
    p = sub.add_parser("ingest", help="file a downloaded MP3, tagged, into its results or album folder")
    p.add_argument("id")
    p.add_argument("--file", help="the MP3 (default: find it in the downloads folder by title)")
    p = sub.add_parser("align", help="word timings for a filed song")
    p.add_argument("id")
    p.add_argument("--lang", default="en", help="sung language, e.g. en or pt")
    p.add_argument("--force", action="store_true", help="redo vocal separation and transcription too")
    p = sub.add_parser("analyze", help="tempo, beats, sections, energy and big moments")
    p.add_argument("id")
    p = sub.add_parser("preview", help="full-song karaoke preview to check word and beat sync")
    p.add_argument("id")
    p.add_argument("--open", action="store_true", help="open the preview when it is ready")
    p = sub.add_parser("mux", help="put the song's audio under a silent render")
    p.add_argument("video")
    p.add_argument("--spec", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--excerpt", help="start-end in seconds, for the sample and the vertical cut")
    p = sub.add_parser("qc", help="check a render: format, black/frozen frames, audio, frame sheet")
    p.add_argument("video")
    p.add_argument("--spec", required=True)
    p.add_argument("--excerpt", help="start-end in seconds when the video is an excerpt")
    p.add_argument("--hold", action="append", help="a designed still or black stretch, start-end in song time (as in video.yaml holds); repeatable")
    p.add_argument("--size", help="expected WIDTHxHEIGHT")
    p.add_argument("--fps", type=float, default=30)
    p = sub.add_parser("new-video", help="start a video's code folder from the template")
    p.add_argument("id")
    p = sub.add_parser("typecheck", help="type-check a video's code against the engine")
    p.add_argument("id")
    for name, text in (("studio", "open Remotion Studio on a video"),
                       ("render", "render a composition: <id> <composition> <out> [remotion flags]"),
                       ("still", "render one frame: <id> <composition> <out.png> [--frame=N]"),
                       ("stills", "several stills + a contact sheet: <id> <composition> <out-dir> <frames> [--seconds]"),
                       ("blur", "motion-blurred render: <id> <composition> <out.mp4> [--samples=32]"),
                       ("board", "the transition board: every cut at 10%%…90%%")):
        p = sub.add_parser(name, help=text)
        p.add_argument("id")
        p.add_argument("rest", nargs=argparse.REMAINDER)
    p = sub.add_parser("loop", help="a seamless audio loop of a song (for a web page), with a seam preview")
    p.add_argument("id")
    p.add_argument("--end", type=float, help="where the loop ends, in song seconds (default: a downbeat before the ending)")
    p = sub.add_parser("web", help="a live web page of the video (its web.tsx), looping, into results/<id>/web")
    p.add_argument("id")
    p.add_argument("--audio-loop", metavar="SONG_ID", help="play this song's audio loop (music-video loop) under it")
    p.add_argument("--title", help="the page title (default: the video id)")
    p.add_argument("--description", help="the page's meta description")
    p.add_argument("--label", help="what the animation shows, for screen readers")
    p.add_argument("--background", help="the page colour behind the animation, e.g. #c9d3e6")
    p.add_argument("--out", help="output folder (default: results/<id>/web)")
    p = sub.add_parser("paths", help="a video's folders (code, work, public, renders, qc, results, web) as JSON")
    p.add_argument("id")
    p = sub.add_parser("clean", help="delete a video's work folder (renders, timings, checks); finals stay")
    p.add_argument("id")
    return parser


def main(argv: list[str] | None = None, parser: argparse.ArgumentParser | None = None,
         handlers: dict | None = None) -> int:
    args = (parser or build_parser()).parse_args(argv)
    handler = (handlers or HANDLERS)[args.command]
    try:
        return handler(args)
    except MVError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
