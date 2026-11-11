"""Word starts on the first sound.

A word starts at the first audible energy of its first sound (Imaginative Prompting's song-timing skill, MIT): a
fricative at its noise onset (a sung s or f hisses well before the vowel), a stop at its release burst, a vowel or
sonorant where the voice rises into it, never on a breath or an "h" before it. The kind of first sound comes from the
word's spelling; its time is measured on the vocal stem.
"""
import unicodedata
from typing import Literal

Sound = Literal["fricative", "stop", "voiced"]

_SOFT = set("eiy")
# A word that starts with a digit is sung as the number's name.
_DIGITS = {"en": "zero one two three four five six seven eight nine".split(),
           "pt": "zero um dois tres quatro cinco seis sete oito nove".split()}


def _letters(word: str) -> str:
    """The word lowercased from its first letter on, accents folded (but ç kept: it is a sound of its own)."""
    out = []
    for ch in word.lower():
        if ch == "ç":
            out.append(ch)
            continue
        base = "".join(c for c in unicodedata.normalize("NFKD", ch) if not unicodedata.combining(c))
        out.append(base)
    text = "".join(out)
    i = next((k for k, c in enumerate(text) if c.isalnum()), len(text))
    return text[i:]


def _english(w: str) -> Sound:
    a, b = w[0], w[1:2]
    if w.startswith(("sh", "ch", "ph", "th")) or a in "sfvzxj":
        return "fricative"
    if a in "cg":
        return "fricative" if b in _SOFT else "stop"
    if a in "pbtdkq":
        return "stop"
    return "voiced"


def _portuguese(w: str) -> Sound:
    a, b = w[0], w[1:2]
    if w.startswith("ch") or a in "sçfvzjxr":
        return "fricative"
    if a in "cg":
        return "fricative" if b in "ei" else "stop"
    if a in "pbtdkq":
        return "stop"
    return "voiced"


def _other(w: str) -> Sound:
    a = w[0]
    if a in "sfvz":
        return "fricative"
    if a in "pbtdk":
        return "stop"
    return "voiced"


def first_sound(word: str, lang: str) -> Sound:
    w = _letters(word)
    code = (lang or "").lower()[:2]
    if w[:1].isdigit():
        w = _DIGITS.get(code, _DIGITS["en"])[int(w[0])]
    if not w:
        return "voiced"
    return _english(w) if code == "en" else _portuguese(w) if code == "pt" else _other(w)
