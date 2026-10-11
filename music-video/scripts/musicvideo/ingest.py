import re
import shutil
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path

from .errors import MVError
from .spec import find_spec, iter_specs, load_spec, now_iso, parse_dt, save_spec, validate
from .tagging import write_tags
from .workspace import Workspace, load_private_names, stored_path

AUDIO_EXTS = {".mp3"}
SINCE_SLACK = timedelta(seconds=5)
_ILLEGAL = re.compile(r'[\\/:*?"<>|]')


def normalize(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "", ascii_text.lower())


def library_filename(artist: str, title: str) -> str:
    name = _ILLEGAL.sub(" ", f"{artist} - {title}")
    return re.sub(r"\s+", " ", name).strip() + ".mp3"


def find_candidates(downloads_dir: Path, title: str, since: datetime | None) -> list[Path]:
    key = normalize(title)
    found = []
    for path in downloads_dir.iterdir():
        if not path.is_file() or path.name.startswith(".") or path.suffix.lower() not in AUDIO_EXTS:
            continue
        if since and datetime.fromtimestamp(path.stat().st_mtime).astimezone() < since:
            continue
        if normalize(path.stem).startswith(key):
            found.append(path)
    return sorted(found, key=lambda p: p.stat().st_mtime, reverse=True)


def ingest(ws: Workspace, spec_id: str, file: Path | None = None) -> Path:
    """File a downloaded MP3 into <media>/<spec id>/, tagged, and mark the spec filed."""
    spec_path = find_spec(ws, spec_id)
    data = load_spec(spec_path)
    kept = data.get("kept") or {}

    if file is None:
        since = parse_dt(kept["downloaded_at"]) - SINCE_SLACK if kept.get("downloaded_at") else None
        candidates = find_candidates(ws.downloads_dir, data["title"], since)
        if not candidates:
            when = f" since {since:%Y-%m-%d %H:%M:%S}" if since else ""
            raise MVError(f"no finished MP3 named like '{data['title']}' in {ws.downloads_dir}{when}; "
                            "pass --file <path>")
        if len(candidates) > 1:
            listing = "\n".join(f"  {c}" for c in candidates)
            raise MVError(f"several candidates — rerun with --file:\n{listing}")
        file = candidates[0]
    file = Path(file).expanduser()
    if not file.is_file():
        raise MVError(f"{file} not found")
    if file.suffix.lower() not in AUDIO_EXTS:
        raise MVError(f"{file.name}: only MP3 is supported — download the MP3 version")

    if not kept.get("downloaded_at"):
        kept["downloaded_at"] = datetime.fromtimestamp(file.stat().st_mtime).astimezone().isoformat(timespec="seconds")
    data["kept"] = kept
    if data.get("status") in ("drafted", "generated"):
        data["status"] = "downloaded"
    errors = validate(data, load_private_names(ws))
    if errors:
        raise MVError("spec invalid:\n" + "\n".join(f"  - {e}" for e in errors))

    dest_dir = ws.media_for(spec_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / library_filename(ws.artist, data["title"])
    rel = stored_path(ws, dest)
    for other_path, other in iter_specs(ws):
        if other_path != spec_path and (other.get("kept") or {}).get("file") == rel:
            raise MVError(f"{dest.name} already belongs to spec '{other['id']}' — change this song's title")

    tmp = dest.with_name(dest.name + ".part")
    shutil.copy2(file, tmp)
    try:
        write_tags(tmp, data, ws.artist, datetime.now().year)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    tmp.replace(dest)
    if file.resolve() != dest.resolve():
        file.unlink()

    kept["file"] = rel
    kept["filed_at"] = now_iso()
    data["status"] = "filed"
    save_spec(spec_path, data)
    return dest
