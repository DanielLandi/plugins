"""The four CC0 VRoid β sample avatars (AvatarSample_1–4, VRoid Project / pixiv Inc.) for the vrm character engine.

They are never bundled with the plugin: `doctor` (or `music-video avatars install`) downloads them once into the
install folder and keeps a file only when its sha256 matches the pinned one. pixiv offers no download without a
login (VRoid Hub), so they come from OpenGameArt's CC0 mirror of the same files; `avatars add <file>` takes a copy
the user downloaded themselves when it is byte-identical. Scenes import them as `@mv/avatars/<file>`.
"""
import hashlib
import json
import os
import re
import shutil
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .errors import MVError
from .workspace import install_dir

Fetch = Callable[[str, Path], None]
CC0_PAGE = "https://vroid.pixiv.help/hc/en-us/articles/4402614652569"
MIRROR_PAGE = "https://opengameart.org/content/vroid-studio-cc0-models"
VERIFIED = ".verified.json"  # size and mtime of files whose sha256 already matched: no rehash on every render
CHUNK = 1 << 20


@dataclass(frozen=True)
class Avatar:
    key: str
    file: str          # the name in the install folder, imported as @mv/avatars/<file>
    name: str          # how pixiv names it
    zip_url: str
    zip_sha256: str
    member: str        # the .vrm inside the zip
    sha256: str        # of the .vrm
    size: int
    page: str          # pixiv's page saying it is CC0


def _sample(n: int, letter: str, zip_name: str, zip_sha: str, sha: str, size: int, article: str) -> Avatar:
    return Avatar(key=f"vroid-sample-{n}", file=f"vroid-sample-{n}.vrm", name=f"β Ver AvatarSample_{n}",
                  zip_url=f"https://opengameart.org/sites/default/files/{zip_name}", zip_sha256=zip_sha,
                  member=f"AvatarSample_{letter}.vrm", sha256=sha, size=size,
                  page=f"https://vroid.pixiv.help/hc/en-us/articles/{article}")


# The β samples were called AvatarSample_D–G before; the mirror keeps those file names.
PINNED: tuple[Avatar, ...] = (
    _sample(1, "D", "avatarsample_d_0.zip", "311a383b0b63b55102c82efa5ab2afec0dfcccc1cc6fa2db10fd5583981b3167",
            "9adf1b44e959d2688d62c2dd558e74315d6aa40e3bf8d281390b7a85dc0df9b7", 16851352, "360012381793"),
    _sample(2, "E", "avatarsample_e.zip", "3b6808e241102221625380d3e5d6911efb5cd484f290bfa16955e1b65856b6b1",
            "aea824cc43a95dd022a57d460ed901534a45fc2ac195f26ffc4d0d5beb0d7911", 17936516, "360014900273"),
    _sample(3, "F", "avatarsample_f.zip", "e187569ebb25b34800b28daf6d75680f8b8945811b368d8478660d8f2798ebd1",
            "d8eff1ed09b41afb94e30da27997560fb901dde925c813f835ab1986708521bb", 14198800, "360014900113"),
    _sample(4, "G", "avatarsample_g.zip", "3dc643aa55bf565512aa445775943b3ee93c71dc157b8ea8394863d494811b34",
            "ad5750ce944b708155abb7ac6807e19d7f5e73a939f0ee32daf0539acfca57c0", 15321932, "360014900233"),
)
AVATARS: tuple[Avatar, ...] = PINNED


def avatar_dir() -> Path:
    return install_dir() / "avatars"


def fetch_url(url: str, dest: Path) -> None:
    """Download url to dest (no login, no cookies)."""
    from urllib.request import Request, urlopen
    req = Request(url, headers={"User-Agent": "music-video-plugin"})
    with urlopen(req, timeout=60) as res, open(dest, "wb") as out:
        shutil.copyfileobj(res, out, CHUNK)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while block := f.read(CHUNK):
            h.update(block)
    return h.hexdigest()


def _verified(folder: Path) -> dict:
    try:
        return json.loads((folder / VERIFIED).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _stamp(path: Path) -> list[int]:
    st = path.stat()
    return [st.st_size, st.st_mtime_ns]


def _remember(folder: Path, a: Avatar, path: Path) -> None:
    known = _verified(folder)
    known[a.file] = {"stamp": _stamp(path), "sha256": a.sha256}
    try:
        (folder / VERIFIED).write_text(json.dumps(known), encoding="utf-8")
    except OSError:
        pass  # only a cache: the next check hashes again


def state(a: Avatar, folder: Path | None = None) -> str:
    """ok (present, checksum matches), missing, or bad (present but not the pinned file)."""
    folder = folder or avatar_dir()
    path = folder / a.file
    if not path.is_file():
        return "missing"
    if path.stat().st_size != a.size:
        return "bad"
    seen = _verified(folder).get(a.file)
    if seen and seen.get("stamp") == _stamp(path) and seen.get("sha256") == a.sha256:
        return "ok"
    if _sha256(path) != a.sha256:
        return "bad"
    _remember(folder, a, path)
    return "ok"


def _sources(folder: Path) -> None:
    rows = "\n".join(f"| `{a.file}` | {a.name} | VRoid Project (pixiv Inc.) | {a.page} | {a.zip_url} |"
                     for a in _avatars())
    text = ("# Avatars: where they came from\n\n"
            f"CC0 1.0 (copyright waived by pixiv Inc.): {CC0_PAGE} and each model's page below. Downloaded by "
            f"music-video from the OpenGameArt CC0 mirror ({MIRROR_PAGE}), checked against pinned sha256. CC0 needs "
            "no credit; a video that uses one says so in its SOURCES.md anyway.\n\n"
            "| File | Model | Author | CC0 page | Downloaded from |\n|---|---|---|---|---|\n" + rows + "\n")
    (folder / "SOURCES.md").write_text(text, encoding="utf-8")


def _avatars() -> tuple[Avatar, ...]:
    return AVATARS


def _place(a: Avatar, vrm: Path, folder: Path) -> Path:
    """Move a checked .vrm into the folder under its install name (atomic on one volume)."""
    target = folder / a.file
    os.replace(vrm, target)
    _remember(folder, a, target)
    return target


def _extract(a: Avatar, zpath: Path, folder: Path) -> Path:
    part = folder / f".{a.file}.part"
    with zipfile.ZipFile(zpath) as z:
        part.write_bytes(z.read(a.member))  # under 25 MB
    return part


def download(a: Avatar, fetch: Fetch | None = None) -> Path:
    """Fetch one avatar's zip, check it, extract and check the .vrm, keep it. Nothing half-done is left behind."""
    fetch = fetch or fetch_url
    folder = avatar_dir()
    folder.mkdir(parents=True, exist_ok=True)
    zpart, vpart = folder / f".{a.key}.zip.part", folder / f".{a.file}.part"
    try:
        fetch(a.zip_url, zpart)
        if _sha256(zpart) != a.zip_sha256:
            raise MVError(f"{a.file}: the download from {a.zip_url} is not the pinned file (checksum differs); "
                          "nothing was kept")
        _extract(a, zpart, folder)
        if vpart.stat().st_size != a.size or _sha256(vpart) != a.sha256:
            raise MVError(f"{a.file}: the model inside {a.zip_url} is not the pinned file; nothing was kept")
        return _place(a, vpart, folder)
    except (OSError, zipfile.BadZipFile, KeyError) as e:
        raise MVError(f"{a.file}: could not download {a.zip_url} ({e})") from e
    finally:
        zpart.unlink(missing_ok=True)
        vpart.unlink(missing_ok=True)


def install(fetch: Fetch | None = None) -> list[str]:
    """Download every avatar not already in place. Raises MVError naming the ones that failed, after trying all."""
    lines, failed = [], []
    for a in _avatars():
        if state(a) == "ok":
            continue
        try:
            download(a, fetch or fetch_url)
            lines.append(f"ok   avatar {a.file} ({a.name}, CC0)")
        except MVError as e:
            failed.append(str(e))
    if any(state(a) == "ok" for a in _avatars()):
        _sources(avatar_dir())
    if failed:
        raise MVError("; ".join(failed))
    return lines


def add(file: Path) -> Avatar:
    """Copy a user-downloaded avatar (.vrm, or the mirror's zip) into the install folder when it is one of the
    pinned files."""
    file = file.expanduser()
    if not file.is_file():
        raise MVError(f"{file} does not exist")
    folder = avatar_dir()
    folder.mkdir(parents=True, exist_ok=True)
    digest = _sha256(file)
    for a in _avatars():
        if digest == a.sha256:
            part = folder / f".{a.file}.part"
            shutil.copyfile(file, part)
            _place(a, part, folder)
            _sources(folder)
            return a
        if digest == a.zip_sha256:
            _place(a, _extract(a, file, folder), folder)
            _sources(folder)
            return a
    names = ", ".join(f"{a.name} ({a.member})" for a in _avatars())
    raise MVError(f"{file.name} is not one of the pinned sample avatars ({names}): its checksum differs. Your own "
                  "CC0 or OFL .vrm files go in the video's folder instead, imported as './<file>.vrm'")


def status_lines() -> list[str]:
    return [f"{state(a):7} {a.file}  {a.name}" for a in _avatars()]


def doctor_lines(install_them: bool, fetch: Fetch | None = None) -> list[str]:
    """What doctor prints about the avatars. Never raises: they are optional (only a vrm video needs them)."""
    try:
        missing = [a for a in _avatars() if state(a) != "ok"]
        if not missing:
            return [f"ok   character avatars ({len(_avatars())} CC0 VRoid samples) in {avatar_dir()}"]
        if install_them:
            print(f"downloading the character avatars ({len(missing)} CC0 VRoid samples, about "
                  f"{sum(a.size for a in missing) // 1_000_000} MB, once)…", flush=True)
            try:
                return [*install(fetch), f"ok   character avatars in {avatar_dir()}"]
            except MVError as e:
                return [f"note the character avatars did not all download ({e}). They are only needed for vrm "
                        "character videos: run music-video avatars install later"]
        return [f"note {len(missing)} character avatars not installed (only vrm character videos need them): "
                "run music-video avatars install"]
    except Exception as e:  # noqa: BLE001 - doctor must never fail on the optional avatars
        return [f"note the character avatars could not be checked ({e}): run music-video avatars install"]


IMPORT_RE = re.compile(r"""["']@mv/avatars/([^"'/]+)["']""")


def imported(video_dir: Path) -> set[str]:
    """The installed avatars a video's code imports (`@mv/avatars/<file>`)."""
    found: set[str] = set()
    for f in video_dir.rglob("*"):
        if f.suffix in (".ts", ".tsx") and f.is_file() and "node_modules" not in f.parts:
            found |= set(IMPORT_RE.findall(f.read_text(encoding="utf-8", errors="replace")))
    return found


def check_video(video_dir: Path) -> None:
    """Before a render: every avatar the video imports is installed and intact, or one line says how to get it."""
    known = {a.file: a for a in _avatars()}
    folder = avatar_dir()
    used = imported(video_dir)
    gone = sorted(f for f in used if f not in known or state(known[f], folder) != "ok")
    if used and not gone:
        credit_avatars(video_dir)
    if gone:
        unknown = [f for f in gone if f not in known]
        hint = (f" ({', '.join(unknown)} is not one of the samples: they are {', '.join(sorted(known))})"
                if unknown else "")
        raise MVError(f"this video uses character avatars that are not installed: {', '.join(gone)}{hint}. Run "
                      "music-video avatars install (or music-video avatars add <file> with a copy you downloaded)")


CREDIT_MARK = "vroid-sample"


def credit_avatars(video_dir: Path) -> None:
    """The video's SOURCES.md names the samples' CC0 source (once): when a bake-off adds a vrm take, and when a
    render finds the video importing them."""
    path = video_dir / "SOURCES.md"
    text = path.read_text(encoding="utf-8") if path.is_file() else "| Asset | Source | Licence |\n|---|---|---|\n"
    if CREDIT_MARK in text or any(a.file in text for a in _avatars()):
        return
    files = ", ".join(f"`{a.file}`" for a in _avatars())
    row = (f"| Characters (vrm): {files} | VRoid β AvatarSample_1–4 by VRoid Project (pixiv Inc.), {CC0_PAGE}; "
           "installed by music-video avatars install | CC0 |\n")
    path.write_text(text.rstrip("\n") + "\n" + row, encoding="utf-8")
