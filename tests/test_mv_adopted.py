"""Material adapted from claude-video-skills (MIT) keeps its notice: the licence in THIRD_PARTY_NOTICES.md and a
one-line credit atop every adapted reference."""
from conftest import REPO

PLUGIN = REPO / "music-video"
REFS = PLUGIN / "skills" / "make" / "references"
ADAPTED = {"animation.md"}


def test_adapted_references_carry_the_credit_and_the_notice_names_them():
    notices = (PLUGIN / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    assert "Copyright (c) 2026 Imaginative Prompting" in notices and "Permission is hereby granted" in notices
    credited = {f.name for f in REFS.glob("*.md")
                if "claude-video-skills (MIT" in f.read_text(encoding="utf-8").split("\n\n", 1)[0]}
    assert credited == ADAPTED
    assert all(f"`{name}`" in notices for name in ADAPTED)


def test_the_make_skill_and_the_scene_brief_read_animation_before_scene_code():
    skill = (PLUGIN / "skills" / "make" / "SKILL.md").read_text(encoding="utf-8")
    assert "`references/animation.md` before any scene code" in skill
    brief = (REFS / "studio.md").read_text(encoding="utf-8").split("## Scene-agent brief", 1)[1]
    assert "references/animation.md" in brief
