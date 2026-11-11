"""Word starts on the first sound.

A word starts at the first audible energy of its first sound (Imaginative Prompting's song-timing skill, MIT): a
fricative at its noise onset (a sung s or f hisses well before the vowel), a stop at its release burst, a vowel or
sonorant where the voice rises into it, never on a breath or an "h" before it. The kind of first sound comes from the
word's spelling; its time is measured on the vocal stem.
"""
import unicodedata
from dataclasses import replace
from typing import Literal

import numpy as np

from .timing import MIN_WORD_S, Word, too_short

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


def _measure(samples: np.ndarray, sr: int, lo: float, hi: float, sound: Sound, win_s: float) -> tuple[float | None, float]:
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
        for k in range(dip + 1, len(p)):
            if p[k] >= threshold and (p[k:k + sustain] >= floor + 0.25 * (level - floor)).all():
                return _crossing(t, p, k, threshold), _confidence(level, floor)
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
    start (kept for the caller's bounds and future tie-breaks)."""
    a, conf_a = _measure(samples, sr, lo, hi, sound, WINDOWS_S[0])
    b, conf_b = _measure(samples, sr, lo, hi, sound, WINDOWS_S[1])
    if a is None:
        return None, 0.0
    if b is None or abs(a - b) > AGREE_S:
        return a, min(conf_a, UNSURE)
    return a, min(conf_a, conf_b)


# ---------------------------------------------------------------- refining the words

ONSET_MIN_CONF = 0.5
ONSET_EARLY_S = 0.30
ONSET_LATE_S = 0.25


def refine_onsets(words: list[Word], samples: np.ndarray, sr: int, lang: str, keep: set[int]) -> list[Word]:
    """Each word's start moved onto its first sound, measured on the vocal stem. Words in `keep` (the ones a timing
    fix changes) keep their start. A start that moves into the word before trims that word's end, unless the trim
    would leave it too short; then the start stays."""
    out = list(words)
    for i, w in enumerate(out):
        sound = first_sound(w.text, lang)
        if i in keep:
            out[i] = replace(w, sound=sound)
            continue
        prev = out[i - 1] if i > 0 else None
        lo = max(0.0, w.start - ONSET_EARLY_S, prev.start + MIN_WORD_S if prev else 0.0)
        hi = min(w.start + ONSET_LATE_S, w.end - MIN_WORD_S)
        if hi <= lo:
            out[i] = replace(w, sound=sound)
            continue
        t, conf = measure_onset(samples, sr, lo, hi, w.start, sound)
        start = round(t, 3) if t is not None and conf >= ONSET_MIN_CONF else w.start
        if prev and start < prev.end:
            if too_short(prev.start, start):
                start = w.start
            else:
                out[i - 1] = replace(prev, end=start)
        if start == w.start:
            out[i] = replace(w, sound=sound, onset_conf=conf)
        else:
            out[i] = replace(w, start=start, source="onset", sound=sound, onset_conf=conf, moved=round(start - w.start, 3))
    return out
