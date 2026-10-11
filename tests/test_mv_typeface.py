import json

from conftest import REPO

FONT = REPO / "music-video" / "studio" / "kit" / "three" / "fonts" / "outfit-800.json"


def test_3d_typeface_covers_portuguese_and_spanish_capitals():
    glyphs = json.loads(FONT.read_text(encoding="utf-8"))["glyphs"]
    missing = [c for c in "ÁÀÂÃÉÊÍÓÔÕÚÜÇÑáàâãéêíóôõúüçñ" if c not in glyphs]
    assert missing == []
