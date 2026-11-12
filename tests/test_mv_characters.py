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


SKILL = PLUGIN / "skills" / "make"


def _look_step():
    return (SKILL / "SKILL.md").read_text(encoding="utf-8").split("## 5. Look", 1)[1].split("\n## 6.", 1)[0]


def test_the_look_step_offers_the_engines():
    step = _look_step()
    for must in ("`raw`", "`vrm`", "**Characters:**", "characterEngine", "characters:", "bakeoff new",
                 "references/bakeoff.md", "--variant", "bakeoff clear"):
        assert must in step, must
    assert re.search(r"raw[^.]*(always|first)", step)


def test_the_model_watch_offers_once_and_never_blocks():
    step = _look_step()
    assert "bakeoff last --model" in step and "bakeoff record" in step
    assert re.search(r"\bonce\b", step) and re.search(r"never block", step)
    assert "--declined" in step


def test_the_bakeoff_reference_holds_the_brief():
    ref = (SKILL / "references" / "bakeoff.md").read_text(encoding="utf-8")
    for must in ("rooftop", "close-up", "clash", "on the hit", "fist bump", "original characters", "10 s",
                 "bakeoff new", "--scene bakeoff --variant", "bakeoff record", "bakeoff last", "avatars install",
                 "bakeoff clear", "`hit`"):
        assert must.lower() in ref.lower(), must
    # The brief is the plugin's own: it never names a show, a studio or a real person to imitate.
    assert not re.search(r"\b(in the style of|like the show|after the anime)\b", ref, re.I)


def test_studio_reference_explains_the_vrm_kit():
    studio = (SKILL / "references" / "studio.md").read_text(encoding="utf-8")
    for must in ("<Avatar", "@mv/avatars/vroid-sample-1.vrm", "avatars install", "poseTrack", "from=", "faceYaw"):
        assert must in studio, must
    look = (SKILL / "references" / "look.md").read_text(encoding="utf-8")
    assert "**Characters:**" in look


def test_docs_name_the_avatar_source_and_command():
    services = (REPO / "SERVICES.md").read_text(encoding="utf-8")
    assert "opengameart.org" in services
    readme = (PLUGIN / "README.md").read_text(encoding="utf-8")
    assert "avatars" in readme and "bakeoff" in readme
    changelog = (PLUGIN / "CHANGELOG.md").read_text(encoding="utf-8")
    assert changelog.split("\n## ", 2)[1].startswith("Unreleased (draft, not bumped)")
