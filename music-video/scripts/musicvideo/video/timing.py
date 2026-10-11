"""Word timings for a sung song.

The forced alignment is repaired from a free transcription and from the separated vocal track, then
the user's fixes (timing-fixes.yaml) are applied. The thresholds were measured on real Suno songs.
"""
import difflib
import re
import unicodedata
from dataclasses import dataclass, replace

import numpy as np

from ..errors import MVError
from .lyrics import Lyrics

SUSPECT_CONF = 0.15     # below this the aligner is guessing
MAX_WORD_S = 2.5        # longer than this is a word stretched over a pause...
MAX_LINE_END_S = 4.0    # ...except a held last word of a line
HEARD_WINDOW_S = 6.0    # the transcription's word must be this close to be the same word
HEARD_MIN_CONF = 0.3
STRETCH_MIN_S = 1.0     # a long word whose end agrees with the transcription...
END_AGREE_S = 0.25
STRETCH_LEAD_S = 0.3    # ...takes the transcription's start when that is this much later
VOICE_FRAME_S = 0.02
VOICE_REL = 0.1         # voice threshold: 10% of the vocal track's 95th-percentile RMS
SILENT_PEAK = 0.5       # a word whose peak stays under half the threshold sits on silence
SNAP_LEN_S = 0.12
MIN_WORD_S = 0.06
MISSING_CONF = 0.3      # a line this unsure throughout, and never heard, may not have been sung
FIX_WINDOW_S = 3.0


@dataclass(frozen=True)
class Word:
    text: str
    start: float
    end: float
    conf: float
    source: str = "align"  # align | transcript | snapped | fixed


def norm(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text.lower())
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in folded if not unicodedata.combining(c)))


def clock(t: float) -> str:
    return f"{int(t // 60)}:{t % 60:04.1f}"


def words_from_json(items: list[dict]) -> list[Word]:
    return [Word(str(i["word"]).strip(), float(i["start"]), float(i["end"]), float(i.get("prob") or 0.0))
            for i in items]


def match_heard(aligned: list[Word], heard: list[Word]) -> dict[int, int]:
    """Pair each aligned word with the transcription's word in the same place of the sequence."""
    sm = difflib.SequenceMatcher(None, [norm(w.text) for w in aligned], [norm(w.text) for w in heard],
                                 autojunk=False)
    return {i + k: j + k for i, j, n in sm.get_matching_blocks() for k in range(n)}


def line_ends(lyrics: Lyrics) -> set[int]:
    ends, k = set(), 0
    for line in lyrics.lines:
        k += len(line.words)
        ends.add(k - 1)
    return ends


def is_suspect(word: Word, ends_line: bool) -> bool:
    longest = MAX_LINE_END_S if ends_line else MAX_WORD_S
    return word.conf < SUSPECT_CONF or word.end - word.start > longest


def reconcile(words: list[Word], heard: list[Word], ends: set[int]) -> list[Word]:
    out = list(words)
    pairs = match_heard(words, heard)
    for i, w in enumerate(out):
        j = pairs.get(i)
        if j is None:
            continue
        t = heard[j]
        if is_suspect(w, i in ends) and abs(t.start - w.start) < HEARD_WINDOW_S and t.conf > HEARD_MIN_CONF:
            lo = out[i - 1].end if i else 0.0
            hi = out[i + 1].start if i + 1 < len(out) else float("inf")
            start, end = max(t.start, lo), min(t.end, hi)
            if end - start >= MIN_WORD_S:
                out[i] = replace(w, start=round(start, 3), end=round(end, 3), source="transcript")
                continue
        stretched = w.end - w.start > STRETCH_MIN_S
        if stretched and abs(t.end - w.end) < END_AGREE_S and t.start > w.start + STRETCH_LEAD_S:
            out[i] = replace(w, start=round(t.start, 3), source="transcript")
    return out


def snap_to_voice(words: list[Word], envelope: np.ndarray, frame_s: float = VOICE_FRAME_S) -> list[Word]:
    if len(envelope) == 0:
        return list(words)
    threshold = VOICE_REL * float(np.percentile(envelope, 95))
    if threshold <= 0:
        return list(words)
    out = list(words)
    for i, w in enumerate(out):
        a = int(w.start / frame_s)
        b = max(int(w.end / frame_s), a + 1)
        if a >= len(envelope) or envelope[a:b].max() >= SILENT_PEAK * threshold:
            continue
        nxt = out[i + 1].start if i + 1 < len(out) else w.end + 2.0
        limit = min(int(nxt / frame_s), len(envelope))
        onset = next((k for k in range(b, limit) if envelope[k] >= threshold), None)
        start = onset * frame_s if onset is not None else nxt - SNAP_LEN_S
        end = min(max(start + SNAP_LEN_S, w.end), nxt)
        if end - start < MIN_WORD_S:
            start = end - 0.1
        out[i] = replace(w, start=round(start, 3), end=round(end, 3), source="snapped")
    return out


def parse_at(value) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    try:
        seconds = 0.0
        for part in str(value).strip().split(":"):
            seconds = seconds * 60 + float(part)
    except ValueError as e:
        raise MVError(f"timing fix: cannot read time {value!r} (use m:ss or seconds)") from e
    return seconds


def apply_fixes(words: list[Word], fixes: list[dict]) -> list[Word]:
    out = list(words)
    for fix in fixes:
        if is_show_only(fix):
            continue
        if not isinstance(fix, dict) or "at" not in fix or "word" not in fix:
            raise MVError(f"timing fix {fix!r} needs 'at' and 'word', plus 'shift' or 'start'/'end'")
        at, key = parse_at(fix["at"]), norm(str(fix["word"]))
        candidates = [i for i, w in enumerate(out) if norm(w.text) == key and abs(w.start - at) <= FIX_WINDOW_S]
        if not candidates:
            raise MVError(f"timing fix {fix['word']!r} at {fix['at']}: no such word within {FIX_WINDOW_S:g} s")
        i = min(candidates, key=lambda k: abs(out[k].start - at))
        w = out[i]

        def number(field: str, default=None) -> float:
            if field not in fix:
                return default
            try:
                if isinstance(fix[field], bool):
                    raise ValueError
                return float(fix[field])
            except (TypeError, ValueError):
                raise MVError(f"timing fix {fix['word']!r} at {fix['at']}: {field} must be a number") from None

        if "shift" in fix:
            shift = number("shift")
            start, end = w.start + shift, w.end + shift
        else:
            start, end = number("start", w.start), number("end", w.end)
        if end - start < MIN_WORD_S:
            raise MVError(f"timing fix {fix['word']!r} at {fix['at']} makes the word too short")
        out[i] = replace(w, start=round(start, 3), end=round(end, 3), source="fixed")
    return out


TIMING_KEYS = ("shift", "start", "end")


def is_show_only(fix) -> bool:
    """A `show:` entry changes how a word is written, not when it is sung."""
    return isinstance(fix, dict) and "show" in fix and not any(k in fix for k in TIMING_KEYS)


def show_words(timing: dict, fixes: list[dict]) -> dict:
    """Write sung words as `show` says (e.g. "Nine-to-five" sung, "9-to-5" shown) in words and line texts.

    An entry is `{word, show}` (every occurrence) or `{at, word, show}` (the one nearest `at`). Times never change.
    """
    words = [dict(w) for w in timing["words"]]
    lines = [dict(line) for line in timing["lines"]]
    for fix in fixes:
        if not isinstance(fix, dict) or "show" not in fix:
            continue
        if "word" not in fix:
            raise MVError(f"timing fix {fix!r}: 'show' needs the sung 'word'")
        key, shown = norm(str(fix["word"])), str(fix["show"])
        matches = [w for w in words if norm(w["text"]) == key]
        if "at" in fix:
            at = parse_at(fix["at"])
            near = [w for w in matches if abs(w["start"] - at) <= FIX_WINDOW_S]
            matches = [min(near, key=lambda w: abs(w["start"] - at))] if near else []
        if not matches:
            where = f" at {fix['at']}" if "at" in fix else ""
            raise MVError(f"timing fix {fix['word']!r}{where}: no such sung word to show as {shown!r}")
        for w in matches:
            line = lines[w["line"]]
            # Rewrite this word's own occurrence in the line: count the same words before it in that line.
            before = sum(1 for x in words if x["line"] == w["line"] and x["i"] < w["i"] and norm(x["text"]) == key)
            parts = line["text"].split(w["text"])
            if len(parts) > before + 1:
                line["text"] = w["text"].join(parts[:before + 1]) + shown + w["text"].join(parts[before + 1:])
            w["text"] = shown
    return {**timing, "words": words, "lines": lines}


def suspects(words: list[Word], ends: set[int]) -> list[int]:
    return [i for i, w in enumerate(words) if w.source != "fixed" and is_suspect(w, i in ends)]


def missing_lines(aligned: list[Word], lyrics: Lyrics, heard_pairs: dict[int, int]) -> list[int]:
    out, k = [], 0
    for li, line in enumerate(lyrics.lines):
        idx = range(k, k + len(line.words))
        k += len(line.words)
        never_heard = all(i not in heard_pairs for i in idx)
        if never_heard and float(np.mean([aligned[i].conf for i in idx])) < MISSING_CONF:
            out.append(li)
    return out


def build_timing(words: list[Word], lyrics: Lyrics, duration: float) -> dict:
    if len(words) != len(lyrics.words):
        raise MVError(f"{len(words)} timed words for {len(lyrics.words)} lyric words")
    out_words, out_lines, k = [], [], 0
    for li, line in enumerate(lyrics.lines):
        first = k
        for token, backing in zip(line.words, line.backing):
            w = words[k]
            out_words.append({"i": k, "text": token, "start": w.start, "end": w.end, "conf": round(w.conf, 3),
                              "source": w.source, "line": li, "backing": backing})
            k += 1
        out_lines.append({"i": li, "text": line.text, "section": line.section, "backing": all(line.backing),
                          "start": words[first].start, "end": max(w.end for w in words[first:k]),
                          "words": [first, k - 1]})
    sections = []
    for si, name in enumerate(lyrics.sections):
        mine = [line for line in out_lines if line["section"] == si]
        sections.append({"i": si, "name": name,
                         "start": mine[0]["start"] if mine else None,
                         "end": mine[-1]["end"] if mine else None,
                         "lines": [mine[0]["i"], mine[-1]["i"]] if mine else None})
    return {"version": 1, "duration": round(duration, 3), "words": out_words, "lines": out_lines,
            "sections": sections}
