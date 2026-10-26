"""GitHub social preview and README hero banners (light and dark).

All text is outlined: GitHub serves README SVGs through <img>, which loads no fonts.
"""
from lib import C, S, Leaf, n, render, svg, text_path, wordmark, write
from logo import ithildin_body, lembas_body

MONO, SANS, SANS_M = "JBMono-Medium", "Inter-Regular", "Inter-Medium"


def t(text, font, size, x, y, color, anchor="start", tracking=0.0):
    d, w = text_path(text, font, size, x, y, tracking, anchor)
    return f'<path fill="{color}" d="{d}"/>', w


def grid(x, y, size, color, opacity):
    """The 48-unit construction grid behind a large mark: major lines only."""
    step = size / 4
    d = "".join(f"M{n(x + i * step)} {n(y)}V{n(y + size)}M{n(x)} {n(y + i * step)}H{n(x + size)}"
                for i in range(5))
    return f'<path stroke="{color}" stroke-opacity="{opacity}" d="{d}"/>'


# ---------------------------------------------------------------- social card
def og() -> str:
    W, H = 1280, 640
    bg, word, body, gold, quiet = C["anduin-night"], C["waybread"], C["silver-bark"], C["mallorn-gold"], "#7F8C86"
    p = [f'<rect width="{W}" height="{H}" fill="{bg}"/>']
    # the mark, large, on its construction grid
    gx, gy, gs = 836, 140, 360
    p.append(grid(gx, gy, gs, C["silver-bark"], 0.12))
    p.append(lembas_body(Leaf(gx, gy, gs), gold))
    # name
    d, _ = wordmark("Lembas", 150, 84, 250)
    p.append(f'<path fill="{word}" d="{d}"/>')
    # what it does, in plain words
    p.append(t("Claude skills for short, dense", SANS_M, 44, 88, 336, word)[0])
    p.append(t("engineering answers.", SANS_M, 44, 88, 392, word)[0])
    # one benchmark number
    p.append(t("61–62%", "Cormorant-SemiBold", 96, 84, 532, gold)[0])
    p.append(t("shorter replies than Claude", SANS, 26, 392, 500, body)[0])
    p.append(t("with no prompt, on 10 dev questions", SANS, 26, 392, 534, body)[0])
    p.append(t("github.com/jmjohns9/lembas", "JBMono-Regular", 22, 88, 596, quiet)[0])
    return svg(W, H, "".join(p), "Lembas: Claude skills for short, dense engineering answers")


# ---------------------------------------------------------------- README hero
def hero(mode: str) -> str:
    W, H = 1280, 440
    light = mode == "light"
    bg = C["waybread"] if light else C["anduin-night"]
    edge = C["waybread-deep"] if light else C["anduin-deep"]
    word = C["ink"] if light else C["waybread"]
    body = C["moss"] if light else C["silver-bark"]
    gold = C["gilt"] if light else C["mallorn-gold"]
    rule = C["silver-bark"] if light else "#2A3A3D"
    silver = C["starlight"] if light else C["ithildin"]

    p = [f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="20" fill="{bg}" stroke="{edge}"/>']
    # lockup
    leaf_box = 120
    p.append(lembas_body(Leaf(56, 44, leaf_box), gold))
    d, _ = wordmark("Lembas", 112, 184, 150)
    p.append(f'<path fill="{word}" d="{d}"/>')
    # what it does
    p.append(t("A Claude skill for short, dense engineering answers.", SANS_M, 30, 72, 222, word)[0])
    p.append(t("Every reply: the problem, the exact fix, the alternatives and why", SANS, 24, 72, 264, body)[0])
    p.append(t("the fix wins. Plus squeeze.py: a 24,000-line log in 1,500 tokens.", SANS, 24, 72, 296, body)[0])
    # the answer shape, as a strip
    x, y = 72, 372
    for i, label in enumerate(("PROBLEM", "FIX", "ALTERNATIVES", "WHY THIS FIX")):
        num, w1 = t(f"0{i + 1}", MONO, 17, x, y, gold, tracking=0.04)
        lab, w2 = t(label, MONO, 17, x + w1 + 10, y, word, tracking=0.08)
        p += [num, lab]
        x += w1 + 10 + w2 + 22
        if i < 3:
            p.append(f'<path stroke="{rule}" d="M{n(x - 11)} {y - 14}V{y + 3}"/>')
    # stats column
    sx = 900
    p.append(f'<path stroke="{rule}" d="M{sx - 40} 64V376"/>')
    p.append(t("61–62%", "Cormorant-SemiBold", 76, sx, 140, gold)[0])
    p.append(t("shorter than no prompt", SANS, 22, sx, 176, body)[0])
    p.append(t("19 of 20", "Cormorant-SemiBold", 76, sx, 282, gold)[0])
    p.append(t("complete in blind review", SANS, 22, sx, 318, body)[0])
    # Ithildin, the sibling, as a quiet footnote
    p.append(ithildin_body(Leaf(sx - 4, 346, 30, 1.2), silver, small=True))
    p.append(t("+ Ithildin for long documents", SANS, 18, sx + 32, 368, body)[0])
    title = "Lembas: a Claude skill for short, dense engineering answers"
    return svg(W, H, "".join(p), title)


README_SNIPPET = """<picture>
  <source media="(prefers-color-scheme: dark)" srcset="brand/readme/hero-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="brand/readme/hero-light.svg">
  <img alt="Lembas: a Claude skill for short, dense engineering answers. Every reply carries the problem, the exact fix, the alternatives and why the fix wins." src="brand/readme/hero-light.svg" width="100%">
</picture>
"""

if __name__ == "__main__":
    write("social/og-image.svg", og())
    render("social/og-image.svg", "social/og-image.png", 1280)
    for mode in ("light", "dark"):
        write(f"readme/hero-{mode}.svg", hero(mode))
        render(f"readme/hero-{mode}.svg", f"previews/hero-{mode}.png", 1280)
    write("readme/README-snippet.md", README_SNIPPET)
    print("banners ok")
