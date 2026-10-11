"""music-video align: word timings for a filed song."""
import json
import os
import subprocess
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import yaml

from ..spec import is_instrumental, lyrics as spec_lyrics
from ..workspace import Workspace, install_dir
from ..errors import MVError
from .lyrics import Lyrics, parse_lyrics
from .media import decode_mono, duration_s, rms_envelope
from .paths import VideoSong, video_song
from .subtitles import to_lrc, to_srt, to_vtt
from .timing import (VOICE_FRAME_S, apply_fixes, build_timing, show_words, line_ends, match_heard, missing_lines,
                     reconcile, snap_to_voice, suspects, words_from_json)

WORKER = Path(__file__).with_name("worker.py")
ENVELOPE_SR = 16000
Runner = Callable[[list[str]], None]


def worker_env() -> dict[str, str]:
    """The worker's Python environment and its model weights live in the install folder, not scattered caches."""
    base = install_dir()
    return {**os.environ, "UV_CACHE_DIR": str(base / "uv"), "TORCH_HOME": str(base / "models" / "torch"),
            "HF_HOME": str(base / "models" / "huggingface")}


def run_worker(args: list[str]) -> None:
    if subprocess.run(["uv", "run", "--script", str(WORKER), *args], env=worker_env()).returncode:
        raise MVError(f"the ML worker failed during '{args[0]}'; its output is above")


@dataclass
class AlignResult:
    timing_path: Path
    timing: dict
    lyrics_source: str
    suspects: list[dict]
    missing: list[dict]
    counts: dict[str, int]


def _lyrics(song: VideoSong) -> tuple[Lyrics, str]:
    if song.paths.as_sung.is_file():
        return parse_lyrics(song.paths.as_sung.read_text(encoding="utf-8")), "as sung"
    return parse_lyrics(spec_lyrics(song.spec)), "spec"


def align(ws: Workspace, spec_id: str, lang: str = "en", force: bool = False,
          runner: Runner | None = None) -> AlignResult:
    runner = runner or run_worker
    song = video_song(ws, spec_id)
    if is_instrumental(song.spec):
        raise MVError(f"{spec_id} is instrumental: there are no words to time")
    lyrics, source = _lyrics(song)
    if not lyrics.lines:
        raise MVError(f"{spec_id} has no lyric lines to align")
    p = song.paths
    stat = p.song.stat()
    key = {"song_size": stat.st_size, "song_mtime": stat.st_mtime_ns, "lang": lang}
    key_file = p.root / "align-cache.json"
    try:
        stored = json.loads(key_file.read_text(encoding="utf-8")) if key_file.is_file() else None
    except ValueError:
        stored = None
    if force or stored != key:  # a new take or another language makes the cached vocals/transcript stale
        for cached in (p.vocals, p.transcript, p.aligned):
            cached.unlink(missing_ok=True)
    key_file.write_text(json.dumps(key), encoding="utf-8")
    p.align_input.write_text(lyrics.alignment_text(), encoding="utf-8")
    runner(["timing", str(p.song), str(p.align_input), lang, str(p.root)])

    aligned = words_from_json(json.loads(p.aligned.read_text(encoding="utf-8"))["words"])
    heard = words_from_json(json.loads(p.transcript.read_text(encoding="utf-8"))["words"])
    if len(aligned) != len(lyrics.words):
        raise MVError(f"the aligner returned {len(aligned)} words for {len(lyrics.words)} lyric words")
    ends = line_ends(lyrics)
    words = reconcile(aligned, heard, ends)
    envelope = rms_envelope(decode_mono(p.vocals, ENVELOPE_SR), ENVELOPE_SR, VOICE_FRAME_S)
    words = snap_to_voice(words, envelope)
    fixes = yaml.safe_load(p.fixes.read_text(encoding="utf-8")) if p.fixes.is_file() else None
    words = apply_fixes(words, fixes or [])

    timing = show_words(build_timing(words, lyrics, duration_s(p.song)), fixes or [])
    p.timing.write_text(json.dumps(timing, indent=1, ensure_ascii=False), encoding="utf-8")
    title, artist = song.spec["title"], ws.artist
    p.subtitle("lrc").write_text(to_lrc(timing, title, artist), encoding="utf-8")
    p.subtitle("srt").write_text(to_srt(timing), encoding="utf-8")
    p.subtitle("vtt").write_text(to_vtt(timing), encoding="utf-8")
    return AlignResult(
        timing_path=p.timing,
        timing=timing,
        lyrics_source=source,
        suspects=[timing["words"][i] for i in suspects(words, ends)],
        missing=[{"i": i, "text": lyrics.lines[i].text}
                 for i in missing_lines(aligned, lyrics, match_heard(aligned, heard))],
        counts=dict(Counter(w.source for w in words)),
    )
