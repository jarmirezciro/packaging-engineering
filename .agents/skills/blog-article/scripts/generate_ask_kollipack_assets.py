#!/usr/bin/env python3
"""Compose the Ask KolliPack article figures from approved production screenshots."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil

from PIL import Image, ImageDraw, ImageFilter, ImageFont


NAVY = "#0f172a"
MUTED = "#64748b"
GREEN = "#10a37f"
GREEN_DARK = "#0b7a60"
GREEN_SOFT = "#ecfdf5"
BACKGROUND = "#f5f7fa"
CARD = "#ffffff"
BORDER = "#dbe2ea"

SOURCE_NAMES = (
    "source-assistant-overview.png",
    "source-assistant-request-clarification.png",
    "source-public-company-question.png",
    "source-assistant-proposal-top.png",
    "source-assistant-proposal-apply.png",
    "source-container-result.png",
    "source-public-packaging-flow-question.png",
    "source-public-design-mode-question.png",
)


def font_path(*, bold: bool) -> str:
    windows = Path("C:/Windows/Fonts/seguisb.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf")
    if windows.is_file():
        return str(windows)
    return "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"


def font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(font_path(bold=bold), size=size)


def wrapped_lines(draw: ImageDraw.ImageDraw, text: str, face, max_width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in text.split("\n"):
        current = ""
        for word in paragraph.split():
            candidate = f"{current} {word}".strip()
            if not current or draw.textbbox((0, 0), candidate, font=face)[2] <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)
    return lines


def draw_wrapped(
    draw: ImageDraw.ImageDraw,
    position: tuple[int, int],
    text: str,
    face,
    fill: str,
    max_width: int,
    *,
    gap: int = 10,
) -> int:
    x, y = position
    for line in wrapped_lines(draw, text, face, max_width):
        draw.text((x, y), line, font=face, fill=fill)
        bounds = draw.textbbox((x, y), line, font=face)
        y = bounds[3] + gap
    return y


def rounded_screenshot(
    canvas: Image.Image,
    source: Image.Image,
    crop: tuple[int, int, int, int],
    *,
    x: int,
    y: int,
    width: int,
    radius: int = 26,
) -> int:
    fragment = source.crop(crop).convert("RGB")
    height = round(fragment.height * width / fragment.width)
    fragment = fragment.resize((width, height), Image.Resampling.LANCZOS)

    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.rounded_rectangle(
        (x + 5, y + 12, x + width + 5, y + height + 12),
        radius=radius,
        fill=(15, 23, 42, 35),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(12))
    canvas.alpha_composite(shadow)

    mask = Image.new("L", (width, height), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, width, height), radius=radius, fill=255)
    canvas.paste(fragment, (x, y), mask)
    ImageDraw.Draw(canvas).rounded_rectangle(
        (x, y, x + width, y + height),
        radius=radius,
        outline=BORDER,
        width=2,
    )
    return height


def label(draw: ImageDraw.ImageDraw, number: str, text: str, y: int) -> int:
    draw.rounded_rectangle((80, y, 142, y + 62), radius=18, fill=GREEN)
    draw.text((102, y + 8), number, font=font(34, bold=True), fill="white")
    draw.text((170, y + 4), text, font=font(42, bold=True), fill=NAVY)
    return y + 82


def save_webp(image: Image.Image, path: Path, *, quality: int = 88) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(path, "WEBP", quality=quality, method=6)
    print(f"Wrote {path} ({image.width}x{image.height})")


def figure_public_expert(assets: Path, sources: dict[str, Image.Image]) -> None:
    canvas = Image.new("RGBA", (1200, 1360), BACKGROUND)
    draw = ImageDraw.Draw(canvas)
    draw.text((80, 70), "Ask KolliPack without opening a tool", font=font(58, bold=True), fill=NAVY)
    draw_wrapped(
        draw,
        (80, 150),
        "The Public Expert explains approved KolliPack concepts while staying outside live calculator state.",
        font(31),
        MUTED,
        1040,
        gap=8,
    )
    height = rounded_screenshot(
        canvas,
        sources["source-public-company-question.png"],
        (0, 0, 546, 530),
        x=180,
        y=270,
        width=840,
        radius=30,
    )
    pill_y = 270 + height + 64
    pills = (
        ("APPROVED KNOWLEDGE", 80, 330),
        ("NO CALCULATOR STATE", 435, 340),
        ("NO ENGINEERING ACTIONS", 800, 320),
    )
    for text, x, width in pills:
        draw.rounded_rectangle((x, pill_y, x + width, pill_y + 72), radius=36, fill=GREEN_SOFT, outline="#b7e4d6", width=2)
        box = draw.textbbox((0, 0), text, font=font(20, bold=True))
        draw.text((x + (width - (box[2] - box[0])) // 2, pill_y + 21), text, font=font(20, bold=True), fill=GREEN_DARK)
    save_webp(canvas, assets / "public-expert-approved-knowledge.webp")


def figure_reviewed_proposal(assets: Path, sources: dict[str, Image.Image]) -> None:
    canvas = Image.new("RGBA", (1200, 2630), BACKGROUND)
    draw = ImageDraw.Draw(canvas)
    draw.text((80, 62), "From a sentence to reviewed inputs", font=font(60, bold=True), fill=NAVY)
    draw_wrapped(
        draw,
        (80, 145),
        "The Assistant interprets the request, prepares a validated proposal, and waits for explicit approval.",
        font(31),
        MUTED,
        1040,
        gap=8,
    )

    y = label(draw, "1", "Describe the engineering intent", 260)
    h = rounded_screenshot(
        canvas,
        sources["source-assistant-request-clarification.png"],
        (16, 98, 475, 448),
        x=150,
        y=y,
        width=900,
    )

    y = label(draw, "2", "Review the proposed values", y + h + 78)
    h = rounded_screenshot(
        canvas,
        sources["source-assistant-proposal-top.png"],
        (20, 110, 477, 572),
        x=220,
        y=y,
        width=760,
    )

    y = label(draw, "3", "Apply the inputs explicitly", y + h + 74)
    rounded_screenshot(
        canvas,
        sources["source-assistant-proposal-apply.png"],
        (24, 387, 474, 655),
        x=220,
        y=y,
        width=760,
    )
    save_webp(canvas, assets / "natural-language-reviewed-input-proposal.webp")


def figure_engine_authority(assets: Path, sources: dict[str, Image.Image]) -> None:
    canvas = Image.new("RGBA", (1200, 1560), BACKGROUND)
    draw = ImageDraw.Draw(canvas)
    draw.text((80, 62), "AI assists. KolliPack calculates.", font=font(62, bold=True), fill=NAVY)
    draw_wrapped(
        draw,
        (80, 150),
        "Input changes remain separate from the deterministic engineering calculation.",
        font(31),
        MUTED,
        1040,
        gap=8,
    )

    draw.text((150, 255), "AI helps define the problem", font=font(40, bold=True), fill=GREEN_DARK)
    h = rounded_screenshot(
        canvas,
        sources["source-assistant-proposal-apply.png"],
        (24, 387, 474, 655),
        x=170,
        y=325,
        width=860,
    )
    divider_y = 325 + h + 55
    draw.line((220, divider_y + 42, 980, divider_y + 42), fill="#b7e4d6", width=4)
    draw.ellipse((548, divider_y, 652, divider_y + 104), fill=GREEN)
    draw.text((577, divider_y + 13), "↓", font=font(56, bold=True), fill="white")

    heading_y = divider_y + 145
    draw.text((150, heading_y), "KolliPack calculates the answer", font=font(40, bold=True), fill=NAVY)
    rounded_screenshot(
        canvas,
        sources["source-container-result.png"],
        (28, 18, 573, 282),
        x=170,
        y=heading_y + 72,
        width=860,
    )
    save_webp(canvas, assets / "assistant-inputs-kollipack-calculation.webp")


def thumbnail(assets: Path, sources: dict[str, Image.Image]) -> None:
    canvas = Image.new("RGBA", (1200, 630), BACKGROUND)
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((850, 0, 1200, 630), radius=0, fill=GREEN_DARK)
    draw.rounded_rectangle((72, 54, 475, 145), radius=26, fill=CARD, outline=BORDER, width=2)

    header = sources["source-assistant-overview.png"].crop((18, 18, 326, 84)).convert("RGBA")
    header.thumbnail((355, 70), Image.Resampling.LANCZOS)
    canvas.alpha_composite(header, (94, 66))

    draw.text((72, 208), "ASK KOLLIPACK", font=font(84, bold=True), fill=NAVY)
    draw.text((76, 328), "ASK. REASON. APPLY.", font=font(42, bold=True), fill=GREEN_DARK)
    draw_wrapped(
        draw,
        (76, 404),
        "Conversational packaging and logistics engineering",
        font(31),
        MUTED,
        690,
        gap=8,
    )

    steps = (("ASK", 95), ("REVIEW", 246), ("APPLY", 397))
    for text, y in steps:
        draw.rounded_rectangle((905, y, 1145, y + 92), radius=46, fill="white")
        box = draw.textbbox((0, 0), text, font=font(31, bold=True))
        draw.text((1025 - (box[2] - box[0]) // 2, y + 25), text, font=font(31, bold=True), fill=GREEN_DARK)
    draw.line((1025, 187, 1025, 236), fill="#8fe0c7", width=6)
    draw.line((1025, 338, 1025, 387), fill="#8fe0c7", width=6)
    save_webp(canvas, assets / "thumbnail.webp", quality=90)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--assets-dir", type=Path, required=True)
    parser.add_argument(
        "--source",
        type=Path,
        action="append",
        default=[],
        help="Eight approved screenshots in the task-supplied order; copied to semantic source names.",
    )
    args = parser.parse_args()
    args.assets_dir.mkdir(parents=True, exist_ok=True)

    if args.source:
        if len(args.source) != len(SOURCE_NAMES):
            raise SystemExit(f"Expected {len(SOURCE_NAMES)} --source values, received {len(args.source)}")
        for source, name in zip(args.source, SOURCE_NAMES):
            shutil.copy2(source, args.assets_dir / name)

    missing = [name for name in SOURCE_NAMES if not (args.assets_dir / name).is_file()]
    if missing:
        raise SystemExit("Missing preserved source screenshots: " + ", ".join(missing))

    sources = {name: Image.open(args.assets_dir / name).convert("RGBA") for name in SOURCE_NAMES}
    figure_public_expert(args.assets_dir, sources)
    figure_reviewed_proposal(args.assets_dir, sources)
    figure_engine_authority(args.assets_dir, sources)
    thumbnail(args.assets_dir, sources)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
