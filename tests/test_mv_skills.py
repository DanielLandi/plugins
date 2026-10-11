import re

from conftest import REPO

SKILLS = REPO / "music-video" / "skills"
CALL = re.compile(r'uv run "\$\{CLAUDE_PLUGIN_ROOT\}/scripts/music-video\.py" ([a-z][a-z-]*)')
# Anywhere in a skill: no old names, no bash-only command syntax.
BANNED = [r"\$\(", r"\bexport\s+\w+=", r"npm --prefix", r"\bsuno-lib\b", r"~/Projects", r"(?m)^\s*open\s",
          r"\bcollections?/", r"\bSUNO_HOME\b"]
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


# Suno is the first generator, not the name of things: its specifics live only in references/generators/suno/.
SUNO_ONLY = re.compile(r"suno\.com|max mode|my taste|advanced mode|unlock & download|weirdness|style influence|"
                       r"\bvariety\b|\bm4a\b", re.I)


def _generic_lines():
    for f in _docs():
        if "generators" in f.relative_to(SKILLS).parts:
            continue
        for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            yield f, n, line


def test_generator_specifics_stay_in_the_generator_references():
    hits = [f"{f.relative_to(REPO)}:{n}" for f, n, line in _generic_lines() if SUNO_ONLY.search(line)]
    assert hits == []


def test_suno_is_named_only_as_a_generator():
    allowed = re.compile(r"description:|generators/suno|`suno:`|generator: suno|Suno today|\(Suno\)", re.I)
    hits = [f"{f.relative_to(REPO)}:{n}" for f, n, line in _generic_lines()
            if re.search(r"suno", line, re.I) and not allowed.search(line)]
    assert hits == []


def test_cli_help_is_generator_neutral():
    from musicvideo.cli import build_parser
    parser = build_parser()
    texts = [parser.description or ""]
    sub = next(a for a in parser._actions if a.dest == "command")
    for name, p in sub.choices.items():
        texts += [a.help or "" for a in p._actions] + [sub._choices_actions[list(sub.choices).index(name)].help or ""]
    assert [t for t in texts if "suno" in t.lower()] == []
