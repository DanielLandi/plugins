"""music-video preview: a full-song karaoke check — word sweep, section label, beat dot, and a paged vocal
waveform (10 s at a time, a moving playhead, 0.1 s ticks and a mark at each word's start), so a word's time can be
read against the voice to the tenth of a second."""
import json
from pathlib import Path

from ..workspace import Workspace
from ..errors import MVError
from .media import duration_s, has_filter, need, run
from .paths import video_song

LEAD_S = 0.6   # a line appears this long before its first word...
TAIL_S = 0.4   # ...and stays this long after its last, never overlapping the next line
WIDTH, HEIGHT = 1280, 720
PAGE_S = 10                    # the waveform panel shows the song a page at a time
PANEL_TOP = 500                # the panel: word labels, then the waveform, then the second labels
WAVE_TOP, WAVE_H = 560, 140
MARK_ROWS = 3                  # word labels alternate over this many rows so close words stay readable

HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1280
PlayResY: 720
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sing,Helvetica Neue,52,&H0000D7FF,&H00FFFFFF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,3,0,5,60,60,0,1
Style: Next,Helvetica Neue,34,&H00808080,&H00808080,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,60,60,250,1
Style: Label,Helvetica Neue,28,&H00C0C0C0,&H00C0C0C0,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,2,0,7,30,30,70,1
Style: Beat,Helvetica Neue,40,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,0,0,9,40,40,30,1
Style: Down,Helvetica Neue,56,&H0000D7FF,&H0000D7FF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,0,0,9,34,34,22,1
Style: Tick,Helvetica Neue,14,&H00909090,&H00909090,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1
Style: Grid,Helvetica Neue,14,&HA0909090,&HA0909090,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1
Style: Mark,Helvetica Neue,16,&H0080E8FF,&H0080E8FF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,1,0,7,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def ass_time(t: float) -> str:
    cs = int(round(max(t, 0.0) * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def _clean(text: str) -> str:
    return text.replace("{", "(").replace("}", ")").replace("\\", "/")


def line_spans(lines: list[dict]) -> list[tuple[float, float]]:
    spans, prev_to = [], 0.0
    for n, line in enumerate(lines):
        start = max(line["start"] - LEAD_S, prev_to)
        end = line["end"] + TAIL_S
        if n + 1 < len(lines):
            end = min(end, max(line["end"], lines[n + 1]["start"] - LEAD_S))
        end = max(end, start + 0.1)
        spans.append((start, end))
        prev_to = end
    return spans


def _event(start: float, end: float, style: str, text: str) -> str:
    return f"Dialogue: 0,{ass_time(start)},{ass_time(end)},{style},,0,0,0,,{text}"


def page_x(t: float) -> int:
    """The panel's x for song time t, on t's own page."""
    return round((t % PAGE_S) / PAGE_S * WIDTH)


def _rects(rects: list[tuple[int, int, int, int]]) -> str:
    return " ".join(f"m {x} {y} l {x + w} {y} l {x + w} {y + h} l {x} {y + h}" for x, y, w, h in rects)


def _drawing(start: float, end: float, style: str, rects: list[tuple[int, int, int, int]]) -> str:
    return _event(start, end, style, f"{{\\an7\\pos(0,0)\\p1}}{_rects(rects)}{{\\p0}}")


def panel_events(words: list[dict], duration: float) -> list[str]:
    """Per page: 0.1 s ticks, a line and a label at every second, and a mark plus the word at each word's start."""
    events, wave_end = [], WAVE_TOP + WAVE_H
    for page in range(int(duration // PAGE_S) + 1):
        t0 = page * PAGE_S
        t1 = min(t0 + PAGE_S, duration)
        if t1 <= t0:
            break
        steps = range(PAGE_S * 10)
        events.append(_drawing(t0, t1, "Tick", [(round(i * WIDTH / (PAGE_S * 10)), wave_end - 6, 1, 6)
                                               for i in steps if i % 10]))
        events.append(_drawing(t0, t1, "Grid", [(round(i * WIDTH / PAGE_S), WAVE_TOP, 1, WAVE_H)
                                               for i in range(1, PAGE_S)]))
        for sec in range(t0, int(t1) + (0 if t1 == int(t1) else 1)):
            events.append(_event(t0, t1, "Tick", f"{{\\pos({page_x(sec) + 3},{wave_end + 2})}}"
                                                   f"{sec // 60}:{sec % 60:02d}"))
        on_page = [w for w in words if t0 <= w["start"] < t0 + PAGE_S]
        for n, w in enumerate(on_page):
            x, y = page_x(w["start"]), PANEL_TOP + 4 + (n % MARK_ROWS) * 18
            events.append(_drawing(t0, t1, "Mark", [(x, y, 1, wave_end - y)]))
            events.append(_event(t0, t1, "Mark", f"{{\\pos({x + 3},{y})}}{_clean(w['text'])}"))
    return events


def build_ass(timing: dict, analysis: dict | None, duration: float | None = None) -> str:
    events, words, lines = [], timing["words"], timing["lines"]
    for n, (line, (shown, hidden)) in enumerate(zip(lines, line_spans(lines))):
        a, b = line["words"]
        cursor = words[a]["start"]
        karaoke = [f"{{\\k{max(round((cursor - shown) * 100), 0)}}}"]
        for w in words[a:b + 1]:
            if w["start"] > cursor:
                karaoke.append(f"{{\\k{round((w['start'] - cursor) * 100)}}}")
            text = _clean(w["text"])
            text = f"{{\\i1}}{text}{{\\i0}}" if w["backing"] else text
            karaoke.append(f"{{\\kf{max(round((w['end'] - w['start']) * 100), 1)}}}{text} ")
            cursor = max(cursor, w["end"])
        events.append(_event(shown, hidden, "Sing", "".join(karaoke).rstrip()))
        if n + 1 < len(lines):
            events.append(_event(shown, hidden, "Next", _clean(lines[n + 1]["text"])))
    sections = analysis["sections"] if analysis else [s for s in timing["sections"] if s["start"] is not None]
    for s in sections:
        events.append(_event(s["start"], s["end"], "Label", _clean(s["name"])))
    if analysis:
        downbeats = set(analysis["downbeats"])
        for beat in analysis["beats"]:
            events.append(_event(beat, beat + 0.12, "Down" if beat in downbeats else "Beat", "●"))
    if duration:
        events += panel_events(words, duration)
    return HEADER + "\n".join(events) + "\n"


def render_wave_strip(wave_source: Path, out: Path, duration: float) -> Path:
    """The whole song's waveform as one strip, PAGE_S seconds per WIDTH pixels (the last page padded)."""
    pages = int(duration // PAGE_S) + 1
    run([need("ffmpeg"), "-y", "-nostdin", "-loglevel", "error", "-i", str(wave_source), "-filter_complex",
         f"[0:a]aformat=channel_layouts=mono,apad=whole_dur={pages * PAGE_S},atrim=0:{pages * PAGE_S},"
         f"showwavespic=s={pages * WIDTH}x{WAVE_H}:colors=0x4fa3ff:scale=sqrt:filter=peak[w]",
         "-map", "[w]", "-frames:v", "1", str(out)],
        "drawing the preview's waveform")
    return out


def render_preview(song: Path, wave_source: Path, ass: Path, out: Path, duration: float) -> Path:
    for name, hint in (("ass", "libass"), ("drawtext", "libfreetype")):
        if not has_filter(name):
            raise MVError(f"this ffmpeg has no '{name}' filter (needs {hint}); install ffmpeg from Homebrew")
    strip = render_wave_strip(wave_source, ass.parent / "preview-wave.png", duration)
    graph = (f"[1:v]crop=w={WIDTH}:h={WAVE_H}:x='{WIDTH}*floor(t/{PAGE_S})':y=0,format=rgba[wv];"
             f"[0:v][wv]overlay=0:{WAVE_TOP}[bg];"
             f"color=c=white:s=2x{HEIGHT - PANEL_TOP}:r=30[ph];"
             f"[bg][ph]overlay=x='mod(t\\,{PAGE_S})*{WIDTH / PAGE_S:g}':y={PANEL_TOP}:eval=frame:shortest=1[pl];"
             f"[pl]drawtext=text='%{{pts\\:hms}}':x=30:y=20:fontcolor=white:fontsize=26,"
             f"ass={ass.name}[v]")
    run([need("ffmpeg"), "-y", "-nostdin", "-loglevel", "error",
         "-f", "lavfi", "-i", f"color=c=0x101418:s={WIDTH}x{HEIGHT}:r=30:d={duration:.3f}",
         "-loop", "1", "-framerate", "30", "-t", f"{duration:.3f}", "-i", str(strip),
         "-i", str(song), "-filter_complex", graph, "-map", "[v]", "-map", "2:a",
         "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-crf", "23",
         "-c:a", "aac", "-b:a", "160k", "-shortest", str(out)],
        "rendering the preview", cwd=ass.parent)
    return out


def preview(ws: Workspace, spec_id: str) -> tuple[Path, bool]:
    p = video_song(ws, spec_id).paths
    if not p.timing.is_file():
        raise MVError(f"no timing for {spec_id}: run music-video align {spec_id} first")
    timing = json.loads(p.timing.read_text(encoding="utf-8"))
    analysis = json.loads(p.analysis.read_text(encoding="utf-8")) if p.analysis.is_file() else None
    duration = duration_s(p.song)
    p.preview_ass.write_text(build_ass(timing, analysis, duration), encoding="utf-8")
    wave = p.vocals if p.vocals.is_file() else p.song
    return render_preview(p.song, wave, p.preview_ass, p.preview, duration), analysis is not None
