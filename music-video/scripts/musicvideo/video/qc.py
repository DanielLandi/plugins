"""music-video qc: the automatic half of checking a render before the user sees it.

The other half is looking at the frame sheet it writes: every frame must make visual sense.
"""
import json
import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from ..errors import MVError
from .media import audio_duration_s, decode_mono, duration_s, need, probe, run
from .scans import Exempt, find_cuts, find_flicker, find_jitter, find_pops, measure

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
# A blank frame at a cut (a scene captured before it finished loading) is dark but not black, and lasts a few
# frames: blackdetect misses it. A run up to FLASH_MAX_S whose mean luma (YAVG, 0-255) departs from BOTH the frame
# before and after it, in the same direction, fails. A cut is a step (the run matches one side), a fade moves
# between its neighbours: neither is a dip. A real draft had runs of 23 against 43 (0.53) and 28 against 97 (0.29);
# finished videos stay above 0.85 of their neighbours.
FLASH_MAX_S = 0.2      # 6 frames at 30 fps (a real one was 5); longer dark stretches are scenes
FLASH_DARK_RATIO, FLASH_DARK_MIN = 0.6, 15.0
FLASH_WHITE_RATIO, FLASH_WHITE_MIN = 1.5, 40.0
FLASH_SCALE = "scale=320:-2"


@dataclass
class Check:
    id: str
    ok: bool
    detail: str
    skipped: bool = False   # not run (no song to check against): never a failure, always said


def _covered(a: float, b: float, holds) -> bool:
    return any(h0 - 0.05 <= a and b <= h1 + 0.05 for h0, h1 in holds)


def _spans(log: str, start_key: str, end_key: str, total: float) -> list[tuple[float, float]]:
    starts = [float(x) for x in re.findall(rf"{start_key}[:=]\s*([0-9.]+)", log)]
    ends = [float(x) for x in re.findall(rf"{end_key}[:=]\s*([0-9.]+)", log)]
    return [(s, ends[i] if i < len(ends) else total) for i, s in enumerate(starts)]


def check_format(info: dict, size, fps: float, expected_s: float | None, silent: bool = False) -> list[Check]:
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
    if audio is None and not silent:
        problems.append("no audio stream")
    sound = f" + {audio['codec_name']}" if audio is not None else ", no audio (silent check)"
    detail = "; ".join(problems) or f"{w}x{h} {rate:g} fps h264{sound}"
    if video.get("duration") not in (None, "N/A"):
        duration = float(video["duration"])
    elif den and video.get("nb_frames"):
        duration = int(video["nb_frames"]) * den / num
    else:
        duration = float(info["format"]["duration"])
    if expected_s is None:
        return [Check("format", not problems, detail),
                Check("duration", True, f"skipped: video {duration:.3f} s, and no song length to hold it to "
                      "(give --excerpt, or a placeholder in video.yaml)", skipped=True)]
    return [Check("format", not problems, detail),
            Check("duration", abs(duration - expected_s) <= 1.0 / fps + 0.03,
                  f"video {duration:.3f} s, expected {expected_s:.3f} s")]


COLOUR_TAGS = (("primaries", "color_primaries", "bt709"), ("transfer", "color_transfer", "bt709"),
               ("matrix", "color_space", "bt709"), ("range", "color_range", "tv"))


def check_colour(info: dict) -> Check:
    """BT.709 everywhere (from claude-video-skills' rendering, MIT): an untagged or BT.601 video is shown with
    whatever colours the player guesses (a green or washed shift against everything else)."""
    video = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    if video is None:
        return Check("colour", False, "no video stream")
    found = {name: video.get(key) or "unknown" for name, key, _ in COLOUR_TAGS}
    wrong = [f"{name} {found[name]}" for name, _, want in COLOUR_TAGS if found[name] != want]
    if not wrong:
        return Check("colour", True, "bt709 primaries, transfer and matrix, tv range")
    return Check("colour", False, ", ".join(wrong) + "; expected bt709 primaries, transfer and matrix with tv range: "
                 "re-render with this engine (it renders BT.709); an ffmpeg step stamps the tags with "
                 "setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709:range=tv")


def detect_black(video: Path, total: float, holds, found: list | None = None) -> Check:
    log = run([need("ffmpeg"), "-nostdin", "-i", str(video), "-an", "-vf",
               f"blackdetect=d={BLACK_MIN_S}:pix_th={BLACK_PIX_TH}", "-f", "null", "-"], "black-frame scan").stderr.decode()
    spans = _spans(log, "black_start", "black_end", total)
    if found is not None:
        found += spans
    bad = [(a, b) for a, b in spans
           if not (b <= EDGE_S + BLACK_MIN_S or a >= total - EDGE_S - BLACK_MIN_S or _covered(a, b, holds))]
    return Check("black", not bad,
                 ", ".join(f"{a:.1f}–{b:.1f} s" for a, b in bad) or "none outside the edges and declared holds")


def detect_frozen(video: Path, total: float, holds) -> Check:
    log = run([need("ffmpeg"), "-nostdin", "-i", str(video), "-map", "0:v:0", "-vf",
               f"freezedetect=n={FREEZE_NOISE}:d={FREEZE_MIN_S}", "-f", "null", "-"], "frozen-frame scan").stderr.decode()
    bad = [(a, b) for a, b in _spans(log, "freeze_start", "freeze_end", total) if not _covered(a, b, holds)]
    return Check("frozen", not bad,
                 ", ".join(f"{a:.1f}–{b:.1f} s" for a, b in bad) or "none outside declared holds")


def _frame_luma(video: Path) -> list[tuple[float, float]]:
    out = run([need("ffmpeg"), "-nostdin", "-loglevel", "error", "-i", str(video), "-map", "0:v:0", "-an", "-vf",
               f"{FLASH_SCALE},signalstats,metadata=print:key=lavfi.signalstats.YAVG:file=-", "-f", "null", "-"],
              "flash-frame scan").stdout.decode()
    return [(float(t), float(y)) for t, y in
            re.findall(r"pts_time:(\S+)\s+lavfi\.signalstats\.YAVG=([0-9.]+)", out)]


def find_flashes(frames: list[tuple[float, float]], fps: float) -> list[tuple[float, float, int, str]]:
    """Runs of 1..FLASH_MAX_S frames far darker (or brighter) than both neighbours: (start, end, frames, kind)."""
    ys = [y for _, y in frames]
    longest = max(2, round(FLASH_MAX_S * fps))
    found, covered_to = [], 0
    for i in range(1, len(ys) - 1):
        if i < covered_to:
            continue
        for n in range(1, longest + 1):
            if i + n >= len(ys):
                break
            run_ = ys[i:i + n]
            lo, hi = min(ys[i - 1], ys[i + n]), max(ys[i - 1], ys[i + n])
            kind = ("dark" if max(run_) < FLASH_DARK_RATIO * lo and lo - max(run_) >= FLASH_DARK_MIN else
                    "white" if min(run_) > FLASH_WHITE_RATIO * hi and min(run_) - hi >= FLASH_WHITE_MIN else None)
            if kind:
                found.append((frames[i][0], frames[i + n][0], n, kind))
                covered_to = i + n
                break
    return found


def detect_flash(video: Path, total: float, holds, fps: float, found: list | None = None) -> Check:
    flashes = find_flashes(_frame_luma(video), fps)
    if found is not None:
        found += [(a, b) for a, b, _, _ in flashes]
    bad = [(a, n, kind) for a, b, n, kind in flashes
           if not (a < EDGE_S or b > total - EDGE_S or _covered(a, b, holds))]
    return Check("flash", not bad,
                 ", ".join(f"{kind} at {a:.2f} s ({n} frame{'s' if n > 1 else ''})" for a, n, kind in bad)
                 or "no blank or flash frames outside the edges and declared holds")


def _list(events: list[str], limit: int = 6) -> str:
    more = len(events) - limit
    return ", ".join(events[:limit]) + (f", and {more} more" if more > 0 else "")


def detect_motion(video: Path, info: dict, total: float, fps: float, holds, cuts, words, reported,
                  jolts: bool = False) -> list[Check]:
    """Flicker, pop, hard-cut and jitter scans (scans.py), on one small decode of every frame."""
    stream = next(s for s in info["streams"] if s["codec_type"] == "video")
    m = measure(video, fps, int(stream["width"]), int(stream["height"]))
    ex = Exempt(total=total, edge=EDGE_S, holds=list(holds), cuts=list(cuts), words=list(words),
                reported=list(reported))
    scanned = f"in {m.count} frames"
    flicker = find_flicker(m, ex)
    pops = find_pops(m, ex)
    hard = find_cuts(m, ex)
    checks = [
        Check("flicker", not flicker,
              (_list([f"{a:.2f}–{b:.2f} s ({share:.1%} of the frame)" for a, b, share in flicker])
               + ": something changes for 1–3 frames and back (coplanar faces, a decal off its surface, a shader "
               "threshold); step those frames, or --hold a designed blink") if flicker else f"none {scanned}"),
        Check("pop", not pops,
              (_list([f"{t:.2f} s ({share:.1%} of the frame)" for t, share in pops])
               + ": something appears or vanishes in one frame; step those frames, or --hold a designed snap")
              if pops else f"none {scanned}"),
        Check("hard-cut", not hard,
              (_list([f"{t:.2f} s" for t in hard]) + ": a hard cut inside a scene; a designed one goes into "
               "video.yaml cuts (song time) or --cut") if hard else "none outside scene changes and declared cuts"),
    ]
    if jolts:
        checks.append(Check("jitter", True, "not scanned: the video jolts on the beat (jolts: true in video.yaml)"))
    else:
        jitter = find_jitter(m, ex)
        checks.append(Check("jitter", not jitter,
                            (_list([f"{a:.1f}–{b:.1f} s (path {p:.0f} px, net {n:.0f} px at 640 wide)"
                                    for a, b, p, n in jitter])
                             + ": the camera wanders and comes back instead of moving once") if jitter
                            else f"none {scanned}"))
    return checks


def check_audio(video: Path, song: Path, excerpt, fps: float, tail: float = 0.0) -> Check:
    if excerpt is None:
        # The full song is AAC (mux): check it is the song, in sync, and not cut short, rather than bit for bit.
        song_s, video_s = duration_s(song), audio_duration_s(video)
        if abs(video_s - (song_s + tail)) > 1.0 / fps + 0.05:
            return Check("audio", False, f"audio is {video_s:.3f} s, the song is {song_s:.3f} s"
                         + (f" + a {tail:g} s tail" if tail else ""))
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


def _clip_times(times, excerpt, length: float) -> list[float]:
    """Song times (cuts, word starts) shifted into the clip, keeping those inside it."""
    shift = excerpt[0] if excerpt else 0.0
    return [t - shift for t in times if 0.0 <= t - shift <= length]


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


def _under(path: Path, folder: Path) -> bool:
    try:
        return Path(path).resolve().is_relative_to(Path(folder).resolve())
    except OSError:
        return False


def check_placeholder(video: Path, placeholder: dict, finals: Path | None) -> Check:
    what = f"a silent placeholder song ({placeholder['seconds']:g} s at {placeholder['bpm']:g} bpm)"
    if finals is not None and _under(video, finals):
        return Check("placeholder", False, f"{what} is not a final: keep this render in renders, out of {finals}, "
                     "until the real song is filed, aligned and analysed")
    return Check("placeholder", True, f"{what}: not a final; file the song, then align and analyze replace it")


def run_qc(video: Path, song: Path | None, out_dir: Path, *, size=None, fps: float = 30,
           excerpt: tuple[float, float] | None = None, holds=(), tail: float = 0.0, cuts=(), words=(),
           jolts: bool = False, length: float | None = None, placeholder: dict | None = None,
           finals: Path | None = None) -> dict:
    """`tail`: seconds the full video runs on past the song, silent (mux --tail). `cuts` (scene changes and designed
    hard cuts) and `words` (sung word starts) are song time, like `holds`; `jolts` skips the jitter scan.

    With no song (`song` None: a placeholder video, or qc --silent) every picture check runs and the song's are
    skipped, never failed; `length` is the song's stand-in length (the placeholder's seconds), and a `placeholder`
    render inside `finals` fails: it is never a final."""
    if tail and excerpt:
        raise MVError("--tail is for the full song only, not an excerpt")
    silent = song is None
    info = probe(video)
    total = float(info["format"]["duration"])
    if excerpt:
        expected = excerpt[1] - excerpt[0]
    elif not silent:
        expected = float(probe(song)["format"]["duration"]) + tail
    else:
        expected = length + tail if length is not None else None
    holds = _clip_holds(holds, excerpt, total)
    checks = check_format(info, size, fps, expected, silent)
    checks.append(check_colour(info))
    reported: list[tuple[float, float]] = []
    checks += [detect_black(video, total, holds, reported), detect_flash(video, total, holds, fps, reported),
               detect_frozen(video, total, holds)]
    checks += detect_motion(video, info, total, fps, holds, _clip_times(cuts, excerpt, total),
                            _clip_times(words, excerpt, total), reported, jolts)
    if silent:
        checks += [Check("audio", True, "skipped: no song to compare (a placeholder, or --silent); mux adds it once "
                         "the song is filed", skipped=True),
                   Check("lyrics", True, "skipped: no words to time or read (lyric-sync, spelling, lyric-early, "
                         "word-late in checks.md wait for the song)", skipped=True)]
    else:
        has_audio = any(s["codec_type"] == "audio" for s in info["streams"])
        checks.append(check_audio(video, song, excerpt, fps, tail) if has_audio
                      else Check("audio", False, "no audio stream"))
    if placeholder is not None:
        checks.append(check_placeholder(video, placeholder, finals))
    out_dir.mkdir(parents=True, exist_ok=True)
    sheet = frame_sheet(video, total, out_dir / f"{video.stem}-sheet.png")
    pages = paged_sheets(video, total, out_dir)
    report = {"video": str(video), "result": "PASS" if all(c.ok for c in checks) else "FAIL",
              "checks": [asdict(c) for c in checks], "sheet": str(sheet), "pages": [str(x) for x in pages],
              "silent": silent, "placeholder": placeholder is not None,
              "note": "Look at the sheet before showing anyone: every frame must make visual sense."}
    (out_dir / f"qc-{video.stem}.json").write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    return report
