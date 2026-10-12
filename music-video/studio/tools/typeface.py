"""Convert an OFL TrueType font into three.js typeface JSON, for extruded 3D lyrics (FontLoader / TextGeometry).

    uv run --with fonttools python -I studio/tools/typeface.py <font.ttf> <out.json> [--weight 800]

A variable font is instanced at --weight first. Only printable ASCII, the Latin accented letters of Portuguese,
Spanish, French and German, and a few typographic marks are kept,
which is all the lyrics use and keeps the file small. Ship the font's OFL.txt next to the JSON.
"""
import argparse
import json
import sys

from fontTools.pens.basePen import BasePen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

CHARS = [chr(c) for c in range(0x20, 0x7F)] + list("’‘“”–—…") + list("ÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇÑ¡¿") + list("áàâãäéèêëíìîïóòôõöúùûüçñ")


class OutlinePen(BasePen):
    """Writes three's outline commands: m x y, l x y, q x y cx cy (end point first), b x y c1x c1y c2x c2y."""

    def __init__(self, glyph_set):
        super().__init__(glyph_set)
        self.out = []

    def _add(self, cmd, *pts):
        self.out.append(cmd)
        for x, y in pts:
            self.out += [str(round(x)), str(round(y))]

    def _moveTo(self, pt):
        self._add("m", pt)

    def _lineTo(self, pt):
        self._add("l", pt)

    def _qCurveToOne(self, pt1, pt2):
        self._add("q", pt2, pt1)

    def _curveToOne(self, pt1, pt2, pt3):
        self._add("b", pt3, pt1, pt2)

    def _closePath(self):
        pass


def main():
    p = argparse.ArgumentParser()
    p.add_argument("font")
    p.add_argument("out")
    p.add_argument("--weight", type=float, default=800)
    a = p.parse_args()
    font = TTFont(a.font)
    if "fvar" in font:
        font = instantiateVariableFont(font, {"wght": a.weight})
    cmap = font.getBestCmap()
    glyph_set = font.getGlyphSet()
    hmtx = font["hmtx"]
    glyphs = {}
    for ch in CHARS:
        name = cmap.get(ord(ch))
        if name is None:
            continue
        pen = OutlinePen(glyph_set)
        glyph_set[name].draw(pen)
        xs = [int(v) for i, v in enumerate(pen.out) if v.lstrip("-").isdigit()][0::2] or [0]
        glyphs[ch] = {"ha": hmtx[name][0], "x_min": min(xs), "x_max": max(xs), "o": " ".join(pen.out)}
    head, hhea = font["head"], font["hhea"]
    name = font["name"].getDebugName(1) or "font"
    data = {
        "glyphs": glyphs,
        "familyName": name,
        "ascender": hhea.ascent,
        "descender": hhea.descent,
        "underlinePosition": font["post"].underlinePosition,
        "underlineThickness": font["post"].underlineThickness,
        "boundingBox": {"xMin": head.xMin, "yMin": head.yMin, "xMax": head.xMax, "yMax": head.yMax},
        "resolution": head.unitsPerEm,
        "original_font_information": {"weight": a.weight, "license": "SIL Open Font License 1.1 (see OFL.txt)"},
    }
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(data, f, separators=(",", ":"))
    print(f"{a.out}: {len(glyphs)} glyphs", file=sys.stderr)


if __name__ == "__main__":
    main()
