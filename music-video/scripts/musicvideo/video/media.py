"""ffmpeg and ffprobe helpers for the video commands."""
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np

from ..errors import MVError


def need(tool: str) -> str:
    path = shutil.which(tool)
    if not path:
        raise MVError(f"{tool} is not installed (brew install ffmpeg)")
    return path


def run(cmd: list[str], what: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    proc = subprocess.run(cmd, capture_output=True, cwd=cwd)
    if proc.returncode:
        raise MVError(f"{what} failed: {proc.stderr.decode(errors='replace').strip()[-400:]}")
    return proc


def probe(path: Path) -> dict:
    out = run([need("ffprobe"), "-v", "error", "-print_format", "json", "-show_format", "-show_streams",
               str(path)], f"ffprobe {Path(path).name}")
    return json.loads(out.stdout)


def duration_s(path: Path) -> float:
    return float(probe(path)["format"]["duration"])


def audio_duration_s(path: Path) -> float:
    """The first audio stream's own duration (a container can be longer than its audio)."""
    info = probe(path)
    stream = next((st for st in info["streams"] if st.get("codec_type") == "audio"), None)
    if stream is None:
        raise MVError(f"{Path(path).name} has no audio stream")
    return float(stream.get("duration") or info["format"]["duration"])


def decode_mono(path: Path, sr: int = 16000, start: float | None = None,
                duration: float | None = None) -> np.ndarray:
    cmd = [need("ffmpeg"), "-nostdin", "-loglevel", "error"]
    if start is not None:
        cmd += ["-ss", f"{start:.3f}"]
    if duration is not None:
        cmd += ["-t", f"{duration:.3f}"]
    cmd += ["-i", str(path), "-map", "0:a:0", "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"]
    return np.frombuffer(run(cmd, f"decoding {Path(path).name}").stdout, dtype=np.float32)


def rms_envelope(samples: np.ndarray, sr: int, frame_s: float) -> np.ndarray:
    hop = max(int(round(sr * frame_s)), 1)
    n = len(samples) // hop
    frames = samples[: n * hop].astype(np.float64).reshape(n, hop)
    return np.sqrt((frames ** 2).mean(axis=1))


def has_filter(name: str) -> bool:
    out = run([need("ffmpeg"), "-hide_banner", "-filters"], "listing ffmpeg filters").stdout.decode()
    return any(line.split()[1:2] == [name] for line in out.splitlines() if len(line.split()) > 1)


def audio_md5(path: Path) -> str:
    """MD5 of the first audio stream's packets, so a stream copied into an MP4 matches its source MP3."""
    out = run([need("ffmpeg"), "-nostdin", "-loglevel", "error", "-i", str(path), "-map", "0:a:0", "-c", "copy",
               "-f", "md5", "-"], f"hashing the audio of {Path(path).name}")
    return out.stdout.decode().strip().removeprefix("MD5=")
