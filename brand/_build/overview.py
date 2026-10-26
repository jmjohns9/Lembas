"""brand/overview.png: the identity on one board, composed from the rendered deliverables."""
import io
import resvg_py
from PIL import Image, ImageDraw, ImageFont
from lib import BRAND, C, PALETTE, FONTS

W, H, M = 2400, 2000, 72
board = Image.new("RGB", (W, H), "#0A1113")
dr = ImageDraw.Draw(board)
f = lambda name, s: ImageFont.truetype(f"{FONTS}/{name}.ttf", s)
LABEL, SMALL, TITLE = f("JBMono-Medium", 20), f("Inter-Regular", 19), f("Cormorant-SemiBold", 64)


def svgimg(rel, width=None, height=None):
    kw = {"svg_path": f"{BRAND}/{rel}"}
    if width: kw["width"] = width
    if height: kw["height"] = height
    return Image.open(io.BytesIO(bytes(resvg_py.svg_to_bytes(**kw)))).convert("RGBA")


def tile(x, y, w, h, fill, outline=None):
    dr.rounded_rectangle((x, y, x + w, y + h), 22, fill=fill, outline=outline, width=2)


def place(im, x, y, w, h):
    board.paste(im, (int(x + (w - im.width) / 2), int(y + (h - im.height) / 2)), im)


def label(t, x, y, col=C["silver-bark"]):
    dr.text((x, y), t.upper(), font=LABEL, fill=col)


dr.text((M, 48), "Lembas", font=TITLE, fill=C["waybread"])
dr.text((M + 250, 78), "Identity overview  ·  v1.0", font=f("Inter-Medium", 24), fill=C["silver-bark"])

# row 1: the mark, then the lockups
y1, h1 = 170, 560
tile(M, y1, 560, h1, C["anduin-night"], "#22323A")
place(svgimg("logo/lembas-mark.svg", 440), M, y1, 560, h1 - 30)
label("Primary mark", M + 28, y1 + h1 - 50, C["mallorn-gold"])

x = M + 600
cw, ch = (W - M - x - 40) // 3, (h1 - 40) // 2
cells = [("lembas-horizontal-color", C["waybread"], "Horizontal · colour", 470, None),
         ("lembas-horizontal-color-dark", C["anduin-night"], "Horizontal · on night", 470, None),
         ("lembas-stacked-color", C["waybread"], "Stacked", None, 150),
         ("lembas-horizontal-black", "#FFFFFF", "One colour · black", 470, None),
         ("lembas-horizontal-white", "#000000", "One colour · white", 470, None),
         ("lembas-mark-small-color-dark", C["anduin-night"], "Small mark · 16 / 32 px", None, None)]
for i, (name, bg, cap, w_, h_) in enumerate(cells):
    cx, cy = x + (i % 3) * (cw + 20), y1 + (i // 3) * (ch + 40)
    tile(cx, cy, cw, ch, bg, "#22323A")
    if name.startswith("lembas-mark-small"):
        for k, s in enumerate((16, 32, 64)):
            im = svgimg(f"logo/{name}.svg", s)
            board.paste(im, (cx + 150 + k * 110, cy + ch // 2 - s // 2), im)
    else:
        place(svgimg(f"logo/{name}.svg", w_, h_), cx, cy, cw, ch - 20)
    dark_bg = bg in (C["anduin-night"], "#000000")
    label(cap, cx + 22, cy + ch - 40, C["silver-bark"] if dark_bg else C["moss"])

# row 2: palette
y2 = y1 + h1 + 50
label("Palette  ·  Lothlórien at dusk", M, y2, C["mallorn-gold"])
n_ = len(PALETTE)
sw = (W - 2 * M - (n_ - 1) * 12) / n_
for i, (tok, (name, hex_, _)) in enumerate(PALETTE.items()):
    sx = M + i * (sw + 12)
    dr.rounded_rectangle((sx, y2 + 40, sx + sw, y2 + 170), 12, fill=hex_, outline="#22323A", width=2)
    dr.text((sx, y2 + 184), name, font=f("Inter-Medium", 18), fill=C["waybread"])
    dr.text((sx, y2 + 210), hex_, font=f("JBMono-Regular", 16), fill=C["silver-bark"])

# row 3: the pairing and the social card
y3 = y2 + 290
pw = 1080
pair = svgimg("logo/lembas-ithildin-pair.svg", pw)
board.paste(pair, (M, y3), pair)
label("Lembas + Ithildin  ·  bread and moon-letters", M, y3 + pair.height + 18, C["mallorn-gold"])
og = Image.open(f"{BRAND}/social/og-image.png").convert("RGBA")
ow = W - 2 * M - pw - 60
og = og.resize((ow, ow // 2), Image.LANCZOS)
mask = Image.new("L", og.size, 0)
ImageDraw.Draw(mask).rounded_rectangle((0, 0, og.width - 1, og.height - 1), 18, fill=255)
board.paste(og, (M + pw + 60, y3), mask)
label("Social preview  ·  1280 × 640", M + pw + 60, y3 + og.height + 18, C["mallorn-gold"])

board = board.crop((0, 0, W, max(y3 + pair.height, y3 + og.height) + 90))
board.save(f"{BRAND}/overview.png")
print(board.size)
