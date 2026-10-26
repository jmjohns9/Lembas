"""Shared helpers for the Lembas brand build: geometry, outlined type, color, rendering.

Every SVG in brand/ is generated from here so the marks stay identical across files.
Text is converted to outlines because GitHub serves SVGs through <img>, which loads no web fonts.
"""
from __future__ import annotations

import math
import os

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

BRAND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS = os.path.join(BRAND, "fonts")

# ---------------------------------------------------------------- palette
PALETTE = {
    # token: (name, hex, role)
    "mallorn-gold": ("Mallorn Gold", "#C9A44C", "Accent on dark. Gilding: marks, rules, one highlight"),
    "gilt": ("Gilt", "#7D5F16", "Gold for text and marks on light surfaces"),
    "lorien-green": ("Lórien Green", "#3E5C47", "Secondary; links and badges on light"),
    "lorien-leaf": ("Lórien Leaf", "#8FB59A", "Green on dark surfaces"),
    "silver-bark": ("Silver Bark", "#B9C4BE", "Borders and dividers on light; secondary text on dark"),
    "ithildin": ("Ithildin", "#DCE6EE", "Ithildin sub-brand; moonlit highlights on dark"),
    "starlight": ("Starlight", "#4E6479", "Ithildin on light surfaces"),
    "anduin-night": ("Anduin Night", "#0E1719", "Dark background"),
    "anduin-deep": ("Anduin Deep", "#172427", "Raised surfaces on dark"),
    "waybread": ("Waybread", "#F4EEE2", "Light background"),
    "waybread-deep": ("Waybread Deep", "#E9E1D1", "Raised surfaces and code on light"),
    "ink": ("Ink", "#1B2422", "Body text on light"),
    "moss": ("Moss", "#56625C", "Secondary text on light"),
}
C = {k: v[1] for k, v in PALETTE.items()}


def _lin(c: float) -> float:
    c /= 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(hex_: str) -> float:
    h = hex_.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def contrast(a: str, b: str) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


# ---------------------------------------------------------------- numbers
def n(v: float) -> str:
    """Format a coordinate: at most 2 decimals, no trailing zeros."""
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


# ---------------------------------------------------------------- the leaf
# The mark lives on a 48-unit square. The leaf is the overlap of two circles of
# radius 42 centred on opposite corners of that square, (0, 0) and (48, 48).
# Their overlap is a vesica lying at 45°, tips near (6.5, 41.5) and (41.5, 6.5).
# Geometry is computed in the leaf's own frame: u runs along the midrib from base
# (lower-left) to tip (upper-right), v runs across it toward the lower-right.
S = 48
R2 = math.sqrt(2)
ARC_R = 42.0
_D = S / 2 * R2                       # corner to centre, 33.94
LEAF_L = math.sqrt(ARC_R ** 2 - _D ** 2)  # half length, 21.17
LEAF_H = ARC_R - _D                   # half width, 6.06
GAP = 3.0                             # the break, 1/16 of the grid


class Leaf:
    """A leaf placed in a square box at (x, y) of side `size`, optionally enlarged by `k`."""

    def __init__(self, x: float = 0, y: float = 0, size: float = S, k: float = 1.0):
        s = size / S
        self.unit = s
        self.cx, self.cy = x + size / 2, y + size / 2
        self.L, self.h = LEAF_L * k * s, LEAF_H * k * s
        self.R = (self.L ** 2 + self.h ** 2) / (2 * self.h)

    def xy(self, u: float, v: float):
        return self.cx + (u + v) / R2, self.cy + (v - u) / R2

    def p(self, u: float, v: float) -> str:
        x, y = self.xy(u, v)
        return f"{n(x)} {n(y)}"

    def bbox(self):
        (x1, y1), (x2, y2) = self.xy(-self.L, 0), self.xy(self.L, 0)
        return x1, y2, x2, y1  # left, top, right, bottom

    def edge(self, u: float) -> float:
        return math.sqrt(max(self.R ** 2 - u ** 2, 0)) - (self.R - self.h)

    def outline(self) -> str:
        R, L = n(self.R), self.L
        return (f"M{self.p(-L, 0)}A{R} {R} 0 0 0 {self.p(L, 0)}"
                f"A{R} {R} 0 0 0 {self.p(-L, 0)}Z")

    def halves(self, gap: float = GAP) -> str:
        """The leaf broken once along its midrib, halves `gap` grid units apart."""
        g = gap * self.unit / 2
        u1 = math.sqrt(self.R ** 2 - (g + self.R - self.h) ** 2)
        R = n(self.R)
        lower = f"M{self.p(u1, g)}A{R} {R} 0 0 1 {self.p(-u1, g)}Z"
        upper = f"M{self.p(-u1, -g)}A{R} {R} 0 0 1 {self.p(u1, -g)}Z"
        return lower + upper

    def midrib(self, trim: float) -> str:
        t = trim * self.unit
        return f"M{self.p(-self.L + t, 0)}L{self.p(self.L - t, 0)}"

    def veins(self, at=(-0.3, 0.1, 0.45), margin: float = 1.6) -> str:
        """Lateral veins from the midrib at 45° toward the tip.

        In the page they come out exactly horizontal and vertical, so the vein
        system sits on the grid.
        """
        m = margin * self.unit
        d = ""
        for f in at:
            u0 = f * self.L
            t = 0.0
            step = self.h / 400
            while t < self.h * 3 and t < self.edge(u0 + t):
                t += step
            t -= m
            d += f"M{self.p(u0 + t, -t)}L{self.p(u0, 0)}L{self.p(u0 + t, t)}"
        return d


# ---------------------------------------------------------------- outlined type
_FONTS: dict[str, tuple] = {}


def _font(name: str):
    if name not in _FONTS:
        path = os.path.join(FONTS, name + ".ttf")
        blob = hb.Blob.from_file_path(path)
        face = hb.Face(blob)
        _FONTS[name] = (TTFont(path), hb.Font(face), face.upem)
    return _FONTS[name]


def shape(text: str, font: str, size: float, tracking: float = 0.0, features=None):
    """Shape `text` and return [(glyph_name, x_offset_in_px)], total advance in px."""
    tt, hbf, upem = _font(font)
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(hbf, buf, features or {"kern": True, "liga": True})
    order = tt.getGlyphOrder()
    s = size / upem
    x, out = 0.0, []
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        out.append((order[info.codepoint], x + pos.x_offset * s))
        x += pos.x_advance * s + tracking * size
    return out, x - tracking * size


def glyph_path(font: str, glyph: str, size: float, x: float, y: float) -> str:
    tt, _, upem = _font(font)
    gs = tt.getGlyphSet()
    s = size / upem
    pen = SVGPathPen(gs, ntos=n)
    gs[glyph].draw(TransformPen(pen, (s, 0, 0, -s, x, y)))
    return pen.getCommands()


def text_path(text: str, font: str, size: float, x: float = 0, y: float = 0,
              tracking: float = 0.0, anchor: str = "start") -> tuple[str, float]:
    """Outline `text` at baseline (x, y). Returns (path d, advance width)."""
    feats = {"kern": True, "liga": True, "lnum": font.startswith("Cormorant")}
    glyphs, width = shape(text, font, size, tracking, feats)
    if anchor == "middle":
        x -= width / 2
    elif anchor == "end":
        x -= width
    d = "".join(glyph_path(font, g, size, x + gx, y) for g, gx in glyphs)
    return d, width


def cap_height(font: str, size: float) -> float:
    tt, _, upem = _font(font)
    return tt["OS/2"].sCapHeight * size / upem


def x_height(font: str, size: float) -> float:
    tt, _, upem = _font(font)
    return tt["OS/2"].sxHeight * size / upem


# ---------------------------------------------------------------- files
def svg(w: float, h: float, body: str, title: str | None = None, vb: str | None = None) -> str:
    vb = vb or f"0 0 {n(w)} {n(h)}"
    t = f"<title>{title}</title>" if title else ""
    role = ' role="img"' if title else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{n(w)}" height="{n(h)}" '
            f'viewBox="{vb}" fill="none"{role}>{t}\n{body}\n</svg>\n')


def write(path: str, content: str) -> str:
    full = os.path.join(BRAND, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w") as f:
        f.write(content)
    return full


def render(svg_rel: str, png_rel: str, width: int | None = None, background: str | None = None) -> str:
    import resvg_py
    src = os.path.join(BRAND, svg_rel)
    out = os.path.join(BRAND, png_rel)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    kw = {"svg_path": src, "font_dirs": [FONTS], "skip_system_fonts": True}
    if width:
        kw["width"] = width
    if background:
        kw["background"] = background
    data = resvg_py.svg_to_bytes(**kw)
    with open(out, "wb") as f:
        f.write(bytes(data))
    return out


# ---------------------------------------------------------------- the wordmarks
# Both names are set in Cormorant Garamond SemiBold, tracked -0.008 em, with
# L–e closed up a further 0.03 em. Each name carries one drawn detail:
#   Lembas    the counter of the "a" is a leaf at the mark's 45°
#   Ithildin  the dot of the last "i" is a four-point star (ithil-din, moon-star)
WM_FONT = "Cormorant-SemiBold"
WM_TRACK = -0.008
WM_PAIRS = {("L", "e"): -0.03}


def _vesica(pen, p1, p2, h, reverse=False):
    """Draw a vesica between p1 and p2 (font units) as four cubic arcs."""
    (x1, y1), (x2, y2) = p1, p2
    L = math.hypot(x2 - x1, y2 - y1) / 2
    R = (L * L + h * h) / (2 * h)
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    ux, uy = (x2 - x1) / (2 * L), (y2 - y1) / (2 * L)
    vx, vy = -uy, ux

    def arc(side):
        ox, oy = cx - side * vx * (R - h), cy - side * vy * (R - h)
        a0, a1 = math.atan2(y1 - oy, x1 - ox), math.atan2(y2 - oy, x2 - ox)
        da = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
        segs = []
        for i in range(2):
            s, e = a0 + da * i / 2, a0 + da * (i + 1) / 2
            k = 4 / 3 * math.tan((e - s) / 4) * R
            ps = (ox + R * math.cos(s), oy + R * math.sin(s))
            pe = (ox + R * math.cos(e), oy + R * math.sin(e))
            segs.append((ps, (ps[0] - k * math.sin(s), ps[1] + k * math.cos(s)),
                         (pe[0] + k * math.sin(e), pe[1] - k * math.cos(e)), pe))
        return segs

    path = arc(1) + [(pe, c2, c1, ps) for ps, c1, c2, pe in reversed(arc(-1))]
    if reverse:
        path = [(pe, c2, c1, ps) for ps, c1, c2, pe in reversed(path)]
    pen.moveTo(path[0][0])
    for _, c1, c2, pe in path:
        pen.curveTo(c1, c2, pe)
    pen.closePath()


def _contours(glyphset, name):
    from fontTools.pens.recordingPen import RecordingPen
    rp = RecordingPen()
    glyphset[name].draw(rp)
    out, cur = [], []
    for op, args in rp.value:
        cur.append((op, args))
        if op in ("closePath", "endPath"):
            out.append(cur)
            cur = []
    return out


def _replay(pen, contour):
    for op, args in contour:
        getattr(pen, op)(*args)


def _leaf_a(pen, gs):
    """Cormorant 'a' with the bowl rebuilt solid and a leaf cut as its counter."""
    _replay(pen, _contours(gs, "a")[0])          # stem and arch, unchanged
    pen.moveTo((129, -7))                         # outer edge of the original bowl
    pen.qCurveTo((87, -7), (46, 33), (46, 64))
    pen.qCurveTo((46, 92), (76, 127), (130, 150), (163, 162))
    pen.lineTo((270, 202))
    pen.lineTo((290, 202))                        # closed into the stem
    pen.lineTo((290, 40))
    pen.lineTo((216, 24))
    pen.qCurveTo((193, 8), (154, -7), (129, -7))
    pen.closePath()
    _vesica(pen, (140, 50), (258, 170), 35, reverse=True)   # the leaf counter


def _star_i(pen, gs):
    """Cormorant 'i' with its dot replaced by a four-point star."""
    _replay(pen, _contours(gs, "dotlessi")[0])
    cx, cy, r, w = 135, 556, 92, 14
    pts = [(cx, cy + r), (cx + r, cy), (cx, cy - r), (cx - r, cy)]
    ctl = [(cx + w, cy + w), (cx + w, cy - w), (cx - w, cy - w), (cx - w, cy + w)]
    pen.moveTo(pts[0])                            # clockwise, like the font's outer contours
    for i in range(4):
        pen.qCurveTo(ctl[i], pts[(i + 1) % 4])
    pen.closePath()


def wordmark(name: str, size: float, x: float = 0, y: float = 0):
    """Outline the Lembas or Ithildin wordmark at baseline (x, y).

    Returns (path d, (left, top, right, bottom)) with the box measured from the ink.
    """
    from fontTools.pens.boundsPen import BoundsPen
    tt, _, upem = _font(WM_FONT)
    gs = tt.getGlyphSet()
    glyphs, _ = shape(name, WM_FONT, size, WM_TRACK)
    s = size / upem
    pen = SVGPathPen(gs, ntos=n)
    bounds = BoundsPen(gs)
    shift, prev = 0.0, None
    last_i = max(i for i, (g, _) in enumerate(glyphs) if g == "i") if name == "Ithildin" else -1
    for i, (g, gx) in enumerate(glyphs):
        shift += WM_PAIRS.get((prev, g), 0) * size
        prev = g
        t = (s, 0, 0, -s, x + gx + shift, y)
        for p in (pen, bounds):
            tp = TransformPen(p, t)
            if name == "Lembas" and g == "a":
                _leaf_a(tp, gs)
            elif i == last_i:
                _star_i(tp, gs)
            else:
                gs[g].draw(tp)
    l, b, r, t = bounds.bounds  # y is already flipped, so "b" is the top
    return pen.getCommands(), (l, b, r, t)


# ---------------------------------------------------------------- path utilities
_ARGS = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "Q": 4, "S": 4, "T": 2, "A": 7, "Z": 0}


def map_path(d: str, fx, fy, scale: float = 1.0) -> str:
    """Apply fx/fy to every absolute coordinate in path `d` (uppercase commands only).

    `scale` is applied to arc radii. Used to place a finished path without a transform.
    """
    import re
    toks = re.findall(r"[A-Za-z]|-?\d*\.?\d+(?:e-?\d+)?", d)
    out, i, cmd = [], 0, None
    while i < len(toks):
        t = toks[i]
        if t.isalpha():
            cmd = t
            assert cmd == cmd.upper(), f"relative command {cmd} not supported"
            out.append(cmd)
            i += 1
            if cmd == "Z":
                continue
        k = _ARGS[cmd]
        a = [float(x) for x in toks[i:i + k]]
        i += k
        if cmd == "H":
            v = [fx(a[0])]
        elif cmd == "V":
            v = [fy(a[0])]
        elif cmd == "A":
            v = [a[0] * scale, a[1] * scale, a[2], a[3], a[4], fx(a[5]), fy(a[6])]
        else:
            v = [fx(c) if j % 2 == 0 else fy(c) for j, c in enumerate(a)]
        s = " ".join(n(x) for x in v)
        out.append(s if out[-1].isalpha() else " " + s)
    return "".join(out).replace(" -", "-")


def shift_path(d: str, dx: float, dy: float) -> str:
    return map_path(d, lambda x: x + dx, lambda y: y + dy)


def scale_path(d: str, s: float, dx: float = 0, dy: float = 0) -> str:
    return map_path(d, lambda x: x * s + dx, lambda y: y * s + dy, s)
