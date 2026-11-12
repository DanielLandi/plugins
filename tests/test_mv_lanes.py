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


# --- init, paths, clean and doctor in a lane ---------------------------------------------------------------------

def test_init_in_a_lane_keeps_settings(mv_lane, tmp_path, capsys, monkeypatch):
    from musicvideo.cli import main
    before = (tmp_path / "settings.json").read_bytes()
    monkeypatch.delenv("MUSIC_VIDEO_HOME")
    monkeypatch.chdir(mv_lane.a)
    assert main(["init"]) == 0  # no --artist needed: the main checkout's config counts
    assert (tmp_path / "settings.json").read_bytes() == before
    assert not (mv_lane.a / "config.yaml").exists()
    out = capsys.readouterr().out
    assert "using existing workspace" in out
    assert "this is a worktree of" in out and f"the saved workspace stays {mv_lane.main}" in out
    assert main(["init", "--path", str(mv_lane.b)]) == 0  # an explicit lane path: still no re-pointing
    assert (tmp_path / "settings.json").read_bytes() == before


def test_paths_in_a_lane(mv_lane, capsys, monkeypatch):
    import json
    from musicvideo.cli import main
    m = _home(monkeypatch, mv_lane.main)
    assert main(["paths", "night-drive"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert list(out) == ["video", "work", "public", "renders", "qc", "results", "web"]
    assert out["work"] == str(m.work_dir / "night-drive") and out["results"] == str(m.results_dir / "night-drive")
    a = _home(monkeypatch, mv_lane.a)
    assert main(["paths", "night-drive"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["lane"] == a.lane and list(out)[-1] == "lane"
    work, finals = m.work_dir / ".lanes" / a.lane, m.results_dir / ".lanes" / a.lane
    for key, value in (("work", work / "night-drive"), ("renders", work / "night-drive" / "renders"),
                       ("qc", work / "night-drive" / "qc"), ("public", work / "night-drive" / "public"),
                       ("results", finals / "night-drive"), ("web", finals / "night-drive" / "web"),
                       ("video", mv_lane.a / "videos" / "night-drive")):
        assert out[key] == str(value), key


def test_clean_in_a_lane_removes_only_lane_work(mv_lane, capsys, monkeypatch):
    from musicvideo.cli import main
    m = _home(monkeypatch, mv_lane.main)
    a = w.load_workspace(mv_lane.a)
    for folder in (m.work_for("night-drive"), a.work_for("night-drive")):
        (folder / "renders").mkdir(parents=True)
        (folder / "renders" / "draft.mp4").write_bytes(b"x")
    monkeypatch.setenv("MUSIC_VIDEO_HOME", str(mv_lane.a))
    assert main(["clean", "night-drive"]) == 0
    assert not a.work_for("night-drive").exists() and m.work_for("night-drive").is_dir()
    (a.work_for("night-drive")).mkdir(parents=True)
    monkeypatch.setenv("MUSIC_VIDEO_HOME", str(mv_lane.main))
    assert main(["clean", "night-drive"]) == 0
    assert not m.work_for("night-drive").exists() and a.work_for("night-drive").is_dir()
    assert (m.work_dir / ".lanes").is_dir()


def test_doctor_names_the_lane(mv_lane, tmp_path, capsys, monkeypatch):
    from musicvideo import doctor, studio
    copy = tmp_path / "plugins" / "cache" / "some-marketplace" / "music-video" / "0.9.0" / "studio"
    copy.mkdir(parents=True)
    (copy / "package-lock.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(studio, "PLUGIN_STUDIO", copy)
    monkeypatch.setattr(doctor.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(doctor, "_node_major", lambda: 22)
    ws = _home(monkeypatch, mv_lane.a)
    doctor.run_doctor(install=False)
    out = capsys.readouterr().out
    assert (f"ok   worktree {ws.lane} of {ws.main_home}: work in {ws.work_root}, video finals in {ws.finals_root}"
            in out)
    _home(monkeypatch, mv_lane.main)
    doctor.run_doctor(install=False)
    assert "worktree" not in capsys.readouterr().out


# --- songs stay shared, one download budget ----------------------------------------------------------------------

def _downloaded(home, spec_id, at=None, **extra):
    from mv_fixtures import valid_spec
    from musicvideo.spec import now_iso, save_spec
    kept = {"take_url": "https://suno.com/song/x", "downloaded_at": at or now_iso()}
    path = home / "specs" / f"{spec_id}.yaml"
    fields = {"title": spec_id.replace("-", " ").title(), **extra}
    save_spec(path, valid_spec(id=spec_id, status="downloaded", kept=kept, **fields))
    return path


def test_downloads_count_across_worktrees(mv_lane, monkeypatch, capsys):
    from musicvideo.cli import main
    from musicvideo.spec import now_iso, save_spec
    from musicvideo.video import home
    from mv_fixtures import valid_spec
    _downloaded(mv_lane.main, "in-main")
    _downloaded(mv_lane.a, "in-a")
    _downloaded(mv_lane.b, "in-b")
    at = now_iso()
    _downloaded(mv_lane.a, "merged", at)  # the same download, merged into two branches: counted once
    _downloaded(mv_lane.b, "merged", at)
    for folder in mv_lane:
        monkeypatch.setenv("MUSIC_VIDEO_HOME", str(folder))
        assert main(["status"]) == 0
        assert "Downloads: 4 of 20" in capsys.readouterr().out
    save_spec(mv_lane.a / "specs" / "fifth.yaml", valid_spec(id="fifth", title="Fifth", status="generated"))
    monkeypatch.setenv("MUSIC_VIDEO_HOME", str(mv_lane.a))
    assert main(["downloaded", "fifth", "--take-url", "u"]) == 0
    assert "recorded download 5 of 20" in capsys.readouterr().out
    for folder in mv_lane:
        assert home.downloads(w.load_workspace(folder))["used"] == 5


def test_status_songs_line_is_this_worktrees_own(mv_lane, monkeypatch, capsys):
    from musicvideo.cli import main
    _downloaded(mv_lane.a, "in-a")
    monkeypatch.setenv("MUSIC_VIDEO_HOME", str(mv_lane.main))
    assert main(["status"]) == 0
    out = capsys.readouterr().out
    assert "Downloads: 1 of 20" in out and "downloaded 0" in out


def test_downloads_in_cycle_counts_one_download_once():
    from datetime import date
    from musicvideo.budget import downloads_in_cycle
    today = date(2026, 11, 20)
    one = {"id": "x", "kept": {"downloaded_at": "2026-11-16T10:00:00+00:00"}}
    no_id = {"kept": {"downloaded_at": "2026-11-16T10:00:00+00:00"}}
    again = {"id": "x", "kept": {"downloaded_at": "2026-11-17T10:00:00+00:00"}}  # downloaded again: two downloads
    assert downloads_in_cycle([one, dict(one)], today, 15) == 1
    assert downloads_in_cycle([no_id, dict(no_id)], today, 15) == 2
    assert downloads_in_cycle([one, again], today, 15) == 2


def test_a_plain_workspace_counts_as_today(mv_ws, capsys):
    from musicvideo.cli import main
    _downloaded(mv_ws.home, "one")
    _downloaded(mv_ws.home, "two")
    assert main(["status"]) == 0
    assert "Downloads: 2 of 20" in capsys.readouterr().out


def test_a_deleted_worktree_is_skipped(mv_lane, monkeypatch, capsys):
    from musicvideo.cli import main
    _downloaded(mv_lane.b, "in-b")
    _downloaded(mv_lane.a, "in-a")
    shutil.rmtree(mv_lane.b)  # main/.git/worktrees/lane-b stays, as when a folder is deleted without git
    for folder in (mv_lane.a, mv_lane.main):
        monkeypatch.setenv("MUSIC_VIDEO_HOME", str(folder))
        assert main(["status"]) == 0
        assert "Downloads: 1 of 20" in capsys.readouterr().out


@pytest.mark.parametrize("results", ["absolute", "relative"])
def test_ingest_in_a_lane_files_into_shared_results(mv_lane, make_mp3, monkeypatch, tmp_path, results):
    from musicvideo.ingest import ingest
    from musicvideo.spec import load_spec
    if results == "relative":
        _set_main_config(mv_lane.main, results_dir="results")
    path = _downloaded(mv_lane.a, "night-drive")
    ws = _home(monkeypatch, mv_lane.a)
    mp3 = make_mp3(tmp_path / "elsewhere" / "Night Drive.mp3")
    dest = ingest(ws, "night-drive", mp3)
    main_ws = w.load_workspace(mv_lane.main)
    assert dest == main_ws.results_dir / "night-drive" / "Test Artist - Night Drive.mp3" and dest.is_file()
    assert ".lanes" not in dest.parts
    kept = load_spec(path)["kept"]["file"]
    assert kept == w.stored_path(main_ws, dest)
    if results == "relative":
        assert dest.parent == mv_lane.main / "results" / "night-drive"
        assert kept == str(Path("results") / "night-drive" / "Test Artist - Night Drive.mp3")
    assert w.filed_path(main_ws, kept) == dest  # valid in the main checkout after the branch merges


ALBUM = "title: Mix\nyear: 2025\n"


def test_ingest_refuses_a_file_another_worktree_owns(mv_lane, make_mp3, monkeypatch, tmp_path):
    from musicvideo.ingest import ingest
    for folder in mv_lane:
        (folder / "albums").mkdir()
        (folder / "albums" / "mix.yaml").write_text(ALBUM, encoding="utf-8")
    ws = _home(monkeypatch, mv_lane.a)
    taken = w.stored_path(ws, ws.album_dir("mix") / "Test Artist - Night Drive.mp3")
    _downloaded(mv_lane.a, "night-drive", album="mix", title="Night Drive")
    other = _downloaded(mv_lane.b, "other", album="mix", title="Night Drive")
    from musicvideo.spec import load_spec, save_spec
    data = load_spec(other)
    data["status"], data["kept"]["file"] = "filed", taken
    save_spec(other, data)
    mp3 = make_mp3(tmp_path / "elsewhere" / "Night Drive.mp3")
    with pytest.raises(MVError, match="already belongs to spec 'other'"):
        ingest(ws, "night-drive", mp3)
    other.unlink()
    same = _downloaded(mv_lane.main, "night-drive", album="mix", title="Night Drive")  # the same song, in main
    data = load_spec(same)
    data["status"], data["kept"]["file"] = "filed", taken
    save_spec(same, data)
    assert ingest(ws, "night-drive", mp3).name == "Test Artist - Night Drive.mp3"


# --- the home and its requests in a lane -------------------------------------------------------------------------

def test_a_lanes_home_takes_a_free_port_and_mains_keeps_8646(mv_lane, monkeypatch):
    from musicvideo.cli import main
    from musicvideo.video import home
    seen = []
    monkeypatch.setattr(home, "serve", lambda ws, port, open_page: seen.append((ws.lane, port)))
    monkeypatch.setenv("MUSIC_VIDEO_HOME", str(mv_lane.main))
    assert main(["home"]) == 0
    monkeypatch.setenv("MUSIC_VIDEO_HOME", str(mv_lane.a))
    assert main(["home"]) == 0
    assert main(["home", "--port", "9000"]) == 0
    key = w.folder_key(mv_lane.a)
    assert seen == [(None, 8646), (key, 0), (key, 9000)]
    assert home.default_port(w.load_workspace(mv_lane.main)) == home.PORT == 8646


def test_a_lanes_home_says_which_worktree_it_serves(mv_lane, monkeypatch, capsys):
    from musicvideo.video import home

    class Stop(Exception):
        pass

    class Server:
        server_address = ("127.0.0.1", 50123)

        def serve_forever(self):
            raise KeyboardInterrupt

        def server_close(self):
            pass

    monkeypatch.setattr(home, "make_server", lambda app, port: Server())
    for folder in (mv_lane.main, mv_lane.a):
        home.serve(w.load_workspace(folder), port=0)
    out = capsys.readouterr().out
    a = w.load_workspace(mv_lane.a)
    assert f"home of {mv_lane.main}: http://127.0.0.1:50123/ (Ctrl-C stops it)" in out
    assert f"home of {a.home} (worktree {a.lane}): http://127.0.0.1:50123/ (Ctrl-C stops it)" in out


def _get(url):
    import json
    import urllib.request
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read())


def _post(url, payload):
    import json
    import urllib.request
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.status, json.loads(r.read())


def test_two_homes_serve_at_once_each_on_its_own_checkout(mv_lane, monkeypatch):
    import threading
    from musicvideo.video.home import Home, make_server
    only = mv_lane.a / "videos" / "only-in-a"
    only.mkdir(parents=True)
    (only / "video.yaml").write_text("song: only-in-a\n", encoding="utf-8")
    urls, apps, servers = {}, [], []
    for name, folder in (("main", mv_lane.main), ("a", mv_lane.a)):
        app = Home(w.load_workspace(folder))
        server = make_server(app, port=0)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        urls[name] = f"http://127.0.0.1:{server.server_address[1]}"
        apps.append(app)
        servers.append(server)
    try:
        assert "only-in-a" in [v["id"] for v in _get(urls["a"] + "/api/state")["videos"]]
        assert "only-in-a" not in [v["id"] for v in _get(urls["main"] + "/api/state")["videos"]]
        status, _ = _post(urls["a"] + "/api/request", {"video": None, "kind": "new-video",
                                                       "data": {"topic": "fog horns"}})
        assert status == 200
        assert (mv_lane.a / "requests" / "requests.json").is_file()
        assert not (mv_lane.main / "requests").exists()
    finally:
        for app, server in zip(apps, servers):
            app.pages.close()
            server.shutdown()
            server.server_close()


def test_requests_are_per_lane(mv_lane, monkeypatch):
    from musicvideo import requests as rq
    ws_main, ws_a, ws_b = (w.load_workspace(f) for f in mv_lane)
    (ws_a.video_dir("night-drive")).mkdir(parents=True, exist_ok=True)
    rq.video_queue(ws_a, "night-drive").add("message", {"note": "warmer"})
    rq.home_queue(ws_a).add("new-video", {"topic": "fog horns"})
    assert (mv_lane.a / "requests" / "requests.json").is_file()
    assert (mv_lane.a / "videos" / "night-drive" / "requests" / "requests.json").is_file()
    assert rq.new_requests(ws_main) == [] and rq.new_requests(ws_b) == []
    assert len(rq.new_requests(ws_a)) == 2
    assert rq.wait_for_new(ws_b, timeout=0.2, every=0.05) == []


# --- final review fixes -----------------------------------------------------------------------------------------

def test_a_hand_made_admin_dir_outside_the_repos_worktrees_is_not_a_lane(mv_lane, tmp_path, monkeypatch):
    evil = tmp_path / "evil"
    (evil / "specs").mkdir(parents=True)
    fake = evil / "fake"
    fake.mkdir()
    (evil / ".git").write_text("gitdir: fake\n", encoding="utf-8")
    (fake / "gitdir").write_text("../.git\n", encoding="utf-8")  # points back, but is not git's own record
    (fake / "commondir").write_text(f"{mv_lane.main / '.git'}\n", encoding="utf-8")
    assert linked_worktree(evil) is None
    monkeypatch.delenv("MUSIC_VIDEO_HOME")
    w.remember_home(mv_lane.main)
    monkeypatch.chdir(evil)
    assert w.workspace_home() == mv_lane.main


def test_a_broken_spec_in_another_worktree_never_stops_this_one(mv_lane, monkeypatch, capsys):
    from musicvideo.cli import main
    from musicvideo.spec import save_spec
    from musicvideo.video import home
    from mv_fixtures import valid_spec
    _downloaded(mv_lane.main, "in-main")
    _downloaded(mv_lane.a, "in-a")
    (mv_lane.b / "specs" / "mid-rebase.yaml").write_text("<<<<<<< HEAD\n- a\n", encoding="utf-8")
    monkeypatch.setenv("MUSIC_VIDEO_HOME", str(mv_lane.main))
    assert main(["status"]) == 0
    out, err = capsys.readouterr()
    assert "Downloads: 2 of 20" in out and "mid-rebase.yaml" in err
    assert home.downloads(w.load_workspace(mv_lane.main))["used"] == 2
    save_spec(mv_lane.main / "specs" / "next.yaml", valid_spec(id="next", title="Next", status="generated"))
    assert main(["downloaded", "next", "--take-url", "u"]) == 0
    assert "recorded download 3 of 20" in capsys.readouterr().out
    monkeypatch.setenv("MUSIC_VIDEO_HOME", str(mv_lane.b))
    assert main(["status"]) == 2  # its own broken spec still stops this worktree's commands, as today


def test_ingest_never_replaces_another_worktrees_take_of_the_same_song(mv_lane, make_mp3, monkeypatch, tmp_path):
    from musicvideo.ingest import ingest
    from musicvideo.spec import load_spec, save_spec
    ws = _home(monkeypatch, mv_lane.a)
    filed = _downloaded(mv_lane.b, "night-drive")  # branch b downloaded and filed its own take first
    data = load_spec(filed)
    data["status"], data["kept"]["take_url"] = "filed", "https://suno.com/song/take-b"
    data["kept"]["file"] = w.stored_path(ws, ws.song_dir("night-drive") / "Test Artist - Night Drive.mp3")
    save_spec(filed, data)
    mine = _downloaded(mv_lane.a, "night-drive")
    data = load_spec(mine)
    data["kept"]["take_url"] = "https://suno.com/song/take-a"
    save_spec(mine, data)
    mp3 = make_mp3(tmp_path / "elsewhere" / "Night Drive.mp3")
    with pytest.raises(MVError, match="another take"):
        ingest(ws, "night-drive", mp3)
    data["kept"]["take_url"] = "https://suno.com/song/take-b"  # the same take: the same song, filed again
    save_spec(mine, data)
    assert ingest(ws, "night-drive", mp3).is_file()
