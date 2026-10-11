"""Where a user's songs and videos live. The plugin folder is replaced on every update, so nothing personal is kept
there: specs and video code go in the workspace, media wherever config.yaml says (default <workspace>/media)."""
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

from .errors import MVError

DEFAULT_HOME = Path.home() / "Movies" / "Music Videos"
CONFIG = "config.yaml"


def cache_dir() -> Path:
    if value := os.environ.get("MV_CACHE_DIR"):
        return Path(value).expanduser()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "music-video"
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "music-video" / "Cache"
    return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "music-video"


def settings_file() -> Path:
    if value := os.environ.get("MV_SETTINGS"):
        return Path(value).expanduser()
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "music-video" / "settings.json"


def workspace_home() -> Path:
    if value := os.environ.get("MUSIC_VIDEO_HOME"):
        return Path(value).expanduser()
    f = settings_file()
    if f.is_file():
        saved = (json.loads(f.read_text(encoding="utf-8")) or {}).get("workspace")
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
    media_dir: Path
    downloads_dir: Path
    billing_day: int | None
    download_budget: int | None

    @property
    def specs_dir(self) -> Path:
        return self.home / "specs"

    def video_dir(self, video_id: str) -> Path:
        return self.videos_dir / video_id

    def media_for(self, video_id: str) -> Path:
        return self.media_dir / video_id


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
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    artist = str(raw.get("artist") or "").strip()
    if not artist:
        raise MVError(f"{path}: artist is empty; set the name your songs are credited to")
    return Workspace(
        home=home,
        artist=artist,
        videos_dir=_absolute(home, raw.get("videos_dir", "videos")),
        media_dir=_absolute(home, raw.get("media_dir", "media")),
        downloads_dir=_absolute(home, raw.get("downloads_dir", "~/Downloads")),
        billing_day=_optional_int(raw, "billing_day", 1, 31, path),
        download_budget=_optional_int(raw, "download_budget", 0, 10_000, path),
    )


def init_workspace(home: Path, artist: str, billing_day: int | None = None, download_budget: int | None = None,
                   media_dir: Path | None = None) -> tuple[Path, bool]:
    home = Path(home).expanduser()
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
            "media_dir": str(media_dir) if media_dir else "media",
        }
        (home / CONFIG).write_text(yaml.safe_dump(config, sort_keys=False, allow_unicode=True), encoding="utf-8")
        _absolute(home, config["media_dir"]).mkdir(parents=True, exist_ok=True)
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
