"""Where a user's songs and videos live. The plugin folder is replaced on every update, so nothing personal is kept
there: specs, albums and video code go in the project folder, finals in results_dir, working files in work_dir (the
OS cache by default), the engine in the install folder."""
import json
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

from .errors import MVError

DEFAULT_HOME = Path.home() / "Documents" / "Music Videos"  # the project: specs, albums, video code (small)
def default_results() -> Path:
    """Finals, web pages, albums (what gets shared): the platform's videos folder."""
    return Path.home() / ("Movies" if sys.platform == "darwin" else "Videos") / "Music Videos"
CONFIG = "config.yaml"


def cache_dir() -> Path:
    if value := os.environ.get("MV_CACHE_DIR"):
        return Path(value).expanduser()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "music-video"
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "music-video" / "Cache"
    return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "music-video"


def install_dir() -> Path:
    """Where the engine (Remotion, compilers, its browser) and the alignment models are installed, per machine."""
    if value := os.environ.get("MV_INSTALL_DIR"):
        return Path(value).expanduser()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "music-video"
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "music-video"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "music-video"


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8")) or {}
    except json.JSONDecodeError as e:
        raise MVError(f"{path}: not valid JSON ({e.msg}); fix or delete it") from e


def settings_file() -> Path:
    if value := os.environ.get("MV_SETTINGS"):
        return Path(value).expanduser()
    if sys.platform == "darwin":
        # Preferences, not Application Support: that is the install folder, and deleting the engine must not
        # forget where the project is.
        base = Path.home() / "Library" / "Preferences"
    elif sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "music-video" / "settings.json"


def _old_settings() -> Path:
    return Path.home() / "Library" / "Application Support" / "music-video" / "settings.json"


def _settings_to_read() -> Path:
    """0.2.0 kept macOS settings in the install folder: copy them to the new place once (a copy, so an older plugin
    still running keeps finding them). If the copy cannot be made, read the old file rather than fail."""
    f = settings_file()
    old = _old_settings()
    if sys.platform != "darwin" or os.environ.get("MV_SETTINGS") or f.exists() or not old.is_file():
        return f
    try:
        f.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(old, f)
        return f
    except OSError:
        return old


def workspace_home() -> Path:
    if value := os.environ.get("MUSIC_VIDEO_HOME"):
        return Path(value).expanduser()
    f = _settings_to_read()
    if f.is_file():
        saved = _read_json(f).get("workspace")
        if saved:
            return Path(saved).expanduser()
    return DEFAULT_HOME


def remember_home(home: Path) -> None:
    f = settings_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"workspace": str(home)}), encoding="utf-8")


@dataclass(frozen=True)
class Workspace:
    home: Path
    artist: str
    videos_dir: Path
    results_dir: Path
    work_dir: Path
    downloads_dir: Path
    billing_day: int | None
    download_budget: int | None

    @property
    def specs_dir(self) -> Path:
        return self.home / "specs"

    def video_dir(self, video_id: str) -> Path:
        return self.videos_dir / video_id

    def results_for(self, video_id: str) -> Path:
        """Finals: what gets shared or published (videos, the song, the web page)."""
        return self.results_dir / video_id

    def work_for(self, video_id: str) -> Path:
        """Everything regenerable while working on a video (timings, renders, checks): `clean` deletes it."""
        return self.work_dir / video_id

    def album_dir(self, album: str) -> Path:
        return self.results_dir / "albums" / album


def _absolute(home: Path, value) -> Path:
    path = Path(str(value)).expanduser()
    return path if path.is_absolute() else home / path


def _optional_int(raw: dict, key: str, low: int, high: int, path: Path) -> int | None:
    if raw.get(key) is None:
        return None
    try:
        value = int(raw[key])
    except (TypeError, ValueError) as e:
        raise MVError(f"{path}: {key} must be a whole number") from e
    if not low <= value <= high:
        raise MVError(f"{path}: {key} must be {low}-{high}, got {value}")
    return value


def load_workspace(home: Path | None = None) -> Workspace:
    home = home or workspace_home()
    path = home / CONFIG
    if not path.is_file():
        raise MVError(f"no workspace at {home} (no {CONFIG}): run music-video init")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        raise MVError(f"{path}: not valid YAML ({str(e).splitlines()[0]})") from e
    artist = str(raw.get("artist") or "").strip()
    if not artist:
        raise MVError(f"{path}: artist is empty; set the name your songs are credited to")
    return Workspace(
        home=home,
        artist=artist,
        videos_dir=_absolute(home, raw.get("videos_dir", "videos")),
        # 0.1.0 called the results folder media_dir.
        results_dir=_absolute(home, raw.get("results_dir") or raw.get("media_dir") or default_results()),
        work_dir=_absolute(home, raw.get("work_dir") or cache_dir() / "work"),
        downloads_dir=_absolute(home, raw.get("downloads_dir", "~/Downloads")),
        billing_day=_optional_int(raw, "billing_day", 1, 31, path),
        download_budget=_optional_int(raw, "download_budget", 0, 10_000, path),
    )


def init_workspace(home: Path, artist: str, billing_day: int | None = None, download_budget: int | None = None,
                   results_dir: Path | None = None) -> tuple[Path, bool]:
    home = Path(home).expanduser()
    if billing_day is not None and not 1 <= billing_day <= 31:
        raise MVError(f"--billing-day must be 1-31, got {billing_day}")
    if download_budget is not None and download_budget < 0:
        raise MVError(f"--download-budget must be 0 or more, got {download_budget}")
    created = not (home / CONFIG).is_file()
    if created:
        for sub in ("specs", "videos"):
            (home / sub).mkdir(parents=True, exist_ok=True)
        config = {
            "artist": artist,
            # From your Suno account's billing page: the day your plan renews and downloads included per cycle.
            "billing_day": billing_day,
            "download_budget": download_budget,
            "downloads_dir": "~/Downloads",
            "videos_dir": "videos",
            # Finals go here; working files (renders, timings) go to the OS cache unless work_dir is set.
            "results_dir": str(results_dir) if results_dir else "~/" + default_results().relative_to(Path.home()).as_posix(),
        }
        (home / CONFIG).write_text(yaml.safe_dump(config, sort_keys=False, allow_unicode=True), encoding="utf-8")
    remember_home(home)
    return home, created


def stored_path(ws: Workspace, path: Path) -> str:
    """How a filed path is written in a spec: relative to the workspace, else `~/…`, else absolute."""
    path = Path(path)
    if path.is_relative_to(ws.home):
        return str(path.relative_to(ws.home))
    if path.is_relative_to(Path.home()):
        return "~/" + str(path.relative_to(Path.home()))
    return str(path)


def filed_path(ws: Workspace, stored: str) -> Path:
    path = Path(stored).expanduser()
    return path if path.is_absolute() else ws.home / path


def load_private_names(ws: Workspace) -> list[str]:
    path = ws.home / "private-names.txt"
    if not path.is_file():
        return []
    lines = (line.strip() for line in path.read_text(encoding="utf-8").splitlines())
    return [line for line in lines if line and not line.startswith("#")]
