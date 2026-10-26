"""Marks, wordmarks, lockups and the construction diagram for Lembas and Ithildin."""
from lib import (ARC_R, C, GAP, LEAF_H, LEAF_L, R2, S, Leaf, n, render, svg, text_path,
                 wordmark, write)

# Colour schemes: (mark colour, word colour). "color" is for light grounds.
SCHEMES = {
    "lembas": {
        "color": (C["gilt"], C["ink"]),
        "color-dark": (C["mallorn-gold"], C["waybread"]),
        "black": ("#000000", "#000000"),
        "white": ("#FFFFFF", "#FFFFFF"),
    },
    "ithildin": {
        "color": (C["starlight"], C["ink"]),
        "color-dark": (C["ithildin"], C["waybread"]),
        "black": ("#000000", "#000000"),
        "white": ("#FFFFFF", "#FFFFFF"),
    },
}
GROUND = {"color": C["waybread"], "color-dark": C["anduin-night"], "black": "#FFFFFF", "white": "#0E1719"}

ITH_STROKE = 1.6        # outline and midrib, in grid units
ITH_VEIN = 1.2
SMALL_K = 1.2           # optical size for 32 px and below: leaf 20% larger
SMALL_GAP = 4.5         # and a heavier break, so it survives at 16 px
ITH_SMALL_STROKE = 3.0


# ---------------------------------------------------------------- mark bodies
def lembas_body(leaf: Leaf, color: str, gap: float = GAP) -> str:
    return f'<path fill="{color}" d="{leaf.halves(gap)}"/>'


def ithildin_body(leaf: Leaf, color: str, small: bool = False) -> str:
    u = leaf.unit
    if small:
        w = ITH_SMALL_STROKE * u
        return (f'<path stroke="{color}" stroke-width="{n(w)}" stroke-linejoin="round" '
                f'stroke-linecap="round" d="{leaf.outline()}{leaf.midrib(5)}"/>')
    return (f'<path stroke="{color}" stroke-width="{n(ITH_STROKE * u)}" stroke-linejoin="round" '
            f'stroke-linecap="round" d="{leaf.outline()}{leaf.midrib(3.2)}"/>'
            f'<path stroke="{color}" stroke-width="{n(ITH_VEIN * u)}" stroke-linecap="round" '
            f'stroke-linejoin="round" d="{leaf.veins()}"/>')


def body(brand: str, leaf: Leaf, color: str, small: bool = False) -> str:
    if brand == "lembas":
        return lembas_body(leaf, color, SMALL_GAP if small else GAP)
    return ithildin_body(leaf, color, small)


# ---------------------------------------------------------------- lockups
WM_SIZE = 100
ASC = 72.5   # ink height of both words above the baseline at WM_SIZE


def horizontal(brand: str, scheme: str) -> str:
    mark_c, word_c = SCHEMES[brand][scheme]
    name = brand.capitalize()
    hm = ASC * 1.3                                # leaf bbox side
    size = hm * S / (LEAF_L * R2)                 # its 48-grid box
    pad = (size - hm) / 2
    base = 100.0
    leaf = Leaf(-pad, base - ASC / 2 - size / 2, size)
    gap = hm * 0.34
    d, (l, t, r, b) = wordmark(name, WM_SIZE, 0, base)
    shift = hm + gap - l
    d, (l, t, r, b) = wordmark(name, WM_SIZE, shift, base)
    lt = leaf.bbox()
    top, bottom = min(t, lt[1]), max(b, lt[3])
    w = r
    # re-anchor so the box starts at 0, 0
    leaf = Leaf(-pad, base - ASC / 2 - size / 2 - top, size)
    d, _ = wordmark(name, WM_SIZE, shift, base - top)
    h = bottom - top
    return svg(w, h, body(brand, leaf, mark_c) + f'<path fill="{word_c}" d="{d}"/>',
               f"{name}")


def stacked(brand: str, scheme: str) -> str:
    mark_c, word_c = SCHEMES[brand][scheme]
    name = brand.capitalize()
    _, (l, t, r, b) = wordmark(name, WM_SIZE, 0, 0)
    ww = r - l
    hm = ASC * 1.7
    size = hm * S / (LEAF_L * R2)
    pad = (size - hm) / 2
    gap = hm * 0.28
    w = ww
    leaf = Leaf(w / 2 - size / 2, -pad, size)
    base = hm + gap - t                       # t is negative: ink above the baseline
    d, _ = wordmark(name, WM_SIZE, -l, base)
    h = base + b
    return svg(w, h, body(brand, leaf, mark_c) + f'<path fill="{word_c}" d="{d}"/>',
               f"{name}")


def word_only(brand: str, scheme: str) -> str:
    _, word_c = SCHEMES[brand][scheme]
    name = brand.capitalize()
    _, (l, t, r, b) = wordmark(name, WM_SIZE, 0, 0)
    d, _ = wordmark(name, WM_SIZE, -l, -t)
    return svg(r - l, b - t, f'<path fill="{word_c}" d="{d}"/>', f"{name}")


def mark(brand: str, scheme: str, small: bool = False) -> str:
    mark_c, _ = SCHEMES[brand][scheme]
    leaf = Leaf(0, 0, S, SMALL_K if small else 1.0)
    return svg(S, S, body(brand, leaf, mark_c, small), brand.capitalize())


# ---------------------------------------------------------------- construction
def construction() -> str:
    k, o = 10, 60                     # 10 px per unit, 60 px margin
    W = S * k + 2 * o + 300
    H = S * k + 2 * o
    g = C["anduin-night"]
    line, strong, guide = "#24363A", "#35504F", C["silver-bark"]
    parts = [f'<rect width="{W}" height="{H}" fill="{g}"/>',
             f'<clipPath id="grid"><rect x="{o}" y="{o}" width="{S * k}" height="{S * k}"/></clipPath>']
    for i in range(0, S + 1, 4):
        c = strong if i % 12 == 0 else line
        x = o + i * k
        parts.append(f'<path stroke="{c}" d="M{x} {o}V{o + S * k}M{o} {x}H{o + S * k}"/>')
    # the leaf
    leaf = Leaf(o, o, S * k)
    parts.append(f'<path fill="{C["mallorn-gold"]}" d="{leaf.halves()}"/>')
    # the two construction circles
    parts.append(f'<g clip-path="url(#grid)" stroke="{guide}" stroke-width="1.25" stroke-dasharray="6 6">'
                 f'<circle cx="{o}" cy="{o}" r="{ARC_R * k}"/>'
                 f'<circle cx="{o + S * k}" cy="{o + S * k}" r="{ARC_R * k}"/></g>')
    # radius callouts
    parts.append(f'<path stroke="{guide}" stroke-width="1.25" d="M{o} {o}L{n(o + ARC_R * k / R2)} {n(o + ARC_R * k / R2)}"/>')
    parts.append(f'<circle cx="{o}" cy="{o}" r="4" fill="{guide}"/><circle cx="{o + S * k}" cy="{o + S * k}" r="4" fill="{guide}"/>')
    # midrib diagonal
    parts.append(f'<path stroke="{C["ithildin"]}" stroke-width="1" stroke-dasharray="2 5" d="M{o} {o + S * k}L{o + S * k} {o}"/>')
    # tips
    for u in (-leaf.L, leaf.L):
        x, y = leaf.xy(u, 0)
        parts.append(f'<circle cx="{n(x)}" cy="{n(y)}" r="5" stroke="{C["ithildin"]}" stroke-width="1.5"/>')
    # annotations
    mono, sans = "JBMono-Regular", "Inter-Medium"
    ax = o + S * k + 40

    def label(t, x, y, font=mono, size=15, col=C["silver-bark"]):
        d, _ = text_path(t, font, size, x, y)
        parts.append(f'<path fill="{col}" d="{d}"/>')

    label("Construction", ax, o + 20, sans, 22, C["waybread"])
    tip = S / 2 - LEAF_L / R2
    rows = [
        ("Grid", "48 × 48, major line every 12"),
        ("Arcs", f"two circles, r = {ARC_R:g}"),
        ("Centres", "opposite corners (0,0) (48,48)"),
        ("Leaf", f"their overlap; tips ≈ ({tip:.1f}, {S - tip:.1f})"),
        ("Length", f"{2 * LEAF_L:.1f} units at 45°"),
        ("Width", f"{2 * LEAF_H:.1f} units"),
        ("Break", f"{GAP:g} units = 1/16 of the grid"),
        ("Small", f"≤ 32 px: leaf ×{SMALL_K}, break {SMALL_GAP:g}"),
    ]
    y = o + 70
    for a, b in rows:
        label(a.upper(), ax, y, mono, 12, C["mallorn-gold"])
        label(b, ax, y + 22, mono, 14)
        y += 56
    label(f"r {ARC_R:g}", o + 150, o + 128, mono, 14, guide)
    return svg(W, H, "".join(parts), "Lembas mark construction")


# ---------------------------------------------------------------- pair
def pair() -> str:
    """Lembas and Ithildin side by side on night: the family lockup."""
    import re
    a = horizontal("lembas", "color-dark")
    b = horizontal("ithildin", "color-dark")
    wa = float(re.search(r'width="([\d.]+)"', a).group(1))
    wb = float(re.search(r'width="([\d.]+)"', b).group(1))
    h = float(re.search(r'height="([\d.]+)"', a).group(1))
    pad, gap = 80, 120
    W, H = pad * 2 + wa + gap + wb, h + pad * 2
    inner_a = re.search(r"</title>\n(.*)\n</svg>", a, re.S).group(1)
    inner_b = re.search(r"</title>\n(.*)\n</svg>", b, re.S).group(1)
    # re-place each lockup by rebuilding at an offset: shift path coordinates
    from lib import shift_path
    def place(inner, dx, dy):
        return re.sub(r'd="([^"]+)"', lambda m: f'd="{shift_path(m.group(1), dx, dy)}"', inner)
    rule_x = pad + wa + gap / 2
    body_ = (f'<rect width="{n(W)}" height="{n(H)}" rx="24" fill="{C["anduin-night"]}"/>'
             + place(inner_a, pad, pad)
             + f'<path stroke="{C["silver-bark"]}" stroke-opacity=".35" d="M{n(rule_x)} {pad}V{n(pad + h)}"/>'
             + place(inner_b, pad + wa + gap, pad))
    return svg(W, H, body_, "Lembas and Ithildin")


if __name__ == "__main__":
    out = []
    for brand in ("lembas", "ithildin"):
        for scheme in SCHEMES[brand]:
            suffix = "" if scheme == "color-dark" and brand == "lembas" else f"-{scheme}"
            out.append(write(f"logo/{brand}-mark-{scheme}.svg", mark(brand, scheme)))
            out.append(write(f"logo/{brand}-mark-small-{scheme}.svg", mark(brand, scheme, True)))
            out.append(write(f"logo/{brand}-wordmark-{scheme}.svg", word_only(brand, scheme)))
            out.append(write(f"logo/{brand}-horizontal-{scheme}.svg", horizontal(brand, scheme)))
            out.append(write(f"logo/{brand}-stacked-{scheme}.svg", stacked(brand, scheme)))
    # canonical names asked for in the brief
    write("logo/lembas-mark.svg", mark("lembas", "color-dark"))
    write("logo/lembas-wordmark.svg", word_only("lembas", "color"))
    write("logo/ithildin-mark.svg", mark("ithildin", "color-dark"))
    write("logo/ithildin-wordmark.svg", word_only("ithildin", "color"))
    write("logo/lembas-mark-construction.svg", construction())
    write("logo/lembas-ithildin-pair.svg", pair())
    print(len(out) + 6, "files")
