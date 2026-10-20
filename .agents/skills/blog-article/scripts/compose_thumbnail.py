#!/usr/bin/env python3
"""Compose and validate KolliLabs thumbnails.

The v1 subcommands implement the approved editorial design system. Invocations
that do not begin with a subcommand retain the earlier background/title overlay
interface so historical article tooling does not break.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageColor, ImageDraw, ImageFont

from thumbnail_workflow import (
    OpenAIImageProvider,
    build_illustration_prompt,
    create_preview_sheets,
    create_thumbnail_gallery,
    generate_with_retries,
    load_tokens,
    make_provenance,
    read_json,
    render_thumbnail,
    sha256_text,
    validate_illustration_spec,
    validate_rendered_thumbnail,
    validate_thumbnail_brief,
    validate_reference,
    write_json,
)


SUBCOMMANDS = {"validate", "prompt", "generate", "render", "preview", "gallery"}


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


def legacy_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Legacy KolliLabs thumbnail composer. Prefer the v1 render subcommand for new work."
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
    args = parser.parse_args(argv)

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
    logo.thumbnail((round(args.width * 0.26), round(args.height * 0.15)), Image.Resampling.LANCZOS)
    overlay.alpha_composite(logo, (args.margin, args.margin))

    font_size = round(args.height * 0.085)
    font = load_font(args.font, font_size)
    lines = wrap_text(draw, args.title, font, args.width - (2 * args.margin))
    while len(lines) > 3 and font_size > 30:
        font_size -= 4
        font = load_font(args.font, font_size)
        lines = wrap_text(draw, args.title, font, args.width - (2 * args.margin))

    line_gap = round(font_size * 0.22)
    line_height = draw.textbbox((0, 0), "Ag", font=font)[3] + line_gap
    y = args.height - args.margin - (len(lines) * line_height)
    for line in lines:
        draw.text((args.margin, y), line, font=font, fill="white")
        y += line_height

    result = Image.alpha_composite(background, overlay).convert("RGB")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    save_kwargs = {"quality": 88, "method": 6} if args.output.suffix.lower() == ".webp" else {"quality": 92}
    result.save(args.output, **save_kwargs)
    print(f"Wrote legacy thumbnail {args.output}")
    return 0


def _common_inputs(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--brief", type=Path, required=True)
    parser.add_argument("--spec", type=Path, required=True)


def workflow_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="KolliLabs thumbnail editorial design system v1")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="Validate a thumbnail brief/spec and approved reference")
    _common_inputs(validate_parser)
    validate_parser.add_argument("--report", type=Path)

    prompt_parser = subparsers.add_parser("prompt", help="Build the locked illustration prompt")
    _common_inputs(prompt_parser)
    prompt_parser.add_argument("--output", type=Path, required=True)
    prompt_parser.add_argument(
        "--append-instruction",
        help="Tool-specific instruction appended verbatim and included in the saved prompt hash",
    )

    generate_parser = subparsers.add_parser("generate", help="Generate a subject illustration with the optional Images API adapter")
    _common_inputs(generate_parser)
    generate_parser.add_argument("--reference", type=Path, required=True)
    generate_parser.add_argument("--output", type=Path, required=True)
    generate_parser.add_argument("--attempts-report", type=Path, required=True)
    generate_parser.add_argument("--model", default="gpt-image-2.5-sunburst-2026-09-08")
    generate_parser.add_argument("--max-attempts", type=int, default=3)

    render_parser = subparsers.add_parser("render", help="Render and validate a branded candidate")
    _common_inputs(render_parser)
    render_parser.add_argument("--illustration", type=Path, required=True)
    render_parser.add_argument("--output", type=Path, required=True)
    render_parser.add_argument("--validation", type=Path, required=True)
    render_parser.add_argument("--provenance", type=Path, required=True)
    render_parser.add_argument("--provider", required=True)
    render_parser.add_argument("--model", required=True)
    render_parser.add_argument("--reference-mode", required=True)
    render_parser.add_argument("--attempts", type=int, required=True)
    render_parser.add_argument("--request-id")
    render_parser.add_argument(
        "--prompt-record",
        type=Path,
        help="Saved exact generation prompt; defaults to rebuilding the locked base prompt",
    )

    preview_parser = subparsers.add_parser("preview", help="Create card previews and approved-reference contact sheet")
    preview_parser.add_argument("--first", type=Path, required=True)
    preview_parser.add_argument("--second", type=Path, required=True)
    preview_parser.add_argument("--output-dir", type=Path, required=True)

    gallery_parser = subparsers.add_parser("gallery", help="Create a labeled contact sheet from rendered thumbnails")
    gallery_parser.add_argument(
        "--item",
        action="append",
        required=True,
        metavar="LABEL=PATH",
        help="Labeled thumbnail path; repeat once per card",
    )
    gallery_parser.add_argument("--output", type=Path, required=True)
    gallery_parser.add_argument("--columns", type=int, default=3)

    args = parser.parse_args(argv)
    tokens = load_tokens()

    if args.command == "preview":
        outputs = create_preview_sheets(args.first, args.second, args.output_dir, tokens=tokens)
        print(outputs)
        return 0

    if args.command == "gallery":
        items: list[tuple[str, Path]] = []
        for item in args.item:
            if "=" not in item:
                parser.error(f"--item must use LABEL=PATH: {item!r}")
            label, raw_path = item.split("=", 1)
            if not label.strip() or not raw_path.strip():
                parser.error(f"--item must use a non-empty LABEL=PATH: {item!r}")
            items.append((label.strip(), Path(raw_path.strip())))
        create_thumbnail_gallery(items, args.output, columns=args.columns, tokens=tokens)
        print(f"Wrote {args.output}")
        return 0

    brief = read_json(args.brief)
    spec = read_json(args.spec)
    brief_warnings = validate_thumbnail_brief(brief, tokens=tokens)
    spec_warnings = validate_illustration_spec(spec, brief=brief, tokens=tokens)
    reference_path, reference_sha = validate_reference(tokens)

    if args.command == "validate":
        report = {
            "status": "pass",
            "brief_warnings": brief_warnings,
            "spec_warnings": spec_warnings,
            "reference_path": reference_path.as_posix(),
            "reference_sha256": reference_sha,
        }
        if args.report:
            write_json(args.report, report)
        print(report)
        return 0

    prompt_record = build_illustration_prompt(brief, spec, tokens=tokens)
    if args.command == "prompt":
        if args.append_instruction:
            prompt_record["prompt"] = f"{prompt_record['prompt']}\n\n{args.append_instruction.strip()}"
            prompt_record["prompt_sha256"] = sha256_text(prompt_record["prompt"])
        write_json(args.output, prompt_record)
        print(f"Wrote {args.output}")
        return 0

    if args.command == "generate":
        provider = OpenAIImageProvider(model=args.model)
        generate_with_retries(
            provider,
            prompt=prompt_record["prompt"],
            reference_path=args.reference,
            output_path=args.output,
            attempts_path=args.attempts_report,
            max_attempts=args.max_attempts,
            transparent=spec["blending_strategy"] == "transparent_alpha",
        )
        print(f"Wrote {args.output}")
        return 0

    if args.prompt_record:
        prompt_record = read_json(args.prompt_record)
        expected_prompt_hash = sha256_text(str(prompt_record.get("prompt", "")))
        if prompt_record.get("prompt_sha256") != expected_prompt_hash:
            parser.error(f"Prompt record hash does not match its prompt: {args.prompt_record}")
    render_report = render_thumbnail(brief, spec, args.illustration, args.output, tokens=tokens)
    validation = validate_rendered_thumbnail(args.output, render_report, tokens=tokens)
    write_json(args.validation, validation)
    provenance = make_provenance(
        brief_path=args.brief,
        spec_path=args.spec,
        illustration_path=args.illustration,
        output_path=args.output,
        prompt_record=prompt_record,
        render_report=render_report,
        provider=args.provider,
        model=args.model,
        reference_mode=args.reference_mode,
        attempts=args.attempts,
        request_id=args.request_id,
    )
    write_json(args.provenance, provenance)
    print(f"Wrote {args.output}, {args.validation}, and {args.provenance}")
    return 0


def main() -> int:
    argv = sys.argv[1:]
    if argv and argv[0] in SUBCOMMANDS:
        return workflow_main(argv)
    return legacy_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
