"""music-video preview: a full-song karaoke check — word sweep, section label, beat dot, vocal waveform."""
import json
from pathlib import Path

from ..workspace import Workspace
from ..errors import MVError
from .media import duration_s, has_filter, need, run
from .paths import video_song

LEAD_S = 0.6   # a line appears this long before its first word...
TAIL_S = 0.4   # ...and stays this long after its last, never overlapping the next line
WIDTH, HEIGHT = 1280, 720

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


def build_ass(timing: dict, analysis: dict | None) -> str:
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
    return HEADER + "\n".join(events) + "\n"


def render_preview(song: Path, wave_source: Path, ass: Path, out: Path, duration: float) -> Path:
    for name, hint in (("ass", "libass"), ("drawtext", "libfreetype")):
        if not has_filter(name):
            raise MVError(f"this ffmpeg has no '{name}' filter (needs {hint}); install ffmpeg from Homebrew")
    graph = (f"[1:a]showwaves=s={WIDTH}x140:mode=cline:rate=30:colors=0x4fa3ff,format=rgba[wv];"
             f"[0:v][wv]overlay=0:{HEIGHT - 140}[bg];"
             f"[bg]drawtext=text='%{{pts\\:hms}}':x={WIDTH - 200}:y={HEIGHT - 180}:fontcolor=gray:fontsize=22,"
             f"ass={ass.name}[v]")
    run([need("ffmpeg"), "-y", "-nostdin", "-loglevel", "error",
         "-f", "lavfi", "-i", f"color=c=0x101418:s={WIDTH}x{HEIGHT}:r=30:d={duration:.3f}",
         "-i", str(wave_source), "-i", str(song), "-filter_complex", graph, "-map", "[v]", "-map", "2:a",
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
    p.preview_ass.write_text(build_ass(timing, analysis), encoding="utf-8")
    wave = p.vocals if p.vocals.is_file() else p.song
    return render_preview(p.song, wave, p.preview_ass, p.preview, duration_s(p.song)), analysis is not None
