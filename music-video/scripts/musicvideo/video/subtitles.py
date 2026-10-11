"""LRC, SRT and WebVTT files from timing.json."""


def _parts(t: float) -> tuple[int, int, int, int]:
    ms = int(round(max(t, 0.0) * 1000))
    return ms // 3_600_000, ms // 60_000 % 60, ms // 1000 % 60, ms % 1000


def lrc_time(t: float) -> str:
    cs = int(round(max(t, 0.0) * 100))
    return f"{cs // 6000:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def srt_time(t: float) -> str:
    h, m, s, ms = _parts(t)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def vtt_time(t: float) -> str:
    h, m, s, ms = _parts(t)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def _line_words(timing: dict, line: dict) -> list[dict]:
    a, b = line["words"]
    return timing["words"][a:b + 1]


def _cues(timing: dict) -> list[tuple[float, float, dict]]:
    """Each line's span on screen, ending no later than the next line starts."""
    lines, out = timing["lines"], []
    for n, line in enumerate(lines):
        end = line["end"]
        if n + 1 < len(lines) and lines[n + 1]["start"] > line["start"]:
            end = min(end, lines[n + 1]["start"])
        out.append((line["start"], max(end, line["start"] + 0.001), line))
    return out


def to_lrc(timing: dict, title: str, artist: str) -> str:
    rows = [f"[ti:{title}]", f"[ar:{artist}]"]
    for line in timing["lines"]:
        words = " ".join(f"<{lrc_time(w['start'])}>{w['text']}" for w in _line_words(timing, line))
        rows.append(f"[{lrc_time(line['start'])}]{words}")
    return "\n".join(rows) + "\n"


def to_srt(timing: dict) -> str:
    return "\n".join(f"{n}\n{srt_time(a)} --> {srt_time(b)}\n{line['text']}\n"
                     for n, (a, b, line) in enumerate(_cues(timing), 1))


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def to_vtt(timing: dict) -> str:
    cues = []
    for a, b, line in _cues(timing):
        parts, last = [], a
        for w in _line_words(timing, line):
            if parts and a < w["start"] < b and w["start"] > last:
                parts.append(f"<{vtt_time(w['start'])}>{_esc(w['text'])}")
                last = w["start"]
            else:
                parts.append(_esc(w["text"]))
        cues.append(f"{vtt_time(a)} --> {vtt_time(b)}\n{' '.join(parts)}\n")
    return "WEBVTT\n\n" + "\n".join(cues)
