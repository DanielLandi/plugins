"""Seeding a git worktree's work folder with the main checkout's timings (concurrency design §4.3, phase 3).

`align` separates the vocals and transcribes them (minutes); a new worktree of the project would otherwise redo it
for every song. The first time a worktree needs a video's work folder and has none, while the main checkout has one,
the timings are copied: real copies, never hard links, since these files are rewritten in place. Renders, checks,
review versions and previews are the branch's own and are never copied.

Two commands may seed the same folder at once: a lock per video makes the second wait, and the copy is made in a
staging folder and renamed into place, so nobody ever sees a half-copied folder, even after a crash.
"""
import os
import shutil
import sys
from pathlib import Path

from .filelock import file_lock

# What a worktree can reuse: the song's copy and its timings (public/), the separated vocals, the transcript, the
# aligned words, the beat grid, the web page's audio loop, and align's cache key (so a later `align` in the worktree
# reuses the copied vocals and transcript instead of separating again).
SEEDED = ("public", "vocals.wav", "transcript.json", "aligned.json", "beats.json", "loop", "align-cache.json")
MARK = ".seeded-from"  # names the main checkout's folder the copy came from
STAGING = ".seeding"  # <work root>/.seeding/<id>.lock and <work root>/.seeding/<id>/<pid>: never a video id (no dot)
TIMEOUT_S = 600


def seed_work(source: Path, dest: Path, lane: str) -> bool:
    """Copy the timings in `source` (the main checkout's work folder) to `dest` (a worktree's), if `dest` does not
    exist and `source` holds any. Prints one line when it copies; returns whether it did."""
    try:
        items = [name for name in SEEDED if (source / name).exists()]
    except OSError:
        return False
    if not items:
        return False
    staging = dest.parent / STAGING
    staging.mkdir(parents=True, exist_ok=True)
    with file_lock(staging / f"{dest.name}.lock", timeout=TIMEOUT_S,
                   busy=f"another music-video command has been copying {dest.name}'s timings into {dest} for "
                        f"{TIMEOUT_S // 60} minutes: wait for it, or stop it, then run again",
                   notice=f"waiting for another music-video command to copy {dest.name}'s timings…"):
        if dest.exists():  # another command seeded it while this one waited
            return False
        mine = staging / dest.name
        shutil.rmtree(mine, ignore_errors=True)  # left by a command that died mid-copy (we hold the lock)
        tmp = mine / str(os.getpid())
        tmp.mkdir(parents=True)
        try:
            for name in items:
                src = source / name
                if src.is_dir():
                    shutil.copytree(src, tmp / name)
                else:
                    shutil.copy2(src, tmp / name)
            (tmp / MARK).write_text(f"{source}\n", encoding="utf-8")
            tmp.rename(dest)
        finally:
            shutil.rmtree(mine, ignore_errors=True)
    print(f"worktree {lane}: copied {dest.name}'s timings from the main checkout ({source})", file=sys.stderr)
    return True
