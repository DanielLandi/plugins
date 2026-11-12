"""Project lanes: a music-video session in a linked git worktree of the project folder works on that worktree's own
specs and video code, with its own work folders, finals and engine entries (concurrency design, phase 2)."""
import shutil
import subprocess

import pytest

from mv_fixtures import fake_repo, fake_worktree
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
