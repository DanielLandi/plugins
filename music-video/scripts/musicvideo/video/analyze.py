"""music-video analyze: the song map scenes are timed to (tempo, beats, sections, energy, hits)."""
import json

import numpy as np

from ..workspace import Workspace
from ..errors import MVError
from ..spec import slugify
from .align import Runner, run_worker
from .media import decode_mono, duration_s
from .paths import video_song

FPS = 30
SR = 22050
WINDOW = 2048
BANDS = {"low": (20.0, 250.0), "mid": (250.0, 4000.0), "high": (4000.0, 11025.0)}
GAP_MIN_S = 2.0        # a silence between sung sections shorter than this joins the previous section
HIT_COUNT = 12
HIT_GAP_S = 4.0
HIT_BEFORE_S = 0.5     # a hit is a jump from the last 0.5 s to the next 0.2 s
HIT_AFTER_S = 0.2


def _unit(x: np.ndarray) -> list[float]:
    ref = float(np.percentile(x, 99)) if len(x) else 0.0
    y = np.clip(x / ref, 0.0, 1.0) if ref > 0 else np.zeros_like(x)
    return [round(float(v), 3) for v in y]


def energy_curves(samples: np.ndarray, sr: int = SR, fps: int = FPS) -> dict[str, list[float]]:
    hop = sr / fps
    n = int(np.ceil(len(samples) / hop))
    padded = np.pad(samples.astype(np.float64), (WINDOW // 2, WINDOW // 2 + int(np.ceil(hop))))
    window = np.hanning(WINDOW)
    freqs = np.fft.rfftfreq(WINDOW, 1.0 / sr)
    masks = {k: (freqs >= lo) & (freqs < hi) for k, (lo, hi) in BANDS.items()}
    rms = np.zeros(n)
    bands = {k: np.zeros(n) for k in BANDS}
    for i in range(n):
        c = int(round(i * hop))
        seg = padded[c:c + WINDOW]
        rms[i] = np.sqrt(np.mean(seg ** 2))
        spectrum = np.abs(np.fft.rfft(seg * window))
        for k, mask in masks.items():
            bands[k][i] = spectrum[mask].mean()
    return {"rms": _unit(rms), **{k: _unit(v) for k, v in bands.items()}}


def pick_hits(curves: dict, fps: int = FPS, count: int = HIT_COUNT, min_gap_s: float = HIT_GAP_S) -> list[dict]:
    e = np.asarray(curves["rms"]) + np.asarray(curves["low"])
    n = len(e)
    before, after = int(HIT_BEFORE_S * fps), max(int(HIT_AFTER_S * fps), 1)
    c = np.concatenate([[0.0], np.cumsum(e)])
    jump = np.zeros(n)
    for i in range(before, n - after):
        jump[i] = (c[i + after] - c[i]) / after - (c[i] - c[i - before]) / before
    picked: list[int] = []
    for i in np.argsort(-jump, kind="stable"):
        if jump[i] <= 0 or len(picked) >= count:
            break
        if all(abs(int(i) - j) >= min_gap_s * fps for j in picked):
            picked.append(int(i))
    top = jump[picked[0]] if picked else 1.0
    return [{"t": round(i / fps, 3), "strength": round(float(jump[i] / top), 3)} for i in sorted(picked)]


def build_sections(timing: dict, duration: float) -> list[dict]:
    out: list[dict] = []
    pending: list[str] = []
    prev_end = 0.0
    for s in timing.get("sections", []):
        if s["start"] is None:
            pending.append(s["name"])
            continue
        if s["start"] - prev_end >= GAP_MIN_S:
            name = pending[-1] if pending else ("Intro" if not out else "Instrumental")
            out.append({"name": name, "start": prev_end, "sung": False})
        pending = []
        out.append({"name": s["name"], "start": s["start"], "sung": True})
        prev_end = s["end"]
    if not out:
        out.append({"name": "Instrumental", "start": 0.0, "sung": False})
    elif duration - prev_end >= GAP_MIN_S:
        out.append({"name": pending[-1] if pending else "Outro", "start": prev_end, "sung": False})
    out[0]["start"] = 0.0
    seen: dict[str, int] = {}
    result = []
    for k, s in enumerate(out):
        end = out[k + 1]["start"] if k + 1 < len(out) else duration
        base = slugify(s["name"]) or "section"
        seen[base] = seen.get(base, 0) + 1
        result.append({"id": base if seen[base] == 1 else f"{base}-{seen[base]}", "name": s["name"],
                       "start": round(s["start"], 3), "end": round(end, 3), "sung": s["sung"]})
    return result


def tempo(beats: list[float]) -> float:
    if len(beats) < 2:
        return 0.0
    return round(60.0 / float(np.median(np.diff(beats))), 1)


def analyze(ws: Workspace, spec_id: str, runner: Runner | None = None) -> dict:
    runner = runner or run_worker
    song = video_song(ws, spec_id)
    p = song.paths
    instrumental = bool(song.spec["suno"].get("instrumental"))
    if not instrumental and not p.timing.is_file():
        raise MVError(f"no timing for {spec_id}: run music-video align {spec_id} first")
    runner(["beats", str(p.song), str(p.beats)])
    grid = json.loads(p.beats.read_text(encoding="utf-8"))
    duration = duration_s(p.song)
    curves = energy_curves(decode_mono(p.song, SR))
    timing = json.loads(p.timing.read_text(encoding="utf-8")) if p.timing.is_file() else {}
    data = {"version": 1, "duration": round(duration, 3), "fps": FPS, "tempo": tempo(grid["beats"]),
            "beats": grid["beats"], "downbeats": grid["downbeats"],
            "sections": build_sections(timing, duration), "energy": curves, "hits": pick_hits(curves)}
    p.analysis.write_text(json.dumps(data), encoding="utf-8")
    return data
