"""Parse a spec's lyrics into sung lines, the section tags around them, and backing words."""
import re
from dataclasses import dataclass

SECTION_WORDS = ("intro", "verse", "pre-chorus", "prechorus", "chorus", "post-chorus", "hook", "refrain",
                 "bridge", "breakdown", "break", "interlude", "instrumental", "solo", "drop", "outro")
_TAG = re.compile(r"\[([^\]]*)\]")
_SECTION = re.compile(r"\b(?:" + "|".join(re.escape(w) for w in SECTION_WORDS) + r")\b", re.IGNORECASE)


@dataclass(frozen=True)
class LyricLine:
    text: str                  # as shown on screen: tags removed, parentheses kept
    section: int               # index into Lyrics.sections
    words: tuple[str, ...]     # tokens to align: parentheses removed, punctuation kept
    backing: tuple[bool, ...]  # one flag per token: sung inside parentheses


@dataclass(frozen=True)
class Lyrics:
    sections: tuple[str, ...]  # every section tag in order; repeats and wordless tags kept
    lines: tuple[LyricLine, ...]

    @property
    def words(self) -> list[str]:
        return [word for line in self.lines for word in line.words]

    def alignment_text(self) -> str:
        return "\n".join(" ".join(line.words) for line in self.lines)


def is_section_tag(tag: str) -> bool:
    return bool(_SECTION.search(tag))


def _tokens(text: str) -> tuple[tuple[str, ...], tuple[bool, ...]]:
    words, backing, inside = [], [], False
    for raw in text.split():
        if "(" in raw:
            inside = True
        word = raw.replace("(", "").replace(")", "")
        if word:
            words.append(word)
            backing.append(inside)
        if ")" in raw:
            inside = False
    return tuple(words), tuple(backing)


def parse_lyrics(text: str) -> Lyrics:
    sections: list[str] = []
    lines: list[LyricLine] = []
    for raw in text.splitlines():
        sections += [tag.strip() for tag in _TAG.findall(raw) if is_section_tag(tag)]
        rest = re.sub(r"\s+", " ", _TAG.sub("", raw)).strip()
        words, backing = _tokens(rest)
        if not words:
            continue
        if not sections:
            sections.append("Intro")
        lines.append(LyricLine(rest, len(sections) - 1, words, backing))
    return Lyrics(tuple(sections), tuple(lines))
