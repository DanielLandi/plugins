"""music-video qc: the automatic half of checking a render before the user sees it.

The other half is looking at the frame sheet it writes: every frame must make visual sense.
"""
import json
import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from .media import audio_duration_s, decode_mono, duration_s, need, probe, run

EDGE_S = 0.6           # a fade from or to black at the very start or end is fine
BLACK_MIN_S = 0.09     # 3 frames at 30 fps: a short black burst (a broken transition) must fail
FREEZE_MIN_S = 2.0
SYNC_SR = 8000
SYNC_WINDOW_S = 10.0
SYNC_MIN_PEAK = 0.5    # normalised correlation peak below this: the excerpt is not the song
SYNC_MIN_RMS = 1e-4    # below this the decoded track is silence
SHEET_TILES = 240
SHEET_COLS = 12
PAGE_COLS, PAGE_ROWS, PAGE_WIDTH = 4, 5, 480   # paged sheets: readable lyrics, one frame per second
PAGE_MIN_S = 20.0                              # shorter videos are covered by the overview alone
# True black only: the template's #101418 background must not read as black, and a small element
# blinking over a still background must not read as frozen (0.001 still flagged a 40 px dot on 1280x720).
BLACK_PIX_TH = 0.03
FREEZE_NOISE = 0.0005


@dataclass
class Check:
    id: str
    ok: bool
    detail: str


def _covered(a: float, b: float, holds) -> bool:
    return any(h0 - 0.05 <= a and b <= h1 + 0.05 for h0, h1 in holds)


def _spans(log: str, start_key: str, end_key: str, total: float) -> list[tuple[float, float]]:
    starts = [float(x) for x in re.findall(rf"{start_key}[:=]\s*([0-9.]+)", log)]
    ends = [float(x) for x in re.findall(rf"{end_key}[:=]\s*([0-9.]+)", log)]
    return [(s, ends[i] if i < len(ends) else total) for i, s in enumerate(starts)]


def check_format(info: dict, size, fps: float, expected_s: float) -> list[Check]:
    video = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    audio = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    if video is None:
        return [Check("format", False, "no video stream")]
    w, h = int(video["width"]), int(video["height"])
    num, den = (int(x) for x in video["avg_frame_rate"].split("/"))
    rate = num / den if den else 0.0
    problems = []
    if size and (w, h) != tuple(size):
        problems.append(f"size {w}x{h}, expected {size[0]}x{size[1]}")
    if abs(rate - fps) > 0.01:
        problems.append(f"{rate:.3f} fps, expected {fps:g}")
    if video.get("codec_name") != "h264":
        problems.append(f"video codec {video.get('codec_name')}, expected h264")
    if audio is None:
        problems.append("no audio stream")
    detail = "; ".join(problems) or f"{w}x{h} {rate:g} fps h264 + {audio['codec_name']}"
    if video.get("duration") not in (None, "N/A"):
        duration = float(video["duration"])
    elif den and video.get("nb_frames"):
        duration = int(video["nb_frames"]) * den / num
    else:
        duration = float(info["format"]["duration"])
    return [Check("format", not problems, detail),
            Check("duration", abs(duration - expected_s) <= 1.0 / fps + 0.03,
                  f"video {duration:.3f} s, expected {expected_s:.3f} s")]


def detect_black(video: Path, total: float, holds) -> Check:
    log = run([need("ffmpeg"), "-nostdin", "-i", str(video), "-an", "-vf",
               f"blackdetect=d={BLACK_MIN_S}:pix_th={BLACK_PIX_TH}", "-f", "null", "-"], "black-frame scan").stderr.decode()
    bad = [(a, b) for a, b in _spans(log, "black_start", "black_end", total)
           if not (b <= EDGE_S + BLACK_MIN_S or a >= total - EDGE_S - BLACK_MIN_S or _covered(a, b, holds))]
    return Check("black", not bad,
                 ", ".join(f"{a:.1f}–{b:.1f} s" for a, b in bad) or "none outside the edges and declared holds")


def detect_frozen(video: Path, total: float, holds) -> Check:
    log = run([need("ffmpeg"), "-nostdin", "-i", str(video), "-map", "0:v:0", "-vf",
               f"freezedetect=n={FREEZE_NOISE}:d={FREEZE_MIN_S}", "-f", "null", "-"], "frozen-frame scan").stderr.decode()
    bad = [(a, b) for a, b in _spans(log, "freeze_start", "freeze_end", total) if not _covered(a, b, holds)]
    return Check("frozen", not bad,
                 ", ".join(f"{a:.1f}–{b:.1f} s" for a, b in bad) or "none outside declared holds")


def check_audio(video: Path, song: Path, excerpt, fps: float) -> Check:
    if excerpt is None:
        # The full song is AAC (mux): check it is the song, in sync, and not cut short, rather than bit for bit.
        song_s, video_s = duration_s(song), audio_duration_s(video)
        if abs(video_s - song_s) > 1.0 / fps + 0.05:
            return Check("audio", False, f"audio is {video_s:.3f} s, the song is {song_s:.3f} s")
        check = _sync(video, song, 0.0, song_s, fps)
        return Check("audio", check.ok, check.detail.replace("excerpt offset", "offset"))
    return _sync(video, song, excerpt[0], excerpt[1], fps)


def _sync(video: Path, song: Path, start: float, end: float, fps: float) -> Check:
    span = min(end - start, SYNC_WINDOW_S)
    v = decode_mono(video, SYNC_SR, start=0.0, duration=span)
    s = decode_mono(song, SYNC_SR, start=start, duration=span)
    n = min(len(v), len(s))
    if n < SYNC_SR // 2:
        return Check("audio", False, "excerpt audio too short to compare")
    v = v[:n] - v[:n].mean()
    s = s[:n] - s[:n].mean()
    if float(np.sqrt((v ** 2).mean())) < SYNC_MIN_RMS or float(np.sqrt((s ** 2).mean())) < SYNC_MIN_RMS:
        return Check("audio", False, "no audio signal in the excerpt")
    size = 1 << int(np.ceil(np.log2(2 * n)))
    corr = np.fft.irfft(np.fft.rfft(v, size) * np.conj(np.fft.rfft(s, size)), size)
    peak = float(corr.max() / (np.linalg.norm(v) * np.linalg.norm(s) + 1e-12))
    if peak < SYNC_MIN_PEAK:
        return Check("audio", False, f"excerpt audio does not match the song (peak {peak:.2f})")
    lag = int(np.argmax(corr))
    lag = lag - size if lag > size // 2 else lag
    offset = lag / SYNC_SR
    return Check("audio", abs(offset) <= 1.0 / fps,
                 f"excerpt offset {offset * 1000:+.0f} ms (peak {peak:.2f}) against the song at {start:.3f}–{end:.3f} s")


def _clip_holds(holds, excerpt, length: float) -> list[tuple[float, float]]:
    """Holds are song time; the video being checked is excerpt time."""
    if excerpt is None:
        return list(holds)
    out = []
    for a, b in holds:
        a, b = max(0.0, a - excerpt[0]), min(length, b - excerpt[0])
        if a < b:
            out.append((a, b))
    return out


def paged_sheets(video: Path, total: float, out_dir: Path) -> list[Path]:
    """4x5 tiles at 480 px, one frame per second: big enough to read the lyrics' spelling."""
    if total <= PAGE_MIN_S:
        return []
    per_page = PAGE_COLS * PAGE_ROWS
    pages = math.ceil(math.ceil(total) / per_page)
    for old in out_dir.glob(f"{video.stem}-sheet-[0-9][0-9].png"):
        old.unlink()
    out = out_dir / f"{video.stem}-sheet-%02d.png"
    run([need("ffmpeg"), "-y", "-nostdin", "-loglevel", "error", "-i", str(video), "-vf",
         f"fps=1,scale={PAGE_WIDTH}:-2,tile={PAGE_COLS}x{PAGE_ROWS}", "-start_number", "1", str(out)],
        "paged frame sheets")
    return [out_dir / f"{video.stem}-sheet-{n:02d}.png" for n in range(1, pages + 1)
            if (out_dir / f"{video.stem}-sheet-{n:02d}.png").is_file()]


def frame_sheet(video: Path, total: float, out_png: Path) -> Path:
    rate = 1.0 if total <= SHEET_TILES else SHEET_TILES / total
    tiles = max(1, min(SHEET_TILES, math.ceil(total * rate)))
    cols = min(SHEET_COLS, tiles)
    rows = math.ceil(tiles / cols)
    run([need("ffmpeg"), "-y", "-nostdin", "-loglevel", "error", "-i", str(video), "-vf",
         f"fps={rate:.6f},scale=320:-2,tile={cols}x{rows}", "-frames:v", "1", str(out_png)],
        "frame sheet")
    return out_png


def run_qc(video: Path, song: Path, out_dir: Path, *, size=None, fps: float = 30,
           excerpt: tuple[float, float] | None = None, holds=()) -> dict:
    info = probe(video)
    total = float(info["format"]["duration"])
    expected = excerpt[1] - excerpt[0] if excerpt else float(probe(song)["format"]["duration"])
    holds = _clip_holds(holds, excerpt, total)
    checks = check_format(info, size, fps, expected)
    checks += [detect_black(video, total, holds), detect_frozen(video, total, holds)]
    has_audio = any(s["codec_type"] == "audio" for s in info["streams"])
    checks.append(check_audio(video, song, excerpt, fps) if has_audio else Check("audio", False, "no audio stream"))
    out_dir.mkdir(parents=True, exist_ok=True)
    sheet = frame_sheet(video, total, out_dir / f"{video.stem}-sheet.png")
    pages = paged_sheets(video, total, out_dir)
    report = {"video": str(video), "result": "PASS" if all(c.ok for c in checks) else "FAIL",
              "checks": [asdict(c) for c in checks], "sheet": str(sheet), "pages": [str(x) for x in pages],
              "note": "Look at the sheet before showing anyone: every frame must make visual sense."}
    (out_dir / f"qc-{video.stem}.json").write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    return report
