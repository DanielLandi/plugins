"""Git worktrees, read from git's own files (no `git` binary, so it works on Windows without git on PATH).

A linked worktree has a `.git` *file* (`gitdir: <admin dir>`); the admin dir names the common git dir in its
`commondir` file, and the common dir's parent is the main working tree. A main checkout has a `.git` directory.
Submodules and `--separate-git-dir` clones also have a `.git` file, but no `commondir`: they are not worktrees.
"""
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Worktree:
    root: Path  # the folder holding the `.git` file
    main: Path  # the main working tree
    common: Path  # the common git dir (main/.git)


def git_root(folder: Path) -> Path | None:
    """The nearest of `folder` and its parents holding a `.git` (a file or a directory)."""
    folder = Path(folder).absolute()
    for candidate in (folder, *folder.parents):
        try:
            if (candidate / ".git").exists():
                return candidate
        except OSError:
            return None
    return None


def _read_line(path: Path) -> str:
    return path.read_text(encoding="utf-8").splitlines()[0].strip()


def _against(base: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else base / path


def linked_worktree(folder: Path) -> Worktree | None:
    """The linked worktree `folder` is in, or None (a main checkout, a plain folder, a submodule)."""
    root = git_root(folder)
    if root is None:
        return None
    try:
        dot_git = root / ".git"
        if not dot_git.is_file():
            return None
        line = _read_line(dot_git)
        if not line.startswith("gitdir:"):
            return None
        admin = _against(root, line[len("gitdir:"):].strip())
        commondir = admin / "commondir"
        if not commondir.is_file():
            return None
        common = _against(admin, _read_line(commondir)).resolve()
        if common.name != ".git" or not common.is_dir():
            return None
        return Worktree(root, common.parent, common)
    except (OSError, UnicodeDecodeError, IndexError, ValueError):
        return None


def repo_worktrees(folder: Path) -> tuple[Path, list[Path]] | None:
    """(main working tree, linked worktree roots that still exist) of the repo `folder` is in; None outside git.
    A worktree whose folder was deleted but never pruned is left out."""
    wt = linked_worktree(folder)
    if wt is not None:
        main, common = wt.main, wt.common
    else:
        root = git_root(folder)
        if root is None or not (root / ".git").is_dir():
            return None
        main, common = root, root / ".git"
    linked = []
    try:
        admins = sorted((common / "worktrees").iterdir()) if (common / "worktrees").is_dir() else []
    except OSError:
        admins = []
    for admin in admins:
        try:
            gitdir = admin / "gitdir"
            if not gitdir.is_file():
                continue
            parent = _against(admin, _read_line(gitdir)).parent
            if (parent / ".git").is_file():
                linked.append(parent)
        except (OSError, UnicodeDecodeError, IndexError, ValueError):
            continue
    return main, sorted(linked, key=str)
