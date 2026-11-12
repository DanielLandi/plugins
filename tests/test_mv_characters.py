"""Character engines are a per-video choice made at the look step (make skill, step 5), like jolts: recorded in
LOOK.md, look.ts and video.yaml. No characters (null) is the default."""
import re

import pytest
import yaml

from conftest import REPO
from musicvideo.characters import ENGINES, characters_setting
from musicvideo.errors import MVError

PLUGIN = REPO / "music-video"
TEMPLATE = PLUGIN / "studio" / "template"


def test_the_engines_are_raw_then_vrm():
    assert ENGINES == ("raw", "vrm")


def test_the_template_starts_with_no_characters():
    look = (TEMPLATE / "look.ts").read_text(encoding="utf-8")
    assert re.search(r"export const characterEngine: CharacterEngine \| null = null;", look)
    assert yaml.safe_load((TEMPLATE / "video.yaml").read_text(encoding="utf-8"))["characters"] is None
    assert re.search(r"\*\*Characters:\*\* none\b", (TEMPLATE / "LOOK.md").read_text(encoding="utf-8"))


def test_the_kit_type_lists_the_same_engines():
    types = (PLUGIN / "studio" / "kit" / "types.ts").read_text(encoding="utf-8")
    union = re.search(r"export type CharacterEngine = ([^;]+);", types).group(1)
    assert tuple(re.findall(r"'([a-z0-9-]+)'", union)) == ENGINES


def test_the_template_registers_bakeoff_compositions():
    index = (TEMPLATE / "index.tsx").read_text(encoding="utf-8")
    assert "from './bakeoff'" in index and "-bakeoff-" in index
    bakeoff = (TEMPLATE / "bakeoff.ts").read_text(encoding="utf-8")
    assert "entries: []" in bakeoff and "export const bakeoff" in bakeoff


def _video(mv_ws, text):
    vdir = mv_ws.video_dir("duel")
    vdir.mkdir(parents=True, exist_ok=True)
    if text is not None:
        (vdir / "video.yaml").write_text(text, encoding="utf-8")


@pytest.mark.parametrize("text, want", [(None, None), ("id: duel\n", None), ("characters: null\n", None),
                                        ("characters: vrm\n", "vrm"), ("characters: raw\n", "raw"),
                                        ("characters: VRM\n", "vrm")])
def test_characters_setting(mv_ws, text, want):
    _video(mv_ws, text)
    assert characters_setting(mv_ws, "duel") == want


def test_an_unknown_engine_names_the_choices(mv_ws):
    _video(mv_ws, "characters: cartoon\n")
    with pytest.raises(MVError, match=r"cartoon.*raw, vrm"):
        characters_setting(mv_ws, "duel")
