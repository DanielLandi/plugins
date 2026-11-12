"""The bake-off: one short brief built once per character engine, side by side on the review page, and a record of
every run (bakeoffs.md) so a later model can be checked against the last one."""
import json

import pytest
import yaml

from musicvideo import bakeoff
from musicvideo.cli import main
from musicvideo.errors import MVError


def _analysis(duration=60.0, hits=None):
    return {"duration": duration, "hits": hits if hits is not None else [{"t": 20.0, "strength": 0.4},
                                                                       {"t": 41.5, "strength": 1.0},
                                                                       {"t": 50.0, "strength": 1.0}]}


def _song(ws, song="night-drive", **kw):
    pub = ws.work_for(song) / "public"
    pub.mkdir(parents=True, exist_ok=True)
    (pub / "analysis.json").write_text(json.dumps(_analysis(**kw)), encoding="utf-8")
    (pub / "timing.json").write_text("{}", encoding="utf-8")
    return song


def test_window_on_the_strongest_hit():
    assert bakeoff.default_window(_analysis()) == (35.5, 45.5)  # the first of the strongest hits, 6 s in


def test_window_short_song_and_no_hits():
    assert bakeoff.default_window(_analysis(duration=4.0, hits=[{"t": 2.2, "strength": 1}])) == (0.0, 4.0)
    assert bakeoff.default_window(_analysis(duration=30.0, hits=[{"t": 1.0, "strength": 1}])) == (0.0, 10.0)
    assert bakeoff.default_window(_analysis(duration=30.0, hits=[{"t": 29.5, "strength": 1}])) == (20.0, 30.0)
    assert bakeoff.default_window(_analysis(duration=30.0, hits=[])) == (0.0, 10.0)


def test_scaffold_new_video_borrows_a_song(mv_ws):
    _song(mv_ws)
    out = bakeoff.scaffold(mv_ws, "duel-check", song="night-drive")
    vdir = mv_ws.video_dir("duel-check")
    meta = yaml.safe_load((vdir / "video.yaml").read_text(encoding="utf-8"))
    assert meta["song"] == "night-drive" and meta["id"] == "duel-check"
    assert "# Step 5's jolts question" in (vdir / "video.yaml").read_text(encoding="utf-8")  # comments kept
    assert out["engines"] == ["raw", "vrm"] and out["window"] == (35.5, 45.5) and out["wired"]
    with pytest.raises(MVError, match="--song"):
        bakeoff.scaffold(mv_ws, "nothing-here")


def test_scaffold_writes_starters_and_bakeoff_ts(mv_ws):
    _song(mv_ws, "duel", duration=4.0, hits=[{"t": 2.2, "strength": 1}])
    assert main(["new-video", "duel"]) == 0
    out = bakeoff.scaffold(mv_ws, "duel", engines=["vrm"])
    vdir = mv_ws.video_dir("duel")
    assert out["engines"] == ["raw", "vrm"]  # raw is always in a bake-off
    assert (vdir / "bakeoff" / "raw.tsx").is_file() and (vdir / "bakeoff" / "vrm.tsx").is_file()
    ts = (vdir / "bakeoff.ts").read_text(encoding="utf-8")
    assert "import { Bakeoff as Raw } from './bakeoff/raw';" in ts and "import { Bakeoff as Vrm } from './bakeoff/vrm';" in ts
    assert "from: 0, to: 4," in ts and ts.index("'raw'") < ts.index("'vrm'")
    assert "vroid-sample" in (vdir / "SOURCES.md").read_text(encoding="utf-8")
    with pytest.raises(MVError, match="cartoon"):
        bakeoff.scaffold(mv_ws, "duel", engines=["cartoon"])


def test_scaffold_raw_only_needs_no_avatars(mv_ws):
    _song(mv_ws, "duel")
    main(["new-video", "duel"])
    bakeoff.scaffold(mv_ws, "duel", engines=["raw"])
    vdir = mv_ws.video_dir("duel")
    assert not (vdir / "bakeoff" / "vrm.tsx").exists()
    assert "vroid" not in (vdir / "SOURCES.md").read_text(encoding="utf-8")


def test_scaffold_keeps_written_scenes(mv_ws):
    _song(mv_ws, "duel")
    main(["new-video", "duel"])
    bakeoff.scaffold(mv_ws, "duel", engines=["raw"], start=12)
    raw = mv_ws.video_dir("duel") / "bakeoff" / "raw.tsx"
    raw.write_text("// my take\n", encoding="utf-8")
    out = bakeoff.scaffold(mv_ws, "duel")
    assert raw.read_text(encoding="utf-8") == "// my take\n"
    assert out["added"] == ["vrm"] and out["window"] == (12.0, 22.0)  # the earlier window stays
    out = bakeoff.scaffold(mv_ws, "duel", start=30)
    assert out["added"] == [] and out["window"] == (30.0, 40.0)


def test_scaffold_says_how_to_wire_an_old_index(mv_ws, capsys):
    _song(mv_ws, "duel")
    main(["new-video", "duel"])
    index = mv_ws.video_dir("duel") / "index.tsx"
    index.write_text("export const Compositions = () => null;\n", encoding="utf-8")
    assert main(["bakeoff", "new", "duel"]) == 0
    out = capsys.readouterr().out
    assert "import { bakeoff } from './bakeoff'" in out and "-bakeoff-" in out


def test_new_prints_the_next_commands(mv_ws, capsys):
    _song(mv_ws, "duel")
    main(["new-video", "duel"])
    assert main(["bakeoff", "new", "duel"]) == 0
    out = capsys.readouterr().out
    for must in ("render duel duel-bakeoff-raw", "render duel duel-bakeoff-vrm", "--excerpt 35.5-45.5",
                 "version duel", "--scene bakeoff --variant vrm", "references/bakeoff.md"):
        assert must in out, must


def test_record_and_last(mv_ws, capsys):
    _song(mv_ws, "duel")
    main(["new-video", "duel"])
    bakeoff.scaffold(mv_ws, "duel")
    assert bakeoff.watch(mv_ws, "model-a")["offer"] is True  # nothing recorded yet
    bakeoff.record(mv_ws, "duel", "model-a", "vrm reads better | raw is stiffer", today="2026-11-11")
    text = (mv_ws.home / "bakeoffs.md").read_text(encoding="utf-8")
    assert "| Date | Model | Engines | Video | Verdict |" in text
    assert "| 2026-11-11 | model-a | raw, vrm | duel | vrm reads better \\| raw is stiffer |" in text
    rows = bakeoff.records(mv_ws)
    assert rows[-1]["verdict"] == "vrm reads better | raw is stiffer" and rows[-1]["engines"] == ["raw", "vrm"]
    assert bakeoff.watch(mv_ws, "model-a")["offer"] is False
    w = bakeoff.watch(mv_ws, "model-b")
    assert w["offer"] is True and w["last"]["model"] == "model-a"
    bakeoff.record(mv_ws, None, "model-b", "", declined=True, today="2026-11-12")
    w = bakeoff.watch(mv_ws, "model-b")
    assert w["offer"] is False and w["last"]["model"] == "model-a"  # a declined offer is not a run
    with pytest.raises(MVError, match="verdict"):
        bakeoff.record(mv_ws, "duel", "model-c", " ")
    assert main(["bakeoff", "last", "--model", "model-c"]) == 0
    out = capsys.readouterr().out
    assert "model-a" in out and "offer" in out
