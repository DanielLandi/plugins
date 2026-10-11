"""Where a video's files live: working files in <work>/<id>/ (regenerable), finals in <results>/<id>/.

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
    root: Path  # the work folder
    results: Path | None = None  # the finals folder (defaults to root/deliver when unknown)
    video: Path | None = None  # the video's own folder in the project (hand-written corrections live there)

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
        return self._kept("timing-fixes.yaml")

    @property
    def as_sung(self) -> Path:
        return self._kept("lyrics-as-sung.txt")

    def _kept(self, name: str) -> Path:
        """A file the user approved by hand: it lives with the video (in the project, not the purgeable work
        folder). One left in an older work folder is still read until a copy exists with the video."""
        if self.video is None:
            return self.root / name
        mine, older = self.video / name, self.root / name
        return older if older.is_file() and not mine.is_file() else mine

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
        return self.results if self.results is not None else self.root / "deliver"

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
    paths = VideoPaths(ws.work_for(spec_id), ws.results_for(spec_id), ws.video_dir(spec_id))
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
