#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

try:
    from PIL import Image, ImageColor, ImageDraw, ImageFont
except ImportError as exc:
    raise SystemExit("Pillow is required: install it in the active environment.") from exc


def fit_background(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    target_w, target_h = size
    source_w, source_h = image.size
    scale = max(target_w / source_w, target_h / source_h)
    resized = image.resize((round(source_w * scale), round(source_h * scale)), Image.Resampling.LANCZOS)
    left = (resized.width - target_w) // 2
    top = (resized.height - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))


def load_font(path: Path | None, size: int):
    if path:
        return ImageFont.truetype(str(path), size=size)
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf", size=size)
    except OSError:
        return ImageFont.load_default()


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        box = draw.textbbox((0, 0), candidate, font=font)
        if box[2] - box[0] <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compose a repeatable KolliLabs article thumbnail from a generated background and official logo."
    )
    parser.add_argument("--background", type=Path, required=True)
    parser.add_argument("--logo", type=Path, required=True, help="Canonical official logo from the repository")
    parser.add_argument("--title", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--accent", required=True, help="Actual project brand color, e.g. #1A7F4B")
    parser.add_argument("--width", type=int, default=1200)
    parser.add_argument("--height", type=int, default=630)
    parser.add_argument("--margin", type=int, default=64)
    parser.add_argument("--font", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    if args.output.exists() and not args.overwrite:
        raise SystemExit(f"Output exists: {args.output}. Pass --overwrite to replace it.")

    size = (args.width, args.height)
    background = fit_background(Image.open(args.background).convert("RGB"), size).convert("RGBA")
    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    accent = ImageColor.getrgb(args.accent)
    panel_height = round(args.height * 0.42)
    draw.rectangle((0, args.height - panel_height, args.width, args.height), fill=(*accent, 226))

    logo = Image.open(args.logo).convert("RGBA")
    max_logo_w = round(args.width * 0.26)
    max_logo_h = round(args.height * 0.15)
    logo.thumbnail((max_logo_w, max_logo_h), Image.Resampling.LANCZOS)
    overlay.alpha_composite(logo, (args.margin, args.margin))

    font_size = round(args.height * 0.085)
    font = load_font(args.font, font_size)
    max_text_width = args.width - (2 * args.margin)
    lines = wrap_text(draw, args.title, font, max_text_width)
    while len(lines) > 3 and font_size > 30:
        font_size -= 4
        font = load_font(args.font, font_size)
        lines = wrap_text(draw, args.title, font, max_text_width)

    line_gap = round(font_size * 0.22)
    line_height = draw.textbbox((0, 0), "Ag", font=font)[3] + line_gap
    total_height = len(lines) * line_height
    y = args.height - args.margin - total_height
    for line in lines:
        draw.text((args.margin, y), line, font=font, fill="white")
        y += line_height

    result = Image.alpha_composite(background, overlay).convert("RGB")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    save_kwargs = {"quality": 88, "method": 6} if args.output.suffix.lower() == ".webp" else {"quality": 92}
    result.save(args.output, **save_kwargs)
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
