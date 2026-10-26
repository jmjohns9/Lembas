"""Favicons, touch icon, app icon and GitHub avatar."""
from PIL import Image

from lib import BRAND, C, S, Leaf, n, render, svg, write
from logo import SMALL_GAP, SMALL_K, lembas_body

NIGHT, GOLD = C["anduin-night"], C["mallorn-gold"]


def tile(size: float, radius: float, small: bool, leaf_frac: float) -> str:
    """The mark on a night tile. `leaf_frac` is the 48-grid box as a fraction of the tile."""
    box = size * leaf_frac
    o = (size - box) / 2
    leaf = Leaf(o, o, box, SMALL_K if small else 1.0)
    rect = (f'<rect width="{n(size)}" height="{n(size)}" rx="{n(radius)}" fill="{NIGHT}"/>'
            if radius >= 0 else f'<rect width="{n(size)}" height="{n(size)}" fill="{NIGHT}"/>')
    return svg(size, size, rect + lembas_body(leaf, GOLD, SMALL_GAP if small else 3), "Lembas")


if __name__ == "__main__":
    # small sizes: optical mark, rounded tile, leaf nearly edge to edge
    write("icons/favicon.svg", tile(32, 7, True, 1.0))
    render("icons/favicon.svg", "icons/favicon-16.png", 16)
    render("icons/favicon.svg", "icons/favicon-32.png", 32)
    render("icons/favicon.svg", "icons/favicon-48.png", 48)
    # Apple touch: full-bleed square (iOS applies its own mask), regular mark
    write("icons/apple-touch-icon.svg", tile(180, -1, False, 0.86))
    render("icons/apple-touch-icon.svg", "icons/apple-touch-icon-180.png", 180)
    # app icon / PWA 512: rounded tile, regular mark
    write("icons/icon-512.svg", tile(512, 112, False, 0.84))
    render("icons/icon-512.svg", "icons/icon-512.png", 512)
    # GitHub avatar: square, GitHub crops it to a circle, so keep the leaf inside 70%
    write("icons/github-avatar.svg", tile(500, -1, False, 0.8))
    render("icons/github-avatar.svg", "icons/github-avatar-500.png", 500)
    # .ico with 16, 32, 48 from the hand-checked PNGs
    imgs = [Image.open(f"{BRAND}/icons/favicon-{s}.png").convert("RGBA") for s in (16, 32, 48)]
    imgs[2].save(f"{BRAND}/icons/favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)],
                 append_images=imgs[:2])

    # review sheet: actual-size icons on GitHub light and dark, plus 8x pixel zooms
    sheet = Image.new("RGB", (1180, 560), "#ffffff")
    dark = Image.new("RGB", (590, 560), "#0d1117")
    sheet.paste(dark, (590, 0))
    for half, x0 in ((0, 20), (1, 610)):
        x = x0
        for s in (16, 32, 48):
            im = Image.open(f"{BRAND}/icons/favicon-{s}.png").convert("RGBA")
            sheet.paste(im, (x, 20), im)
            z = im.resize((s * 8 if s < 48 else s * 4,) * 2, Image.NEAREST)
            sheet.paste(z, (x, 90), z)
            x += z.width + 20
        for name, sz in (("apple-touch-icon-180", 120), ("icon-512", 120), ("github-avatar-500", 120)):
            pass
    x = 20
    for name in ("apple-touch-icon-180", "icon-512", "github-avatar-500"):
        im = Image.open(f"{BRAND}/icons/{name}.png").convert("RGBA").resize((160, 160), Image.LANCZOS)
        sheet.paste(im, (x, 380), im)
        x += 180
    # avatar with GitHub's circular crop
    av = Image.open(f"{BRAND}/icons/github-avatar-500.png").convert("RGBA").resize((160, 160), Image.LANCZOS)
    mask = Image.new("L", (160, 160), 0)
    from PIL import ImageDraw
    ImageDraw.Draw(mask).ellipse((0, 0, 159, 159), fill=255)
    sheet.paste(av, (630, 380), mask)
    sheet.save(f"{BRAND}/previews/icons-sheet.png")
    print("icons ok")
