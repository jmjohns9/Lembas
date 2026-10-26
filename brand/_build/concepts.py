"""Three logo directions, drawn on the same 48-unit grid so they compare fairly."""
from lib import C, Leaf, n, render, svg, text_path, write

GOLD, NIGHT, BREAD, INK = C["mallorn-gold"], C["anduin-night"], C["waybread"], C["ink"]

# A. The folded leaf: a mallorn leaf at 45°, broken once along its midrib.
concept_a = f'<path fill="{GOLD}" d="{Leaf().halves()}"/>'

# B. The broken wafer: a square wafer with one clean break; the smaller piece set apart.
def wafer():
    # wafer 30x30 at (9,9), radius 4, broken by the line x - y = 6 (a shallow diagonal off-centre)
    big = "M13 9H33L18 39H13A4 4 0 0 1 9 35V13A4 4 0 0 1 13 9Z"
    small = "M36.5 10.5A4 4 0 0 1 39.5 14.5V36.5A4 4 0 0 1 35.5 40.5H22.5Z"
    return f'<path fill="{GOLD}" d="{big}"/><path fill="{GOLD}" d="{small}"/>'

concept_b = wafer()

# C. The waymark seal: an upright leaf inside a brooch ring, with a star at the crown.
def seal():
    ring = f'<circle cx="24" cy="24" r="20" stroke="{GOLD}" stroke-width="2.5"/>'
    # an upright vesica: tips at (24,12) and (24,38), arcs of radius 20
    leaf = (f'<path fill="{GOLD}" d="M24 14A18 18 0 0 1 24 40A18 18 0 0 1 24 14Z"/>'
            f'<path stroke="{NIGHT}" stroke-width="1.5" stroke-linecap="round" d="M24 20V35"/>')
    star = f'<path fill="{GOLD}" d="M24 6.3Q24.7 8.8 27.2 9.5Q24.7 10.2 24 12.7Q23.3 10.2 20.8 9.5Q23.3 8.8 24 6.3Z"/>'
    return ring + leaf + star

concept_c = seal()

CONCEPTS = [
    ("concept-a-folded-leaf", "Folded leaf", concept_a),
    ("concept-b-broken-wafer", "Broken wafer", concept_b),
    ("concept-c-waymark-seal", "Waymark seal", concept_c),
]

if __name__ == "__main__":
    for slug, title, body in CONCEPTS:
        write(f"concepts/{slug}.svg", svg(48, 48, body, f"Lembas concept: {title}"))

    # comparison sheet: each concept large on night, then at 32 and 16 px on both grounds
    cells = []
    for i, (slug, title, body) in enumerate(CONCEPTS):
        x = 40 + i * 320
        cells.append(f'<rect x="{x}" y="40" width="280" height="280" rx="16" fill="{NIGHT}"/>')
        cells.append(f'<g transform="translate({x + 44} 84) scale(4)">{body}</g>')
        for j, (bg, px) in enumerate([(NIGHT, 32), (NIGHT, 16), (BREAD, 32), (BREAD, 16)]):
            cx = x + j * 70
            cells.append(f'<rect x="{cx}" y="340" width="60" height="60" rx="8" fill="{bg}" stroke="#2a3a3d"/>')
            s = px / 48
            off = (60 - px) / 2
            cells.append(f'<g transform="translate({n(cx + off)} {n(340 + off)}) scale({n(s)})">{body}</g>')
        d, _ = text_path(f"{chr(65 + i)}. {title}", "Inter-Medium", 18, x, 440)
        cells.append(f'<path fill="{BREAD}" d="{d}"/>')
    sheet = svg(1000, 470, f'<rect width="1000" height="470" fill="#121c1e"/>' + "".join(cells),
                "Lembas logo concepts compared")
    write("previews/concepts-sheet.svg", sheet)
    render("previews/concepts-sheet.svg", "previews/concepts-sheet.png", 2000)
