"""Plugin versions (MAJOR.MINOR.PATCH, digits only) and the line that says a newer one is available."""
from __future__ import annotations

import re

import lv

_VERSION = re.compile(r"(\d{1,4})\.(\d{1,4})\.(\d{1,4})")
STEPS = ("run /plugin update lesson-videos, then close and reopen Claude Code, then run /lesson-videos:serve")
MOVED = ("lesson-videos is now slide2video. To switch: run /plugin marketplace add slide2video/slide2video-plugin, "
         "then /plugin install slide2video@slide2video, then /plugin uninstall lesson-videos, and close and reopen "
         "Claude Code. Your keys and settings come along.")


def parse(s) -> tuple[int, int, int] | None:
    m = _VERSION.fullmatch(s) if isinstance(s, str) else None
    return (int(m[1]), int(m[2]), int(m[3])) if m else None


def update_line(latest) -> str | None:
    """What to tell the teacher when the website is built for a newer version with this plugin's major."""
    have, site = parse(lv.__version__), parse(latest)
    if not have or not site or site[0] != have[0] or site <= have:
        return None
    return f"A newer lesson-videos ({latest}) is available. To update: {STEPS}."
