"""Where a video's audio, timings and renders live: <media>/<spec id>/ (config.yaml media_dir).

public/ is the Remotion public folder for that one video, so a render bundles only the song and its JSON.
"""
import shutil
from dataclasses import dataclass
from pathlib import Path

from ..workspace import Workspace, filed_path
from ..errors import MVError
from ..spec import find_spec, load_spec


@dataclass(frozen=True)
class VideoPaths:
    root: Path

    @property
    def public(self) -> Path:
        return self.root / "public"

    @property
    def song(self) -> Path:
        return self.public / "song.mp3"

    @property
    def timing(self) -> Path:
        return self.public / "timing.json"

    @property
    def analysis(self) -> Path:
        return self.public / "analysis.json"

    @property
    def vocals(self) -> Path:
        return self.root / "vocals.wav"

    @property
    def aligned(self) -> Path:
        return self.root / "aligned.json"

    @property
    def transcript(self) -> Path:
        return self.root / "transcript.json"

    @property
    def beats(self) -> Path:
        return self.root / "beats.json"

    @property
    def fixes(self) -> Path:
        return self.root / "timing-fixes.yaml"

    @property
    def as_sung(self) -> Path:
        return self.root / "lyrics-as-sung.txt"

    @property
    def align_input(self) -> Path:
        return self.root / "align-input.txt"

    @property
    def preview(self) -> Path:
        return self.root / "preview.mp4"

    @property
    def preview_ass(self) -> Path:
        return self.root / "preview.ass"

    @property
    def renders(self) -> Path:
        return self.root / "renders"

    @property
    def qc(self) -> Path:
        return self.root / "qc"

    @property
    def deliver(self) -> Path:
        return self.root / "deliver"

    def subtitle(self, ext: str) -> Path:
        return self.root / f"lyrics.{ext}"


@dataclass(frozen=True)
class VideoSong:
    spec_id: str
    spec: dict
    source: Path
    paths: VideoPaths


def video_song(ws: Workspace, spec_id: str) -> VideoSong:
    spec_path = find_spec(ws, spec_id)
    spec = load_spec(spec_path)
    file = (spec.get("kept") or {}).get("file")
    if spec.get("status") != "filed" or not file:
        raise MVError(f"{spec_id} is not filed yet: download and ingest the song first")
    source = filed_path(ws, file)
    if not source.is_file():
        raise MVError(f"{source} is missing; re-run music-video ingest {spec_id}")
    paths = VideoPaths(ws.media_for(spec_id))
    paths.public.mkdir(parents=True, exist_ok=True)
    stale = (not paths.song.exists()
             or paths.song.stat().st_size != source.stat().st_size
             or paths.song.stat().st_mtime < source.stat().st_mtime)
    if stale:
        shutil.copy2(source, paths.song)
    return VideoSong(spec_id, spec, source, paths)


def open_file(path: Path) -> None:
    """Show a file in the system's default app."""
    import os
    import subprocess
    import sys
    if sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=False)
    elif sys.platform == "win32":
        os.startfile(str(path))  # noqa: S606 (no shell)
    else:
        subprocess.run(["xdg-open", str(path)], check=False)
