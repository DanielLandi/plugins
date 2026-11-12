"""Material adapted from claude-video-skills (MIT) keeps its notice: the licence in THIRD_PARTY_NOTICES.md and a
one-line credit atop every adapted reference."""
from conftest import REPO

PLUGIN = REPO / "music-video"
REFS = PLUGIN / "skills" / "make" / "references"
ADAPTED = {"animation.md", "shot-design.md", "shot-balance.md", "shot-card.md"}


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


def test_shot_design_fits_our_scene_changes_and_jolts():
    shot = (REFS / "shot-design.md").read_text(encoding="utf-8")
    assert "cuts.ts" in shot and "--cut" in shot and "`ease: 'cut'`" in shot
    assert "Hold the framing with a slight shake on the beat instead" not in shot
    skill = (PLUGIN / "skills" / "make" / "SKILL.md").read_text(encoding="utf-8")
    assert "`references/shot-design.md` before keying any camera move" in skill


def test_look_and_light_is_in_the_3d_sections():
    studio = (REFS / "studio.md").read_text(encoding="utf-8").split("## 3D", 1)[1].split("\n## ", 1)[0]
    for phrase in ("Poly Haven", "CC0", "Only real light sources glow", "decay = 2", "A dark space, not a void"):
        assert phrase in studio, phrase
    assert "Only real lights\n  glow" in (REFS / "look.md").read_text(encoding="utf-8")


def test_the_scene_brief_passes_the_users_notes_word_for_word():
    brief = (REFS / "studio.md").read_text(encoding="utf-8").split("## Scene-agent brief", 1)[1]
    assert "word for word" in brief and "verbatim" in brief
