"""Project lanes: a music-video session in a linked git worktree of the project folder works on that worktree's own
specs and video code, with its own work folders, finals and engine entries (concurrency design, phase 2)."""
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from mv_fixtures import fake_repo, fake_worktree
from test_mv_web import web_video  # noqa: F401 (a fixture)
from musicvideo import workspace as w
from musicvideo.errors import MVError
from musicvideo.worktrees import linked_worktree, repo_worktrees


def test_linked_worktree_reads_git_files(tmp_path):
    main = fake_repo(tmp_path / "proj")
    for rel in (False, True):
        w = fake_worktree(main, tmp_path / f"wt-{rel}", relative=rel)
        (w / "sub").mkdir()
        found = linked_worktree(w / "sub")
        assert found.root.resolve() == w.resolve() and found.main.resolve() == main.resolve()
        assert found.common.resolve() == (main / ".git").resolve()


def test_main_checkout_and_plain_folder_are_not_lanes(tmp_path):
    assert linked_worktree(fake_repo(tmp_path / "proj")) is None
    (tmp_path / "plain").mkdir()
    assert linked_worktree(tmp_path / "plain") is None


def test_submodule_is_not_a_lane(tmp_path):
    sub = tmp_path / "proj" / "sub"
    (tmp_path / "proj" / ".git" / "modules" / "sub").mkdir(parents=True)
    sub.mkdir()
    (sub / ".git").write_text("gitdir: ../.git/modules/sub\n", encoding="utf-8")  # no commondir
    assert linked_worktree(sub) is None


def test_repo_worktrees_lists_live_worktrees_only(tmp_path):
    main = fake_repo(tmp_path / "proj")
    a, b = fake_worktree(main, tmp_path / "a"), fake_worktree(main, tmp_path / "b")
    shutil.rmtree(b)  # deleted, never pruned
    for start in (main, a):
        m, linked = repo_worktrees(start)
        assert m.resolve() == main.resolve() and [p.resolve() for p in linked] == [a.resolve()]
    (tmp_path / "elsewhere").mkdir()
    assert repo_worktrees(tmp_path / "elsewhere") is None


@pytest.mark.skipif(not shutil.which("git"), reason="git not installed")
def test_real_git_worktree_is_detected(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@example.com"]
    subprocess.run(git + ["init", "-q"], cwd=proj, check=True)
    subprocess.run(git + ["commit", "-q", "--allow-empty", "-m", "start"], cwd=proj, check=True)
    subprocess.run(git + ["worktree", "add", "-q", str(tmp_path / "real")], cwd=proj, check=True)
    assert linked_worktree(tmp_path / "real").main.resolve() == proj.resolve()
    m, linked = repo_worktrees(proj)
    assert [p.resolve() for p in linked] == [(tmp_path / "real").resolve()]


# --- the workspace in a lane -------------------------------------------------------------------------------------

def _home(monkeypatch, folder):
    monkeypatch.setenv("MUSIC_VIDEO_HOME", str(folder))
    return w.load_workspace()


def _workspace_at(folder, artist="Test Artist"):
    (folder / "specs").mkdir(parents=True, exist_ok=True)
    (folder / "config.yaml").write_text(f"artist: {artist}\n", encoding="utf-8")
    return folder


def test_plain_folder_resolves_to_todays_paths(mv_ws, tmp_path):
    assert mv_ws.lane is None and mv_ws.main_home == mv_ws.home
    assert mv_ws.work_root == tmp_path / "My Work é"
    assert mv_ws.finals_root == tmp_path / "My Results é"
    assert mv_ws.work_for("x") == tmp_path / "My Work é" / "x"
    assert mv_ws.results_for("x") == mv_ws.song_dir("x") == tmp_path / "My Results é" / "x"
    assert mv_ws.album_dir("a") == tmp_path / "My Results é" / "albums" / "a"


def test_main_checkout_of_a_repo_resolves_to_todays_paths(mv_ws, mv_lane, tmp_path):
    ws = w.load_workspace()
    assert ws.home == mv_lane.main and ws.lane is None and ws.main_home == ws.home
    assert ws.work_root == tmp_path / "My Work é"
    assert ws.finals_root == tmp_path / "My Results é"
    assert ws.work_for("x") == tmp_path / "My Work é" / "x"
    assert ws.results_for("x") == ws.song_dir("x") == tmp_path / "My Results é" / "x"
    assert ws.album_dir("a") == tmp_path / "My Results é" / "albums" / "a"


def test_two_worktrees_get_distinct_folders(mv_lane, monkeypatch):
    a, b, m = (_home(monkeypatch, f) for f in (mv_lane.a, mv_lane.b, mv_lane.main))
    for one, other in ((a, b), (a, m), (b, m)):
        assert one.work_for("x") != other.work_for("x")
        assert one.results_for("x") != other.results_for("x")
        assert one.song_dir("x") == other.song_dir("x")
        assert one.album_dir("y") == other.album_dir("y")
    assert a.lane == w.load_workspace(mv_lane.a).lane == w.folder_key(mv_lane.a)
    assert a.results_for("x") == m.results_dir / ".lanes" / a.lane / "x"
    assert a.work_for("x") == m.work_dir / ".lanes" / a.lane / "x"
    assert a.main_home.resolve() == mv_lane.main.resolve()


def test_lane_key_is_readable_and_distinct_for_same_folder_name(mv_ws, tmp_path):
    main = fake_repo(mv_ws.home)
    one = fake_worktree(main, tmp_path / "p1" / "feature")
    two = fake_worktree(main, tmp_path / "p2" / "feature", name="feature1")
    keys = []
    for root in (one, two):
        (root / "specs").mkdir()
        keys.append(w.load_workspace(root).lane)
    assert all(k.startswith("feature-") for k in keys) and keys[0] != keys[1]


def test_cwd_in_worktree_maps_the_saved_workspace(mv_lane, tmp_path, monkeypatch):
    monkeypatch.delenv("MUSIC_VIDEO_HOME")
    w.remember_home(mv_lane.main)
    monkeypatch.chdir(mv_lane.a / "videos")
    assert w.workspace_home().resolve() == mv_lane.a.resolve()
    # the workspace in a sub-folder of the repo
    repo = fake_repo(tmp_path / "repo")
    _workspace_at(repo / "music")
    tree = fake_worktree(repo, tmp_path / "trees" / "music-wt")
    (tree / "music" / "specs").mkdir(parents=True)
    w.remember_home(repo / "music")
    monkeypatch.chdir(tree / "music" / "specs")
    assert w.workspace_home().resolve() == (tree / "music").resolve()
    monkeypatch.chdir(tree)
    assert w.workspace_home().resolve() == (tree / "music").resolve()


def test_cwd_outside_a_worktree_keeps_the_saved_workspace(mv_lane, tmp_path, monkeypatch):
    monkeypatch.delenv("MUSIC_VIDEO_HOME")
    w.remember_home(mv_lane.main)
    plain = _workspace_at(tmp_path / "plain", artist="Someone Else")
    monkeypatch.chdir(plain)
    assert w.workspace_home() == mv_lane.main
    inner = _workspace_at(mv_lane.main / "other", artist="Someone Else")  # inside the main checkout
    monkeypatch.chdir(inner)
    assert w.workspace_home() == mv_lane.main


def test_worktree_missing_the_workspace_folder_keeps_the_saved_workspace(mv_ws, tmp_path, monkeypatch):
    monkeypatch.delenv("MUSIC_VIDEO_HOME")
    repo = fake_repo(tmp_path / "repo")
    saved = _workspace_at(repo / "music")
    tree = fake_worktree(repo, tmp_path / "trees" / "old-branch")  # made before music/ existed
    w.remember_home(saved)
    monkeypatch.chdir(tree)
    assert w.workspace_home() == saved


def test_music_video_home_still_wins(mv_lane, monkeypatch):
    monkeypatch.chdir(mv_lane.a)
    ws = _home(monkeypatch, mv_lane.b)
    assert w.workspace_home() == mv_lane.b
    assert ws.home == mv_lane.b and ws.lane == w.folder_key(mv_lane.b)


def test_worktree_without_config_reads_the_main_config(mv_lane, monkeypatch):
    ws = _home(monkeypatch, mv_lane.a)
    assert ws.artist == "Test Artist" and ws.billing_day == 15
    assert ws.videos_dir == mv_lane.a / "videos"
    (mv_lane.a / "config.yaml").write_text("artist: Lane Artist\n", encoding="utf-8")
    ws = w.load_workspace()
    assert ws.artist == "Lane Artist" and ws.billing_day is None
    assert ws.videos_dir == mv_lane.a / "videos"


def test_a_missing_config_names_both_places(mv_lane, monkeypatch):
    (mv_lane.main / "config.yaml").unlink()
    monkeypatch.setenv("MUSIC_VIDEO_HOME", str(mv_lane.a))
    with pytest.raises(MVError, match="no config.yaml here or in"):
        w.load_workspace()


def _set_main_config(main, **values):
    cfg = main / "config.yaml"
    raw = yaml.safe_load(cfg.read_text(encoding="utf-8"))
    raw.update(values)
    cfg.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")


def test_relative_results_dir_in_a_lane_is_mains(mv_lane, monkeypatch):
    _set_main_config(mv_lane.main, results_dir="results")
    ws = _home(monkeypatch, mv_lane.a)
    assert ws.results_dir.resolve() == (mv_lane.main / "results").resolve()
    song = ws.results_dir / "x" / "s.mp3"
    assert w.stored_path(ws, song) == str(Path("results") / "x" / "s.mp3")
    assert w.filed_path(ws, "results/x/s.mp3").resolve() == (mv_lane.main / "results" / "x" / "s.mp3").resolve()


def test_private_names_fall_back_to_main(mv_lane, monkeypatch):
    (mv_lane.main / "private-names.txt").write_text("Secret Name\n", encoding="utf-8")
    ws = _home(monkeypatch, mv_lane.a)
    assert w.load_private_names(ws) == ["Secret Name"]
    assert w.private_names_warning(ws) is None  # the main checkout's file is checked
    (mv_lane.a / "private-names.txt").write_text("Other\nSecret Name\n", encoding="utf-8")
    assert w.load_private_names(ws) == ["Other", "Secret Name"]


def test_a_lane_without_any_private_names_still_warns(mv_lane, monkeypatch):
    ws = _home(monkeypatch, mv_lane.a)
    assert "private names were not checked" in w.private_names_warning(ws)


# --- engine entries and finals per lane --------------------------------------------------------------------------

def test_plain_folder_entry_is_todays(mv_ws, tmp_path):
    from musicvideo import studio
    d = mv_ws.video_dir("x")
    d.mkdir(parents=True)
    (d / "index.tsx").write_text("", encoding="utf-8")
    assert mv_ws.lane is None
    assert studio.write_entry(tmp_path / "rt", d, "x", lane=mv_ws.lane) == tmp_path / "rt" / ".entries" / "x" / "index.ts"


def test_web_default_out_in_a_lane_is_the_lane_folder(web_video, mv_lane, monkeypatch):
    from musicvideo.cli import main
    calls, rt = web_video
    ws = _home(monkeypatch, mv_lane.a)
    pub = ws.work_for("night-drive") / "public"
    pub.mkdir(parents=True)
    for name in ("timing.json", "analysis.json"):
        (pub / name).write_text("{}", encoding="utf-8")
    assert main(["web", "night-drive"]) == 0
    cmd, cwd, env = calls[0]
    out = cmd[cmd.index("--out") + 1]
    assert out == str(ws.results_dir / ".lanes" / ws.lane / "night-drive" / "web")
    assert out != str(ws.song_dir("night-drive") / "web")
    assert env["MV_WEB_ENTRY"] == str(rt / ".entries" / f".lane-{ws.lane}" / "night-drive" / "web.ts")
    assert env["MV_PUBLIC"] == str(pub)


def test_library_does_not_list_lane_results(mv_ws, tmp_path):
    from musicvideo import library
    for folder in (mv_ws.results_dir / ".lanes" / "k" / "x", mv_ws.results_dir / "x"):
        folder.mkdir(parents=True)
        (folder / "final.mp4").write_bytes(b"x")
    assert [s.rel for s in library.scan(mv_ws.results_dir)] == ["x"]


# --- only a real worktree of the saved workspace's own repo moves the session (security review) --------------------

def test_an_unrelated_worktree_holding_a_workspace_does_not_switch(mv_lane, tmp_path, monkeypatch):
    monkeypatch.delenv("MUSIC_VIDEO_HOME")
    w.remember_home(mv_lane.main)
    other = fake_repo(tmp_path / "other-repo")
    tree = fake_worktree(other, tmp_path / "other-trees" / "x")
    _workspace_at(tree, artist="Someone Else")  # looks like a workspace, in another repo's worktree
    monkeypatch.chdir(tree)
    assert w.workspace_home() == mv_lane.main


def test_a_worktree_with_no_saved_workspace_does_not_switch(mv_lane, tmp_path, monkeypatch):
    monkeypatch.delenv("MUSIC_VIDEO_HOME")
    (tmp_path / "settings.json").unlink()
    _workspace_at(mv_lane.a / "nested")
    monkeypatch.chdir(mv_lane.a / "nested")
    assert w.workspace_home() == w.DEFAULT_HOME


def test_a_git_file_whose_admin_dir_does_not_point_back_is_not_a_lane(mv_lane, tmp_path, monkeypatch):
    monkeypatch.delenv("MUSIC_VIDEO_HOME")
    w.remember_home(mv_lane.main)
    forged = tmp_path / "forged"
    (forged / "specs").mkdir(parents=True)
    admin = mv_lane.main / ".git" / "worktrees" / "lane-a"  # lane a's admin dir, which names lane a, not this folder
    (forged / ".git").write_text(f"gitdir: {admin}\n", encoding="utf-8")
    assert linked_worktree(forged) is None
    monkeypatch.chdir(forged)
    assert w.workspace_home() == mv_lane.main


@pytest.mark.skipif(not shutil.which("git"), reason="git not installed")
def test_a_real_worktree_of_the_saved_workspace_switches(tmp_path, monkeypatch):
    proj = tmp_path / "proj"
    _workspace_at(proj)
    (proj / "specs" / ".keep").write_text("", encoding="utf-8")
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@example.com"]
    subprocess.run(git + ["init", "-q"], cwd=proj, check=True)
    subprocess.run(git + ["add", "-A"], cwd=proj, check=True)
    subprocess.run(git + ["commit", "-q", "-m", "start"], cwd=proj, check=True)
    subprocess.run(git + ["worktree", "add", "-q", str(tmp_path / "real")], cwd=proj, check=True)
    monkeypatch.delenv("MUSIC_VIDEO_HOME", raising=False)
    w.remember_home(proj)
    monkeypatch.chdir(tmp_path / "real" / "specs")
    assert w.workspace_home().resolve() == (tmp_path / "real").resolve()
    assert w.load_workspace().lane == w.folder_key(tmp_path / "real")
