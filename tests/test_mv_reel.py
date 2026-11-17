"""A reel: finished clips chained by joins; adding a clip makes only its own pieces."""
import json
import subprocess

import pytest

from musicvideo.errors import MVError
from musicvideo.video import reel as R

FPS = 30


def write(tmp_path, text):
    p = tmp_path / "reel.yaml"
    p.write_text(text, encoding="utf-8")
    return p


def known(reel, frames):
    """Give every clip a frame count and a stamp, as run() does from the files."""
    for c in reel.clips:
        c.frames = frames.get(c.id, 300)
        c.stamp = f"{c.id}|{c.frames}"
    return reel


def test_head_clips_and_tail_keep_their_order(tmp_path):
    r = R.load(write(tmp_path, "head: [intro]\nclips: [a, {id: b, title: Bee, exit: [0.4, 0.5]}]\ntail: [outro]\n"), "v")
    assert [c.id for c in r.clips] == ["intro", "a", "b", "outro"]
    assert r.clips[2].title == "Bee" and r.clips[2].exit == [0.4, 0.5]
    assert r.out == "v-reel.mp4" and r.join["transition"] == "passage" and r.join["seconds"] == 1.5


def test_a_clip_twice_or_a_bad_exit_is_refused(tmp_path):
    with pytest.raises(MVError, match="appears twice: a"):
        R.load(write(tmp_path, "clips: [a, b, a]\n"), "v")
    with pytest.raises(MVError, match="exit is"):
        R.load(write(tmp_path, "clips: [a, {id: b, exit: 3}]\n"), "v")
    with pytest.raises(MVError, match="at least two"):
        R.load(write(tmp_path, "clips: [a]\n"), "v")


def test_the_plan_trims_each_body_by_its_joins(tmp_path):
    r = known(R.load(write(tmp_path, "head: [a]\nclips: [b]\ntail: [c]\n"), "v"), {"a": 200, "b": 300, "c": 400})
    pieces = R.plan(r, tmp_path)
    assert [(p.kind, p.name, p.start, p.frames) for p in pieces] == [
        ("body", "a", 0, 155), ("join", "a>b", 155, 45), ("body", "b", 45, 210), ("join", "b>c", 255, 45),
        ("body", "c", 45, 355)]
    assert sum(p.frames for p in pieces) == 200 + 300 + 400 - 2 * 45


def test_inserting_a_clip_makes_only_its_body_and_its_two_joins(tmp_path):
    before = R.plan(known(R.load(write(tmp_path, "head: [o]\nclips: [a, b, c]\ntail: [z]\n"), "v"), {}), tmp_path)
    after = R.plan(known(R.load(write(tmp_path, "head: [o]\nclips: [a, n, b, c]\ntail: [z]\n"), "v"), {}), tmp_path)
    new = {p.file.name for p in after} - {p.file.name for p in before}
    assert sorted(n.split("-")[0] + " " + n.split("-")[1] for n in new) == ["body n", "join a", "join n"]
    assert len(new) == 3


def test_a_changed_clip_file_remakes_its_pieces_only(tmp_path):
    r = known(R.load(write(tmp_path, "clips: [a, b, c]\n"), "v"), {})
    before = {p.file.name for p in R.plan(r, tmp_path)}
    r.clips[1].stamp = "b|new render"
    after = {p.file.name for p in R.plan(r, tmp_path)}
    assert sorted(n.split("-")[0] + " " + n.split("-")[1] for n in after - before) == ["body b", "join a", "join b"]


def test_a_join_takes_the_exit_of_the_clip_before_it_and_the_pair_overrides(tmp_path):
    r = known(R.load(write(tmp_path, (
        "join: {seconds: 1, params: {dim: 0.2}}\nclips: [{id: a, exit: [0.3, 0.4]}, b, c]\n"
        "joins: {'b>c': {seconds: 2, transition: iris, params: {x: 0.9}}}\n")), "v"), {})
    a_b, b_c = [p for p in R.plan(r, tmp_path) if p.kind == "join"]
    assert a_b.frames == 30 and a_b.spec["params"] == {"dim": 0.2, "x": 0.3, "y": 0.4}
    assert b_c.frames == 60 and b_c.spec["transition"] == "iris" and b_c.spec["params"] == {"dim": 0.2, "x": 0.9}


def test_a_clip_too_short_for_its_joins_is_refused(tmp_path):
    r = known(R.load(write(tmp_path, "clips: [a, b, c]\n"), "v"), {"b": 90})
    with pytest.raises(MVError, match="b has 90 frames"):
        R.plan(r, tmp_path)


def test_chapters_start_at_each_join_and_fold_short_ones(tmp_path):
    r = known(R.load(write(tmp_path, "head: [{id: o, title: Opening}]\nclips: [{id: a, title: A}, {id: b, title: B}]\n"
                                     "tail: [{id: z, title: End}]\n"), "v"),
              {"o": 200, "a": 900, "b": 600, "z": 300})
    marks = R.chapters(r, R.plan(r, tmp_path))
    # the opening (5.2 s before the next join) folds into A; the rest start where the join into them starts
    assert [t for _, t in marks] == ["A", "B", "End"]
    assert [s for s, _ in marks] == pytest.approx([0.0, (155 + 45 + 810) / 30, (1010 + 45 + 510) / 30])
    assert R.timestamp(34.0) == "0:34" and R.timestamp(3725) == "1:02:05"


def make_clip(path, frames, color):
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    f"color=c={color}:s=64x36:r={FPS}:d={frames / FPS}", "-frames:v", str(frames), "-pix_fmt",
                    "yuv420p", str(path)], check=True)


def test_run_cuts_bodies_reuses_what_exists_and_splices_frame_exact(tmp_path, requires_ffmpeg, capsys):
    renders, cache, results = tmp_path / "renders", tmp_path / "cache", tmp_path / "results"
    renders.mkdir()
    for name, n, color in (("a", 120, "red"), ("b", 150, "green"), ("c", 100, "blue")):
        make_clip(renders / f"{name}.mp4", n, color)
    path = write(tmp_path, "out: r.mp4\nclips: [a, b, c]\n")
    reel = R.load(path, "v")
    # stand-ins for the joins (rendering one needs the engine): made with the same encoding as the bodies
    for c in reel.clips:
        c.file = renders / f"{c.id}.mp4"
        c.frames, c.stamp = R.count_frames(c.file), R.stamp(c.file)
    cache.mkdir()
    for p in R.plan(reel, cache):
        if p.kind == "join":
            subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                            f"color=c=white:s=64x36:r={FPS}", "-frames:v", str(p.frames), *R.encode_args(FPS),
                            str(p.file)], check=True)
    out = R.run(R.load(path, "v"), renders=renders, cache=cache, public=tmp_path / "public", results=results)
    assert out == results / "r.mp4"
    assert R.count_frames(out) == 120 + 150 + 100 - 2 * 45
    layout = json.loads((results / "r.reel.json").read_text(encoding="utf-8"))
    assert [p["frames"] for p in layout["pieces"]] == [75, 45, 60, 45, 55]
    # every clip is under 10 s: YouTube would ignore such chapters, so they fold into one
    assert (results / "r.chapters.txt").read_text(encoding="utf-8") == "0:00 c\n"
    capsys.readouterr()
    # a second run makes nothing and splices again
    R.run(R.load(path, "v"), renders=renders, cache=cache, public=tmp_path / "public", results=results)
    assert "0 piece(s) to make" in capsys.readouterr().out


def test_a_missing_clip_is_listed_on_a_dry_run(tmp_path, capsys):
    (tmp_path / "renders").mkdir()
    out = R.run(R.load(write(tmp_path, "clips: [a, b]\n"), "v"), renders=tmp_path / "renders",
                cache=tmp_path / "cache", public=tmp_path, results=tmp_path, dry_run=True)
    assert out is None
    assert "missing clip a" in capsys.readouterr().out


def test_an_exit_track_becomes_join_keys_and_its_height_sizes_the_opening(tmp_path):
    r = known(R.load(write(tmp_path, (
        "clips: [{id: a, exit: [[-1.5, 0.7, 0.4, 0.05], [-0.75, 0.6, 0.42, 0.1], [0, 0.5, 0.45]]}, b]\n")), "v"), {})
    join = next(p for p in R.plan(r, tmp_path) if p.kind == "join")
    assert join.spec["params"]["track"] == [[0.0, 0.7, 0.4], [0.5, 0.6, 0.42], [1.0, 0.5, 0.45]]
    assert join.spec["params"]["size"] == 0.05
    with pytest.raises(MVError, match="exit is"):
        R.load(write(tmp_path, "clips: [{id: a, exit: [[1, 0.5, 0.5]]}, b]\n"), "v")
