"""music-video mux: put the song's audio under a silent Remotion render."""
from pathlib import Path

from .media import need, run

FADE_S = 0.05


def mux(video: Path, song: Path, out: Path, excerpt: tuple[float, float] | None = None) -> Path:
    """Full song: the whole song as AAC 320 kbps. Excerpt: cut, 50 ms fades, AAC 320 kbps.

    Never the MP3 stream copied as is: MP3 inside MP4 plays silent in QuickTime (found 2026-10-10, draft v1).
    """
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [need("ffmpeg"), "-y", "-nostdin", "-loglevel", "error", "-i", str(video)]
    if excerpt is None:
        cmd += ["-i", str(song), "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "320k"]
    else:
        start, end = excerpt
        length = end - start
        fades = f"afade=t=in:d={FADE_S},afade=t=out:st={max(length - FADE_S, 0):.3f}:d={FADE_S}"
        cmd += ["-ss", f"{start:.3f}", "-t", f"{length:.3f}", "-i", str(song), "-map", "0:v:0", "-map", "1:a:0",
                "-c:v", "copy", "-af", fades, "-c:a", "aac", "-b:a", "320k"]
    run(cmd + ["-movflags", "+faststart", str(out)], f"muxing {out.name}")
    return out
