import re

from conftest import REPO

SKILLS = REPO / "music-video" / "skills"
CALL = re.compile(r'uv run "\$\{CLAUDE_PLUGIN_ROOT\}/scripts/music-video\.py" ([a-z][a-z-]*)')
# Anywhere in a skill: no old names, no bash-only command syntax.
BANNED = [r"\$\(", r"\bexport\s+\w+=", r"npm --prefix", r"\bsuno-lib\b", r"~/Projects", r"(?m)^\s*open\s",
          r"\bcollections?/", r"\bmanifest\.json\b", r"\bSUNO_HOME\b"]
# Only in shell commands (JavaScript snippets for the Suno page legitimately use &&).
SHELL_BANNED = [r"&&", r"\|\|", r"\\\s*$", r"\bfor \w+ in\b", r"\bcd \S"]
SHELLS = {"", "bash", "sh", "shell", "zsh", "console"}


def _docs():
    return sorted(SKILLS.rglob("*.md"))


def _shell(text):
    blocks, lang, body = [], None, []
    for line in text.splitlines():
        fence = re.match(r"\s*```(\w*)\s*$", line)
        if fence and lang is None:
            lang, body = fence.group(1), []
        elif fence:
            if lang in SHELLS:
                blocks.append("\n".join(body))
            lang = None
        elif lang is not None:
            body.append(line)
    inline = re.findall(r"`(uv run [^`]*|ffmpeg [^`]*)`", text)
    return "\n".join(blocks + inline)


def test_three_skills_with_frontmatter():
    for name in ("make", "song", "ingest"):
        text = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
        assert text.startswith("---\n") and f"name: {name}\n" in text and "description: Use " in text


def test_every_command_exists():
    from musicvideo.cli import build_parser
    sub = next(a for a in build_parser()._actions if a.dest == "command")
    used = {m for f in _docs() for m in CALL.findall(f.read_text(encoding="utf-8"))}
    assert used, "skills must call the CLI"
    assert used <= set(sub.choices), used - set(sub.choices)


def test_no_bash_only_syntax_or_old_names():
    hits = []
    for f in _docs():
        text = f.read_text(encoding="utf-8")
        hits += [f"{f.relative_to(REPO)}: {p}" for p in BANNED if re.search(p, text)]
        shell = _shell(text)
        hits += [f"{f.relative_to(REPO)} (shell): {p}" for p in SHELL_BANNED if re.search(p, shell, re.M)]
    assert hits == []


def test_shell_check_bites():
    assert re.search(SHELL_BANNED[0], _shell("```bash\nnpm ci && npm test\n```"))
    assert not _shell("```js\na && b\n```")
    assert _shell("```bash\nls\n```\n\nprose && more\n\n```text\ncard\n```") == "ls"


def test_references_exist():
    for f in _docs():
        for ref in re.findall(r"`(references/[\w-]+\.md)`", f.read_text(encoding="utf-8")):
            assert (f.parent / ref).is_file() or (f.parent.parent / ref).is_file(), f"{f}: {ref}"
