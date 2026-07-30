#!/usr/bin/env python3
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[4]
OUTPUT_DIR = ROOT / "static" / "img" / "blog" / "rsc-material-optimization"
APPROVED_MARK_SOURCE = (
    ROOT
    / "static"
    / "img"
    / "blog"
    / "box-selection-3d-bin-packing-problem"
    / "blog1_thumbnail_kollipack_box_selection.png"
)

NAVY = "#17324d"
GREEN = "#168a5b"
GREEN_DARK = "#0f6b49"
TEAL = "#18a5a5"
MUTED = "#64748b"
LINE = "#cbd5e1"
BACKGROUND = "#f6f8f9"
WHITE = "#ffffff"
CARDBOARD = "#d9b178"
CARDBOARD_LIGHT = "#efd4a8"
CARDBOARD_DARK = "#b98549"
GREEN_TINT = "#eaf7f0"
BLUE_TINT = "#eef5fb"
ORANGE = "#f59e0b"

FONT_BOLD = Path("C:/Windows/Fonts/arialbd.ttf")
FONT_REGULAR = Path("C:/Windows/Fonts/arial.ttf")


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = FONT_BOLD if bold else FONT_REGULAR
    return ImageFont.truetype(str(path), size)


def canvas(size: tuple[int, int]) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", size, BACKGROUND)
    return image, ImageDraw.Draw(image)


def save(image: Image.Image, name: str, quality: int = 90) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / name
    image.save(path, "WEBP", quality=quality, method=6)
    print(f"Wrote {path}")


def header(
    draw: ImageDraw.ImageDraw,
    title: str,
    subtitle: str,
    width: int,
    *,
    y: int = 52,
) -> int:
    draw.text((64, y), title, fill=NAVY, font=font(52, True))
    draw.text((64, y + 70), subtitle, fill=MUTED, font=font(25))
    draw.rounded_rectangle((width - 238, y + 3, width - 64, y + 48), radius=22, fill=GREEN_TINT)
    draw.text((width - 214, y + 12), "KolliPack", fill=GREEN_DARK, font=font(23, True))
    return y + 145


def card(
    draw: ImageDraw.ImageDraw,
    bounds: tuple[int, int, int, int],
    *,
    fill: str = WHITE,
    outline: str = LINE,
    radius: int = 28,
) -> None:
    draw.rounded_rectangle(bounds, radius=radius, fill=fill, outline=outline, width=2)


def centered_text(
    draw: ImageDraw.ImageDraw,
    bounds: tuple[int, int, int, int],
    text: str,
    text_font: ImageFont.FreeTypeFont,
    fill: str,
) -> None:
    box = draw.textbbox((0, 0), text, font=text_font)
    x = bounds[0] + (bounds[2] - bounds[0] - (box[2] - box[0])) / 2
    y = bounds[1] + (bounds[3] - bounds[1] - (box[3] - box[1])) / 2
    draw.text((x, y), text, fill=fill, font=text_font)


def draw_box_iso(
    draw: ImageDraw.ImageDraw,
    origin: tuple[float, float],
    dims: tuple[float, float, float],
    scale: float,
    *,
    label: str | None = None,
    area_label: str | None = None,
) -> tuple[int, int, int, int]:
    x, y = origin
    length, breadth, height = dims
    w = length * scale
    d = breadth * scale * 0.48
    h = height * scale
    p0 = (x, y)
    p1 = (x + w, y)
    p2 = (x + w + d, y - d * 0.55)
    p3 = (x + d, y - d * 0.55)
    p4 = (x, y - h)
    p5 = (x + w, y - h)
    p6 = (x + w + d, y - h - d * 0.55)
    p7 = (x + d, y - h - d * 0.55)

    draw.polygon([p0, p1, p5, p4], fill=CARDBOARD, outline=NAVY)
    draw.polygon([p1, p2, p6, p5], fill=CARDBOARD_DARK, outline=NAVY)
    draw.polygon([p4, p5, p6, p7], fill=CARDBOARD_LIGHT, outline=NAVY)
    for a, b in ((p0, p1), (p1, p2), (p4, p5), (p5, p6), (p6, p7), (p7, p4), (p0, p4), (p1, p5), (p2, p6)):
        draw.line([a, b], fill=NAVY, width=3)

    if label:
        label_box = (int(x - 10), int(y + 18), int(x + w + d + 10), int(y + 58))
        centered_text(draw, label_box, label, font(22, True), NAVY)
    if area_label:
        area_box = (int(x - 10), int(y + 58), int(x + w + d + 10), int(y + 94))
        centered_text(draw, area_box, area_label, font(19, True), GREEN_DARK)

    return (
        int(x),
        int(y - h - d * 0.55),
        int(x + w + d),
        int(y + 95),
    )


def flap_depths(style: str, length: float, breadth: float) -> tuple[list[float], list[float]]:
    if style == "0200":
        return [0, 0, 0, 0], [breadth / 2] * 4
    if style == "0201":
        return [breadth / 2] * 4, [breadth / 2] * 4
    if style == "0203":
        return [breadth] * 4, [breadth] * 4
    if style == "0204":
        return [breadth / 2, length / 2, breadth / 2, length / 2], [
            breadth / 2,
            length / 2,
            breadth / 2,
            length / 2,
        ]
    raise ValueError(style)


def retained_area(style: str, length: float, breadth: float, height: float) -> float:
    widths = [length, breadth, length, breadth]
    top, bottom = flap_depths(style, length, breadth)
    body = sum(widths) * height
    return body + sum(w * d for w, d in zip(widths, top)) + sum(
        w * d for w, d in zip(widths, bottom)
    )


def draw_blank(
    draw: ImageDraw.ImageDraw,
    origin: tuple[float, float],
    style: str,
    dims: tuple[float, float, float],
    scale: float,
    *,
    label_panels: bool = False,
) -> tuple[int, int, int, int]:
    x0, body_y = origin
    length, breadth, height = dims
    widths = [length, breadth, length, breadth]
    labels = ["L", "B", "L", "B"]
    top, bottom = flap_depths(style, length, breadth)
    max_top = max(top)
    max_bottom = max(bottom)
    x = x0
    for panel_width, panel_label, top_depth, bottom_depth in zip(widths, labels, top, bottom):
        x1 = x
        x2 = x + panel_width * scale
        y1 = body_y
        y2 = body_y + height * scale
        draw.rectangle((x1, y1, x2, y2), fill=CARDBOARD_LIGHT, outline=NAVY, width=2)
        if top_depth:
            draw.rectangle(
                (x1, y1 - top_depth * scale, x2, y1),
                fill=CARDBOARD,
                outline=NAVY,
                width=2,
            )
        if bottom_depth:
            draw.rectangle(
                (x1, y2, x2, y2 + bottom_depth * scale),
                fill=CARDBOARD,
                outline=NAVY,
                width=2,
            )
        if label_panels:
            box = draw.textbbox((0, 0), panel_label, font=font(17, True))
            draw.text(
                (
                    (x1 + x2 - (box[2] - box[0])) / 2,
                    (y1 + y2 - (box[3] - box[1])) / 2,
                ),
                panel_label,
                fill=NAVY,
                font=font(17, True),
            )
        x = x2
    return (
        int(x0),
        int(body_y - max_top * scale),
        int(x),
        int(body_y + height * scale + max_bottom * scale),
    )


def arrow(
    draw: ImageDraw.ImageDraw,
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    fill: str = GREEN,
    width: int = 5,
) -> None:
    draw.line([start, end], fill=fill, width=width)
    angle = math.atan2(end[1] - start[1], end[0] - start[0])
    for delta in (2.55, -2.55):
        p = (
            end[0] + 17 * math.cos(angle + delta),
            end[1] + 17 * math.sin(angle + delta),
        )
        draw.line([end, p], fill=fill, width=width)


def double_arrow(
    draw: ImageDraw.ImageDraw,
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    fill: str = GREEN,
    width: int = 4,
) -> None:
    arrow(draw, start, end, fill=fill, width=width)
    arrow(draw, end, start, fill=fill, width=width)


def figure_1() -> None:
    image, draw = canvas((1600, 900))
    content_y = header(
        draw,
        "Geometry changes board demand in two ways",
        "Equal volume can hide different proportions; equal dimensions can hide different constructions.",
        1600,
    )
    left = (52, content_y, 790, 842)
    right = (810, content_y, 1548, 842)
    card(draw, left)
    card(draw, right)

    draw.text((86, content_y + 32), "A  Same construction, equal volume", fill=NAVY, font=font(28, True))
    draw.text((86, content_y + 72), "100-litre FEFCO 0201 boxes", fill=MUTED, font=font(21))
    boxes = [
        ((585, 292, 585), "2:1:2", "100.0%"),
        ((737, 368, 368), "2:1:1", "105.8%"),
        ((464, 464, 464), "1:1:1", "112.0%"),
    ]
    origins = [(112, 657), (330, 657), (590, 657)]
    for origin, (dims, label, area_label) in zip(origins, boxes):
        draw_box_iso(draw, origin, dims, 0.22, label=label, area_label=area_label)
    draw.rounded_rectangle((105, 756, 735, 815), radius=24, fill=GREEN_TINT)
    centered_text(draw, (105, 756, 735, 815), "Same volume  ≠  same blank area", font(24, True), GREEN_DARK)

    draw.text((844, content_y + 32), "B  Equal internal dimensions", fill=NAVY, font=font(28, True))
    draw.text((844, content_y + 72), "600 × 300 × 600 mm", fill=MUTED, font=font(21))
    draw_blank(draw, (862, content_y + 265), "0200", (600, 300, 600), 0.18)
    draw_blank(draw, (1200, content_y + 265), "0203", (600, 300, 600), 0.18)
    centered_text(draw, (850, 680, 1198, 715), "FEFCO 0200", font(22, True), NAVY)
    centered_text(draw, (850, 715, 1198, 750), "1.350 m²", font(23, True), GREEN_DARK)
    centered_text(draw, (1188, 680, 1536, 715), "FEFCO 0203", font(22, True), NAVY)
    centered_text(draw, (1188, 715, 1536, 750), "2.160 m²", font(23, True), GREEN_DARK)
    draw.rounded_rectangle((858, 770, 1500, 825), radius=24, fill=BLUE_TINT)
    centered_text(
        draw,
        (858, 770, 1500, 825),
        "Same dimensions  ≠  same retained area",
        font(24, True),
        NAVY,
    )
    save(image, "figure-1-geometry-material-demand.webp")


def figure_2() -> None:
    image, draw = canvas((1600, 900))
    content_y = header(
        draw,
        "FEFCO 0201 blank geometry",
        "Four body panels plus top and bottom flaps create a blank approximately 2(L+B) by H+B.",
        1600,
    )
    left = (52, content_y, 620, 842)
    right = (640, content_y, 1548, 842)
    card(draw, left)
    card(draw, right)
    draw.text((86, content_y + 32), "Erected RSC", fill=NAVY, font=font(30, True))
    draw_box_iso(draw, (145, 710), (600, 300, 600), 0.58)
    draw.text((282, 744), "L", fill=GREEN_DARK, font=font(25, True))
    draw.text((508, 674), "B", fill=GREEN_DARK, font=font(25, True))
    draw.text((105, 420), "H", fill=GREEN_DARK, font=font(25, True))

    draw.text((674, content_y + 32), "Unfolded blank", fill=NAVY, font=font(30, True))
    blank = draw_blank(draw, (720, 345), "0201", (600, 300, 600), 0.38, label_panels=True)
    double_arrow(draw, (blank[0], 730), (blank[2], 730))
    centered_text(draw, (blank[0], 738, blank[2], 780), "2(L + B)", font(25, True), GREEN_DARK)
    double_arrow(draw, (1465, blank[1]), (1465, blank[3]))
    draw.text((1480, 465), "H + B", fill=GREEN_DARK, font=font(23, True))
    double_arrow(draw, (690, blank[1]), (690, 345))
    draw.text((650, 260), "B/2", fill=GREEN_DARK, font=font(20, True))
    double_arrow(draw, (690, 573), (690, blank[3]))
    draw.text((650, 640), "B/2", fill=GREEN_DARK, font=font(20, True))
    draw.rounded_rectangle((775, 785, 1410, 830), radius=20, fill=GREEN_TINT)
    centered_text(draw, (775, 785, 1410, 830), "A = 2(L+B)(H+B)", font(25, True), GREEN_DARK)
    save(image, "figure-2-fefco-0201-blank-geometry.webp")


def figure_3() -> None:
    image, draw = canvas((1600, 760))
    header(
        draw,
        "How the 2:1:2 result follows",
        "The image summarizes the logic; the article keeps every equation as selectable text.",
        1600,
    )
    labels = [
        ("Blank geometry", "A = 2(L+B)(H+B)"),
        ("Fixed volume", "V = LBH"),
        ("Height condition", "L = H"),
        ("Breadth condition", "H = 2B"),
        ("Material minimum", "L:B:H = 2:1:2"),
    ]
    x_positions = [52, 360, 668, 976, 1284]
    colors = [WHITE, WHITE, BLUE_TINT, BLUE_TINT, GREEN_TINT]
    for index, ((title, formula), x, fill) in enumerate(zip(labels, x_positions, colors)):
        bounds = (x, 265, x + 264, 560)
        card(draw, bounds, fill=fill)
        draw.rounded_rectangle((x + 24, 292, x + 82, 350), radius=28, fill=GREEN)
        centered_text(draw, (x + 24, 292, x + 82, 350), str(index + 1), font(24, True), WHITE)
        centered_text(draw, (x + 18, 372, x + 246, 430), title, font(24, True), NAVY)
        centered_text(draw, (x + 18, 448, x + 246, 516), formula, font(22, True), GREEN_DARK)
        if index < len(labels) - 1:
            arrow(draw, (x + 270, 412), (x + 300, 412), fill=TEAL, width=5)
    draw.rounded_rectangle((392, 620, 1208, 700), radius=34, fill=NAVY)
    centered_text(
        draw,
        (392, 620, 1208, 700),
        "A fixed-volume benchmark—not a universal box specification",
        font(25, True),
        WHITE,
    )
    save(image, "figure-3-mathematical-result.webp")


def figure_4() -> None:
    image, draw = canvas((1600, 900))
    content_y = header(
        draw,
        "Same 100-litre volume, different board area",
        "The construction stays FEFCO 0201. Only the L:B:H proportions change.",
        1600,
    )
    configs = [
        ((585, 292, 585), "2:1:2", "585 × 292 × 585 mm", "1.539 m²", "100.0%"),
        ((737, 368, 368), "2:1:1", "737 × 368 × 368 mm", "1.629 m²", "105.8%"),
        ((464, 464, 464), "1:1:1", "464 × 464 × 464 mm", "1.724 m²", "112.0%"),
    ]
    xs = [52, 562, 1072]
    for index, (x, (dims, ratio, dimensions, area, relative)) in enumerate(zip(xs, configs)):
        bounds = (x, content_y, x + 476, 842)
        card(draw, bounds, fill=GREEN_TINT if index == 0 else WHITE)
        draw.rounded_rectangle((x + 30, content_y + 28, x + 160, content_y + 76), radius=20, fill=GREEN if index == 0 else NAVY)
        centered_text(draw, (x + 30, content_y + 28, x + 160, content_y + 76), ratio, font(24, True), WHITE)
        draw_box_iso(draw, (x + 78, 585), dims, 0.43)
        centered_text(draw, (x + 30, 660, x + 446, 700), dimensions, font(23, True), NAVY)
        centered_text(draw, (x + 30, 715, x + 446, 755), area, font(24, True), GREEN_DARK)
        draw.rounded_rectangle((x + 95, 775, x + 381, 823), radius=22, fill=NAVY if index else GREEN)
        centered_text(draw, (x + 95, 775, x + 381, 823), relative + " relative area", font(20, True), WHITE)
    save(image, "figure-4-equal-volume-comparison.webp")


def figure_5() -> None:
    image, draw = canvas((1600, 1110))
    content_y = header(
        draw,
        "Same internal dimensions, different construction",
        "Each idealized blank encloses 600 × 300 × 600 mm, but flap geometry changes retained area.",
        1600,
    )
    configs = [
        ("0200", "Half Slotted", "1.350 m²", "83.3%"),
        ("0201", "Regular Slotted", "1.620 m²", "100.0%"),
        ("0203", "Full Overlap Slotted", "2.160 m²", "133.3%"),
        ("0204", "Center Special Slotted", "1.800 m²", "111.1%"),
    ]
    positions = [(52, content_y), (810, content_y), (52, 630), (810, 630)]
    for (style, name, area, relative), (x, y) in zip(configs, positions):
        bounds = (x, y, x + 738, y + 425)
        card(draw, bounds, fill=GREEN_TINT if style == "0201" else WHITE)
        draw.rounded_rectangle((x + 28, y + 24, x + 130, y + 68), radius=20, fill=GREEN if style == "0201" else NAVY)
        centered_text(draw, (x + 28, y + 24, x + 130, y + 68), style, font(22, True), WHITE)
        draw.text((x + 152, y + 30), name, fill=NAVY, font=font(24, True))
        draw_blank(draw, (x + 70, y + 150), style, (600, 300, 600), 0.27)
        draw.text((x + 565, y + 160), area, fill=GREEN_DARK, font=font(25, True))
        draw.text((x + 565, y + 200), relative, fill=NAVY, font=font(22, True))
        draw.text((x + 565, y + 232), "of 0201", fill=MUTED, font=font(18))
    draw.rounded_rectangle((440, 1062, 1160, 1102), radius=20, fill=NAVY)
    centered_text(draw, (440, 1062, 1160, 1102), "Equal internal space does not mean equal board demand", font(23, True), WHITE)
    save(image, "figure-5-same-dimensions-construction.webp")


def thumbnail() -> None:
    image, draw = canvas((1200, 630))
    draw.rectangle((0, 0, 1200, 630), fill="#f3f6f7")
    draw.rounded_rectangle((48, 46, 1152, 584), radius=34, fill=WHITE, outline=LINE, width=2)

    mark_source = Image.open(APPROVED_MARK_SOURCE).convert("RGB")
    mark = mark_source.crop((45, 52, 470, 184))
    mark.thumbnail((340, 106), Image.Resampling.LANCZOS)
    image.paste(mark, (78, 72))

    draw.text((78, 214), "GEOMETRY", fill=NAVY, font=font(64, True))
    draw.text((78, 285), "HAS A COST", fill=GREEN, font=font(64, True))
    draw.text((82, 376), "Same volume.", fill=MUTED, font=font(28))
    draw.text((82, 414), "Different material.", fill=NAVY, font=font(28, True))
    draw.rounded_rectangle((78, 487, 340, 543), radius=26, fill=NAVY)
    centered_text(draw, (78, 487, 340, 543), "FEFCO 0201 · 2:1:2", font(20, True), WHITE)

    draw_box_iso(draw, (676, 495), (585, 292, 585), 0.34)
    draw_box_iso(draw, (929, 495), (464, 464, 464), 0.34)
    centered_text(draw, (620, 520, 875, 556), "100.0% area", font(20, True), GREEN_DARK)
    centered_text(draw, (900, 520, 1130, 556), "112.0% area", font(20, True), NAVY)
    arrow(draw, (868, 337), (925, 337), fill=ORANGE, width=7)
    save(image, "thumbnail.webp", quality=92)


def verify_calculations() -> None:
    length, breadth, height = 600.0, 300.0, 600.0
    expected = {
        "0200": 1_350_000.0,
        "0201": 1_620_000.0,
        "0203": 2_160_000.0,
        "0204": 1_800_000.0,
    }
    for style, area in expected.items():
        assert math.isclose(retained_area(style, length, breadth, height), area)

    volume = 100_000_000.0
    ratios = [(2.0, 1.0, 2.0), (2.0, 1.0, 1.0), (1.0, 1.0, 1.0)]
    areas = []
    for l_ratio, b_ratio, h_ratio in ratios:
        base = (volume / (l_ratio * b_ratio * h_ratio)) ** (1 / 3)
        dims = (l_ratio * base, b_ratio * base, h_ratio * base)
        areas.append(retained_area("0201", *dims))
    assert math.isclose(areas[1] / areas[0], 1.0582673679787997)
    assert math.isclose(areas[2] / areas[0], 1.1199298221289906)


def main() -> int:
    verify_calculations()
    figure_1()
    figure_2()
    figure_3()
    figure_4()
    figure_5()
    thumbnail()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
