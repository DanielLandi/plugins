import re
from pathlib import Path

from mutagen.id3 import APIC, ID3, ID3NoHeaderError, TALB, TDRC, TIT2, TPE1, TXXX, USLT

_SECTION_TAG = re.compile(r"^\s*\[[^\]]*\]\s*$")


def display_lyrics(lyrics: str) -> str:
    lines = [line.rstrip() for line in lyrics.splitlines() if not _SECTION_TAG.match(line)]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _is_c2pa(frame) -> bool:
    return frame.mime == "application/c2pa" or frame.desc.startswith("c2pa")


def write_tags(mp3: Path, spec: dict, artist: str, year: int, cover: Path | None = None) -> None:
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
    elif cover is not None:
        mime = "image/png" if cover.suffix.lower() == ".png" else "image/jpeg"
        tags.add(APIC(encoding=3, mime=mime, type=3, desc="Cover", data=cover.read_bytes()))

    suno = spec["suno"]
    tags.add(TIT2(encoding=3, text=spec["title"]))
    tags.add(TPE1(encoding=3, text=artist))
    tags.add(TALB(encoding=3, text=spec["title"]))  # each song is its own single
    tags.add(TDRC(encoding=3, text=str(year)))
    if not suno.get("instrumental"):
        tags.add(USLT(encoding=3, lang="eng", desc="", text=display_lyrics(suno["lyrics"])))

    hidden = {
        "SPEC_ID": spec["id"],
        "SUNO_URL": (spec.get("kept") or {}).get("take_url"),
        "KIND": spec["kind"],
        "GENERATOR": f"Suno {suno['model']}",
    }
    for desc, value in hidden.items():
        if value:
            tags.add(TXXX(encoding=3, desc=desc, text=value))
    tags.save(mp3, v2_version=4)
