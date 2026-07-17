#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

try:
    from PIL import Image, ImageOps
except ImportError as exc:
    raise SystemExit("Pillow is required: install it in the active environment.") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="Optimize a blog image and export WebP.")
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--max-width", type=int, default=1800)
    parser.add_argument("--max-height", type=int, default=1400)
    parser.add_argument("--quality", type=int, default=86)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    if args.output.exists() and not args.overwrite:
        raise SystemExit(f"Output exists: {args.output}. Pass --overwrite to replace it.")

    image = ImageOps.exif_transpose(Image.open(args.input)).convert("RGB")
    image.thumbnail((args.max_width, args.max_height), Image.Resampling.LANCZOS)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    image.save(args.output, format="WEBP", quality=args.quality, method=6)
    print(f"Wrote {args.output} ({image.width}×{image.height})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
