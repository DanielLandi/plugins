from calendar import monthrange
from datetime import date
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


def downloads_in_cycle(specs: Iterable[dict], today: date, billing_day: int) -> int:
    start = cycle_start(today, billing_day)
    count = 0
    for data in specs:
        at = (data.get("kept") or {}).get("downloaded_at")
        if at and start <= parse_dt(at).astimezone().date() <= today:
            count += 1
    return count
