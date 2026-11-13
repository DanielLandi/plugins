"""Character engines: how a video's characters are animated, chosen per video at the look step (make skill, step 5)
and recorded as `characters:` in video.yaml, `characterEngine` in look.ts and the **Characters:** line of LOOK.md.

- raw: the model writes the characters and their motion from scratch in scene code (SVG, canvas or three.js).
  Always available; needs nothing installed.
- vrm: 3D anime characters through three-vrm (`@mv/kit/three`: Avatar, poses), with the CC0 sample avatars
  (`music-video avatars install`) or the user's own CC0/OFL .vrm files.
- cartoon: hand-inked 2D rubber-hose characters (`@mv/kit/cartoon`: brush lines that boil, faces that act, squash
  and stretch, smears). Original characters drawn in code; needs nothing installed beyond the engine.

Later engines (inochi2d) are added here, in kit/types.ts and with a starter in studio/bakeoff/.
"""
import yaml

from .errors import MVError
from .workspace import Workspace

ENGINES: tuple[str, ...] = ("raw", "vrm", "cartoon")  # raw first: it is always offered and always in a bake-off


def check_engines(names: list[str]) -> list[str]:
    """Known engines, lower-cased, without repeats, in the order given."""
    out: list[str] = []
    for name in (n.strip().lower() for n in names):
        if name not in ENGINES:
            raise MVError(f"'{name}' is not a character engine: use {', '.join(ENGINES)}")
        if name not in out:
            out.append(name)
    return out


def engine_of(meta: object) -> str | None:
    """`characters:` in a parsed video.yaml: an engine, or None when it has no characters (or the key is absent).
    An unknown value raises MVError naming the engines, so a typo stops the video's first render or typecheck."""
    value = meta.get("characters") if isinstance(meta, dict) else None
    if value is None or value is False:
        return None
    return check_engines([str(value)])[0]


def characters_setting(ws: Workspace, video_id: str) -> str | None:
    """`characters:` in the video's video.yaml (see engine_of)."""
    path = ws.video_dir(video_id) / "video.yaml"
    return engine_of(yaml.safe_load(path.read_text(encoding="utf-8")) if path.is_file() else None)
