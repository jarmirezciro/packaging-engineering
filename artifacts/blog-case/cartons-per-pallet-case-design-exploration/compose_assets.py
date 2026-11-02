"""Create deterministic figures and the thumbnail subject for the benchmark article."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[3]
SLUG = "cartons-per-pallet-case-design-exploration"
ARTIFACT = ROOT / "artifacts" / "blog-case" / SLUG
SOURCE = ARTIFACT / "source"
OUTPUT = ROOT / "static" / "img" / "blog" / SLUG
THUMBNAIL_OUTPUT = ARTIFACT / "thumbnail"


def font(size: int, bold: bool = False):
    candidates = [
        Path("C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
    ]
    for path in candidates:
        if path.is_file():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def fit(image: Image.Image, size: tuple[int, int], background=(248, 250, 252)) -> Image.Image:
    image = image.convert("RGB")
    fitted = ImageOps.contain(image, size, method=Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", size, background)
    canvas.paste(fitted, ((size[0] - fitted.width) // 2, (size[1] - fitted.height) // 2))
    return canvas


def label_bar(draw, xy, text, fill=(11, 48, 57), width=None):
    x, y = xy
    f = font(28, True)
    box = draw.textbbox((x, y), text, font=f)
    right = x + (width or (box[2] - box[0] + 40))
    draw.rounded_rectangle((x, y, right, y + 52), radius=12, fill=fill)
    draw.text((x + 20, y + 9), text, font=f, fill=(255, 255, 255))


def source(name: str, group: str) -> Image.Image:
    return Image.open(SOURCE / group / name).convert("RGB")


def make_parity_figure(name: str, cape_crop: tuple[int, int, int, int], kolli_crop: tuple[int, int, int, int], output_name: str):
    cape = source(name, "capepack").crop(cape_crop)
    kolli_name = "kollipack_216_pallet.png" if name.endswith("216_result.png") else "kollipack_240_pallet.png"
    kolli = source(kolli_name, "kollipack").crop(kolli_crop)
    canvas = Image.new("RGB", (1600, 930), (248, 250, 252))
    draw = ImageDraw.Draw(canvas)
    title = "216 cartons per pallet" if "216" in name else "240 cartons per pallet"
    draw.text((64, 36), title, font=font(42, True), fill=(25, 54, 79))
    draw.text((64, 92), "Matched headline result; screenshot provenance is kept visible.", font=font(24), fill=(86, 105, 124))
    left = (42, 166, 778, 858)
    right = (822, 166, 1558, 858)
    for panel in (left, right):
        draw.rounded_rectangle(panel, radius=18, fill=(255, 255, 255), outline=(213, 224, 234), width=3)
    left_image = fit(cape, (700, 590), (255, 255, 255))
    right_image = fit(kolli, (700, 590), (255, 255, 255))
    canvas.paste(left_image, (60 + (700 - left_image.width) // 2, 196 + (590 - left_image.height) // 2))
    canvas.paste(right_image, (840 + (700 - right_image.width) // 2, 196 + (590 - right_image.height) // 2))
    label_bar(draw, (70, 778), "CapePack Arrange · supplied reference", fill=(56, 83, 105), width=670)
    label_bar(draw, (850, 778), "KolliPack · independent reproduction", fill=(10, 144, 111), width=670)
    canvas.save(OUTPUT / output_name, format="WEBP", quality=92, method=6)


def make_alternatives():
    image = source("kollipack_design_alternatives.png", "kollipack")
    canvas = Image.new("RGB", (1600, 790), (248, 250, 252))
    draw = ImageDraw.Draw(canvas)
    draw.text((64, 30), "Design Mode makes the case geometry inspectable", font=font(40, True), fill=(25, 54, 79))
    draw.text((64, 84), "The source table contains both the 216 and 240 candidates; highlighted rows are not edited.", font=font(23), fill=(86, 105, 124))
    panel = fit(image, (1470, 610), (255, 255, 255))
    x = (1600 - panel.width) // 2
    y = 145
    canvas.paste(panel, (x, y))
    scale = panel.width / image.width
    # Original row geometry: first visible row begins just below the table header;
    # rank 1 is the fifth visible row in the supplied table.
    for row in (0, 4):
        row_origin = 160 if row == 0 else 195
        top = int(y + (row_origin + row * 31) * scale)
        bottom = int(y + (row_origin + 31 + row * 31) * scale)
        draw.rounded_rectangle((x + 5, top, x + panel.width - 5, bottom), radius=8, outline=(16, 163, 127), width=5)
    draw.text((64, 748), "Highlighted: 240-carton 4 × 3 × 1 candidate and 216-carton 3 × 2 × 2 candidate.", font=font(22), fill=(25, 73, 104))
    canvas.save(OUTPUT / "design-mode-alternatives.webp", format="WEBP", quality=92, method=6)


def make_tradeoff_chart():
    canvas = Image.new("RGB", (1600, 900), (248, 250, 252))
    draw = ImageDraw.Draw(canvas)
    draw.text((64, 34), "The flatter case changes the trade-off", font=font(42, True), fill=(25, 54, 79))
    draw.text((64, 92), "Supplied result metrics for the two fixed-quantity designs; each panel uses its own stated unit.", font=font(24), fill=(86, 105, 124))
    groups = [
        ("Floor utilization", [88.5, 77.6], "%", 100),
        ("Cube utilization", [66.2, 75.3], "%", 100),
        ("Primary cartons / pallet", [216, 240], "cartons", 260),
    ]
    colors = [(56, 83, 105), (10, 144, 111)]
    starts = [110, 605, 1100]
    for (title, values, unit, maximum), x in zip(groups, starts):
        draw.text((x, 180), title, font=font(28, True), fill=(25, 54, 79))
        base_y = 720
        top_y = 260
        chart_h = base_y - top_y
        draw.line((x, base_y, x + 360, base_y), fill=(150, 165, 177), width=3)
        for index, value in enumerate(values):
            bar_x = x + 55 + index * 150
            bar_h = chart_h * value / maximum
            draw.rounded_rectangle((bar_x, base_y - bar_h, bar_x + 92, base_y), radius=10, fill=colors[index])
            draw.text((bar_x + 46, base_y - bar_h - 48), f"{value:g}", font=font(25, True), anchor="ms", fill=(25, 54, 79))
            draw.text((bar_x + 46, base_y + 18), "A · 216" if index == 0 else "B · 240", font=font(20, True), anchor="mt", fill=(86, 105, 124))
        draw.text((x, 785), unit, font=font(20), fill=(86, 105, 124))
    draw.text((64, 850), "A = 15 × 12 × 16 in ID, 3 × 2 × 2; B = 20 × 18 × 8 in ID, 4 × 3 × 1.", font=font(22), fill=(25, 73, 104))
    canvas.save(OUTPUT / "case-design-tradeoff.webp", format="WEBP", quality=92, method=6)


def draw_box_stack(draw, origin, scale, cols, rows, layers, palette):
    ox, oy = origin
    w, d, h = 34 * scale, 28 * scale, 22 * scale
    for layer in range(layers):
        z = layer * h * 0.82
        for row in range(rows):
            for col in range(cols):
                x = ox + col * w - row * d * 0.62
                y = oy - z + row * d * 0.38
                draw.polygon([(x, y), (x + w, y - d * 0.28), (x + w + d * 0.62, y), (x + d * 0.62, y + d * 0.28)], fill=palette[0], outline=(120, 220, 210))
                draw.polygon([(x, y), (x + d * 0.62, y + d * 0.28), (x + d * 0.62, y + h), (x, y + h * 0.72)], fill=palette[1], outline=(34, 88, 92))
                draw.polygon([(x + d * 0.62, y + d * 0.28), (x + w + d * 0.62, y), (x + w + d * 0.62, y + h * 0.72), (x + d * 0.62, y + h)], fill=palette[2], outline=(34, 88, 92))


def make_thumbnail_subject():
    image = Image.new("RGBA", (1100, 720), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rectangle((250, 600, 920, 645), fill=(147, 91, 43), outline=(84, 53, 28), width=3)
    draw.rectangle((285, 645, 330, 690), fill=(147, 91, 43), outline=(84, 53, 28), width=3)
    draw.rectangle((815, 645, 860, 690), fill=(147, 91, 43), outline=(84, 53, 28), width=3)
    draw_box_stack(draw, (410, 590), 2.2, 3, 3, 2, ((67, 147, 170), (34, 103, 126), (42, 121, 143)))
    draw.rectangle((700, 600, 1060, 635), fill=(147, 91, 43), outline=(84, 53, 28), width=3)
    draw.rectangle((735, 635, 780, 680), fill=(147, 91, 43), outline=(84, 53, 28), width=3)
    draw.rectangle((980, 635, 1025, 680), fill=(147, 91, 43), outline=(84, 53, 28), width=3)
    draw_box_stack(draw, (770, 590), 1.7, 2, 2, 5, ((77, 177, 168), (22, 107, 105), (38, 137, 132)))
    image.save(THUMBNAIL_OUTPUT / "illustration-v1.png", format="PNG")


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    THUMBNAIL_OUTPUT.mkdir(parents=True, exist_ok=True)
    # The crops retain the numeric result blocks and the relevant 3D views.
    make_parity_figure("capepack_216_result.png", (0, 0, 1287, 520), (1170, 0, 1801, 600), "parity-216-cape-kollipack.webp")
    make_parity_figure("capepack_240_result.png", (0, 0, 897, 430), (1170, 0, 1780, 600), "parity-240-cape-kollipack.webp")
    make_alternatives()
    make_tradeoff_chart()
    make_thumbnail_subject()


if __name__ == "__main__":
    main()
