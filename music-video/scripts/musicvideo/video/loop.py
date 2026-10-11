"""music-video loop: an endless version of a filed song, for a web page that plays it forever.

The loop runs from the song's first downbeat (or first sound) to a downbeat before its ending. The 4 s after the
loop end are crossfaded (equal power) under its opening, and the file carries a 1 s margin that repeats the
opening, so a player that loops any one-loop window starting inside the margin hears no seam
(the web page's sound.ts loops from half a margin in, which also clears any AAC priming a browser keeps).
"""
import json
import tempfile
from pathlib import Path

import numpy as np

from ..errors import MVError
from .media import need, rms_envelope, run

RATE = 44100
XFADE_S = 4.0
MARGIN_S = 1.0
TAIL_GUARD_S = 12.0    # the loop ends at least this long before the file does
ENV_FRAME_S = 0.5
FALL = 0.5             # the ending starts where the level drops under half the body's median for good
SILENCE = 1e-3         # leading samples quieter than this (about -60 dBFS) are not the song yet
MIN_LOOP_S = 30.0
PREVIEW_S = 10.0
MIN_DOWNBEATS = 8      # fewer than this and the beat grid is not trusted


def decode_stereo(path: Path, sr: int = RATE) -> np.ndarray:
    cmd = [need("ffmpeg"), "-nostdin", "-loglevel", "error", "-i", str(path), "-map", "0:a:0", "-ac", "2",
           "-ar", str(sr), "-f", "f32le", "-"]
    return np.frombuffer(run(cmd, f"decoding {Path(path).name}").stdout, dtype=np.float32).reshape(-1, 2)


def beat_grid(audio: np.ndarray, sr: int, downbeats: list[float] | None) -> tuple[float, list[float]]:
    """The first sound in seconds, and the downbeats from it on: empty when there are too few to trust."""
    loud = np.flatnonzero(np.abs(audio).max(axis=1) > SILENCE)
    if not len(loud):
        raise MVError("the song is silent")
    first = loud[0] / sr
    beats = sorted(b for b in (downbeats or []) if b >= first)
    return first, beats if len(beats) >= MIN_DOWNBEATS else []


def loop_points(audio: np.ndarray, sr: int, downbeats: list[float] | None = None,
                end: float | None = None) -> tuple[float, float]:
    """Loop start and end in seconds."""
    first, beats = beat_grid(audio, sr, downbeats)
    length = len(audio) / sr
    grid = bool(beats)
    start = beats[0] if grid else first
    if end is None:
        env = rms_envelope(audio.mean(axis=1), sr, ENV_FRAME_S)
        lo, hi = int(start / ENV_FRAME_S), int((length - TAIL_GUARD_S) / ENV_FRAME_S)
        body = float(np.median(env[lo:hi])) if hi > lo else float(np.median(env))
        loud_frames = np.flatnonzero(env >= FALL * body)
        fall = (loud_frames[-1] + 1) * ENV_FRAME_S if len(loud_frames) else length
        limit = min(fall - XFADE_S, length - TAIL_GUARD_S)
        candidates = [b for b in beats if b <= limit] if grid else []
        end = candidates[-1] if candidates else limit
    if end - start < MIN_LOOP_S:
        raise MVError(f"the song is too short to loop: {end - start:.1f} s between {start:.1f} and {end:.1f} s")
    return start, end


def build_loop(audio: np.ndarray, sr: int, start: float, end: float) -> tuple[np.ndarray, int, int]:
    """The loop file's samples, the loop length and the margin, both in samples."""
    x = audio[int(round(start * sr)):].astype(np.float64)
    n = int(round((end - start) * sr))
    fade = int(round(XFADE_S * sr))
    margin = int(round(MARGIN_S * sr))
    if n + fade > len(x):
        raise MVError(f"a loop ending at {end:.1f} s leaves no room for the {XFADE_S:.0f} s crossfade")
    k = (np.arange(fade) / fade)[:, None]
    loop = x[:n].copy()
    loop[:fade] = x[:fade] * np.sin(k * np.pi / 2) + x[n:n + fade] * np.cos(k * np.pi / 2)
    out = np.clip(np.concatenate([loop, loop[:margin]]), -1.0, 1.0)
    return out.astype(np.float32), n, margin


def encode(samples: np.ndarray, sr: int, out: Path) -> Path:
    # The raw samples go through a file in a temporary folder, closed before ffmpeg opens it (on Windows an open
    # temporary file cannot be read by another process).
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / "samples.f32"
        raw.write_bytes(np.ascontiguousarray(samples, dtype=np.float32).tobytes())
        run([need("ffmpeg"), "-y", "-nostdin", "-loglevel", "error", "-f", "f32le", "-ar", str(sr), "-ac", "2",
             "-i", str(raw), "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out)],
            f"encoding {out.name}")
    return out


def make_loop(src: Path, out_dir: Path, downbeats: list[float] | None = None, end: float | None = None) -> dict:
    audio = decode_stereo(src)
    start, stop = loop_points(audio, RATE, downbeats, end)
    samples, n, margin = build_loop(audio, RATE, start, stop)
    out_dir.mkdir(parents=True, exist_ok=True)
    encode(samples, RATE, out_dir / "loop.m4a")
    p = int(PREVIEW_S * RATE)
    encode(np.concatenate([samples[n - p:n], samples[:p]]), RATE, out_dir / "seam-preview.m4a")
    meta = {"loopSamples": n, "marginSamples": margin, "rate": RATE,
            "start_s": round(start, 3), "end_s": round(stop, 3), "source": Path(src).name,
            "onDownbeats": bool(beat_grid(audio, RATE, downbeats)[1]),
            # samples at full scale: the crossfade's sum went over and was clipped
            "clipped": int(np.count_nonzero(np.abs(samples) >= 1.0))}
    (out_dir / "loop.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return meta
