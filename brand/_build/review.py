"""Render every logo file to previews/ and build a contact sheet for review."""
import glob, os, re
from lib import BRAND, C, render, svg, write, scale_path, n

files = sorted(glob.glob(os.path.join(BRAND, "logo", "*.svg")))
cells, x, y, rowh = [], 20, 20, 0
W = 1600
for f in files:
    rel = os.path.relpath(f, BRAND)
    name = os.path.basename(f)[:-4]
    render(rel, f"previews/logo/{name}.png", 600 if "construction" not in name and "pair" not in name else 1600)
    src = open(f).read()
    w = float(re.search(r'width="([\d.]+)"', src).group(1)); h = float(re.search(r'height="([\d.]+)"', src).group(1))
    if "construction" in name or "pair" in name:
        continue
    scheme = next((s for s in ("color-dark", "color", "black", "white") if name.endswith(s)), "color-dark" if name in ("lembas-mark", "ithildin-mark") else "color")
    ground = {"color": C["waybread"], "color-dark": C["anduin-night"], "black": "#FFFFFF", "white": "#0E1719"}[scheme]
    s = 90 / h if w / h < 3 else min(90 / h, 260 / w)
    cw, ch = w * s + 40, 130
    if x + cw > W - 20:
        x, y = 20, y + 150
    inner = re.search(r"</title>\n(.*)\n</svg>", src, re.S).group(1)
    inner = re.sub(r'd="([^"]+)"', lambda m: f'd="{scale_path(m.group(1), s, x + 20, y + 20)}"', inner)
    inner = re.sub(r'stroke-width="([\d.]+)"', lambda m: f'stroke-width="{n(float(m.group(1)) * s)}"', inner)
    cells.append(f'<rect x="{n(x)}" y="{y}" width="{n(cw)}" height="{ch}" rx="10" fill="{ground}" stroke="#33444a"/>' + inner)
    x += cw + 14
write("previews/logo-sheet.svg", svg(W, y + 170, f'<rect width="{W}" height="{y + 170}" fill="#1c2628"/>' + "".join(cells)))
render("previews/logo-sheet.svg", "previews/logo-sheet.png", 1600)
print("ok", len(files))
