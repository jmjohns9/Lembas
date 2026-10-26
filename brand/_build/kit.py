"""brand/kit/lembas-brandkit.svg/.png: the identity as a 3x3 presentation board.

Panels: mark, construction, terminal, essence, colour, type, objects, image, system.
Each panel is a nested <svg>, so it clips its own content and needs no transforms.
"""
import math

from guidelines import ICONS
from lib import ARC_R, C, R2, S, Leaf, n, render, svg, text_path, wordmark, write
from logo import ithildin_body, lembas_body

W, H, M, G = 2400, 1500, 64, 24
PW, PH = (W - 2 * M - 2 * G) / 3, (H - 2 * M - 2 * G) / 3
NIGHT, DEEP, BREAD, INK = C["anduin-night"], C["anduin-deep"], C["waybread"], C["ink"]
GOLD, SILVER, BARK, QUIET = C["mallorn-gold"], C["ithildin"], C["silver-bark"], "#7F8C86"
MONO, MONO_R, SANS, SANS_M, SERIF = "JBMono-Medium", "JBMono-Regular", "Inter-Regular", "Inter-Medium", "Cormorant-SemiBold"


def txt(s, font, size, x, y, color, anchor="start", tracking=0.0):
    d, w = text_path(s, font, size, x, y, tracking, anchor)
    return f'<path fill="{color}" d="{d}"/>', w


def label(num, name, dark=True):
    """Footer: section label bottom-left, page number bottom-right."""
    col = QUIET if dark else C["moss"]
    a, _ = txt(f"{num:02d}  {name.upper()}", MONO, 13, 28, PH - 26, col, tracking=0.1)
    b, _ = txt(f"{num} / 9", MONO_R, 13, PW - 28, PH - 26, col, "end")
    return a + b


def panel(i, fill, body, stroke="#1E2C2F"):
    x = M + (i % 3) * (PW + G)
    y = M + (i // 3) * (PH + G)
    return (f'<svg x="{n(x)}" y="{n(y)}" width="{n(PW)}" height="{n(PH)}" viewBox="0 0 {n(PW)} {n(PH)}">'
            f'<rect x=".5" y=".5" width="{n(PW - 1)}" height="{n(PH - 1)}" rx="18" fill="{fill}" stroke="{stroke}"/>'
            f'{body}</svg>')


# 1 -------------------------------------------------------------- the mark
def p_mark():
    size = 150
    lf = Leaf(PW / 2 - 300, PH / 2 - size / 2 - 14, size)
    d, (l, t, r, b) = wordmark("Lembas", 132, 0, 0)
    wx = PW / 2 - 300 + size + 14
    d, _ = wordmark("Lembas", 132, wx - l, PH / 2 + 30)
    return lembas_body(lf, GOLD) + f'<path fill="{BREAD}" d="{d}"/>' + label(1, "Mark")


# 2 -------------------------------------------------------------- construction
def p_construction():
    k = 300 / S
    ox, oy = PW / 2 - 150, PH / 2 - 172
    g = "".join(f"M{n(ox + i * 12 * k)} {n(oy)}V{n(oy + 300)}M{n(ox)} {n(oy + i * 12 * k)}H{n(ox + 300)}" for i in range(5))
    minor = "".join(f"M{n(ox + i * 4 * k)} {n(oy)}V{n(oy + 300)}M{n(ox)} {n(oy + i * 4 * k)}H{n(ox + 300)}" for i in range(13))
    lf = Leaf(ox, oy, 300)
    tips = "".join(f'<circle cx="{n(x)}" cy="{n(y)}" r="5" stroke="{SILVER}" stroke-width="1.5"/>'
                   for x, y in (lf.xy(-lf.L, 0), lf.xy(lf.L, 0)))
    clip = f'<clipPath id="cg"><rect x="{n(ox)}" y="{n(oy)}" width="300" height="300"/></clipPath>'
    body = (clip + f'<path stroke="#1C2A2D" d="{minor}"/><path stroke="#2C4144" d="{g}"/>'
            + lembas_body(lf, GOLD)
            + f'<g clip-path="url(#cg)" stroke="{BARK}" stroke-opacity=".7" stroke-dasharray="5 6">'
            f'<circle cx="{n(ox)}" cy="{n(oy)}" r="{n(ARC_R * k)}"/>'
            f'<circle cx="{n(ox + 300)}" cy="{n(oy + 300)}" r="{n(ARC_R * k)}"/></g>'
            + f'<path stroke="{SILVER}" stroke-opacity=".6" stroke-dasharray="2 5" d="M{n(ox)} {n(oy + 300)}L{n(ox + 300)} {n(oy)}"/>'
            + tips)
    body += txt("r 42 · 48 grid · break 1/16", MONO_R, 15, PW / 2, oy + 336, BARK, "middle", 0.04)[0]
    return body + label(2, "Construction")


# 3 -------------------------------------------------------------- terminal
def p_terminal():
    x0, y0, w, h = 44, 44, PW - 88, PH - 120
    body = (f'<rect x="{x0}" y="{y0}" width="{n(w)}" height="{n(h)}" rx="12" fill="#0A1113" stroke="#24363A"/>'
            f'<path stroke="#24363A" d="M{x0} {y0 + 44}H{n(x0 + w)}"/>')
    for i in range(3):
        body += f'<circle cx="{x0 + 24 + i * 18}" cy="{y0 + 22}" r="5" fill="#2A3B3E"/>'
    body += lembas_body(Leaf(x0 + w / 2 - 70, y0 + 10, 24, 1.2), GOLD)
    body += txt("squeeze.py", MONO_R, 14, x0 + w / 2 - 40, y0 + 27, QUIET)[0]
    lines = [
        [("$ ", GOLD), ("npm test 2>&1 | python3 squeeze.py", BREAD)],
        [],
        [("› ", GOLD), ("24,000 lines in", BARK), ("   →   ", QUIET), ("1,500 tokens out", BREAD)],
        [("› ", GOLD), ("every error, warning and trace kept", BARK)],
        [("› ", GOLD), ("repeats collapsed, original saved", BARK)],
        [],
        [("$ ", GOLD), ("▍", GOLD)],
    ]
    y = y0 + 92
    for ln in lines:
        x = x0 + 26
        for s, col in ln:
            p, wd = txt(s, MONO_R, 18, x, y, col)
            body += p
            x += wd
        y += 34
    return body + label(3, "Application · terminal")


# 4 -------------------------------------------------------------- essence
def p_essence():
    body = txt("One bite", SERIF, 92, 48, 150, INK)[0]
    body += txt("is enough.", SERIF, 92, 48, 236, INK)[0]
    body += f'<path stroke="{C["gilt"]}" stroke-width="2" d="M50 282H110"/>'
    body += txt("Small, because every sentence", SANS, 21, 50, 322, C["moss"])[0]
    body += txt("carries something you need.", SANS, 21, 50, 352, C["moss"])[0]
    body += lembas_body(Leaf(PW - 132, 36, 96), C["gilt"])
    return body + label(4, "Essence", dark=False)


# 5 -------------------------------------------------------------- colour
def p_colour():
    # widths follow use: mostly night and waybread, gold as a sliver of gilding
    cols = [("Night", NIGHT, 0.30), ("Waybread", BREAD, 0.22), ("Ink", INK, 0.12),
            ("Lórien", C["lorien-green"], 0.12), ("Bark", BARK, 0.08), ("Ithildin", SILVER, 0.08),
            ("Gold", GOLD, 0.08)]
    x0, y0, w, h = 40, 40, PW - 80, 196
    body, x = "", x0
    body += f'<clipPath id="cc"><rect x="{x0}" y="{y0}" width="{n(w)}" height="{h}" rx="10"/></clipPath><g clip-path="url(#cc)">'
    for _, hex_, frac in cols:
        cw = w * frac
        body += f'<rect x="{n(x)}" y="{y0}" width="{n(cw + .5)}" height="{h}" fill="{hex_}"/>'
        x += cw
    body += "</g>" + f'<rect x="{x0}" y="{y0}" width="{n(w)}" height="{h}" rx="10" stroke="#24363A"/>'
    # legend: evenly spaced, so narrow swatches still get a readable label
    lw = w / len(cols)
    for i, (name, hex_, _) in enumerate(cols):
        lx, ly = x0 + i * lw, y0 + h + 30
        body += f'<rect x="{n(lx)}" y="{ly - 11}" width="12" height="12" rx="3" fill="{hex_}" stroke="#3A4C50"/>'
        body += txt(name, SANS_M, 13, lx + 18, ly, BREAD)[0]
        body += txt(hex_, MONO_R, 12, lx, ly + 24, QUIET)[0]
    return body + label(5, "Colour · Lothlórien at dusk")


# 6 -------------------------------------------------------------- type
def p_type():
    body = txt("Aa", SERIF, 210, 40, 236, BREAD)[0]
    x = 300
    rows = [("Cormorant Garamond", SERIF, 34, BREAD, "Names and numbers"),
            ("Inter", SANS_M, 28, BREAD, "Everything that works"),
            ("JetBrains Mono", MONO_R, 24, GOLD, "Anything you type")]
    y = 112
    for name, font, size, col, note in rows:
        body += txt(name, font, size, x, y, col)[0]
        body += txt(note, SANS, 15, x, y + 26, QUIET)[0]
        y += 82
    body += txt("61–62%", SERIF, 56, 44, 340, GOLD)[0]
    body += txt("lining figures for every number", SANS, 15, 230, 332, QUIET)[0]
    return body + label(6, "Type")


# 7 -------------------------------------------------------------- objects
def p_objects():
    sh = '<filter id="sh" x="-20%" y="-20%" width="140%" height="160%"><feDropShadow dx="0" dy="14" stdDeviation="16" flood-color="#000" flood-opacity=".45"/></filter>'
    # a card in waybread, and a die-cut night sticker
    cx, cy, cw, ch = 70, 70, 380, 228
    d, _ = wordmark("Lembas", 48, cx + 92, cy + 82)
    card = (f'<rect x="{cx}" y="{cy}" width="{cw}" height="{ch}" rx="10" fill="{BREAD}" filter="url(#sh)"/>'
            + lembas_body(Leaf(cx + 30, cy + 30, 64), C["gilt"]) + f'<path fill="{INK}" d="{d}"/>'
            + txt("Problem · Fix · Alternatives · Why", MONO_R, 13, cx + 34, cy + ch - 62, C["moss"], tracking=0.02)[0]
            + txt("github.com/jmjohns9/lembas", MONO_R, 13, cx + 34, cy + ch - 34, C["gilt"])[0])
    sx, sy, ss = PW - 260, 118, 196
    sticker = (f'<rect x="{n(sx)}" y="{sy}" width="{ss}" height="{ss}" rx="44" fill="{NIGHT}" stroke="{BREAD}" stroke-width="6" filter="url(#sh)"/>'
               + lembas_body(Leaf(sx + 18, sy + 18, ss - 36), GOLD))
    return f'<defs>{sh}</defs>' + card + sticker + label(7, "Objects")


# 8 -------------------------------------------------------------- image
def p_image():
    """A halftone moon over a river at dusk: Ithildin's light, the Anduin below."""
    body = ('<defs><linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="#070C0E"/><stop offset=".62" stop-color="{DEEP}"/>'
            '<stop offset=".63" stop-color="#0B1416"/><stop offset="1" stop-color="#070C0E"/></linearGradient></defs>'
            f'<rect x=".5" y=".5" width="{n(PW - 1)}" height="{n(PH - 1)}" rx="18" fill="url(#sky)"/>')
    mx, my, mr = PW * 0.66, PH * 0.34, 78
    horizon = PH * 0.62
    step = 9
    dots = []
    for gy in range(int(step / 2), int(horizon), step):
        for gx in range(int(step / 2), int(PW), step):
            dist = math.hypot(gx - mx, gy - my)
            if dist < mr:
                v = 0.92 - 0.25 * (dist / mr) ** 2
            else:
                v = 0.26 * math.exp(-(dist - mr) / 30)
            r = step / 2 * math.sqrt(max(v, 0)) * 0.95
            if r > 0.45:
                dots.append(f'<circle cx="{gx}" cy="{gy}" r="{n(r)}"/>')
    body += f'<g fill="{SILVER}">{"".join(dots)}</g>'
    # far bank: a low, smooth line of hills, one path
    import random
    rnd = random.Random(7)
    bank, x = f"M0 {n(horizon)}L0 {n(horizon - 8)}", 0.0
    while x < PW:
        w = 120 + rnd.random() * 140
        bank += f"Q{n(x + w / 2)} {n(horizon - 10 - rnd.random() * 18)} {n(x + w)} {n(horizon - 6 - rnd.random() * 6)}"
        x += w
    bank += f"L{n(x)} {n(horizon)}Z"
    body += f'<path fill="#05090A" d="{bank}"/>'
    # river: reflection of the moon as broken horizontal strokes
    refl = ""
    for i, yy in enumerate(range(int(horizon) + 10, int(PH) - 60, 9)):
        spread = 26 + i * 7
        for j in range(3):
            x1 = mx - spread + rnd.random() * spread * 2 - 10
            ln = 8 + rnd.random() * (38 - i * 1.2)
            refl += f"M{n(x1)} {yy}H{n(x1 + max(ln, 6))}"
    body += f'<path stroke="{SILVER}" stroke-opacity=".55" stroke-width="2" stroke-linecap="round" d="{refl}"/>'
    body += f'<path stroke="{GOLD}" stroke-opacity=".8" stroke-width="2" stroke-linecap="round" d="M{n(mx - 30)} {n(horizon + 14)}H{n(mx + 22)}"/>'
    body += txt("Light where you need it.", "Cormorant-MediumItalic", 34, 40, 74, BREAD)[0]
    return body + label(8, "Image · Ithildin")


# 9 -------------------------------------------------------------- system
def p_system():
    body = ""
    # the answer shape as chips
    x, y = 36, 48
    for i, s in enumerate(("PROBLEM", "FIX", "ALTERNATIVES", "WHY THIS FIX")):
        num, w1 = text_path(f"0{i + 1}", MONO, 14, 0, 0, 0.04)
        lab, w2 = text_path(s, MONO, 14, 0, 0, 0.08)
        cw = w1 + w2 + 38
        hl = i == 1
        body += (f'<rect x="{n(x)}" y="{y}" width="{n(cw)}" height="36" rx="18" '
                 f'fill="{"#2A2412" if hl else DEEP}" stroke="{GOLD if hl else "#2C4144"}"/>')
        body += txt(f"0{i + 1}", MONO, 14, x + 16, y + 23, GOLD, tracking=0.04)[0]
        body += txt(s, MONO, 14, x + 22 + w1, y + 23, BREAD, tracking=0.08)[0]
        x += cw + 10
    # icon row
    x, y = 36, 124
    for name, d in ICONS.items():
        body += (f'<rect x="{x}" y="{y}" width="88" height="88" rx="14" fill="{DEEP}" stroke="#24363A"/>'
                 f'<svg x="{x + 26}" y="{y + 18}" width="36" height="36" viewBox="0 0 24 24" fill="none" '
                 f'stroke="{BREAD}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" color="{BREAD}">{d}</svg>')
        body += txt(name, MONO_R, 11, x + 44, y + 74, QUIET, "middle")[0]
        x += 100
    # badges, as shields draws them in the palette
    x, y = 36, 248
    for lab, val, col in (("release", "v2.1.0", C["gilt"]), ("license", "Apache 2.0", C["lorien-green"]),
                          ("ithildin", "long documents", C["starlight"])):
        _, w1 = text_path(lab, SANS, 14, 0, 0)
        _, w2 = text_path(val, SANS, 14, 0, 0)
        a, b = w1 + 20, w2 + 20
        body += (f'<rect x="{n(x)}" y="{y}" width="{n(a)}" height="28" fill="{NIGHT}" stroke="#2C4144"/>'
                 f'<rect x="{n(x + a)}" y="{y}" width="{n(b)}" height="28" fill="{col}"/>')
        body += txt(lab, SANS, 14, x + 10, y + 19, "#FFFFFF")[0] + txt(val, SANS, 14, x + a + 10, y + 19, "#FFFFFF")[0]
        x += a + b + 12
    # the sibling
    body += ithildin_body(Leaf(36, 300, 40, 1.2), SILVER, small=True)
    body += txt("Ithildin · reads long documents by map", SANS, 16, 86, 326, BARK)[0]
    return body + label(9, "System")


def board():
    panels = [
        panel(0, NIGHT, p_mark()),
        panel(1, NIGHT, p_construction()),
        panel(2, DEEP, p_terminal()),
        panel(3, BREAD, p_essence(), C["waybread-deep"]),
        panel(4, NIGHT, p_colour()),
        panel(5, NIGHT, p_type()),
        panel(6, "#121C1F", p_objects()),
        panel(7, "#070C0E", p_image()),
        panel(8, NIGHT, p_system()),
    ]
    return svg(W, H, f'<rect width="{W}" height="{H}" fill="#0A1013"/>' + "".join(panels),
               "Lembas brand kit")


if __name__ == "__main__":
    write("kit/lembas-brandkit.svg", board())
    render("kit/lembas-brandkit.svg", "kit/lembas-brandkit.png", 2400)
    print("kit ok")
