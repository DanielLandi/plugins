"""music-video analyze, the drums: kick, snare, hat and crash hits measured on the song's audio.

After claude-video-skills' song-timing (MIT; see THIRD_PARTY_NOTICES.md): onset candidates by spectral flux, each
classified by the band it rises in and how long it rings. The ideal input is a drum stem; `align` separates only the
vocals (demucs, two stems), so the drums are measured on the mix with the vocal stem's spectrum taken off it (or on
the plain mix when there is no vocal stem: an instrumental, or before align). The analysis says which.

The hits are data for scenes, never motion of their own: a scene keys a jolt to them only when the video's jolts
answer is yes (kit `useJolt`).
"""
import numpy as np

SR = 44100
N_FFT = 2048
HOP = 441                  # 10 ms
RATE = SR / HOP            # analysis frames per second
CHUNK = 2048               # frames per FFT batch (memory)
BANDS = {"kick": (30.0, 110.0), "snare": (1200.0, 5000.0), "high": (7000.0, 16000.0)}
RISE_FRAMES = 3            # flux: the rise over the last 30 ms
PEAK_HALF = 5              # a peak is the largest within ±50 ms
THRESHOLD = 0.25           # a candidate's flux, as a share of the band's own 99th-percentile flux
LOCAL_S = 1.0              # ... and above 1.5x the median flux of the second around it
TAIL_LEVEL = 0.3           # a hit rings while its band stays above this share of its peak
SNARE_TAIL = 3             # frames (30 ms): a snare or clap rings; a kick's click and a consonant do not
CRASH_TAIL = 15            # frames (150 ms): a crash rings, a hat does not
SAME_S = 0.05              # two hits of one kind closer than this are one


def _spectra(x: np.ndarray, start: int, stop: int) -> np.ndarray:
    window = np.hanning(N_FFT).astype(np.float32)
    idx = np.arange(start, stop)[:, None] * HOP + np.arange(N_FFT)[None, :]
    frames = x[idx] * window
    return np.abs(np.fft.rfft(frames, axis=1)).astype(np.float32)


def band_energies(mix: np.ndarray, vocals: np.ndarray | None = None) -> dict[str, np.ndarray]:
    """Energy per band per 10 ms frame, with the vocal stem's magnitude spectrum subtracted when given."""
    pad = N_FFT // 2
    x = np.pad(mix.astype(np.float32), (pad, pad + N_FFT))
    v = None
    if vocals is not None:
        v = np.zeros_like(x)
        n = min(len(vocals), len(mix))
        v[pad:pad + n] = vocals[:n]
    frames = max(0, (len(mix) + HOP - 1) // HOP)
    freqs = np.fft.rfftfreq(N_FFT, 1.0 / SR)
    masks = {k: (freqs >= lo) & (freqs < hi) for k, (lo, hi) in BANDS.items()}
    out = {k: np.zeros(frames, dtype=np.float64) for k in BANDS}
    for start in range(0, frames, CHUNK):
        stop = min(frames, start + CHUNK)
        mag = _spectra(x, start, stop)
        if v is not None:
            mag = np.maximum(mag - _spectra(v, start, stop), 0.0)
        power = mag.astype(np.float64) ** 2
        for k, mask in masks.items():
            out[k][start:stop] = power[:, mask].sum(axis=1)
    return out


def _onsets(e: np.ndarray) -> list[tuple[int, float]]:
    """(frame, strength 0-1) of the rises in one band's energy."""
    if not len(e) or e.max() <= 0:
        return []
    x = np.log1p(100.0 * e / (np.percentile(e, 99) + 1e-12))
    prev = np.full_like(x, np.inf)
    for k in range(1, RISE_FRAMES + 1):
        prev[k:] = np.minimum(prev[k:], x[:-k])
    flux = np.maximum(x - np.where(np.isinf(prev), x, prev), 0.0)
    ref = float(np.percentile(flux, 99))
    if ref <= 0:
        return []
    half = int(LOCAL_S * RATE / 2)
    found = []
    for t in np.flatnonzero(flux >= THRESHOLD * ref):
        lo, hi = max(0, t - PEAK_HALF), min(len(flux), t + PEAK_HALF + 1)
        if flux[t] < flux[lo:hi].max() or (t > lo and flux[t] == flux[t - 1]):
            continue
        if flux[t] < 1.5 * float(np.median(flux[max(0, t - half):t + half + 1])):
            continue
        found.append((int(t), min(1.0, float(flux[t] / ref))))
    return found


def _tail(e: np.ndarray, t: int) -> int:
    """Frames the band stays above TAIL_LEVEL of its peak (the peak within 30 ms of the onset), on the energy
    smoothed over 30 ms (what is left after taking the vocals off is choppy)."""
    e = np.convolve(e, np.ones(3) / 3, mode="same")
    end = min(len(e), t + RISE_FRAMES + 1)
    peak_at = t + int(np.argmax(e[t:end]))
    level = TAIL_LEVEL * e[peak_at]
    n = 0
    while peak_at + n + 1 < len(e) and e[peak_at + n + 1] >= level:
        n += 1
    return n


def find_hits(mix: np.ndarray, vocals: np.ndarray | None = None) -> list[dict]:
    """Every drum hit: {"t": seconds, "kind": kick | snare | hat | crash, "strength": 0-1}, in time order."""
    bands = band_energies(mix, vocals)
    hits = []
    for t, s in _onsets(bands["kick"]):
        hits.append((t, "kick", s))
    for t, s in _onsets(bands["snare"]):
        if _tail(bands["snare"], t) >= SNARE_TAIL:
            hits.append((t, "snare", s))
    for t, s in _onsets(bands["high"]):
        hits.append((t, "crash" if _tail(bands["high"], t) >= CRASH_TAIL else "hat", s))
    hits.sort()
    out: list[dict] = []
    last: dict[str, float] = {}
    for t, kind, s in hits:
        sec = t / RATE
        if sec - last.get(kind, -1.0) < SAME_S:
            continue
        last[kind] = sec
        out.append({"t": round(sec, 3), "kind": kind, "strength": round(s, 3)})
    return out


def grid_fit(beats: list[float], hits: list[dict]) -> float | None:
    """How far the beat grid sits from the kicks and snares, in beats (mean over beats with a hit within half a
    beat). Under ~0.1 the grid is on the drums; a grid half a beat off lands every accent on the "and"."""
    drums = np.array([h["t"] for h in hits if h["kind"] in ("kick", "snare")])
    if len(beats) < 2 or not len(drums):
        return None
    period = float(np.median(np.diff(beats)))
    offsets = []
    for b in beats:
        d = float(np.min(np.abs(drums - b)))
        if d <= period / 2:
            offsets.append(d / period)
    return round(float(np.mean(offsets)), 3) if offsets else None
