import re
from pathlib import Path

from mutagen.id3 import APIC, ID3, ID3NoHeaderError, TALB, TCON, TDRC, TIT2, TPE1, TXXX, USLT

from .spec import generator, is_instrumental, settings

_SECTION_TAG = re.compile(r"^\s*\[[^\]]*\]\s*$")


def display_lyrics(lyrics: str) -> str:
    lines = [line.rstrip() for line in lyrics.splitlines() if not _SECTION_TAG.match(line)]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _is_c2pa(frame) -> bool:
    return frame.mime == "application/c2pa" or frame.desc.startswith("c2pa")


def write_tags(mp3: Path, spec: dict, credit) -> None:
    """Tags from a Credit (albums.credit): artist, album, genre, year and the cover when the file has none."""
    try:
        tags = ID3(mp3)
    except ID3NoHeaderError:
        tags = ID3()
    art = tags.getall("APIC")
    # C2PA content credentials (AI provenance) stay: players never show them.
    credentials = [frame for frame in tags.getall("GEOB") if _is_c2pa(frame)]
    for key in list(tags.keys()):
        del tags[key]
    for frame in credentials:
        tags.add(frame)
    if art:
        for frame in art:
            tags.add(frame)
    elif credit.cover is not None and credit.cover.is_file():
        mime = "image/png" if credit.cover.suffix.lower() == ".png" else "image/jpeg"
        tags.add(APIC(encoding=3, mime=mime, type=3, desc="Cover", data=credit.cover.read_bytes()))

    gen = generator(spec)
    block = settings(spec)
    tags.add(TIT2(encoding=3, text=spec["title"]))
    tags.add(TPE1(encoding=3, text=credit.artist))
    tags.add(TALB(encoding=3, text=credit.album))
    if credit.genre:
        tags.add(TCON(encoding=3, text=credit.genre))
    tags.add(TDRC(encoding=3, text=str(credit.year)))
    if not is_instrumental(spec):
        tags.add(USLT(encoding=3, lang="eng", desc="", text=display_lyrics(block["lyrics"])))

    hidden = {
        "SPEC_ID": spec["id"],
        "TAKE_URL": (spec.get("kept") or {}).get("take_url"),
        "KIND": spec["kind"],
        "GENERATOR": f"{gen.capitalize()} {block.get('model', '')}".strip(),
    }
    for desc, value in hidden.items():
        if value:
            tags.add(TXXX(encoding=3, desc=desc, text=value))
    tags.save(mp3, v2_version=4)
