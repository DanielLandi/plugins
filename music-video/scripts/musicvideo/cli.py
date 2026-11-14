import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter
from datetime import date
from pathlib import Path

import yaml

from . import __version__
from . import avatars, bakeoff, library, studio
from .doctor import run_doctor
from .albums import load_album, write_manifest
from .errors import MVError
from .ingest import ingest
from .budget import cycle_start, downloads_in_cycle
from .spec import (STATUSES, find_spec, iter_specs, iter_worktree_specs, load_spec, now_iso, save_spec, slugify,
                   validate)
from .video.align import align
from .video.analyze import analyze
from .video.loop import make_loop
from .video.mux import mux
from .video.paths import VideoPaths, open_file, song_for, video_song
from .video.preview import preview
from .video.qc import run_qc
from .video.review import build_page, load_versions, mark_review, record_version, review_mark, version_label
from .video.songfix import lifted_song
from .video.timing import clock
from .video import placeholder, timing_editor
from .workspace import (cache_dir, config_path, init_workspace, install_dir, load_private_names, load_workspace,
                        main_counterpart, remember_home, saved_home, warn_if_no_private_names, workspace_home)
from .worktrees import linked_worktree



def cmd_init(args) -> int:
    home = Path(args.path).expanduser() if args.path else workspace_home()
    if not config_path(home).is_file() and not args.artist:
        raise MVError("a new workspace needs --artist (the name your songs are credited to)")
    home, created = init_workspace(home, args.artist or "", args.billing_day, args.download_budget,
                                   Path(args.results_dir).expanduser() if args.results_dir else None)
    print(f"{'created' if created else 'using existing'} workspace {home}")
    if (wt := linked_worktree(home)) is not None:
        if (saved := saved_home()) is None:
            # Nothing saved yet: save the main checkout's folder (never the worktree), so that commands run here map
            # to this worktree and commands run in the main checkout find the workspace there.
            saved = main_counterpart(home)
            remember_home(saved)
            print(f"this is a worktree of {wt.main}; saved the workspace as {saved} (the main checkout's folder): "
                  "this worktree maps to it")
        else:
            print(f"this is a worktree of {wt.main}; the saved workspace stays {saved}")
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
    warn_if_no_private_names(ws)
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
    specs = list(iter_worktree_specs(ws))  # every worktree
    used = downloads_in_cycle(specs, today, billing_day)
    if used >= budget and not args.paid_extra:
        raise MVError(f"download budget used up: {used} of {budget} since {start}; "
                      "pass --paid-extra only if the user confirmed buying an extra download")
    data["kept"] = {"take_url": args.take_url, "downloaded_at": now_iso()}
    data["status"] = "downloaded"
    save_spec(path, data)
    extra = " (paid extra)" if used >= budget else ""
    print(f"recorded download {used + 1} of {budget} for the cycle starting {start}{extra}")
    for other_path, other in specs:  # ingest refuses to file a second take of one song: say so now
        other_take = (other.get("kept") or {}).get("take_url")
        if other_path.stem == path.stem and other_path != path and other_take and other_take != args.take_url:
            print(f"warning: {other_path} records another take of '{args.id}' ({other_take}): ingest will refuse "
                  "to file this one until one take is kept (merge that branch's spec, or undo one)", file=sys.stderr)
    return 0


def cmd_status(args) -> int:
    ws = load_workspace()
    specs = [d for _, d in iter_specs(ws)]
    if ws.billing_day is None or ws.download_budget is None:
        print("Downloads: not tracked (set billing_day and download_budget in config.yaml)")
    else:
        today = date.today()
        used = downloads_in_cycle(iter_worktree_specs(ws), today, ws.billing_day)
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
    r = align(load_workspace(), args.id, lang=args.lang, force=args.force, onsets=args.onsets)
    t = r.timing
    print(f"timing: {r.timing_path} ({len(t['words'])} words, {len(t['lines'])} lines; "
          f"lyrics from the {r.lyrics_source})")
    print(f"repaired: {r.counts.get('transcript', 0)} from the transcription, "
          f"{r.counts.get('snapped', 0)} moved onto the voice, {r.counts.get('fixed', 0)} fixed by you")
    if r.onsets.startswith("on"):
        shifts = sorted(m["moved"] for m in r.moves)
        median = f"{shifts[len(shifts) // 2]:+.2f}" if shifts else "+0.00"
        biggest = ", ".join(f"{clock(m['start'])} {m['text']} {m['moved']:+.2f} s" for m in r.moves[:5])
        print(f"onsets: {r.onsets}: {len(r.moves)} of {len(r.timing['words'])} words moved (median {median} s)"
              + (f"; biggest: {biggest}" if biggest else ""))
    else:
        print(f"onsets: {r.onsets}")
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
    d = data["drums"]
    counts = Counter(h["kind"] for h in d["hits"])
    source = ("the mix minus the vocal stem (there is no drum stem: align separates only the vocals)"
              if d["source"] == "mix minus vocals" else "the whole mix (no vocal stem to take off)")
    print(f"drums: {counts['kick']} kicks, {counts['snare']} snares, {counts['hat']} hats, {counts['crash']} crashes, "
          f"from {source}" + (f"; the beat grid sits {d['grid']:.2f} beat from them"
                              + (" (more than 0.1: check the grid)" if d["grid"] > 0.1 else "")
                              if d["grid"] is not None else ""))
    return 0


def cmd_preview(args) -> int:
    path, beats = preview(load_workspace(), args.id)
    print(path)
    if not beats:
        print("no beat dots: run music-video analyze first to see them")
    if args.open:
        open_file(path)
    return 0


def cmd_edit_timing(args) -> int:
    ws = load_workspace()
    lang = args.lang
    if not lang:
        meta_file = ws.video_dir(args.id) / "video.yaml"
        meta = (yaml.safe_load(meta_file.read_text(encoding="utf-8")) or {}) if meta_file.is_file() else {}
        lang = str(meta.get("lang") or "en")
    timing_editor.serve(ws, args.id, lang, port=args.port, open_page=args.open)
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
    ws = load_workspace()
    song = video_song(ws, song_for(ws, args.spec))
    excerpt = _range(args.excerpt) if args.excerpt else None
    print(mux(Path(args.video), lifted_song(song.paths), Path(args.out), excerpt, args.tail))
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


def _qc_context(ws, spec: str, public: Path) -> tuple[list[float], list[float], bool]:
    """What qc reads on its own, all song time: the scene changes (analysis.json sections) and the video's designed
    hard cuts (video.yaml `cuts:`), the sung word starts (timing.json), and the jolts answer (video.yaml)."""
    meta_file = ws.video_dir(spec) / "video.yaml"
    meta = yaml.safe_load(meta_file.read_text(encoding="utf-8")) if meta_file.is_file() else None
    meta = meta if isinstance(meta, dict) else {}
    cuts = [float(c) for c in meta.get("cuts") or []]
    analysis, timing = public / "analysis.json", public / "timing.json"
    if analysis.is_file():
        cuts += [float(s["start"]) for s in json.loads(analysis.read_text(encoding="utf-8"))["sections"]]
    words = ([float(w["start"]) for w in json.loads(timing.read_text(encoding="utf-8")).get("words", [])]
             if timing.is_file() else [])
    return cuts, words, meta.get("jolts") is True


def cmd_qc(args) -> int:
    ws = load_workspace()
    meta = placeholder.read_meta(ws.video_dir(args.spec))
    stand_in = None if meta.get("song") else placeholder.declared(meta)
    if stand_in is not None and placeholder.song_filed(ws, args.spec):
        stand_in = None  # the real song is here: video_song below replaces the placeholder
    common = dict(size=_size(args.size) if args.size else None, fps=args.fps,
                  excerpt=_range(args.excerpt) if args.excerpt else None,
                  holds=[_range(h) for h in args.hold or []], tail=args.tail)
    if args.silent or stand_in is not None:
        # No song: every picture check, none of the song's (a placeholder video, or a clip with no song at all).
        public = ws.work_for(str(meta.get("song") or args.spec)) / "public"
        if stand_in is not None:
            placeholder.ensure(public, meta)
        cuts, words, jolts = _qc_context(ws, args.spec, public)
        report = run_qc(Path(args.video), None, ws.work_for(args.spec) / "qc", **common,
                        cuts=cuts + list(args.cut or []), words=words, jolts=jolts,
                        length=stand_in["seconds"] if stand_in else None, placeholder=stand_in,
                        finals=ws.results_for(args.spec))
    else:
        try:
            song = video_song(ws, song_for(ws, args.spec))
        except MVError as e:
            raise MVError(f"{e} (a clip with no song: qc --silent, or give the video a placeholder song with "
                          f"music-video placeholder {args.spec} --seconds <s>)") from e
        cuts, words, jolts = _qc_context(ws, args.spec, song.paths.public)
        report = run_qc(Path(args.video), lifted_song(song.paths), song.paths.qc, **common,
                        cuts=cuts + list(args.cut or []), words=words, jolts=jolts)
    for check in report["checks"]:
        status = "SKIP" if check.get("skipped") else "PASS" if check["ok"] else "FAIL"
        print(f"{status}  {check['id']:<9} {check['detail']}")
    print(f"sheet: {report['sheet']} (look at it)")
    if report["placeholder"]:
        print("placeholder: this render stands on a silent placeholder song; it is not a final")
    return 0 if report["result"] == "PASS" else 1


def cmd_placeholder(args) -> int:
    ws = load_workspace()
    value = placeholder.make(ws, args.id, args.seconds, args.bpm)
    print(f"placeholder song for {args.id}: {placeholder.describe(value)}, silent, no words, a steady beat grid "
          f"→ {ws.work_for(args.id) / 'public'}")
    print("render, still, studio and qc work on it now; once the real song is filed, align and analyze replace it")
    return 0


def cmd_version(args) -> int:
    if args.excerpt and args.at is not None:
        raise MVError("give --excerpt (a clip) or --at (a still), not both")
    start = _range(args.excerpt)[0] if args.excerpt else args.at
    ws = load_workspace()
    v = record_version(ws, args.id, Path(args.file), args.scene, start=start, note=args.note or "",
                       variant=args.variant, issues=args.issue)
    shows = f"{clock(v['start'])}–{clock(v['start'] + v['duration'])}" if v["kind"] == "video" else "a still"
    issues = f", {len(v['issues'])} known issue{'s' if len(v['issues']) != 1 else ''}" if v["issues"] else ""
    print(f"kept {version_label(v)} ({shows}{', code ' + v['code'] if v['code'] else ''}{issues}), waiting review")
    print(f"review: {build_page(ws, args.id)}")
    return 0


def cmd_review(args) -> int:
    ws = load_workspace()
    if args.reviewed is not None or args.waiting or args.issue:
        if not args.version:
            raise MVError("say which version: --version scene:vN (e.g. relay:v2)")
        v = mark_review(ws, args.id, args.version, reviewed=args.reviewed, waiting=args.waiting, issue=args.issue)
        print(f"{version_label(v)}: {review_mark(v) or 'no mark'}"
              + (f"; {len(v.get('issues', []))} known issues" if v.get("issues") else ""))
    versions = load_versions(ws, args.id)
    page = build_page(ws, args.id, versions)
    scenes: dict[str, list[dict]] = {}
    for v in versions:
        scenes.setdefault(v["scene"], []).append(v)
    for scene, vs in scenes.items():
        print(f"{scene}: " + " · ".join(
            f"v{v['n']} {v['at'][5:16].replace('T', ' ')}" + (f" [{review_mark(v)}]" if review_mark(v) else "")
            + (f" ({len(v['issues'])} known issues)" if v.get("issues") else "") for v in vs))
    print(page if versions else f"{page} (no versions yet: keep one with music-video version)")
    if args.open:
        open_file(page)
    return 0


def cmd_sections(args) -> int:
    from .video import sections
    sections.serve(load_workspace(), args.id, Path(args.video) if args.video else None, args.start, port=args.port,
                   open_page=args.open)
    return 0


def cmd_notes(args) -> int:
    from .video import sections
    ws = load_workspace()
    store = sections.Notes(sections.notes_dir(ws, args.id))
    try:
        order = sections.read_scenes(ws.video_dir(args.id))
    except MVError:
        order = None
    if args.taken is not None:
        taken = store.take(args.taken)
        print(f"{len(taken)} note(s) marked as taken into Round {args.taken} of NOTES.md" if taken
              else "no new notes to mark")
        return 0
    notes = store.all() if args.all else store.new()
    if args.json:
        print(json.dumps({"folder": str(store.folder), "notes": notes}, indent=1, ensure_ascii=False))
        return 0
    if not notes:
        print(f"no new notes for {args.id} (the sections page saves them to {store.folder})")
        return 0
    print(f"{len(notes)} {'' if args.all else 'new '}note(s) for {args.id}, in song order:")
    print(sections.describe(notes, store.folder, order))
    return 0


def cmd_requests(args) -> int:
    from . import requests as rq
    ws = load_workspace()
    acts = [a for a in ("take", "update", "done") if getattr(args, a)]
    if len(acts) > 1:
        raise MVError("give one of --take, --update, --done")
    if acts:
        act = acts[0]
        name, rid = rq.parse_ref(getattr(args, act))
        q = rq.queue(ws, name)
        if act == "take":
            req = q.take(rid, args.message or "")
        elif act == "update":
            req = q.update(rid, args.message or "")
        else:
            if args.video and not studio.ID_RE.match(args.video):
                raise MVError(f"'{args.video}' is not a video id")
            req = q.done(rid, args.message or "", args.video)
        print(f"{name}:{rid} is {req['state']}: {req['text']}")
        return 0
    if args.wait:
        found = rq.wait_for_new(ws, args.timeout)
        if not found:
            print("no new requests")
            return 0
        print(f"{len(found)} new request(s): take each one (requests --take <ref>) and carry it out")
        print(rq.describe(found))
        return 0
    items = [(q.name, r) for q in rq.queues(ws, args.id) for r in (q.all() if args.all else q.pending())]
    items.sort(key=lambda x: x[1]["at"])
    if args.json:
        print(json.dumps([{"ref": f"{n}:{r['id']}", **r} for n, r in items], indent=1, ensure_ascii=False))
        return 0
    if not items:
        print(f"no open requests{' for ' + args.id if args.id else ''} (the home and the sections page queue them)")
        return 0
    print(f"{len(items)} {'' if args.all else 'open '}request(s), oldest first:")
    print(rq.describe(items))
    return 0


def cmd_home(args) -> int:
    from .video import home
    ws = load_workspace()
    home.serve(ws, port=args.port if args.port is not None else home.default_port(ws), open_page=args.open)
    return 0


def cmd_paths(args) -> int:
    ws = load_workspace()
    meta_file = ws.video_dir(args.id) / "video.yaml"
    meta = (yaml.safe_load(meta_file.read_text(encoding="utf-8")) or {}) if meta_file.is_file() else {}
    song = str(meta.get("song") or args.id)  # a video can borrow another song's timings
    p = VideoPaths(ws.work_for(args.id), ws.results_for(args.id))
    out = {"video": str(ws.video_dir(args.id)), "work": str(p.root),
           "public": str(ws.work_for(song) / "public"), "renders": str(p.renders), "qc": str(p.qc),
           "results": str(p.deliver), "web": str(p.deliver / "web")}
    if (stand_in := placeholder.declared(meta if isinstance(meta, dict) else {})) is not None:
        out["placeholder"] = stand_in
    if ws.lane:  # only in a git worktree: a main checkout's output is unchanged
        out["lane"] = ws.lane
    print(json.dumps(out, indent=2))
    return 0


def _overlaps(a: Path, b: Path) -> bool:
    return a == b or a.is_relative_to(b) or b.is_relative_to(a)


def cmd_clean(args) -> int:
    """Delete one video's work folder, and nothing else: it asks nothing, so the target is checked first."""
    if not studio.ID_RE.match(args.id or ""):
        raise MVError(f"'{args.id}' is not a video id (lowercase words joined by hyphens): nothing was deleted")
    ws = load_workspace()
    work_root = ws.work_root.expanduser().resolve()  # work_dir, or work_dir/.lanes/<key> in a git worktree
    work = (work_root / args.id).resolve()
    if work.parent != work_root:
        raise MVError(f"{work} is not inside the work folder {work_root}: nothing was deleted")
    work_dir = ws.work_dir.expanduser().resolve()
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
    return run_doctor(not args.no_install, avatars=not args.no_avatars)


def cmd_bakeoff(args) -> int:
    ws = load_workspace()
    if args.action == "last":
        if not args.model:
            raise MVError("say which model this session runs: --model <model id>")
        w = bakeoff.watch(ws, args.model)
        last = w["last"]
        print(f"last bake-off: {last['date']}, {last['model']} ({', '.join(last['engines'])}, video {last['video']}): "
              f"{last['verdict']}" if last else "last bake-off: none yet")
        print(("offer the benchmark once (never blocking): " if w["offer"] else "no offer: ") + w["reason"])
        print(f"record: {ws.home / bakeoff.BAKEOFFS}")
        return 0
    if args.action == "record":
        row = bakeoff.record(ws, args.id, args.model or "", args.verdict or "",
                             engines=args.engines.split(",") if args.engines else None, declined=args.declined)
        print(f"recorded {row['date']} {row['model']}: {row['verdict']} in {ws.home / bakeoff.BAKEOFFS}")
        return 0
    if not args.id:
        raise MVError(f"say which video: music-video bakeoff {args.action} <id>")
    if args.action == "clear":
        vdir = bakeoff.clear(ws, args.id)
        print(f"cleared the bake-off in {vdir}: takes removed, bakeoff.ts empty (kept versions stay on the review page)")
        return 0
    out = bakeoff.scaffold(ws, args.id, engines=args.engines.split(",") if args.engines else None,
                           start=args.start, song=args.song)
    a, b = out["window"]
    print(f"bake-off in {out['dir']}: {', '.join(out['engines'])} over {clock(a)}–{clock(b)} of the song, "
          f"the hit {out['hit']:g} s in"
          + (f" (new: {', '.join(out['added'])})" if out["added"] else ""))
    print("write each take from the brief: the make skill's references/bakeoff.md (bakeoff/<engine>.tsx)")
    if not out["wired"]:
        print("this video's index.tsx does not register bake-off compositions yet: add")
        print(bakeoff.WIRING)
    if "vrm" in out["engines"] and any(avatars.state(x) != "ok" for x in avatars.AVATARS):
        print("the vrm take needs the sample avatars: run music-video avatars install")
    print("then, per engine, render, add the song, check and keep it as a variant:")
    for line in bakeoff.next_steps(ws, out):
        print(f"  {line}")
    return 0


def cmd_avatars(args) -> int:
    if args.action == "add":
        if not args.file:
            raise MVError("say which file: music-video avatars add <file.vrm or .zip>")
        a = avatars.add(Path(args.file))
        print(f"ok   {a.file} ({a.name}) in {avatars.avatar_dir()}")
        return 0
    if args.action == "install":
        for line in avatars.install():
            print(line)
    for line in avatars.status_lines():
        print(line)
    print(f"folder: {avatars.avatar_dir()} (CC0, see SOURCES.md there)")
    return 0


def _prepare(video_id, need_avatars: bool = True):
    ws = load_workspace()
    rt = studio.ensure_ready(video_id, ws.lane)  # with this command's lease on the engine, released when it ends (main)
    ctx = studio.video_context(ws, video_id)
    if need_avatars:
        avatars.check_video(ctx.dir)  # a missing avatar stops here in one line, not in the bundler
    entry = studio.write_entry(rt, ctx.dir, video_id, lane=ctx.lane)
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
        watch = [a for a in rest if a.startswith(("--stall=", "--retries="))] if command == "render" else []
        rest = [a for a in rest if a not in watch]
        cmd = [*studio.tool(rt, "remotion"), command, str(entry), *rest, f"--public-dir={ctx.public}"]
        if command != "studio":
            cmd.append(f"--gl={ctx.gl}")
        if command == "render":  # a long render can hang with no frame failing: watch it as blur does (#16)
            flags = {a.split("=", 1)[0]: a for a in ["--stall=15", "--retries=2", *watch]}
            cmd = [*studio.tool(rt, "tsx"), "tools/watched.ts", flags["--stall"], flags["--retries"], "--label=render",
                   "--", *cmd]
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
    web_entry = studio.web_entry(rt, ctx)
    env["MV_WEB_ENTRY"] = str(web_entry)
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
    # This build's song data stages in a folder of its own, made and removed here: Ctrl-C stops node before its own
    # clean-up runs, and would leave the folder beside the entry.
    stage = Path(tempfile.mkdtemp(prefix="web-data-", dir=web_entry.parent))
    env["MV_WEB_STAGE"] = str(stage)
    try:
        return studio.run_node(cmd, rt, env)
    finally:
        shutil.rmtree(stage, ignore_errors=True)


def cmd_new_video(args) -> int:
    ws = load_workspace()
    if args.placeholder is not None:  # a bad length stops before the folder is made
        placeholder.check(args.placeholder, args.bpm if args.bpm is not None else placeholder.DEFAULT_BPM)
    print(studio.new_video(ws, args.id))
    if args.placeholder is not None:
        value = placeholder.make(ws, args.id, args.placeholder, args.bpm)
        print(f"placeholder song: {placeholder.describe(value)}, silent (music-video placeholder changes it)")
    return 0


def cmd_typecheck(args) -> int:
    rt, ctx, entry, env = _prepare(args.id, need_avatars=False)  # types need no model files
    return studio.run_node([*studio.tool(rt, "tsc"), "-p", str(studio.typecheck_config(rt, ctx))], rt, env)


def cmd_library(args) -> int:
    ws = load_workspace()
    folder, cache = install_dir() / "library", cache_dir() / "library"
    if args.action == "serve":
        if not ws.results_dir.is_dir():
            raise MVError(f"no results folder yet ({ws.results_dir}): finish a video or a song first")
        return library.main(["--root", str(ws.results_dir), "--port", str(args.port), "--host", args.host,
                             "--cache", str(cache)])
    if args.action in ("install", "uninstall") and sys.platform != "darwin":
        raise MVError("starting the library at login is macOS-only for now: run `music-video library serve` instead")
    if args.action == "install":
        try:
            plist = library.install_agent(ws.results_dir, args.port, cache, folder)
        except (RuntimeError, OSError, subprocess.CalledProcessError) as e:
            raise MVError(f"could not start the library at login: {e}") from e
        for _ in range(40):
            if library.answering(args.port):
                break
            time.sleep(0.25)
        else:
            raise MVError(f"the library did not answer on port {args.port}: see {cache / 'library.log'}")
        print(f"the library starts at every login ({plist})")
    elif args.action == "uninstall":
        print("the library no longer starts at login" if library.uninstall_agent(folder) else "it was not installed")
        return 0
    elif not library.answering(args.port):
        print(f"the library is not running on port {args.port}: `music-video library install` (at login) or "
              "`music-video library serve` (now)")
        return 1
    for u in library.lan_urls(args.port):
        print(f"open on any phone, tablet or TV on this network: {u}")
    print(f"showing {ws.results_dir}")
    return 0


HANDLERS: dict = {"library": cmd_library, "web": cmd_web, "album": cmd_album, "loop": cmd_loop, "clean": cmd_clean, "new-video": cmd_new_video, "placeholder": cmd_placeholder, "typecheck": cmd_typecheck, "studio": _remotion("studio"),
                  "render": _remotion("render"), "still": _remotion("still"), "stills": _tool("stills.ts", 1),
                  "blur": _tool("blur.ts", 1), "board": _tool("board.ts"), "doctor": cmd_doctor, "align": cmd_align, "analyze": cmd_analyze, "preview": cmd_preview, "edit-timing": cmd_edit_timing, "mux": cmd_mux,
                  "qc": cmd_qc, "version": cmd_version, "review": cmd_review, "sections": cmd_sections, "notes": cmd_notes, "requests": cmd_requests, "home": cmd_home, "paths": cmd_paths, "ingest": cmd_ingest, "init": cmd_init, "new": cmd_new, "validate": cmd_validate, "round": cmd_round,
                  "downloaded": cmd_downloaded, "status": cmd_status, "avatars": cmd_avatars, "bakeoff": cmd_bakeoff}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="music-video", description="Songs (from your own song generator account) and the music videos made from them.")
    parser.add_argument("--version", action="version", version=f"music-video {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("doctor", help="check the tools and install the video engine (once, about 1.7 GB)")
    p.add_argument("--no-install", action="store_true", help="only check; do not install the engine's packages")
    p.add_argument("--no-avatars", action="store_true", help="do not download the character avatars")
    p = sub.add_parser("bakeoff", help="character engines side by side: start a bake-off in a video, record its verdict, see the last one, or clear it")
    p.add_argument("action", choices=["new", "record", "last", "clear"])
    p.add_argument("id", nargs="?", help="the video (new, record, clear)")
    p.add_argument("--song", help="new: start a new video for the bake-off, borrowing this song's timing")
    p.add_argument("--engines", help="comma-separated engines (default: all; raw is always included)")
    p.add_argument("--from", dest="start", type=float, help="new: where the window starts, in song seconds")
    p.add_argument("--model", help="record, last: the model id that ran it, or this session's")
    p.add_argument("--verdict", help="record: the user's verdict, in their words")
    p.add_argument("--declined", action="store_true", help="record: the user declined the offer (not offered again to this model)")
    p = sub.add_parser("avatars", help="the CC0 sample characters for the vrm engine: status, install, or add a downloaded file")
    p.add_argument("action", nargs="?", default="status", choices=["status", "install", "add"])
    p.add_argument("file", nargs="?", help="with add: a .vrm (or the mirror's .zip) you downloaded yourself")
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
    g = p.add_mutually_exclusive_group()
    g.add_argument("--onsets", dest="onsets", action="store_true", default=None,
                   help="this run only: word starts on the first sound, whatever video.yaml says")
    g.add_argument("--no-onsets", dest="onsets", action="store_false",
                   help="this run only: keep the aligner's word starts, whatever video.yaml says")
    p = sub.add_parser("analyze", help="tempo, beats, sections, energy, big moments and drum hits")
    p.add_argument("id")
    p = sub.add_parser("preview", help="full-song karaoke preview to check word and beat sync")
    p.add_argument("id")
    p.add_argument("--open", action="store_true", help="open the preview when it is ready")
    p = sub.add_parser("edit-timing", help="drag each word to where it is sung on the vocal waveform, then save")
    p.add_argument("id")
    p.add_argument("--lang", help="sung language for the re-align (default: the video's lang, else en)")
    p.add_argument("--port", type=int, default=timing_editor.PORT)
    p.add_argument("--open", action="store_true", help="open the page in the browser")
    p = sub.add_parser("mux", help="put the song's audio under a silent render")
    p.add_argument("video")
    p.add_argument("--spec", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--excerpt", help="start-end in seconds, for the sample and the vertical cut")
    p.add_argument("--tail", type=float, default=0.0, help="seconds of silence after the song, for a video that runs on past it (an end screen)")
    p = sub.add_parser("qc", help="check a render: format, black/flash/frozen frames, flicker, pops, hard cuts, jitter, audio, frame sheet")
    p.add_argument("video")
    p.add_argument("--spec", required=True)
    p.add_argument("--excerpt", help="start-end in seconds when the video is an excerpt")
    p.add_argument("--hold", action="append", help="a designed still or black stretch, start-end in song time (as in video.yaml holds); repeatable")
    p.add_argument("--tail", type=float, default=0.0, help="seconds the video runs on past the song, silent (as given to mux)")
    p.add_argument("--cut", type=float, action="append", help="a designed hard cut inside a scene, in song seconds (scene changes and video.yaml cuts are read on their own); repeatable")
    p.add_argument("--size", help="expected WIDTHxHEIGHT")
    p.add_argument("--fps", type=float, default=30)
    p.add_argument("--silent", action="store_true", help="a clip with no song: every picture check, the song's skipped (a video with a placeholder song is checked this way on its own)")
    p = sub.add_parser("version", help="keep a checked render (or a still) as the next version of a scene, for review")
    p.add_argument("id")
    p.add_argument("file", help="a render that passed qc, or a still (.png/.jpg)")
    p.add_argument("--scene", required=True, help="the scene's name as in scenes.ts, or draft, sample, vertical")
    p.add_argument("--excerpt", help="start-end in song seconds when the render is an excerpt (as for mux and qc)")
    p.add_argument("--at", type=float, help="the song time a still shows, in seconds")
    p.add_argument("--note", help="what changed in this version (the notes it answers)")
    p.add_argument("--variant", help="keep it as a named variant of the scene (b, from-above…), to compare on the sections page")
    p.add_argument("--issue", action="append", help="something you already know is wrong in it, shown first on the review page (repeatable)")
    p = sub.add_parser("review", help="the review page: every version of every scene, two at a time in sync")
    p.add_argument("id")
    p.add_argument("--version", metavar="SCENE:vN", help="the version to mark (with --reviewed, --waiting or --issue)")
    p.add_argument("--reviewed", metavar="WORDS", help="mark it reviewed, with what the user said about it (reviewed is not approved)")
    p.add_argument("--waiting", action="store_true", help="mark it waiting review again")
    p.add_argument("--issue", help="add a known issue to it")
    p.add_argument("--open", action="store_true", help="open the page in the browser")
    p = sub.add_parser("sections", help="every scene of the newest draft on one page; open one to watch it large and leave notes on its frames")
    p.add_argument("id")
    p.add_argument("--video", help="another render to show (default: the newest draft kept with version)")
    p.add_argument("--start", type=float, help="the song time the --video render starts at, in seconds (default 0)")
    p.add_argument("--port", type=int, default=8645)
    p.add_argument("--open", action="store_true", help="open the page in the browser")
    p = sub.add_parser("notes", help="the notes left on the sections page, for the next round of NOTES.md")
    p.add_argument("id")
    p.add_argument("--all", action="store_true", help="also the notes already taken into a round")
    p.add_argument("--json", action="store_true")
    p.add_argument("--taken", type=int, metavar="ROUND", help="mark every new note as taken into this round")
    p = sub.add_parser("home", help="one page with every song and video and its stage; its buttons queue requests for Claude")
    p.add_argument("--port", type=int, default=None, help="default 8646; a free port in a git worktree")
    p.add_argument("--open", action="store_true", help="open the page in the browser")
    p = sub.add_parser("requests", help="what the user asked for on the home and sections pages, for Claude to carry out")
    p.add_argument("id", nargs="?", help="only this video's requests")
    p.add_argument("--all", action="store_true", help="also the requests already done")
    p.add_argument("--json", action="store_true")
    p.add_argument("--take", metavar="REF", help="start on a request (<video>:r<n>, as listed)")
    p.add_argument("--update", metavar="REF", help="a progress line for a request (with --message)")
    p.add_argument("--done", metavar="REF", help="mark a request done (with --message saying what came of it)")
    p.add_argument("--message", help="what the page shows about the request")
    p.add_argument("--video", help="with --done on a new-video request: the video it started")
    p.add_argument("--wait", action="store_true", help="return as soon as a new request is waiting (run it in the background)")
    p.add_argument("--timeout", type=float, help="with --wait: give up after this many seconds")
    p = sub.add_parser("new-video", help="start a video's code folder from the template")
    p.add_argument("id")
    p.add_argument("--placeholder", type=float, metavar="SECONDS", help="start on a silent placeholder song this long (the picture before the song)")
    p.add_argument("--bpm", type=float, help="the placeholder's tempo (default 120)")
    p = sub.add_parser("placeholder", help="a silent placeholder song for a video whose song does not exist yet: render, still and qc work on it; align replaces it")
    p.add_argument("id")
    p.add_argument("--seconds", type=float, help="its length (required the first time)")
    p.add_argument("--bpm", type=float, help="its steady tempo (default 120, or the one it has)")
    p = sub.add_parser("typecheck", help="type-check a video's code against the engine")
    p.add_argument("id")
    for name, text in (("studio", "open Remotion Studio on a video"),
                       ("render", "render a composition: <id> <composition> <out> [--stall=15] [--retries=2] [remotion flags]"),
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
    p = sub.add_parser("library", help="your finished videos, songs and lessons as one page for phones and TVs at home")
    p.add_argument("action", nargs="?", default="status", choices=["status", "serve", "install", "uninstall"],
                   help="status (the address), serve (run it now), install (run it from every login), uninstall")
    p.add_argument("--port", type=int, default=library.PORT)
    p.add_argument("--host", default="0.0.0.0", help="serve: 0.0.0.0 (the home network) or 127.0.0.1 (this computer only)")
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
    finally:
        studio.release_leases()
