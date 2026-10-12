"""Albums: songs published together, with a manifest.json a website or player can read.

`albums/<id>.yaml` in the project: `title`, `year`, `artist` (default: the project's), `cover` (an image path,
relative to the albums folder), and optional `styles:` (`<key>: {artist, album, genre, era}`) so one album can
credit a different artist and album name per style, as a compilation does. A song joins with `album:` and
`style:` in its spec; its tagged MP3 is filed in `<results>/albums/<id>/`.
"""
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

import yaml
from mutagen.mp3 import MP3

from .errors import MVError
from .spec import iter_specs
from .workspace import Workspace, filed_path


@dataclass(frozen=True)
class Style:
    artist: str | None = None
    album: str | None = None
    genre: str | None = None
    era: str | None = None


@dataclass(frozen=True)
class Album:
    id: str
    title: str
    year: int
    artist: str
    cover: Path | None
    styles: dict[str, Style] = field(default_factory=dict)


class Credit(NamedTuple):
    """What a song's tags and manifest entry say about it."""
    artist: str
    album: str
    genre: str | None
    era: str | None
    year: int
    cover: Path | None


def album_file(ws: Workspace, album_id: str) -> Path:
    return ws.home / "albums" / f"{album_id}.yaml"


def load_album(ws: Workspace, album_id: str) -> Album:
    path = album_file(ws, album_id)
    if not path.is_file():
        raise MVError(f"no album '{album_id}' ({path})")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        raise MVError(f"{path}: not valid YAML ({str(e).splitlines()[0]})") from e
    if not isinstance(raw, dict):
        raise MVError(f"{path}: an album is a mapping (title, year, artist, cover, styles)")
    if not isinstance(raw.get("styles") or {}, dict):
        raise MVError(f"{path}: styles must map each style key to its artist/album/genre/era")
    try:
        styles = {str(k): Style(**(v or {})) for k, v in (raw.get("styles") or {}).items()}
        year = int(raw.get("year") or datetime.now().year)
    except (TypeError, ValueError) as e:
        raise MVError(f"{path}: needs title, year and styles of artist/album/genre/era ({e})") from e
    if raw.get("cover") is not None and not isinstance(raw["cover"], str):
        raise MVError(f"{path}: cover must be an image file name (next to the album file), not {raw['cover']!r}")
    cover = path.parent / raw["cover"] if raw.get("cover") else None
    if cover is not None and not cover.is_file():
        raise MVError(f"{path}: cover {cover} does not exist")
    return Album(id=album_id, title=str(raw.get("title") or album_id), year=year,
                 artist=str(raw.get("artist") or ws.artist), cover=cover, styles=styles)


def album_errors(data: dict, album: Album) -> list[str]:
    if not album.styles:
        return []
    names = ", ".join(sorted(album.styles))
    style = data.get("style")
    if not style:
        return [f"style missing: album '{album.id}' credits by style (styles: {names})"]
    if style not in album.styles:
        return [f"style '{style}' is not in album '{album.id}' (styles: {names})"]
    return []


def credit(ws: Workspace, spec: dict) -> Credit:
    if not spec.get("album"):
        return Credit(artist=ws.artist, album=spec["title"], genre=None, era=None, year=datetime.now().year, cover=None)
    album = load_album(ws, spec["album"])
    style = album.styles.get(spec.get("style") or "", Style())
    return Credit(artist=style.artist or album.artist, album=style.album or album.title, genre=style.genre,
                  era=style.era, year=album.year, cover=album.cover)


def build_manifest(ws: Workspace, album_id: str) -> list[dict]:
    entries = []
    for _, data in iter_specs(ws):
        if data.get("album") != album_id or data.get("status") != "filed":
            continue
        kept = data["kept"]
        audio = filed_path(ws, kept["file"])
        if not audio.is_file():
            raise MVError(f"{data['id']}: filed audio missing at {audio}")
        errors = album_errors(data, load_album(ws, album_id))
        if errors:
            raise MVError(f"{data['id']}: {errors[0]}")
        c = credit(ws, data)
        entries.append({
            "id": data["id"], "title": data["title"], "artist": c.artist, "album": c.album, "genre": c.genre,
            "era": c.era, "kind": data["kind"], "duration_s": round(MP3(audio).info.length, 1), "file": audio.name,
            "sha256": hashlib.sha256(audio.read_bytes()).hexdigest(),
            "added_at": str(kept.get("filed_at") or kept["downloaded_at"]),
        })
    return sorted(entries, key=lambda e: (e["added_at"], e["id"]))


def write_manifest(ws: Workspace, album_id: str) -> tuple[Path, int]:
    load_album(ws, album_id)  # an unknown album id is an error, never an empty manifest in a new folder
    entries = build_manifest(ws, album_id)
    out = ws.album_dir(album_id)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "manifest.json"
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(entries, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)
    return path, len(entries)
