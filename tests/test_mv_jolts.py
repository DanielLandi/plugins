"""Jolts are a per-video question (make skill, step 5), never a rule: the answer lives in LOOK.md, look.ts and
video.yaml, and an unanswered question means no jolts."""
import re

import yaml

from conftest import REPO

PLUGIN = REPO / "music-video"
TEMPLATE = PLUGIN / "studio" / "template"


def test_the_template_starts_with_no_jolts():
    assert re.search(r"export const jolts(: boolean)? = false;", (TEMPLATE / "look.ts").read_text(encoding="utf-8"))
    assert yaml.safe_load((TEMPLATE / "video.yaml").read_text(encoding="utf-8"))["jolts"] is False
    assert re.search(r"\*\*Jolts:\*\* no\b", (TEMPLATE / "LOOK.md").read_text(encoding="utf-8"))


def test_the_make_skill_asks_at_the_look_step():
    skill = (PLUGIN / "skills" / "make" / "SKILL.md").read_text(encoding="utf-8")
    look_step = skill.split("## 5. Look", 1)[1].split("\n## 6.", 1)[0]
    assert "jolt" in look_step and "look.ts" in look_step and "video.yaml" in look_step and "LOOK.md" in look_step
    assert re.search(r"(unanswered|does not answer)[^.]*\bno\b", look_step)


def test_no_reference_makes_a_shake_a_rule():
    # Wherever a reference talks of shaking or kicking the camera, it ties it to the video's jolts answer.
    refs = PLUGIN / "skills" / "make" / "references"
    for f in sorted(refs.glob("*.md")):
        for para in f.read_text(encoding="utf-8").split("\n\n"):
            if re.search(r"\bshak(e|es|ing)\b|\bkick (on|the camera)|\bjogs?\b", para, re.I):
                assert "jolt" in para.lower(), f"{f.name}: {para[:120]}"
