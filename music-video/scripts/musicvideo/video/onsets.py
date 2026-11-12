"""Word starts on the first sound.

A word starts at the first audible energy of its first sound (Imaginative Prompting's song-timing skill, MIT): a
fricative at its noise onset (a sung s or f hisses well before the vowel), a stop at its release burst, a vowel or
sonorant where the voice rises into it, never on a breath or an "h" before it. The kind of first sound comes from the
word's spelling; its time is measured on the vocal stem.
"""
import re
import unicodedata
from dataclasses import replace
from typing import Literal

import numpy as np

from .timing import MIN_WORD_S, Word, too_short

Sound = Literal["fricative", "stop", "voiced"]

_SOFT = set("eiy")
# A word that starts with a digit is sung as the number's name: the whole number's in English and Portuguese, the
# first digit's when the number is not a plain integer (12.5, 1º, 007) or the language is another one.
_DIGITS = {"en": "zero one two three four five six seven eight nine".split(),
           "pt": "zero um dois tres quatro cinco seis sete oito nove".split()}
_TEENS = {"en": "ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split(),
          "pt": "dez onze doze treze catorze quinze dezesseis dezessete dezoito dezenove".split()}
_TENS = {"en": "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split(),
         "pt": "_ _ vinte trinta quarenta cinquenta sessenta setenta oitenta noventa".split()}
_PT_HUNDREDS = "_ cento duzentos trezentos quatrocentos quinhentos seiscentos setecentos oitocentos novecentos".split()
_EN_ORDINALS = {1: "first", 2: "second", 3: "third"}  # the others start like the number itself (twelfth, twenty-first)


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


# These start with a voiced th (as in "the"): a soft voiced sound with little hiss, so the voice marks the start.
_VOICED_TH = {"the", "this", "that", "these", "those", "them", "they", "their", "theirs", "there", "then", "than",
              "though", "thus", "thee", "thou", "thy", "thine"}
# A g before e, i or y is soft (gentle, giant) except in these common words.
_HARD_G = ("get", "giv", "girl", "gift", "gigg", "gear", "geese", "gidd", "gimm", "gild", "girth", "gizm")


def _english(w: str) -> Sound:
    a, b = w[0], w[1:2]
    head = w.replace("\u2019", "'").split("'")[0]  # that's, they're: the word before the apostrophe
    if "".join(c for c in head if c.isalpha()) in _VOICED_TH:
        return "voiced"
    if w.startswith(("sh", "ch", "ph", "th")) or a in "sfvzxj":
        return "fricative"
    if w.startswith(_HARD_G):
        return "stop"
    if a in "cg":
        return "fricative" if b in _SOFT else "stop"
    if a in "pbtdkq":
        return "stop"
    return "voiced"


def _portuguese(w: str) -> Sound:
    # A word-initial r is classed as a hiss: in Brazilian Portuguese it is usually [h] or [x], though some singers
    # trill or tap it (voiced). Checked 2026-11-11 (#28) against real timing corrections: 0 corrected Portuguese
    # words start with r (no Portuguese song has corrections yet; the 164 corrected English starts were scored), so
    # fricative vs voiced could not be compared. Kept fricative until there are at least 5 such words; then score
    # both on those words with the onsets scorer and keep the lower median |start - correction|.
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


def _english_number(n: int) -> str:
    if n < 10:
        return _DIGITS["en"][n]
    if n < 20:
        return _TEENS["en"][n - 10]
    if n < 100:
        return _TENS["en"][n // 10] + (f"-{_DIGITS['en'][n % 10]}" if n % 10 else "")
    if n < 1000:
        rest = n % 100
        return f"{_DIGITS['en'][n // 100]} hundred" + (f" and {_english_number(rest)}" if rest else "")
    rest = n % 100
    if n < 2000 and (n // 100) % 10:  # 1100-1999 are sung as years: fifteen hundred, nineteen eighty-four
        tail = " hundred" if not rest else f" oh {_DIGITS['en'][rest]}" if rest < 10 else f" {_english_number(rest)}"
        return _english_number(n // 100) + tail
    rest = n % 1000
    head = f"{_english_number(n // 1000)} thousand"
    return head + ("" if not rest else f" and {_english_number(rest)}" if rest < 100 else f" {_english_number(rest)}")


def _portuguese_number(n: int) -> str:
    if n < 10:
        return _DIGITS["pt"][n]
    if n < 20:
        return _TEENS["pt"][n - 10]
    if n < 100:
        return _TENS["pt"][n // 10] + (f" e {_DIGITS['pt'][n % 10]}" if n % 10 else "")
    if n < 1000:
        if n == 100:
            return "cem"
        rest = n % 100
        return _PT_HUNDREDS[n // 100] + (f" e {_portuguese_number(rest)}" if rest else "")
    rest = n % 1000
    head = "mil" if n < 2000 else f"{_portuguese_number(n // 1000)} mil"
    if not rest:
        return head
    # "e" before a last group under a hundred or of whole hundreds: mil e cem, mil novecentos e oitenta e cinco
    return head + (" e " if rest < 100 or rest % 100 == 0 else " ") + _portuguese_number(rest)


def spell_number(n: int, lang: str) -> str | None:
    """The number as it is sung, in English or Portuguese (accents folded), for 0 <= n < 1,000,000; None otherwise."""
    code = (lang or "").lower()[:2]
    if code not in ("en", "pt") or not 0 <= n < 1_000_000:
        return None
    return _english_number(n) if code == "en" else _portuguese_number(n)


def _number_name(w: str, code: str) -> str:
    """The name a word starting with a digit is sung as."""
    digits = re.match(r"\d+", w).group()
    rest = w[len(digits):]
    whole = None
    if not (len(digits) > 1 and digits[0] == "0") and not re.match(r"[.,]\d", rest):
        n = int(digits)
        if not rest[:1].isalnum():  # 12, 9-to-5, 24/7
            whole = spell_number(n, code)
        elif code == "en" and re.fullmatch(r"(st|nd|rd|th)\b.*", rest):  # 1st, 12th
            whole = _EN_ORDINALS.get(n) or spell_number(n, code)
        elif code == "en" and re.fullmatch(r"s\b.*", rest):  # the 80s
            whole = spell_number(n, code)
    return whole or _DIGITS.get(code, _DIGITS["en"])[int(digits[0])]


def first_sound(word: str, lang: str) -> Sound:
    w = _letters(word)
    code = (lang or "").lower()[:2]
    if w[:1].isdigit():
        w = _number_name(w, code)
    if not w:
        return "voiced"
    return _english(w) if code == "en" else _portuguese(w) if code == "pt" else _other(w)


# ---------------------------------------------------------------- measuring on the vocal stem

ONSET_SR = 44100        # decoded at full rate: a sung s hisses well above 8 kHz
HOP_S = 0.005
WINDOWS_S = (0.020, 0.040)  # measured twice; the two must agree
AGREE_S = 0.025
PAD_S = 0.10            # context analysed before the window, for the floor
SUSTAIN_S = 0.030       # a hiss or a voice that lasts at least this long
FLOOR_S = 0.060         # a hiss or a burst is measured against the 60 ms just before it
BANDS = {"fricative": (4000.0, 12000.0), "stop": (100.0, 12000.0), "voiced": (100.0, 1500.0)}
LOW_BAND = (100.0, 1500.0)
RISE_DB = 10.0          # an event stands this far above the floor
CONF_DB = (6.0, 20.0)   # confidence 0 at the first, 1 at the second
UNSURE = 0.3            # the confidence when the two windows disagree


def _band_power(samples: np.ndarray, sr: int, t0: float, t1: float, win_s: float,
                bands: list[tuple[float, float]]) -> tuple[np.ndarray, list[np.ndarray]]:
    """Frame centres every HOP_S from t0 to t1, and each band's power at each centre (Hann window)."""
    win = max(int(round(win_s * sr)), 8)
    half = win // 2
    centres = np.arange(t0, t1 + 1e-9, HOP_S)
    idx = np.round(centres * sr).astype(int)
    keep = (idx - half >= 0) & (idx + half <= len(samples))
    centres, idx = centres[keep], idx[keep]
    if len(idx) == 0:
        return centres, [np.zeros(0) for _ in bands]
    frames = np.stack([samples[i - half:i - half + win] for i in idx]).astype(np.float64)
    power = np.abs(np.fft.rfft(frames * np.hanning(win), axis=1)) ** 2
    freqs = np.fft.rfftfreq(win, 1 / sr)
    out = []
    for lo_f, hi_f in bands:
        sel = (freqs >= lo_f) & (freqs < hi_f)
        out.append(power[:, sel].sum(axis=1) + 1e-12)
    return centres, out


def _crossing(t: np.ndarray, p: np.ndarray, k: int, threshold: float) -> float:
    """The time p rises through threshold around frame k (the rise that frame k is part of), interpolated linearly."""
    j = k
    while j < len(p) - 1 and p[j] < threshold:
        j += 1
    while j > 0 and p[j - 1] >= threshold:
        j -= 1
    if j == 0 or p[j] == p[j - 1]:
        return float(t[j])
    a = (threshold - p[j - 1]) / (p[j] - p[j - 1])
    return float(t[j - 1] + a * (t[j] - t[j - 1]))


def _confidence(level: float, floor: float) -> float:
    db = 10 * np.log10(level / floor)
    return float(np.clip((db - CONF_DB[0]) / (CONF_DB[1] - CONF_DB[0]), 0.0, 1.0))


def _measure(samples: np.ndarray, sr: int, lo: float, hi: float, guess: float, sound: Sound,
             win_s: float) -> tuple[float | None, float]:
    t, (p, low) = _band_power(samples, sr, max(0.0, lo - PAD_S), hi, win_s, [BANDS[sound], LOW_BAND])
    inside = np.flatnonzero(t >= lo)
    if len(inside) < 2:
        return None, 0.0
    first = inside[0]
    sustain = max(int(round(SUSTAIN_S / HOP_S)), 1)
    if sound == "voiced":
        # From the window's quietest point, the voice rising halfway to its peak: a breath stays far below it.
        dip = first + int(np.argmin(p[first:]))
        floor = p[dip]
        level = float(p[dip:].max())
        if level < floor * 10 ** (RISE_DB / 10):
            return None, 0.0
        threshold = floor + 0.5 * (level - floor)
        # The note before still sounding at the window's opening and at the word's start, with the dip after that
        # start: the dip can be a closure inside the word (af-ter), so the rise after it is unsure.
        g = first + int(np.argmin(np.abs(t[first:] - guess)))
        opens, at_start = ((p[k:k + sustain] >= threshold).all() for k in (first, g))
        held = bool(opens and at_start) and dip > g
        for k in range(dip + 1, len(p)):
            if p[k] >= threshold and (p[k:k + sustain] >= floor + 0.25 * (level - floor)).all():
                conf = _confidence(level, floor)
                return _crossing(t, p, k, threshold), min(conf, UNSURE) if held else conf
        return None, 0.0
    look = max(int(round(FLOOR_S / HOP_S)), 2)
    for k in range(max(first, look), len(p)):
        floor = float(np.median(p[k - look:k]))
        rise = floor * 10 ** (RISE_DB / 10)
        if p[k] < rise or p[k - 1] >= rise:
            continue  # only a frame that rises through the line counts
        if sound == "fricative":
            run = slice(k, k + sustain)
            if len(p[run]) < sustain or not (p[run] >= rise).all() or np.median(p[run]) <= np.median(low[run]):
                continue
            level = float(np.median(p[run]))
        else:
            level = float(p[k:k + max(sustain // 2, 1)].max())
        threshold = floor + 0.5 * (level - floor)
        return _crossing(t, p, k, threshold), _confidence(level, floor)
    return None, 0.0


def measure_onset(samples: np.ndarray, sr: int, lo: float, hi: float, guess: float,
                  sound: Sound) -> tuple[float | None, float]:
    """Where the word's first sound starts within [lo, hi] (song seconds), and how sure (0-1). Measured with two
    window lengths; when they disagree by more than AGREE_S the confidence drops to UNSURE. `guess` is the current
    start: a voice rising after a dip that the note before runs past it into is unsure."""
    a, conf_a = _measure(samples, sr, lo, hi, guess, sound, WINDOWS_S[0])
    b, conf_b = _measure(samples, sr, lo, hi, guess, sound, WINDOWS_S[1])
    if a is None:
        return None, 0.0
    if b is None or abs(a - b) > AGREE_S:
        return a, min(conf_a, UNSURE)
    return a, min(conf_a, conf_b)


# ---------------------------------------------------------------- refining the words

ONSET_MIN_CONF = 0.5
ONSET_EARLY_S = 0.30
OVERLAP_S = 0.05      # how far a start may reach into the previous word's end
ONSET_LATE_S = 0.35   # the aligner tends to start words early (tuned on real corrections)


def refine_onsets(words: list[Word], samples: np.ndarray, sr: int, lang: str, keep: set[int]) -> list[Word]:
    """Each word's start moved onto its first sound, measured on the vocal stem. Words in `keep` (the ones a timing
    fix changes) keep their start and end. A start that moves into the word before trims that word's end, unless the
    trim would leave it too short (then the start stays) or that word is kept (then the start stays after its end)."""
    out = list(words)
    for i, w in enumerate(out):
        sound = first_sound(w.text, lang)
        if i in keep:
            out[i] = replace(w, sound=sound)
            continue
        prev = out[i - 1] if i > 0 else None
        # Never earlier than the previous word allows: past its first MIN_WORD_S, and at most OVERLAP_S into its end.
        lo = max(0.0, w.start - ONSET_EARLY_S, prev.start + MIN_WORD_S if prev else 0.0,
                 prev.end - OVERLAP_S if prev else 0.0)
        if prev and i - 1 in keep:
            lo = max(lo, prev.end)
        hi = min(w.start + ONSET_LATE_S, w.end - MIN_WORD_S)
        if hi <= lo:
            out[i] = replace(w, sound=sound)
            continue
        t, conf = measure_onset(samples, sr, lo, hi, w.start, sound)
        start = round(t, 3) if t is not None and conf >= ONSET_MIN_CONF else w.start
        if prev and start < prev.end:
            if too_short(prev.start, start) or i - 1 in keep:
                start = w.start
            else:
                out[i - 1] = replace(prev, end=start)
        if start == w.start:
            out[i] = replace(w, sound=sound, onset_conf=conf)
        else:
            out[i] = replace(w, start=start, source="onset", sound=sound, onset_conf=conf, moved=round(start - w.start, 3))
    return out
