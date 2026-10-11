import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Iterator

import yaml

from .errors import MVError
from .workspace import Workspace

KINDS = {"original"}
MODELS = {"v6", "v6-wild"}
STATUSES = ("drafted", "generated", "downloaded", "filed")
VOCAL_GENDERS = {"male", "female"}
# Suno's Variety slider labels for positions 0-4, lower-cased (see suno-ui-map.md).
VARIETY_VALUES = {"off", "normal", "high", "extra", "max"}
TITLE_MAX = 80
STYLES_MAX = 1000
LYRICS_MAX = 5000
REQUIRED = ("id", "title", "kind", "suno", "status")
ID_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def slugify(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")


def parse_dt(value) -> datetime:
    dt = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    return dt if dt.tzinfo else dt.astimezone()


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


class _Dumper(yaml.SafeDumper):
    pass


def _represent_str(dumper, value):
    style = "|" if "\n" in value else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


_Dumper.add_representer(str, _represent_str)


def load_spec(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise MVError(f"{path}: invalid YAML: {e}") from e
    if not isinstance(data, dict):
        raise MVError(f"{path}: spec must be a mapping")
    return data


def save_spec(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(yaml.dump(data, Dumper=_Dumper, sort_keys=False, allow_unicode=True, width=1000), encoding="utf-8")
    tmp.replace(path)


def iter_specs(ws: Workspace) -> Iterator[tuple[Path, dict]]:
    for path in sorted(ws.specs_dir.glob("*.yaml")):
        yield path, load_spec(path)


def find_spec(ws: Workspace, spec_id: str) -> Path:
    path = ws.specs_dir / f"{spec_id}.yaml"
    if not path.is_file():
        raise MVError(f"no spec '{spec_id}' in {ws.specs_dir}")
    return path


def _is_percent(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 100


def validate(data: dict, private_names: list[str] = ()) -> list[str]:
    errors = [f"missing field: {field}" for field in REQUIRED if not data.get(field)]
    if errors:
        return errors
    if not ID_RE.match(str(data["id"])):
        errors.append(f"id '{data['id']}' must be lowercase words joined by hyphens")
    if len(data["title"]) > TITLE_MAX:
        errors.append(f"title is {len(data['title'])} chars, max {TITLE_MAX}")
    if data["kind"] not in KINDS:
        errors.append("kind must be original (this plugin makes original songs only)")
    suno = data["suno"]
    if not isinstance(suno, dict):
        return errors + ["suno must be a mapping"]
    if suno.get("model") not in MODELS:
        errors.append(f"suno.model must be one of {sorted(MODELS)}")
    instrumental = suno.get("instrumental", False)
    if not isinstance(instrumental, bool):
        errors.append("suno.instrumental must be true or false")
    # An instrumental is made by leaving Suno's lyrics editor empty.
    text_fields = (("styles", STYLES_MAX),) if instrumental is True else (("styles", STYLES_MAX), ("lyrics", LYRICS_MAX))
    for key, limit in text_fields:
        value = str(suno.get(key) or "")
        if not value.strip():
            errors.append(f"missing field: suno.{key}")
        elif len(value) > limit:
            errors.append(f"suno.{key} is {len(value)} chars, max {limit}")
    if instrumental is True:
        if str(suno.get("lyrics") or "").strip():
            errors.append("suno.lyrics must be empty when suno.instrumental is true")
        if "vocal_gender" in suno:
            errors.append("suno.vocal_gender must be unset when suno.instrumental is true")
    if len(str(suno.get("exclude_styles") or "")) > STYLES_MAX:
        errors.append(f"suno.exclude_styles is longer than {STYLES_MAX} chars")
    if "vocal_gender" in suno and suno["vocal_gender"] not in VOCAL_GENDERS:
        errors.append(f"suno.vocal_gender must be one of {sorted(VOCAL_GENDERS)}")
    for key in ("weirdness", "style_influence"):
        if key in suno and not _is_percent(suno[key]):
            errors.append(f"suno.{key} must be an integer 0-100")
    if "variety" in suno and suno["variety"] not in VARIETY_VALUES:
        errors.append(f"suno.variety must be one of {sorted(VARIETY_VALUES)}")
    if data["status"] not in STATUSES:
        errors.append(f"status must be one of {list(STATUSES)}")
    kept = data.get("kept") or {}
    if data["status"] in ("downloaded", "filed") and not kept.get("downloaded_at"):
        errors.append(f"status {data['status']} needs kept.downloaded_at")
    if data["status"] == "filed" and not kept.get("file"):
        errors.append("status filed needs kept.file")
    text = f"{data['title']}\n{suno.get('lyrics') or ''}"
    for name in private_names:
        if re.search(rf"\b{re.escape(name)}\b", text, re.IGNORECASE):
            errors.append(f"private name '{name}' appears in the song")
    return errors
