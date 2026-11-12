from calendar import monthrange
from datetime import date
from pathlib import Path
from typing import Iterable

from .spec import parse_dt


def _on_day(year: int, month: int, day: int) -> date:
    return date(year, month, min(day, monthrange(year, month)[1]))


def cycle_start(today: date, billing_day: int) -> date:
    this_month = _on_day(today.year, today.month, billing_day)
    if today >= this_month:
        return this_month
    year, month = (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12)
    return _on_day(year, month, billing_day)


def downloads_in_cycle(specs: Iterable[dict | tuple[Path, dict]], today: date, billing_day: int) -> int:
    """Downloads recorded since the cycle started. A spec seen in several git worktrees (one download merged into
    two branches) counts once, by its id and download time; given as (path, data), a spec without an id is known
    by its file name."""
    start = cycle_start(today, billing_day)
    count = 0
    seen = set()
    for item in specs:
        path, data = item if isinstance(item, tuple) else (None, item)
        at = (data.get("kept") or {}).get("downloaded_at")
        if not at or not start <= parse_dt(at).astimezone().date() <= today:
            continue
        name = data.get("id") or (path.stem if path is not None else None)
        if name:
            key = (name, str(at))
            if key in seen:
                continue
            seen.add(key)
        count += 1
    return count
