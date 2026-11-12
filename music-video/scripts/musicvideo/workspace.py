"""Where a user's songs and videos live. The plugin folder is replaced on every update, so nothing personal is kept
there: specs, albums and video code go in the project folder, finals in results_dir, working files in work_dir (the
OS cache by default), the engine in the install folder."""
import hashlib
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

from .errors import MVError
from .worktrees import linked_worktree

DEFAULT_HOME = Path.home() / "Documents" / "Music Videos"  # the project: specs, albums, video code (small)
def default_results() -> Path:
    """Finals, web pages, albums (what gets shared): the platform's videos folder."""
    return Path.home() / ("Movies" if sys.platform == "darwin" else "Videos") / "Music Videos"
CONFIG = "config.yaml"
LANES = ".lanes"  # a linked git worktree's own work and finals: work_dir/.lanes/<key>, results_dir/.lanes/<key>


def cache_dir() -> Path:
    if value := os.environ.get("MV_CACHE_DIR"):
        return Path(value).expanduser()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "music-video"
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "music-video" / "Cache"
    return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "music-video"


def folder_key(root: Path) -> str:
    """A folder's name as a short readable slug plus a hash of its full path: stable for the folder's life, and
    distinct for two folders with the same name (two clones, two worktrees)."""
    slug = re.sub(r"[^a-z0-9]+", "-", root.name.lower()).strip("-")[:24].strip("-") or "x"
    path = os.path.normcase(str(root.resolve()))
    return f"{slug}-{hashlib.sha256(path.encode('utf-8')).hexdigest()[:8]}"


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


def saved_home() -> Path | None:
    """The project folder `init` saved in settings.json, if any."""
    f = _settings_to_read()
    if f.is_file():
        saved = _read_json(f).get("workspace")
        if saved:
            return Path(saved).expanduser()
    return None


def main_counterpart(folder: Path) -> Path | None:
    """The same folder in the main checkout, for a folder inside a linked git worktree; else None."""
    wt = linked_worktree(folder)
    if wt is None:
        return None
    return wt.main / Path(folder).absolute().relative_to(wt.root)


def config_path(home: Path) -> Path:
    """A workspace's config.yaml. In a git worktree without one (it may be gitignored), the main checkout's."""
    own = Path(home) / CONFIG
    if own.is_file():
        return own
    counterpart = main_counterpart(home)
    if counterpart is not None and (counterpart / CONFIG).is_file():
        return counterpart / CONFIG
    return own


def is_workspace(folder: Path) -> bool:
    """A folder `init` made: its config.yaml names an artist and it has specs/. Never raises."""
    try:
        if not (Path(folder) / "specs").is_dir():
            return False
        raw = yaml.safe_load(config_path(folder).read_text(encoding="utf-8"))
        return isinstance(raw, dict) and bool(str(raw.get("artist") or "").strip())
    except (OSError, UnicodeDecodeError, yaml.YAMLError, ValueError):
        return False


def _mapped_home(cwd: Path, saved: Path | None) -> Path | None:
    """Inside a linked git worktree only: the saved workspace's folder in this worktree, else the nearest workspace
    from the cwd up to the worktree's root. A plain folder or a main checkout never overrides the saved workspace."""
    wt = linked_worktree(cwd)
    if wt is None:
        return None
    if saved is not None:
        try:
            rel = saved.expanduser().resolve().relative_to(wt.main.resolve())
        except (OSError, ValueError):
            rel = None
        if rel is not None and is_workspace(wt.root / rel):
            return wt.root / rel
    cwd = Path(cwd).absolute()
    for folder in (cwd, *cwd.parents):
        if is_workspace(folder):
            return folder
        if folder == wt.root:
            break
    return None


def workspace_home() -> Path:
    if value := os.environ.get("MUSIC_VIDEO_HOME"):
        return Path(value).expanduser()
    saved = saved_home()
    try:
        cwd = Path.cwd()
    except OSError:
        cwd = None
    if cwd is not None and (mapped := _mapped_home(cwd, saved)) is not None:
        return mapped
    return saved or DEFAULT_HOME


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
    lane: str | None = None  # the linked git worktree's key (folder_key of its root); None in a main checkout
    main_home: Path | None = None  # the same folder in the main checkout; `home` itself when not in a lane

    def __post_init__(self):
        if self.main_home is None:
            object.__setattr__(self, "main_home", self.home)

    @property
    def specs_dir(self) -> Path:
        return self.home / "specs"

    def video_dir(self, video_id: str) -> Path:
        return self.videos_dir / video_id

    @property
    def work_root(self) -> Path:
        """Where this checkout's work folders live: work_dir, or work_dir/.lanes/<key> in a git worktree."""
        return self.work_dir if self.lane is None else self.work_dir / LANES / self.lane

    @property
    def finals_root(self) -> Path:
        """Where this checkout's video finals live: results_dir, or results_dir/.lanes/<key> in a git worktree
        (a dot-folder, so the library never lists it)."""
        return self.results_dir if self.lane is None else self.results_dir / LANES / self.lane

    def results_for(self, video_id: str) -> Path:
        """Video finals: what gets shared or published (videos, the web page)."""
        return self.finals_root / video_id

    def song_dir(self, song_id: str) -> Path:
        """Where a downloaded song is filed: shared by every worktree (a download costs from one budget)."""
        return self.results_dir / song_id

    def work_for(self, video_id: str) -> Path:
        """Everything regenerable while working on a video (timings, renders, checks): `clean` deletes it."""
        return self.work_root / video_id

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
    path = config_path(home)
    wt = linked_worktree(home)
    main_home = main_counterpart(home) if wt is not None else home
    if not path.is_file():
        if wt is not None:
            raise MVError(f"no workspace at {home} (no {CONFIG} here or in {main_home})")
        raise MVError(f"no workspace at {home} (no {CONFIG}): run music-video init")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        raise MVError(f"{path}: not valid YAML ({str(e).splitlines()[0]})") from e
    artist = str(raw.get("artist") or "").strip()
    if not artist:
        raise MVError(f"{path}: artist is empty; set the name your songs are credited to")
    # In a git worktree, the project's own folders (videos, work) are the worktree's; the shared ones (results,
    # downloads) are the main checkout's, so a filed song's path stays valid after the branch merges.
    return Workspace(
        home=home,
        artist=artist,
        videos_dir=_absolute(home, raw.get("videos_dir", "videos")),
        # 0.1.0 called the results folder media_dir.
        results_dir=_absolute(main_home, raw.get("results_dir") or raw.get("media_dir") or default_results()),
        work_dir=_absolute(home, raw.get("work_dir") or cache_dir() / "work"),
        downloads_dir=_absolute(main_home, raw.get("downloads_dir", "~/Downloads")),
        billing_day=_optional_int(raw, "billing_day", 1, 31, path),
        download_budget=_optional_int(raw, "download_budget", 0, 10_000, path),
        lane=folder_key(wt.root) if wt is not None else None,
        main_home=main_home,
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
    """How a filed path is written in a spec: relative to the workspace (the main checkout's, in a git worktree),
    else `~/…`, else absolute."""
    path = Path(path)
    if path.is_relative_to(ws.main_home):
        return str(path.relative_to(ws.main_home))
    if path.is_relative_to(Path.home()):
        return "~/" + str(path.relative_to(Path.home()))
    return str(path)


def filed_path(ws: Workspace, stored: str) -> Path:
    path = Path(stored).expanduser()
    return path if path.is_absolute() else ws.main_home / path


PRIVATE_NAMES = "private-names.txt"


def _private_names_files(ws: Workspace) -> list[Path]:
    """The workspace's private-names.txt, then, in a git worktree, the main checkout's (the file is usually
    gitignored, so a fresh worktree has none of its own)."""
    files = [ws.home / PRIVATE_NAMES]
    if ws.lane is not None and ws.main_home is not None:
        files.append(ws.main_home / PRIVATE_NAMES)
    return files


def load_private_names(ws: Workspace) -> list[str]:
    names: list[str] = []
    for path in _private_names_files(ws):
        if not path.is_file():
            continue
        lines = (line.strip() for line in path.read_text(encoding="utf-8").splitlines())
        names += [line for line in lines if line and not line.startswith("#") and line not in names]
    return names


def private_names_warning(ws: Workspace) -> str | None:
    """What to tell the user when the workspace keeps no private-names.txt, so no name was checked.
    A file with no names in it is a deliberate empty list and says nothing."""
    path = ws.home / PRIVATE_NAMES
    if any(f.is_file() for f in _private_names_files(ws)):
        return None
    return (f"warning: no {PRIVATE_NAMES} in {ws.home}; private names were not checked "
            f"(list them one per line in {path})")


def warn_if_no_private_names(ws: Workspace) -> None:
    """Print the missing-file warning to stderr; it never changes the command's outcome."""
    warning = private_names_warning(ws)
    if warning:
        print(warning, file=sys.stderr)
