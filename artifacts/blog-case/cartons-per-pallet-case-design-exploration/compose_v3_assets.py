"""Compose the V3 article figures from verified evidence and explicit geometry."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[3]
SLUG = "cartons-per-pallet-case-design-exploration"
ARTIFACT = ROOT / "artifacts" / "blog-case" / SLUG
SOURCE = ARTIFACT / "source"
OUTPUT = ROOT / "static" / "img" / "blog" / SLUG

NAVY = (24, 53, 73)
MUTED = (88, 105, 121)
GREEN = (10, 145, 112)
KRAFT = (190, 125, 67)
KRAFT_LIGHT = (222, 164, 96)
KRAFT_DARK = (143, 83, 43)
WOOD = (157, 105, 57)
WOOD_LIGHT = (202, 151, 91)
PANEL = (255, 255, 255)
CANVAS = (247, 249, 251)


def font(size: int, bold: bool = False):
    candidates = [
        Path("C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
    ]
    for path in candidates:
        if path.is_file():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def text(draw, xy, value, size, fill=NAVY, bold=False, anchor=None):
    draw.text(xy, value, font=font(size, bold), fill=fill, anchor=anchor)


def fit(image, size, background=CANVAS):
    image = image.convert("RGB")
    fitted = ImageOps.contain(image, size, method=Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", size, background)
    canvas.paste(fitted, ((size[0] - fitted.width) // 2, (size[1] - fitted.height) // 2))
    return canvas


def source(group, name):
    return Image.open(SOURCE / group / name).convert("RGB")


def iso_box(draw, x, y, width, depth, height, top=KRAFT_LIGHT, left=KRAFT, right=KRAFT_DARK, outline=(107, 72, 44)):
    top_poly = [(x, y), (x + width, y - depth * 0.42), (x + width + depth * 0.72, y), (x + depth * 0.72, y + depth * 0.42)]
    left_poly = [(x, y), (x + depth * 0.72, y + depth * 0.42), (x + depth * 0.72, y + depth * 0.42 + height), (x, y + height * 0.78)]
    right_poly = [(x + depth * 0.72, y + depth * 0.42), (x + width + depth * 0.72, y), (x + width + depth * 0.72, y + height * 0.78), (x + depth * 0.72, y + depth * 0.42 + height)]
    draw.polygon(top_poly, fill=top, outline=outline)
    draw.polygon(left_poly, fill=left, outline=outline)
    draw.polygon(right_poly, fill=right, outline=outline)
    return (x, y - depth * 0.42, x + width + depth * 0.72, y + height + depth * 0.42)


def pallet(draw, x, y, width, depth, slats=4):
    deck = [(x, y), (x + width, y - depth * 0.42), (x + width + depth * 0.72, y), (x + depth * 0.72, y + depth * 0.42)]
    draw.polygon(deck, fill=WOOD_LIGHT, outline=WOOD, width=3)
    for i in range(slats + 1):
        px = x + i * width / slats
        draw.line((px, y, px + depth * 0.72, y + depth * 0.42), fill=WOOD, width=2)
    for offset in (0.16, 0.84):
        bx = x + width * offset
        draw.polygon([(bx, y + 6), (bx + depth * 0.72, y + depth * 0.42 + 6), (bx + depth * 0.72, y + depth * 0.42 + 30), (bx, y + 30)], fill=WOOD, outline=WOOD)


def open_case(draw, x, y, case_w, case_d, case_h, cols, rows, layers):
    # The RSC is drawn as a real open case: floor, back wall, side walls, and flaps.
    floor = [(x, y), (x + case_w, y - case_d * 0.38), (x + case_w + case_d * 0.62, y), (x + case_d * 0.62, y + case_d * 0.38)]
    draw.polygon(floor, fill=(226, 178, 117), outline=KRAFT_DARK, width=3)
    draw.polygon([(x + case_d * 0.62, y + case_d * 0.38), (x + case_w + case_d * 0.62, y), (x + case_w + case_d * 0.62, y - case_h), (x + case_d * 0.62, y + case_d * 0.38 - case_h)], fill=(177, 108, 57), outline=KRAFT_DARK, width=3)
    draw.polygon([(x, y), (x + case_d * 0.62, y + case_d * 0.38), (x + case_d * 0.62, y + case_d * 0.38 - case_h), (x, y - case_h * 0.78)], fill=(202, 137, 76), outline=KRAFT_DARK, width=3)
    draw.polygon([(x + case_w, y - case_d * 0.38), (x + case_w + case_d * 0.62, y), (x + case_w + case_d * 0.62, y - case_h), (x + case_w, y - case_d * 0.38 - case_h * 0.78)], fill=(202, 137, 76), outline=KRAFT_DARK, width=3)
    # Four open flaps make the object read as an RSC rather than a cube.
    draw.polygon([(x, y - case_h * 0.78), (x - case_w * 0.22, y - case_h * 0.98), (x - case_w * 0.12, y - case_h * 0.72), (x, y)], fill=(225, 174, 108), outline=KRAFT_DARK, width=2)
    draw.polygon([(x + case_w, y - case_d * 0.38 - case_h * 0.78), (x + case_w * 1.2, y - case_d * 0.55 - case_h), (x + case_w * 1.18, y - case_d * 0.35 - case_h * 0.74), (x + case_w, y - case_d * 0.38)], fill=(225, 174, 108), outline=KRAFT_DARK, width=2)
    cell_w = case_w / cols * 0.72
    cell_d = case_d / rows * 0.56
    cell_h = min(case_h / max(layers, 1) * 0.62, 36)
    start_x = x + 18
    start_y = y - 20
    for layer in range(layers):
        for row in range(rows):
            for col in range(cols):
                bx = start_x + col * cell_w - row * cell_d * 0.56
                by = start_y - layer * cell_h * 0.82 + row * cell_d * 0.34
                iso_box(draw, bx, by, cell_w * 0.82, cell_d * 0.72, cell_h, top=(236, 184, 110), left=(210, 139, 73), right=(180, 104, 52), outline=(117, 75, 43))


def pallet_load(draw, x, y, cols, rows, layers, case_width, case_depth, case_height):
    pallet(draw, x, y, case_width * cols * 0.94, case_depth * rows * 0.70, slats=max(3, cols + rows))
    cell_w = case_width * 0.74
    cell_d = case_depth * 0.58
    cell_h = case_height * 0.78
    for layer in range(layers):
        for row in range(rows):
            for col in range(cols):
                bx = x + col * cell_w - row * cell_d * 0.52 + 18
                by = y - layer * cell_h * 0.86 + row * cell_d * 0.30 - 12
                iso_box(draw, bx, by, cell_w, cell_d, cell_h, top=(203, 146, 83), left=(177, 105, 54), right=(142, 76, 42), outline=(103, 64, 40))


def comparison_figure():
    image = Image.new("RGB", (1800, 1120), CANVAS)
    draw = ImageDraw.Draw(image)
    text(draw, (70, 42), "Same 12 cartons. Different case geometry. Different pallet result.", 44, bold=True)
    text(draw, (70, 100), "A physical comparison of the two verified configurations in the fixed CapePack / KolliPack case.", 24, fill=MUTED)
    panels = [(54, 165, 858, 1050), (942, 165, 1746, 1050)]
    for panel in panels:
        draw.rounded_rectangle(panel, radius=24, fill=PANEL, outline=(218, 226, 232), width=3)
    text(draw, (92, 200), "A · 216 CARTONS / PALLET", 30, bold=True)
    text(draw, (980, 200), "B · 240 CARTONS / PALLET", 30, fill=GREEN, bold=True)
    text(draw, (92, 250), "Taller 15 × 12 × 16 in ID case", 22, fill=MUTED)
    text(draw, (980, 250), "Flatter 20 × 18 × 8 in ID case", 22, fill=MUTED)
    open_case(draw, 175, 430, 350, 220, 145, 3, 2, 2)
    open_case(draw, 1080, 430, 410, 190, 100, 4, 3, 1)
    text(draw, (220, 585), "3 × 2 × 2 cartons", 23, bold=True)
    text(draw, (1135, 585), "4 × 3 × 1 cartons", 23, bold=True)
    draw.line((110, 625, 800, 625), fill=(221, 228, 233), width=2)
    draw.line((1000, 625, 1690, 625), fill=(221, 228, 233), width=2)
    text(draw, (92, 665), "9 cases / layer × 2 layers = 18 cases", 22, fill=NAVY, bold=True)
    text(draw, (980, 665), "4 cases / layer × 5 layers = 20 cases", 22, fill=NAVY, bold=True)
    pallet_load(draw, 160, 870, 3, 3, 2, 132, 100, 72)
    pallet_load(draw, 1070, 870, 2, 2, 5, 168, 125, 42)
    text(draw, (410, 970), "216", 48, bold=True, anchor="mm")
    text(draw, (1360, 970), "240", 48, fill=GREEN, bold=True, anchor="mm")
    text(draw, (410, 1012), "primary cartons / pallet", 19, fill=MUTED, anchor="mm")
    text(draw, (1360, 1012), "primary cartons / pallet", 19, fill=MUTED, anchor="mm")
    image.save(OUTPUT / "case-design-comparison-v3.webp", format="WEBP", quality=94, method=6)


def parity_figure(number, cape_name, kolli_name, output_name, cape_crop, kolli_crop, title, details):
    cape = source("capepack", cape_name).crop(cape_crop)
    kolli = source("kollipack", kolli_name).crop(kolli_crop)
    image = Image.new("RGB", (1800, 1040), CANVAS)
    draw = ImageDraw.Draw(image)
    text(draw, (70, 40), title, 44, bold=True)
    text(draw, (70, 100), "Large result views with compact evidence labels; original source identities remain explicit.", 24, fill=MUTED)
    panels = [(54, 165, 866, 900), (934, 165, 1746, 900)]
    for panel in panels:
        draw.rounded_rectangle(panel, radius=22, fill=PANEL, outline=(218, 226, 232), width=3)
    left = fit(cape, (760, 600), (255, 255, 255))
    right = fit(kolli, (760, 600), (255, 255, 255))
    image.paste(left, (80 + (760 - left.width) // 2, 205 + (600 - left.height) // 2))
    image.paste(right, (960 + (760 - right.width) // 2, 205 + (600 - right.height) // 2))
    draw.rounded_rectangle((80, 820, 840, 878), radius=12, fill=(56, 83, 105))
    draw.rounded_rectangle((960, 820, 1720, 878), radius=12, fill=GREEN)
    text(draw, (105, 849), "CapePack Arrange · supplied screenshot", 25, fill=(255, 255, 255), bold=True, anchor="lm")
    text(draw, (985, 849), "KolliPack · independent reproduction", 25, fill=(255, 255, 255), bold=True, anchor="lm")
    draw.rounded_rectangle((54, 930, 1746, 1005), radius=16, fill=(232, 241, 240))
    text(draw, (82, 967), details, 24, fill=NAVY, bold=True, anchor="lm")
    image.save(OUTPUT / output_name, format="WEBP", quality=94, method=6)


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    comparison_figure()
    parity_figure(
        216,
        "capepack_216_result.png",
        "kollipack_216_pallet.png",
        "parity-216-evidence-v3.webp",
        (0, 0, 1287, 540),
        (1160, 0, 1801, 861),
        "216 parity: original case reproduced",
        "15 × 12 × 16 in ID · 3 × 2 × 2 cartons · 9 cases/layer × 2 layers · 216 cartons/pallet",
    )
    parity_figure(
        240,
        "capepack_240_result.png",
        "kollipack_240_pallet.png",
        "parity-240-evidence-v3.webp",
        (0, 0, 897, 430),
        (1160, 0, 1807, 882),
        "240 parity: CapePack also reaches 240",
        "20 × 18 × 8 in ID · 4 × 3 × 1 cartons · 4 cases/layer × 5 layers · 240 cartons/pallet",
    )


if __name__ == "__main__":
    main()
