"""A lock that holds across processes: one lock file, held with flock on POSIX and msvcrt.locking on Windows.

Each holder opens the lock file on its own, so two threads of one process exclude each other too. The lock is
released when the holder leaves the block, or by the OS when its process dies. Not re-entrant."""
import contextlib
import sys
import time
from pathlib import Path

from .errors import MVError


@contextlib.contextmanager
def file_lock(lock_file: Path, timeout: float, busy: str, every: float = 0.1, notice: str = "",
              notice_after: float = 2.0):
    """Hold lock_file for the block. Waits for another holder, polling every `every` seconds; prints `notice` once
    after `notice_after` seconds of waiting, and raises MVError(busy) after `timeout`."""
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_file, "a+b") as fd:
        start, told = time.monotonic(), False
        while not _try_lock(fd):
            waited = time.monotonic() - start
            if waited >= timeout:
                raise MVError(busy)
            if notice and waited >= notice_after and not told:
                print(notice, file=sys.stderr, flush=True)
                told = True
            time.sleep(every)
        try:
            yield
        finally:
            _unlock(fd)


def _try_lock(fd) -> bool:
    try:
        if sys.platform == "win32":
            import msvcrt
            fd.seek(0)
            msvcrt.locking(fd.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False


def _unlock(fd) -> None:
    if sys.platform == "win32":
        import msvcrt
        fd.seek(0)
        msvcrt.locking(fd.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(fd.fileno(), fcntl.LOCK_UN)
