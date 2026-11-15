"""Draw conceptual subjects and reflow the authentic seven-tile legend.

The editorial-figures renderer adds all labels and card layout to the subject art.
The retained 1582 × 905 KolliPack capture supplies the legend tiles.
"""

from pathlib import Path
import sys

from PIL import Image, ImageDraw, ImageFilter


ARTIFACTS = Path(__file__).resolve().parent
STATIC = ARTIFACTS.parents[1] / "static/img/blog/mixed-cargo-loading-delivery-sequence"
ART = ARTIFACTS / "figure-art"
GREEN = "#0D9279"
NAVY = "#344D63"
KRAFT = ("#F0C994", "#D8A168", "#C28B58")
TEAL = ("#83CDBC", "#52AA99", "#388978")
AMBER = ("#F4CB8A", "#E2A552", "#C88C38")
SLATE = ("#E6EDF0", "#B5CAD1", "#879FA9")


def scene():
    return Image.new("RGBA", (460, 298))


def shadow(image, box):
    layer = scene()
    ImageDraw.Draw(layer).ellipse(box, fill=(18, 39, 51, 48))
    image.alpha_composite(layer.filter(ImageFilter.GaussianBlur(12)))


def cuboid(draw, x, y, length, width, height, colors=KRAFT, taped=False):
    """Draw a rectangular unit from its front-bottom corner in an isometric view."""
    a = (x, y - height)
    b = (x + length * .86, a[1] + length * .41)
    c = (b[0] + width * .86, b[1] - width * .41)
    d = (x + width * .86, a[1] - width * .41)
    down = lambda point: (point[0], point[1] + height)
    outline = "#816447" if colors == KRAFT else "#57777D"
    for points, fill in (
        ((a, b, down(b), down(a)), colors[1]),
        ((b, c, down(c), down(b)), colors[2]),
        ((a, b, c, d), colors[0]),
    ):
        draw.polygon(points, fill=fill, outline=outline, width=2)
    if taped:
        seam = ((a[0] + d[0]) / 2, (a[1] + d[1]) / 2)
        end = ((b[0] + c[0]) / 2, (b[1] + c[1]) / 2)
        draw.line((seam, end), fill="#F9DFB6", width=8)
        draw.line((end, (end[0], end[1] + min(18, height))), fill="#EFC795", width=8)


def arrow(draw, x1, y1, x2, y2):
    draw.line((x1, y1, x2, y2), fill=GREEN, width=5)
    if x1 == x2:
        draw.polygon(((x2, y2), (x2-9, y2+15), (x2+9, y2+15)), fill=GREEN)
    else:
        draw.polygon(((x2, y2), (x2-15, y2-9), (x2-15, y2+9)), fill=GREEN)


def cargo(image, draw):
    shadow(image, (58, 205, 409, 274))
    cuboid(draw, 69, 158, 72, 75, 102, taped=True)
    cuboid(draw, 196, 168, 90, 115, 47, taped=True)
    cuboid(draw, 258, 233, 79, 60, 48, taped=True)
    cuboid(draw, 112, 231, 93, 73, 58, taped=True)


def stops(image, draw):
    draw.rounded_rectangle((19, 194, 441, 252), radius=25, fill="#E1E9EB")
    arrow(draw, 73, 223, 389, 223)
    shadow(image, (46, 167, 409, 201))
    for x, color in ((41, AMBER), (254, TEAL)):
        cuboid(draw, x, 133, 81, 85, 63, SLATE)
        draw.polygon(((x+13, 102), (x+52, 120), (x+52, 157), (x+13, 139)), fill=NAVY)
        draw.line((x+61, 155, x+124, 184), fill=color[2], width=5)
        cuboid(draw, x+61, 145, 45, 44, 31, color)
        cx = x+58
        draw.polygon(((cx-13, 57), (cx+13, 57), (cx, 80)), fill=color[2])
        draw.ellipse((cx-15, 42, cx+15, 71), fill=color[2])
        draw.ellipse((cx-5, 50, cx+5, 60), fill="#FFFFFF")


def rear_trailer(image, draw):
    shadow(image, (38, 219, 444, 286))
    for x, y in ((237, 255), (269, 267)):
        draw.ellipse((x-17, y-19, x+17, y+19), fill=NAVY, outline="#213745", width=2)
        draw.ellipse((x-7, y-8, x+7, y+8), fill="#AFC2CA")
    draw.line((94, 168, 94, 221), fill=NAVY, width=10)
    draw.line((82, 221, 106, 221), fill=NAVY, width=5)
    cuboid(draw, 49, 151, 294, 93, 107, SLATE)
    draw.polygon(((305, 169), (380, 134), (380, 236), (305, 272)), fill="#34505B", outline="#6D8B96", width=3)
    cuboid(draw, 312, 260, 23, 31, 35, taped=True)
    cuboid(draw, 341, 249, 20, 29, 47, taped=True)
    draw.polygon(((380, 134), (428, 144), (428, 245), (380, 236)), fill="#DCE7EA", outline="#6D8B96", width=3)
    draw.line((414, 154, 414, 229), fill="#8FA7AF", width=4)
    draw.line((56, 153, 299, 267), fill="#D7E3E7", width=4)


def orientations(image, draw):
    for x, dims, color in (
        (17, (61, 37, 96), AMBER),
        (167, (96, 37, 61), TEAL),
        (312, (96, 61, 37), SLATE),
    ):
        length, width, height = dims
        shadow(image, (x-5, 205, x+131, 248))
        y = 208 - length * .41
        cuboid(draw, x, y, length, width, height, color)
        arrow_x = round(x + (length + width) * .43)
        arrow(draw, arrow_x, round(y-height-14), arrow_x, round(y-height-57))


def stackability(image, draw):
    shadow(image, (10, 201, 234, 260))
    shadow(image, (240, 201, 452, 260))
    cuboid(draw, 25, 176, 109, 86, 67, TEAL)
    cuboid(draw, 52, 122, 72, 58, 54, taped=True)
    cuboid(draw, 260, 176, 109, 86, 67, AMBER)
    draw.line(((274, 86), (402, 86)), fill="#B7723D", width=4)
    draw.line(((330, 63), (348, 81)), fill="#B7723D", width=5)
    draw.line(((348, 63), (330, 81)), fill="#B7723D", width=5)


def sequence(image, draw):
    shadow(image, (24, 170, 407, 220))
    draw.rounded_rectangle((27, 75, 402, 176), radius=11, fill="#EBF0F1", outline="#839DA5", width=4)
    draw.rectangle((43, 91, 211, 160), fill=TEAL[1])
    draw.rectangle((215, 91, 385, 160), fill=AMBER[1])
    draw.line((39, 176, 377, 176), fill=NAVY, width=6)
    draw.line((56, 176, 56, 194), fill=NAVY, width=7)
    for x in (318, 355):
        draw.ellipse((x-16, 170, x+16, 201), fill=NAVY)
        draw.ellipse((x-6, 180, x+6, 191), fill="#B5CAD1")
    draw.line((403, 77, 431, 55), fill=NAVY, width=6)
    draw.line((403, 175, 431, 195), fill=NAVY, width=6)
    arrow(draw, 337, 127, 445, 127)


def make_legend(capture):
    starts = (28, 246, 463, 680, 898, 1115, 1333)
    with Image.open(capture) as screenshot:
        assert screenshot.size == (1582, 905)
        source = screenshot.convert("RGB")
        tiles = [source.crop((x, 420, x+142, 468)) for x in starts]
    row_height = 58
    column_width = 152
    for columns, suffix in ((4, ""), (2, "-mobile")):
        rows = [tiles[i:i+columns] for i in range(0, len(tiles), columns)]
        legend = Image.new("RGB", (columns*column_width, len(rows)*row_height), "#F5F7F9")
        for i, row in enumerate(rows):
            offset = (columns-len(row))*column_width//2
            for j, tile in enumerate(row):
                legend.paste(tile, (offset+j*column_width+5, i*row_height+5))
        legend.resize((legend.width*2, legend.height*2), Image.Resampling.LANCZOS).save(
            STATIC / f"progressive-infill-product-legend{suffix}.webp", lossless=True
        )


if __name__ == "__main__":
    ART.mkdir(exist_ok=True)
    for name, draw_subject in (
        ("cargo", cargo), ("stops", stops), ("rear-trailer", rear_trailer),
        ("orientations", orientations), ("stackability", stackability), ("sequence", sequence),
    ):
        image = scene()
        draw_subject(image, ImageDraw.Draw(image))
        image = image.crop(image.getbbox())
        image.save(ART / f"{name}.png")
    capture = Path(sys.argv[1]) if len(sys.argv) > 1 else ARTIFACTS / "loading-view-source.png"
    make_legend(capture)
