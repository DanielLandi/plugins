"""qc's motion scans: flicker, pop, hard cut and camera jitter, measured on a small copy of every frame.

Adapted from claude-video-skills' render-checks (MIT; see THIRD_PARTY_NOTICES.md). One ffmpeg decode at 320 px on
the long side feeds all four. The thresholds are deliberately conservative: each flags only what a viewer would see
as a fault, and each has a test that makes it fail. A flagged frame is either a designed effect (declare it: a
`--hold` for a designed blink or strobe, a `--cut` for a designed hard cut) or a bug to fix.
"""
import subprocess
from dataclasses import dataclass, field

import numpy as np

from ..errors import MVError
from .media import need

SCAN_LONG = 320            # the analysis copy's long side, in pixels

# Differences are measured tolerantly: a pixel counts only by how far it lies outside the range of the other frame's
# 3x3 neighbourhood, so edges, sub-pixel motion and compression grain stay quiet. Luma, 0-255.

# Hard cut: a one-frame world switch where no cut was declared (a scene boundary from analysis.json, or --cut).
# Either the colour histograms jump (16 bins per channel, half the L1 distance: 0 the same, 1 nothing in common), or
# most of the frame changes at once; and the frames on either side are steady by comparison, so a whip (which changes
# a lot on every frame) is not a cut, and the new picture stays. Measured on five finished videos: camera cuts
# changed 27-69% of the frame or jumped 0.37-0.74, while no frame inside a shot changed more than 6%.
CUT_JUMP = 0.45
CUT_AREA = 0.2             # or this share of the frame changes by POP_DELTA or more
CUT_RATIO = 3.0            # ... and is this many times the change of the frame pairs either side
CUT_NEAR_S = 0.5           # a declared cut covers jumps this close to it (transitions are centred on the boundary)

# Pop: something appears or vanishes between two frames and stays that way. A region of at least POP_MIN_AREA of
# the frame changes by POP_DELTA or more, at least POP_RATIO times the change of the frame pairs before and after (an
# entrance animated over 6-12 frames spreads its change and passes), and at least POP_KEEP of it is still changed two
# frames later (one that changes back is a flicker). Larger than CUT_AREA is a cut. A pop within POP_WORD_S of a
# sung word's start is taken for the subtitles' word highlight (a word turning colour is a pop to this scan); an
# entrance keyed to a word is checked by stepping its frames instead (animation.md).
POP_DELTA = 40.0
POP_MIN_AREA = 0.004       # 0.4% of the frame: about 90x90 px at 1080p
POP_WORD_S = 0.07          # two frames at 30 fps
POP_RATIO = 6.0
POP_FLOOR = 0.0005         # the neighbours' change never counts as less than this
POP_KEEP = 0.5
POP_STILL = 2.0            # a frame whose whole picture shifted this far (px at 640 wide) is motion, not a pop
POP_SURE = 0.3             # ... when the shift is measured surely (a pop itself blurs the measurement)

# Flicker: a region that changes for 1-3 frames and changes back, while the frames either side agree. Per pixel:
# min over the run of min(d(frame, before), d(frame, after)) - d(before, after). A change that stays, a fade, a
# move and something uncovered all score zero. Without optical flow, motion is quieted instead: a run is tested
# only where the frames either side agree (under FLICKER_AGREE of the frame changed between them), and a pixel
# counts only where its 17x17 neighbourhood is still between them (mean d under FLICKER_STILL), so a fast occluder
# passing the lens is not a flicker. Flagged pixels need 3 flagged neighbours (no specks); an event is a flagged area
# of FLICKER_MIN_AREA or more. Above FLICKER_MAX_AREA it is a whole-frame flash (the flash check's).
FLICKER_DELTA = 30.0
FLICKER_MIN_AREA = 0.003   # 0.3%: about 80x80 px at 1080p
FLICKER_MAX_AREA = 0.5
FLICKER_AGREE = 0.2
FLICKER_STILL = 4.0
FLICKER_MOVING = 0.005     # ... and the frame pairs just before and after the event change under 0.5% of the frame
FLICKER_RUN = 3

# Camera jitter: the picture's overall shift between frames (phase correlation), in pixels of a 640-wide frame. A
# one-second window with no step over JITTER_STEP (so not a whip) whose path is JITTER_PATH or more while its net
# travel is under JITTER_NET of the path, turning back at least JITTER_TURNS times: the camera wandered and came back
# instead of moving once to a framing. (One smooth swing back is a camera move to judge by eye, shot-design.md; a
# final had one.) A video whose jolts answer is yes (video.yaml) kicks on the beat by design and is not scanned.
JITTER_UNIT = 640
JITTER_WINDOW_S = 1.0
JITTER_STEP = 12.0
JITTER_PATH = 14.0
JITTER_NET = 0.35
JITTER_TURNS = 2
JITTER_TURN_PX = 0.5        # steps smaller than this along an axis do not count as turning
JITTER_PEAK = 0.1          # a step whose correlation peak is weaker than this is unmeasured (flat or dark frame)


@dataclass
class Measures:
    """Per-frame measurements; index i compares frame i with frame i - 1 (index 0 is empty)."""
    fps: float
    size: tuple[int, int]
    jump: list[float] = field(default_factory=list)      # histogram distance
    area: list[float] = field(default_factory=list)      # share of pixels changed by POP_DELTA
    keep: list[float] = field(default_factory=list)      # share of that change still there two frames later
    flicker: list[float] = field(default_factory=list)   # flickering share, for a run starting at frame i
    shift: list[tuple[float, float, float]] = field(default_factory=list)   # dx, dy (640 px units), peak

    @property
    def count(self) -> int:
        return len(self.jump)


def scan_size(width: int, height: int) -> tuple[int, int]:
    scale = SCAN_LONG / max(width, height)
    return max(2, round(width * scale / 2) * 2), max(2, round(height * scale / 2) * 2)


def _range3(g: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    h, w = g.shape
    p = np.pad(g, 1, mode="edge")
    stack = np.stack([p[y:y + h, x:x + w] for y in range(3) for x in range(3)])
    return stack.min(axis=0), stack.max(axis=0)


class _Frame:
    def __init__(self, rgb: np.ndarray, window: np.ndarray):
        g = rgb.astype(np.float32) @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
        self.g = g
        self.lo, self.hi = _range3(g)
        self.hist = np.concatenate([np.bincount(rgb[..., c].ravel() >> 4, minlength=16) for c in range(3)]
                                   ).astype(np.float64) / rgb.size
        self.spectrum = np.fft.rfft2((g - g.mean()) * window)


def _dist(a: _Frame, b: _Frame) -> np.ndarray:
    """How far each pixel of a lies outside b's local range, and the other way round; the smaller of the two."""
    ab = np.maximum(np.maximum(a.g - b.hi, b.lo - a.g), 0)
    ba = np.maximum(np.maximum(b.g - a.hi, a.lo - b.g), 0)
    return np.minimum(ab, ba)


def _phase_shift(a: _Frame, b: _Frame, unit: float) -> tuple[float, float, float]:
    """b's shift against a: (dx, dy, peak), dx and dy scaled by unit."""
    cross = b.spectrum * np.conj(a.spectrum)
    cross /= np.abs(cross) + 1e-9
    r = np.fft.irfft2(cross, s=a.g.shape)
    h, w = r.shape
    iy, ix = np.unravel_index(int(np.argmax(r)), r.shape)
    peak = float(r[iy, ix])

    def sub(m1, c, p1):   # parabolic peak offset
        den = m1 - 2 * c + p1
        return 0.5 * (m1 - p1) / den if abs(den) > 1e-12 else 0.0

    dy = iy + sub(r[(iy - 1) % h, ix], r[iy, ix], r[(iy + 1) % h, ix])
    dx = ix + sub(r[iy, (ix - 1) % w], r[iy, ix], r[iy, (ix + 1) % w])
    dy = dy - h if dy > h / 2 else dy
    dx = dx - w if dx > w / 2 else dx
    return dx * unit, dy * unit, peak


def _box(x: np.ndarray, r: int) -> np.ndarray:
    """The mean over each pixel's (2r+1)x(2r+1) neighbourhood."""
    h, w = x.shape
    c = np.pad(x, r + 1, mode="edge").astype(np.float64).cumsum(0).cumsum(1)
    k = 2 * r + 1
    s = c[k:k + h, k:k + w] - c[:h, k:k + w] - c[k:k + h, :w] + c[:h, :w]
    return s / (k * k)


def _flicker_share(f: list, dist) -> float:
    """f = [before, i, i+1, i+2, i+3]: the flickering share of the frame for a run starting at i."""
    best = None
    for run in range(1, FLICKER_RUN + 1):
        if run + 1 >= len(f):
            break
        before, after = 0, run + 1
        apart = dist(before, after)
        if (apart >= POP_DELTA).mean() > FLICKER_AGREE:
            continue
        inside = None
        for j in range(1, run + 1):
            d = np.minimum(dist(j, before), dist(j, after))
            inside = d if inside is None else np.minimum(inside, d)
        score = np.where(_box(apart, 8) < FLICKER_STILL, inside - apart, 0.0)
        best = score if best is None else np.maximum(best, score)
    if best is None:
        return 0.0
    mask = (best >= FLICKER_DELTA).astype(np.uint8)
    p = np.pad(mask, 1)
    h, w = mask.shape
    neighbours = sum(p[y:y + h, x:x + w] for y in range(3) for x in range(3)) - mask
    return float((mask & (neighbours >= 3)).mean())


def measure(video, fps: float, width: int, height: int) -> Measures:
    w, h = scan_size(width, height)
    m = Measures(fps=fps, size=(w, h))
    window = np.outer(np.hanning(h), np.hanning(w)).astype(np.float32)
    unit = JITTER_UNIT / max(w, h)
    proc = subprocess.Popen([need("ffmpeg"), "-nostdin", "-loglevel", "error", "-i", str(video), "-map", "0:v:0", "-an",
                             "-vf", f"scale={w}:{h}:flags=area", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    frames: list[_Frame] = []       # the last 5 frames (indices count-5 .. count-1)
    pairs: dict[tuple[int, int], np.ndarray] = {}
    size = w * h * 3

    def dist(i: int, j: int) -> np.ndarray:   # absolute frame indices
        key = (min(i, j), max(i, j))
        if key not in pairs:
            first = m.count - len(frames)
            pairs[key] = _dist(frames[i - first], frames[j - first])
        return pairs[key]

    def finish_flicker(start: int) -> None:   # a run starting at `start`, its before at start-1
        first = m.count - len(frames)
        if start - 1 < first:
            return
        sel = list(range(start - 1, min(start + FLICKER_RUN + 1, m.count)))
        m.flicker[start] = _flicker_share(sel, lambda a, b: dist(sel[a], sel[b]))

    try:
        while True:
            buf = proc.stdout.read(size)
            if len(buf) < size:
                break
            cur = _Frame(np.frombuffer(buf, np.uint8).reshape(h, w, 3), window)
            i = m.count
            frames.append(cur)
            m.jump.append(0.0)
            m.area.append(0.0)
            m.keep.append(0.0)
            m.flicker.append(0.0)
            m.shift.append((0.0, 0.0, 0.0))
            if len(frames) > 5:
                frames.pop(0)
                pairs = {k: v for k, v in pairs.items() if k[0] >= i - 4}
            if i >= 1:
                prev = frames[-2]
                m.jump[i] = float(0.5 * np.abs(cur.hist - prev.hist).sum())
                m.area[i] = float((dist(i - 1, i) >= POP_DELTA).mean())
                m.shift[i] = _phase_shift(prev, cur, unit)
            if i >= 3:   # frame i-2's change, two frames on: does it stay?
                changed = dist(i - 3, i - 2) >= POP_DELTA
                n = int(changed.sum())
                m.keep[i - 2] = float((changed & (dist(i - 3, i) >= POP_DELTA)).sum() / n) if n else 0.0
            if i >= 4:
                finish_flicker(i - 3)
    finally:
        proc.stdout.close()
        err = proc.stderr.read().decode(errors="replace")
        code = proc.wait()
    if code:
        raise MVError(f"motion scan failed: {err.strip()[-400:]}")
    for start in range(max(1, m.count - 3), m.count - 1):   # the last runs, as far as the frames go
        finish_flicker(start)
    return m


def _spans(frames: list[int], fps: float, gap: int = 2) -> list[tuple[int, int]]:
    """Consecutive (or nearly) flagged frames as [first, last] spans."""
    out: list[list[int]] = []
    for f in sorted(frames):
        if out and f - out[-1][1] <= gap + 1:
            out[-1][1] = f
        else:
            out.append([f, f])
    return [(a, b) for a, b in out]


def _near(t: float, cuts, tol: float = CUT_NEAR_S) -> bool:
    return any(abs(t - c) <= tol for c in cuts)


def _inside(a: float, b: float, spans) -> bool:
    return any(s0 - 0.05 <= a and b <= s1 + 0.05 for s0, s1 in spans)


def _touches(a: float, b: float, spans, pad: float) -> bool:
    return any(a <= s1 + pad and b >= s0 - pad for s0, s1 in spans)


@dataclass
class Exempt:
    """What the scans accept. Times are the video's own (excerpt time for a clip)."""
    total: float
    edge: float
    holds: list = field(default_factory=list)     # designed holds: [start, end]
    cuts: list = field(default_factory=list)      # declared cuts: scene boundaries, video.yaml cuts and --cut
    words: list = field(default_factory=list)     # sung word starts (the subtitles' highlight)
    reported: list = field(default_factory=list)  # black and flash spans, already failed by their own checks

    def ok(self, a: float, b: float, near_cut: bool = True) -> bool:
        return (a < self.edge or b > self.total - self.edge or _inside(a, b, self.holds)
                or _touches(a, b, self.reported, 2.5 / 30) or (near_cut and (_near(a, self.cuts) or _near(b, self.cuts))))


def find_cuts(m: Measures, ex: Exempt) -> list[float]:
    out = []
    for i in range(2, m.count - 2):
        side_jump = max(m.jump[i - 1], m.jump[i + 1])
        side_area = max(m.area[i - 1], m.area[i + 1])
        by_hist = m.jump[i] >= CUT_JUMP and m.jump[i] >= CUT_RATIO * side_jump
        by_area = m.area[i] >= CUT_AREA and m.area[i] >= CUT_RATIO * side_area
        if (by_hist or by_area) and m.keep[i] >= POP_KEEP:
            t = i / m.fps
            if not ex.ok(t - 1 / m.fps, t):
                out.append(t)
    return out


def find_pops(m: Measures, ex: Exempt) -> list[tuple[float, float]]:
    out = []
    for i in range(2, m.count - 2):
        a = m.area[i]
        if not POP_MIN_AREA <= a < CUT_AREA or m.keep[i] < POP_KEEP:
            continue
        if a < POP_RATIO * max(m.area[i - 1], m.area[i + 1], POP_FLOOR):
            continue
        dx, dy, peak = m.shift[i]
        if peak >= POP_SURE and np.hypot(dx, dy) >= POP_STILL:   # the whole picture moved: not a pop
            continue
        t = i / m.fps
        if not ex.ok(t - 1 / m.fps, t) and not _near(t, ex.words, POP_WORD_S):
            out.append((t, a))
    return out


def find_flicker(m: Measures, ex: Exempt) -> list[tuple[float, float, float]]:
    flagged = [i for i, s in enumerate(m.flicker) if FLICKER_MIN_AREA <= s <= FLICKER_MAX_AREA]
    out = []
    for a, b in _spans(flagged, m.fps):
        # the picture just before and just after the event is still: a moving picture is not scanned
        if max(m.area[max(a - 1, 0)], m.area[min(b + 2, m.count - 1)]) > FLICKER_MOVING:
            continue
        t0, t1 = a / m.fps, (b + 1) / m.fps
        if not ex.ok(t0, t1, near_cut=False):
            out.append((t0, t1, max(m.flicker[a:b + 1])))
    return out


def _turns(steps) -> int:
    """How many times the motion reverses, along the axis that reverses most."""
    best = 0
    for axis in (0, 1):
        signs = [1 if s[axis] > 0 else -1 for s in steps if abs(s[axis]) >= JITTER_TURN_PX]
        best = max(best, sum(1 for a, b in zip(signs, signs[1:]) if a != b))
    return best


def find_jitter(m: Measures, ex: Exempt) -> list[tuple[float, float, float, float]]:
    n = max(2, round(JITTER_WINDOW_S * m.fps))
    hits = []
    for start in range(1, m.count - n + 1, max(1, n // 2)):
        steps = [(dx, dy) if peak >= JITTER_PEAK else (0.0, 0.0) for dx, dy, peak in m.shift[start:start + n]]
        lengths = [float(np.hypot(dx, dy)) for dx, dy in steps]
        if not lengths or max(lengths) > JITTER_STEP:
            continue
        path = sum(lengths)
        net = float(np.hypot(sum(s[0] for s in steps), sum(s[1] for s in steps)))
        if path >= JITTER_PATH and net < JITTER_NET * path and _turns(steps) >= JITTER_TURNS:
            t0, t1 = (start - 1) / m.fps, (start + n) / m.fps
            if not ex.ok(t0, t1) and not _touches(t0, t1, ex.holds, 0.0):
                hits.append((t0, t1, path, net))
    merged: list[list[float]] = []
    for t0, t1, path, net in hits:
        if merged and t0 <= merged[-1][1]:
            merged[-1][1] = t1
            merged[-1][2] = max(merged[-1][2], path)
        else:
            merged.append([t0, t1, path, net])
    return [tuple(x) for x in merged]
