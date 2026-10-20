"""KolliLabs thumbnail workflow v1.

This module keeps the editorial contract, prompt assembly, provider boundary,
deterministic card renderer, validation, and preview generation in one small
content-tooling surface. It does not participate in Django request handling.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Protocol

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps
except ImportError as exc:  # pragma: no cover - environment failure path
    raise SystemExit("Pillow is required for the thumbnail workflow.") from exc


REPO_ROOT = Path(__file__).resolve().parents[4]
SKILL_ROOT = Path(__file__).resolve().parents[1]
TOKENS_PATH = SKILL_ROOT / "assets" / "thumbnail-design-tokens-v1.json"
BASE_PROMPT_PATH = SKILL_ROOT / "assets" / "thumbnail-illustration-prompt-v1.txt"
BRIEF_SCHEMA_VERSION = "1.0"
ILLUSTRATION_SCHEMA_VERSION = "1.0"
PROMPT_VERSION = "1.0.0"
REFERENCE_STANDARD = "thumbnail-design-system-v1"
IMAGE_MODES = {"editorial_illustration", "evidence_derived"}
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
NUMBER_RE = re.compile(r"(?<![A-Za-z])(?:[+\-])?\d[\d,.]*(?:\s?%|\s?→\s?\d[\d,.]*)?")


class ThumbnailWorkflowError(RuntimeError):
    """Base exception for expected workflow failures."""


class SchemaValidationError(ThumbnailWorkflowError):
    def __init__(self, errors: Iterable[str]):
        self.errors = list(errors)
        super().__init__("; ".join(self.errors))


class RenderValidationError(ThumbnailWorkflowError):
    pass


class ProviderUnavailableError(ThumbnailWorkflowError):
    pass


class UnsupportedReferenceError(ThumbnailWorkflowError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_tokens(path: Path = TOKENS_PATH) -> dict[str, Any]:
    payload = read_json(path)
    required = {"design_standard_version", "renderer_template_version", "canvas", "palette", "layout", "reference"}
    missing = sorted(required - payload.keys())
    if missing:
        raise SchemaValidationError([f"Design tokens are missing: {', '.join(missing)}"])
    return payload


def resolve_repo_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


def _require_string(payload: Mapping[str, Any], field: str, errors: list[str]) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{field} must be a non-empty string")
        return ""
    return value.strip()


def _normalized_claim_token(value: str) -> str:
    return re.sub(r"[\s,]", "", value).casefold()


def numeric_tokens(*values: str) -> list[str]:
    tokens: list[str] = []
    for value in values:
        tokens.extend(match.group(0).strip() for match in NUMBER_RE.finditer(value or ""))
    return tokens


def validate_thumbnail_brief(brief: Mapping[str, Any], *, tokens: Mapping[str, Any] | None = None) -> list[str]:
    tokens = tokens or load_tokens()
    errors: list[str] = []
    warnings: list[str] = []

    schema_version = _require_string(brief, "schema_version", errors)
    article_slug = _require_string(brief, "article_slug", errors)
    composition = _require_string(brief, "composition", errors)
    hook_primary = _require_string(brief, "hook_primary", errors)
    hook_secondary = brief.get("hook_secondary", "")
    support_line = _require_string(brief, "support_line", errors)
    _require_string(brief, "scene_subject", errors)
    image_mode = _require_string(brief, "image_mode", errors)
    reference_standard = _require_string(brief, "reference_standard", errors)

    if schema_version and schema_version != BRIEF_SCHEMA_VERSION:
        errors.append(f"schema_version must be {BRIEF_SCHEMA_VERSION}")
    if article_slug and not SLUG_RE.fullmatch(article_slug):
        errors.append("article_slug must be lowercase kebab-case")
    if composition and composition not in tokens["scene_families"]:
        errors.append(f"composition must be one of {sorted(tokens['scene_families'])}")
    if image_mode and image_mode not in IMAGE_MODES:
        errors.append(f"image_mode must be one of {sorted(IMAGE_MODES)}")
    if reference_standard and reference_standard != REFERENCE_STANDARD:
        errors.append(f"reference_standard must be {REFERENCE_STANDARD}")
    if brief.get("screenshots_allowed") is not False:
        errors.append("screenshots_allowed must be false")
    if hook_secondary is not None and not isinstance(hook_secondary, str):
        errors.append("hook_secondary must be a string when supplied")
        hook_secondary = ""

    limits = tokens["limits"]
    for field, value, ideal_key, max_key in (
        ("hook_primary", hook_primary, "hook_primary_ideal_chars", "hook_primary_max_chars"),
        ("hook_secondary", str(hook_secondary or ""), "hook_secondary_ideal_chars", "hook_secondary_max_chars"),
        ("support_line", support_line, "support_line_ideal_chars", "support_line_max_chars"),
    ):
        if len(value) > limits[max_key]:
            errors.append(f"{field} exceeds the hard {limits[max_key]}-character limit")
        elif len(value) > limits[ideal_key]:
            warnings.append(f"{field} exceeds the preferred {limits[ideal_key]}-character budget; renderer measurement is required")

    claims = brief.get("supported_claims")
    if not isinstance(claims, list):
        errors.append("supported_claims must be a list")
        claims = []
    normalized_claims: list[str] = []
    for index, claim in enumerate(claims):
        if not isinstance(claim, Mapping):
            errors.append(f"supported_claims[{index}] must be an object")
            continue
        text = claim.get("text")
        evidence = claim.get("evidence")
        source = claim.get("source")
        if not isinstance(text, str) or not text.strip():
            errors.append(f"supported_claims[{index}].text must be non-empty")
        else:
            normalized_claims.append(_normalized_claim_token(text))
        if not isinstance(evidence, str) or len(evidence.strip()) < 12:
            errors.append(f"supported_claims[{index}].evidence must describe the accepted evidence")
        if not isinstance(source, str) or not source.strip():
            errors.append(f"supported_claims[{index}].source must identify the article or evidence file")

    displayed_numbers = numeric_tokens(hook_primary, str(hook_secondary or ""), support_line)
    for displayed in displayed_numbers:
        normalized = _normalized_claim_token(displayed)
        if not any(normalized in claim for claim in normalized_claims):
            errors.append(f"Displayed numeric claim {displayed!r} has no matching supported_claims entry")

    if image_mode == "evidence_derived":
        evidence_assets = brief.get("evidence_asset_paths")
        if not isinstance(evidence_assets, list) or not evidence_assets:
            errors.append("evidence_derived briefs require evidence_asset_paths")

    if errors:
        raise SchemaValidationError(errors)
    return warnings


def validate_illustration_spec(
    spec: Mapping[str, Any],
    *,
    brief: Mapping[str, Any] | None = None,
    tokens: Mapping[str, Any] | None = None,
) -> list[str]:
    tokens = tokens or load_tokens()
    errors: list[str] = []
    warnings: list[str] = []

    schema_version = _require_string(spec, "schema_version", errors)
    article_slug = _require_string(spec, "article_slug", errors)
    scene_family = _require_string(spec, "scene_family", errors)
    camera = _require_string(spec, "camera", errors)
    materials = _require_string(spec, "materials", errors)
    lighting = _require_string(spec, "lighting", errors)
    blending_strategy = _require_string(spec, "blending_strategy", errors)
    image_mode = _require_string(spec, "image_mode", errors)

    if schema_version and schema_version != ILLUSTRATION_SCHEMA_VERSION:
        errors.append(f"schema_version must be {ILLUSTRATION_SCHEMA_VERSION}")
    if article_slug and not SLUG_RE.fullmatch(article_slug):
        errors.append("article_slug must be lowercase kebab-case")
    if scene_family and scene_family not in tokens["scene_families"]:
        errors.append(f"scene_family must be one of {sorted(tokens['scene_families'])}")
    if image_mode and image_mode not in IMAGE_MODES:
        errors.append(f"image_mode must be one of {sorted(IMAGE_MODES)}")
    if "three-quarter" not in camera.casefold() and "isometric" not in camera.casefold():
        warnings.append("camera should normally specify three-quarter or isometric-like framing")
    if blending_strategy not in {"transparent_alpha", "teal_studio_matte"}:
        errors.append("blending_strategy must be transparent_alpha or teal_studio_matte")

    subjects = spec.get("subjects")
    if not isinstance(subjects, list) or not subjects:
        errors.append("subjects must be a non-empty list")
        subjects = []
    unknown_subjects = sorted({str(subject) for subject in subjects} - set(tokens["allowed_subjects"]))
    if unknown_subjects:
        errors.append(f"Unsupported subjects: {', '.join(unknown_subjects)}")

    reserved = spec.get("reserved_blank_zones")
    if not isinstance(reserved, list) or "left_text_zone" not in reserved:
        errors.append("reserved_blank_zones must include left_text_zone")

    exclusions = spec.get("exclusions")
    required_exclusions = {"text", "logos", "people", "screenshots", "watermarks"}
    if not isinstance(exclusions, list):
        errors.append("exclusions must be a list")
        exclusions = []
    missing_exclusions = sorted(required_exclusions - {str(value) for value in exclusions})
    if missing_exclusions:
        errors.append(f"exclusions must include: {', '.join(missing_exclusions)}")

    if image_mode == "evidence_derived":
        evidence_assets = spec.get("evidence_asset_paths")
        if not isinstance(evidence_assets, list) or not evidence_assets:
            errors.append("evidence_derived specs require evidence_asset_paths")

    if brief:
        if article_slug and article_slug != brief.get("article_slug"):
            errors.append("spec article_slug must match the brief")
        if scene_family and scene_family != brief.get("composition"):
            errors.append("spec scene_family must match brief composition")
        if image_mode and image_mode != brief.get("image_mode"):
            errors.append("spec image_mode must match the brief")

    for value, label in ((materials, "materials"), (lighting, "lighting")):
        if len(value) > 320:
            errors.append(f"{label} is too long; use a normalized specification")

    if errors:
        raise SchemaValidationError(errors)
    return warnings


def validate_reference(tokens: Mapping[str, Any] | None = None) -> tuple[Path, str]:
    tokens = tokens or load_tokens()
    reference = resolve_repo_path(tokens["reference"]["path"])
    if not reference.is_file():
        raise SchemaValidationError([f"Approved reference image is missing: {reference}"])
    actual_sha = sha256_file(reference)
    expected_sha = tokens["reference"]["sha256"]
    if actual_sha != expected_sha:
        raise SchemaValidationError([f"Approved reference SHA mismatch: expected {expected_sha}, got {actual_sha}"])
    return reference, actual_sha


def build_illustration_prompt(
    brief: Mapping[str, Any],
    spec: Mapping[str, Any],
    *,
    tokens: Mapping[str, Any] | None = None,
    base_prompt_path: Path = BASE_PROMPT_PATH,
) -> dict[str, str]:
    tokens = tokens or load_tokens()
    validate_thumbnail_brief(brief, tokens=tokens)
    validate_illustration_spec(spec, brief=brief, tokens=tokens)

    variable_values = [
        str(brief["scene_subject"]),
        " ".join(str(value) for value in spec["subjects"]),
        str(spec["camera"]),
        str(spec["materials"]),
        str(spec["lighting"]),
        str(spec["blending_strategy"]),
        " ".join(str(value) for value in spec["exclusions"]),
    ]
    forbidden = ("kollilabs", "kollipack")
    if any(term in value.casefold() for term in forbidden for value in variable_values):
        raise SchemaValidationError(["Illustration variables must not ask the image model to render brand names"])

    template = base_prompt_path.read_text(encoding="utf-8").strip()
    rendered = template.format(
        family_clause=tokens["scene_families"][spec["scene_family"]],
        scene_subject=brief["scene_subject"],
        subjects=", ".join(spec["subjects"]),
        camera=spec["camera"],
        materials=spec["materials"],
        lighting=spec["lighting"],
        blending_strategy=spec["blending_strategy"],
        exclusions=", ".join(spec["exclusions"]),
    )
    return {
        "prompt_version": PROMPT_VERSION,
        "prompt_template_sha256": sha256_file(base_prompt_path),
        "prompt_sha256": sha256_text(rendered),
        "prompt": rendered,
    }


def _resolve_font(candidates: Iterable[str], size: int) -> tuple[ImageFont.FreeTypeFont, str]:
    errors: list[str] = []
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size), candidate
        except OSError as exc:
            errors.append(f"{candidate}: {exc}")
    raise RenderValidationError("No approved font candidate is available: " + " | ".join(errors))


def _font_with_path(tokens: Mapping[str, Any], size: int, *, bold: bool) -> tuple[ImageFont.FreeTypeFont, str]:
    key = "bold_candidates" if bold else "regular_candidates"
    return _resolve_font(tokens["fonts"][key], size)


def _hex(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[index : index + 2], 16) for index in (0, 2, 4))


def _mix(left: tuple[int, int, int], right: tuple[int, int, int], amount: float) -> tuple[int, int, int]:
    return tuple(round(a + (b - a) * amount) for a, b in zip(left, right))


def create_studio_background(tokens: Mapping[str, Any]) -> Image.Image:
    width = int(tokens["canvas"]["width"])
    height = int(tokens["canvas"]["height"])
    start = _hex(tokens["palette"]["near_black"])
    end = _hex(tokens["palette"]["deep_teal"])
    image = Image.new("RGB", (width, height), start)
    draw = ImageDraw.Draw(image)
    for x in range(width):
        eased = (x / max(width - 1, 1)) ** 0.84
        draw.line((x, 0, x, height), fill=_mix(start, end, eased))

    atmosphere = Image.new("RGBA", image.size, (0, 0, 0, 0))
    atmosphere_draw = ImageDraw.Draw(atmosphere)
    atmosphere_draw.ellipse((560, -170, 1450, 660), fill=(17, 112, 99, 105))
    atmosphere_draw.ellipse((470, 390, 1420, 840), fill=(15, 81, 75, 95))
    atmosphere = atmosphere.filter(ImageFilter.GaussianBlur(115))
    image = Image.alpha_composite(image.convert("RGBA"), atmosphere)

    floor = Image.new("RGBA", image.size, (0, 0, 0, 0))
    floor_draw = ImageDraw.Draw(floor)
    floor_draw.ellipse((520, 545, 1320, 745), fill=(18, 125, 105, 35))
    floor_draw.line((520, 610, 1260, 610), fill=(91, 202, 177, 32), width=2)
    floor = floor.filter(ImageFilter.GaussianBlur(18))
    return Image.alpha_composite(image, floor)


def _extract_approved_lockup(reference_path: Path, tokens: Mapping[str, Any]) -> Image.Image:
    with Image.open(reference_path) as board:
        crop = board.convert("RGB").crop(tuple(tokens["reference"]["logo_crop"]))

    rgba = Image.new("RGBA", crop.size, (0, 0, 0, 0))
    source = crop.load()
    target = rgba.load()
    for y in range(crop.height):
        for x in range(crop.width):
            red, green, blue = source[x, y]
            brightness = max(red, green, blue)
            mint_signal = green - max(red, blue)
            white_signal = min(red, green, blue)
            alpha = max((brightness - 70) * 4, (white_signal - 70) * 4, (mint_signal - 8) * 5)
            alpha = max(0, min(255, alpha))
            if alpha < 18:
                alpha = 0
            target[x, y] = (red, green, blue, alpha)

    bbox = rgba.getbbox()
    if not bbox:
        raise RenderValidationError("Could not extract the approved lockup from the reference board")
    return rgba.crop(bbox)


def _wrap_lines(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    words = text.split()
    if not words:
        return []
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        box = draw.textbbox((0, 0), candidate, font=font)
        if box[2] - box[0] <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _fit_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    *,
    tokens: Mapping[str, Any],
    max_width: int,
    max_lines: int,
    size_max: int,
    size_min: int,
    bold: bool,
) -> tuple[ImageFont.FreeTypeFont, str, list[str]]:
    for size in range(size_max, size_min - 1, -2):
        font, font_path = _font_with_path(tokens, size, bold=bold)
        lines = _wrap_lines(draw, text, font, max_width)
        if len(lines) <= max_lines and all(draw.textbbox((0, 0), line, font=font)[2] <= max_width for line in lines):
            return font, font_path, lines
    raise RenderValidationError(f"Text does not fit the approved zone without going below {size_min}px: {text!r}")


def _illustration_layer(
    illustration_path: Path,
    zone: tuple[int, int, int, int],
    blending_strategy: str,
) -> tuple[Image.Image, dict[str, Any]]:
    with Image.open(illustration_path) as opened:
        source = opened.convert("RGBA")
        source_format = opened.format

    alpha = source.getchannel("A")
    alpha_extrema = alpha.getextrema()
    has_transparency = alpha_extrema[0] < 255
    # Image generators may leave numerically non-zero but visually empty alpha
    # across the canvas. Ignore that sub-visible fringe when calculating scale,
    # while retaining the original soft edge pixels inside the tightened crop.
    visible_alpha = alpha.point(lambda value: 255 if value >= 4 else 0)
    bbox = visible_alpha.getbbox() if has_transparency else source.getbbox()
    if not bbox:
        raise RenderValidationError("Illustration is empty")
    source = source.crop(bbox)

    left, top, right, bottom = zone
    max_size = (right - left, bottom - top)
    fitted = ImageOps.contain(source, max_size, Image.Resampling.LANCZOS)
    if not has_transparency:
        if blending_strategy == "transparent_alpha":
            raise RenderValidationError("Illustration requested transparent_alpha but the file is fully opaque")
        mask = Image.new("L", fitted.size, 255)
        edge = max(20, round(min(fitted.size) * 0.055))
        edge_mask = Image.new("L", fitted.size, 0)
        ImageDraw.Draw(edge_mask).rounded_rectangle(
            (edge, edge, fitted.width - edge, fitted.height - edge),
            radius=max(24, edge),
            fill=255,
        )
        mask = edge_mask.filter(ImageFilter.GaussianBlur(edge))
        fitted.putalpha(mask)

    x = right - fitted.width
    y = top + max(0, (bottom - top - fitted.height) // 2)
    layer = Image.new("RGBA", (1280, 720), (0, 0, 0, 0))
    layer.alpha_composite(fitted, (x, y))
    return layer, {
        "source_format": source_format,
        "source_size": list(source.size),
        "has_transparency": has_transparency,
        "placed_box": [x, y, x + fitted.width, y + fitted.height],
    }


def _draw_primary(
    draw: ImageDraw.ImageDraw,
    text: str,
    position: tuple[int, int],
    font: ImageFont.FreeTypeFont,
    *,
    white: str,
    mint: str,
) -> tuple[int, int, int, int]:
    x, y = position
    if text.endswith("%") and len(text) > 1:
        base = text[:-1]
        draw.text((x, y), base, font=font, fill=white)
        base_box = draw.textbbox((x, y), base, font=font)
        draw.text((base_box[2] - 2, y), "%", font=font, fill=mint)
        return draw.textbbox((x, y), text, font=font)
    draw.text((x, y), text, font=font, fill=white)
    return draw.textbbox((x, y), text, font=font)


def render_thumbnail(
    brief: Mapping[str, Any],
    spec: Mapping[str, Any],
    illustration_path: Path,
    output_path: Path,
    *,
    tokens: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    tokens = tokens or load_tokens()
    brief_warnings = validate_thumbnail_brief(brief, tokens=tokens)
    spec_warnings = validate_illustration_spec(spec, brief=brief, tokens=tokens)
    reference_path, reference_sha = validate_reference(tokens)
    if not illustration_path.is_file():
        raise RenderValidationError(f"Illustration does not exist: {illustration_path}")

    canvas = create_studio_background(tokens)
    layout = tokens["layout"]
    palette = tokens["palette"]
    illustration_zone = tuple(layout["illustration_zone"])
    illustration, illustration_meta = _illustration_layer(
        illustration_path,
        illustration_zone,
        str(spec["blending_strategy"]),
    )

    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    placed = illustration_meta["placed_box"]
    shadow_draw.ellipse(
        (placed[0] + 30, min(674, placed[3] - 72), placed[2] - 10, min(710, placed[3] + 12)),
        fill=(0, 0, 0, 115),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(24))
    canvas = Image.alpha_composite(canvas, shadow)
    canvas = Image.alpha_composite(canvas, illustration)

    text_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(text_layer)
    x = int(layout["margin_left"])
    text_width = int(layout["text_zone_right"]) - x

    kicker_font, kicker_font_path = _font_with_path(tokens, int(layout["kicker_size"]), bold=True)
    kicker_prefix = "KOLLILABS / "
    draw.text((x, int(layout["margin_top"])), kicker_prefix, font=kicker_font, fill=palette["white"])
    kicker_prefix_box = draw.textbbox((x, int(layout["margin_top"])), kicker_prefix, font=kicker_font)
    draw.text((kicker_prefix_box[2], int(layout["margin_top"])), "INSIGHTS", font=kicker_font, fill=palette["mint"])

    primary_font, primary_font_path, primary_lines = _fit_text(
        draw,
        str(brief["hook_primary"]),
        tokens=tokens,
        max_width=text_width,
        max_lines=1,
        size_max=int(layout["primary_size_max"]),
        size_min=int(layout["primary_size_min"]),
        bold=True,
    )
    if len(primary_lines) != 1:
        raise RenderValidationError("hook_primary must fit one line")
    primary_box = _draw_primary(
        draw,
        primary_lines[0],
        (x, 132),
        primary_font,
        white=palette["white"],
        mint=palette["mint"],
    )

    secondary_text = str(brief.get("hook_secondary") or "").strip()
    secondary_lines: list[str] = []
    secondary_boxes: list[list[int]] = []
    secondary_font_path = primary_font_path
    cursor_y = primary_box[3] + 12
    if secondary_text:
        secondary_font, secondary_font_path, secondary_lines = _fit_text(
            draw,
            secondary_text,
            tokens=tokens,
            max_width=text_width,
            max_lines=2,
            size_max=int(layout["secondary_size_max"]),
            size_min=int(layout["secondary_size_min"]),
            bold=True,
        )
        secondary_fill = palette["mint"] if spec["scene_family"] in {"benchmark", "product", "hero"} else palette["white"]
        line_step = round(secondary_font.size * 1.02)
        for line in secondary_lines:
            draw.text((x, cursor_y), line, font=secondary_font, fill=secondary_fill)
            box = draw.textbbox((x, cursor_y), line, font=secondary_font)
            secondary_boxes.append(list(box))
            cursor_y += line_step
        cursor_y += 19
    else:
        cursor_y += 18

    support_font, support_font_path, support_lines = _fit_text(
        draw,
        str(brief["support_line"]),
        tokens=tokens,
        max_width=text_width,
        max_lines=4,
        size_max=int(layout["support_size_max"]),
        size_min=int(layout["support_size_min"]),
        bold=False,
    )
    support_boxes: list[list[int]] = []
    support_step = round(support_font.size * 1.18)
    for line in support_lines:
        draw.text((x, cursor_y), line, font=support_font, fill=palette["neutral"])
        box = draw.textbbox((x, cursor_y), line, font=support_font)
        support_boxes.append(list(box))
        cursor_y += support_step

    if support_boxes and support_boxes[-1][3] > 592:
        raise RenderValidationError("Support text collides with the approved lower-left brand zone")

    lockup = _extract_approved_lockup(reference_path, tokens)
    target_logo_width = int(layout["logo_width"])
    target_logo_height = round(lockup.height * target_logo_width / lockup.width)
    lockup = lockup.resize((target_logo_width, target_logo_height), Image.Resampling.LANCZOS)
    logo_y = int(tokens["canvas"]["height"]) - int(layout["logo_bottom"]) - lockup.height
    text_layer.alpha_composite(lockup, (x, logo_y))

    canvas = Image.alpha_composite(canvas, text_layer).convert("RGB")
    expected_size = (int(tokens["canvas"]["width"]), int(tokens["canvas"]["height"]))
    if canvas.size != expected_size:
        raise RenderValidationError(f"Renderer produced {canvas.size}, expected {expected_size}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    suffix = output_path.suffix.casefold()
    if suffix == ".webp":
        canvas.save(output_path, format="WEBP", quality=92, method=6)
    elif suffix == ".png":
        canvas.save(output_path, format="PNG", optimize=True)
    else:
        raise RenderValidationError("Final thumbnail must be .webp or .png")

    layout_report = {
        "canvas": list(canvas.size),
        "text_zone": [x, int(layout["margin_top"]), int(layout["text_zone_right"]), 592],
        "illustration_zone": list(illustration_zone),
        "primary_box": list(primary_box),
        "secondary_boxes": secondary_boxes,
        "support_boxes": support_boxes,
        "logo_box": [x, logo_y, x + lockup.width, logo_y + lockup.height],
        "font_paths": {
            "kicker": kicker_font_path,
            "primary": primary_font_path,
            "secondary": secondary_font_path,
            "support": support_font_path,
        },
        "font_sizes": {
            "kicker": kicker_font.size,
            "primary": primary_font.size,
            "secondary": secondary_font.size if secondary_text else None,
            "support": support_font.size,
        },
        "illustration": illustration_meta,
    }
    layout_report["layout_sha256"] = sha256_text(json.dumps(layout_report, sort_keys=True))
    return {
        "status": "pass",
        "warnings": brief_warnings + spec_warnings,
        "reference_sha256": reference_sha,
        "output_sha256": sha256_file(output_path),
        "output_bytes": output_path.stat().st_size,
        "layout": layout_report,
    }


def validate_rendered_thumbnail(
    output_path: Path,
    render_report: Mapping[str, Any],
    *,
    tokens: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    tokens = tokens or load_tokens()
    hard_failures: list[str] = []
    warnings = list(render_report.get("warnings", []))
    expected_size = (int(tokens["canvas"]["width"]), int(tokens["canvas"]["height"]))
    if not output_path.is_file():
        hard_failures.append("output file is missing")
        image_size = None
        image_format = None
        image_mode = None
    else:
        with Image.open(output_path) as image:
            image.load()
            image_size = image.size
            image_format = image.format
            image_mode = image.mode
        if image_size != expected_size:
            hard_failures.append(f"output dimensions are {image_size}, expected {expected_size}")
        if image_format not in {"WEBP", "PNG"}:
            hard_failures.append(f"unsupported output format {image_format}")
        if image_mode not in {"RGB", "RGBA"}:
            hard_failures.append(f"unsupported color mode {image_mode}")
        if output_path.stat().st_size > int(tokens["limits"]["max_output_bytes"]):
            hard_failures.append("output exceeds the configured file-size ceiling")
        if not re.fullmatch(r"thumbnail-v\d+\.(?:webp|png)", output_path.name, re.IGNORECASE):
            hard_failures.append("candidate output filename must match thumbnail-v<version>.webp or .png")

    layout = render_report.get("layout") or {}
    for box_name in ("primary_box", "logo_box"):
        box = layout.get(box_name)
        if not isinstance(box, list) or len(box) != 4:
            hard_failures.append(f"{box_name} metadata is missing")
            continue
        if box[0] < 0 or box[1] < 0 or box[2] > expected_size[0] or box[3] > expected_size[1]:
            hard_failures.append(f"{box_name} exceeds the canvas")
    for collection_name in ("secondary_boxes", "support_boxes"):
        for box in layout.get(collection_name, []):
            if box[0] < 0 or box[1] < 0 or box[2] > expected_size[0] or box[3] > expected_size[1]:
                hard_failures.append(f"{collection_name} contains a clipped box")

    visual_checks = [
        "Owner confirms family resemblance to the approved nine-tile board.",
        "Subject is clear at 360 × 203 px and remains in the right-hand zone.",
        "No stray text, fake labels, people, UI fragments, clutter, or misleading exact count appears.",
        "Lighting, materials, perspective, and palette feel coherent with the approved studio reference.",
    ]
    return {
        "schema_version": "1.0",
        "hard_status": "fail" if hard_failures else "pass",
        "visual_status": "review_required",
        "approval_status": "review_required",
        "hard_failures": hard_failures,
        "warnings": warnings,
        "visual_review_checklist": visual_checks,
        "file": {
            "path": output_path.as_posix(),
            "dimensions": list(image_size) if image_size else None,
            "format": image_format,
            "mode": image_mode,
            "bytes": output_path.stat().st_size if output_path.is_file() else None,
            "sha256": sha256_file(output_path) if output_path.is_file() else None,
        },
        "layout": layout,
    }


def can_publish(validation: Mapping[str, Any], provenance: Mapping[str, Any]) -> bool:
    return (
        validation.get("hard_status") == "pass"
        and validation.get("visual_status") == "approved"
        and provenance.get("approval_status") in {"approved", "staged", "published"}
    )


def make_provenance(
    *,
    brief_path: Path,
    spec_path: Path,
    illustration_path: Path,
    output_path: Path,
    prompt_record: Mapping[str, Any],
    render_report: Mapping[str, Any],
    provider: str,
    model: str,
    reference_mode: str,
    attempts: int,
    request_id: str | None = None,
    usage: Mapping[str, Any] | None = None,
    error_reason: str | None = None,
) -> dict[str, Any]:
    tokens = load_tokens()
    reference_path, reference_sha = validate_reference(tokens)
    spec = read_json(spec_path)
    with Image.open(illustration_path) as illustration:
        illustration.load()
        illustration_format = illustration.format
        illustration_mode = illustration.mode
        illustration_size = list(illustration.size)
        alpha_received = "A" in illustration.getbands() and illustration.getchannel("A").getextrema()[0] < 255
    generation_performed = attempts > 0
    return {
        "schema_version": "1.0",
        "created_at": utc_now(),
        "design_standard_version": tokens["design_standard_version"],
        "renderer_template_version": tokens["renderer_template_version"],
        "prompt_version": prompt_record["prompt_version"],
        "prompt_template_sha256": prompt_record["prompt_template_sha256"],
        "prompt_sha256": prompt_record["prompt_sha256"],
        "prompt": prompt_record["prompt"],
        "reference_asset": str(reference_path.relative_to(REPO_ROOT)).replace("\\", "/"),
        "reference_sha256": reference_sha,
        "provider": provider,
        "model": model,
        "reference_mode": reference_mode,
        "request_id": request_id,
        "generation_attempts": attempts,
        "generation_performed": generation_performed,
        "generation_parameters": {
            "candidate_count": 1 if generation_performed else 0,
            "reference_image_supplied": generation_performed and reference_mode != "text_only",
            "transparent_background_requested": generation_performed and spec.get("blending_strategy") == "transparent_alpha",
            "transparent_background_received": alpha_received,
            "output_dimensions_received": illustration_size,
            "output_format_received": illustration_format,
            "output_mode_received": illustration_mode,
            "quality": (
                "not-applicable-rerender"
                if not generation_performed
                else "undisclosed-by-tool"
                if provider == "openai-built-in-imagegen"
                else "high"
            ),
            "illustration_reused": not generation_performed,
        },
        "usage": dict(usage) if usage else None,
        "error_reason": error_reason,
        "brief_path": brief_path.as_posix(),
        "brief_sha256": sha256_file(brief_path),
        "illustration_spec_path": spec_path.as_posix(),
        "illustration_spec_sha256": sha256_file(spec_path),
        "illustration_path": illustration_path.as_posix(),
        "illustration_sha256": sha256_file(illustration_path),
        "thumbnail_path": output_path.as_posix(),
        "thumbnail_sha256": sha256_file(output_path),
        "render_layout_sha256": render_report["layout"]["layout_sha256"],
        "approval_status": "review_required",
        "release_status": "not_staged",
        "rollback_target": "Existing published article thumbnail/front matter remain unchanged.",
    }


@dataclass(frozen=True)
class ProviderCapabilities:
    supports_reference_images: bool
    supports_transparent_background: bool


class ImageProvider(Protocol):
    name: str
    model: str
    capabilities: ProviderCapabilities

    def generate(
        self,
        *,
        prompt: str,
        reference_path: Path | None,
        output_path: Path,
        transparent: bool,
    ) -> Mapping[str, Any]: ...


class OpenAIImageProvider:
    """Optional official Images API adapter; imported only for live generation."""

    name = "openai-images-api"
    capabilities = ProviderCapabilities(
        supports_reference_images=True,
        supports_transparent_background=True,
    )

    def __init__(self, *, model: str = "gpt-image-2.5-sunburst-2026-09-08", client: Any | None = None):
        self.model = model
        self._client = client

    def _client_or_raise(self) -> Any:
        if self._client is not None:
            return self._client
        if not os.environ.get("OPENAI_API_KEY"):
            raise ProviderUnavailableError("OPENAI_API_KEY is not configured")
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ProviderUnavailableError("The official openai package is not installed") from exc
        return OpenAI()

    def generate(
        self,
        *,
        prompt: str,
        reference_path: Path | None,
        output_path: Path,
        transparent: bool,
    ) -> Mapping[str, Any]:
        client = self._client_or_raise()
        common = {
            "model": self.model,
            "prompt": prompt,
            "size": "1280x720",
            "quality": "high",
            "background": "transparent" if transparent else "opaque",
            "output_format": "png",
        }
        if reference_path:
            if not self.capabilities.supports_reference_images:
                raise UnsupportedReferenceError(f"Provider {self.name} does not support reference images")
            encoded = base64.b64encode(reference_path.read_bytes()).decode("ascii")
            mime = "image/png" if reference_path.suffix.casefold() == ".png" else "image/webp"
            result = client.images.edit(images=[{"image_url": f"data:{mime};base64,{encoded}"}], **common)
            reference_mode = "images_edit_reference"
        else:
            result = client.images.generate(**common)
            reference_mode = "text_only"

        data = getattr(result, "data", None) or []
        if not data or not getattr(data[0], "b64_json", None):
            raise ProviderUnavailableError("Provider returned no base64 image payload")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(base64.b64decode(data[0].b64_json))
        usage = getattr(result, "usage", None)
        if hasattr(usage, "model_dump"):
            usage = usage.model_dump()
        return {
            "request_id": getattr(result, "_request_id", None),
            "usage": usage,
            "reference_mode": reference_mode,
        }


def generate_with_retries(
    provider: ImageProvider,
    *,
    prompt: str,
    reference_path: Path | None,
    output_path: Path,
    attempts_path: Path,
    max_attempts: int = 3,
    transparent: bool = True,
) -> dict[str, Any]:
    if not 1 <= max_attempts <= 3:
        raise ValueError("max_attempts must be between 1 and 3")
    if reference_path and not provider.capabilities.supports_reference_images:
        report = {
            "status": "failed",
            "provider": provider.name,
            "model": provider.model,
            "attempts": [],
            "error_reason": "reference_images_unsupported",
            "approval_status": "review_required",
        }
        write_json(attempts_path, report)
        raise UnsupportedReferenceError(f"Provider {provider.name} does not support reference images")
    if transparent and not provider.capabilities.supports_transparent_background:
        report = {
            "status": "failed",
            "provider": provider.name,
            "model": provider.model,
            "attempts": [],
            "error_reason": "transparent_background_unsupported",
            "approval_status": "review_required",
        }
        write_json(attempts_path, report)
        raise ProviderUnavailableError(f"Provider {provider.name} does not support transparent backgrounds")

    attempts: list[dict[str, Any]] = []
    for attempt in range(1, max_attempts + 1):
        started = utc_now()
        try:
            metadata = dict(
                provider.generate(
                    prompt=prompt,
                    reference_path=reference_path,
                    output_path=output_path,
                    transparent=transparent,
                )
            )
            attempts.append({"attempt": attempt, "started_at": started, "status": "succeeded"})
            report = {
                "status": "succeeded",
                "provider": provider.name,
                "model": provider.model,
                "attempts": attempts,
                "metadata": metadata,
                "approval_status": "review_required",
            }
            write_json(attempts_path, report)
            return report
        except Exception as exc:  # provider failures are persisted for editorial review
            attempts.append(
                {
                    "attempt": attempt,
                    "started_at": started,
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "error_reason": str(exc),
                }
            )

    report = {
        "status": "failed",
        "provider": provider.name,
        "model": provider.model,
        "attempts": attempts,
        "error_reason": attempts[-1]["error_reason"],
        "approval_status": "review_required",
    }
    write_json(attempts_path, report)
    raise ProviderUnavailableError(f"Image generation failed after {max_attempts} attempts: {report['error_reason']}")


def create_card_preview(source_path: Path, output_path: Path, *, tokens: Mapping[str, Any] | None = None) -> None:
    tokens = tokens or load_tokens()
    size = (int(tokens["canvas"]["card_preview_width"]), int(tokens["canvas"]["card_preview_height"]))
    with Image.open(source_path) as source:
        preview = source.convert("RGB").resize(size, Image.Resampling.LANCZOS)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.suffix.casefold() == ".webp":
        preview.save(output_path, format="WEBP", quality=90, method=6)
    else:
        preview.save(output_path, format="PNG", optimize=True)


def create_thumbnail_gallery(
    items: Iterable[tuple[str, Path]],
    output_path: Path,
    *,
    columns: int = 3,
    tokens: Mapping[str, Any] | None = None,
) -> None:
    """Create a deterministic labeled contact sheet for owner visual review."""

    tokens = tokens or load_tokens()
    normalized = [(str(label).strip(), Path(path)) for label, path in items]
    if not normalized:
        raise RenderValidationError("A thumbnail gallery requires at least one item")
    if columns < 1:
        raise RenderValidationError("Gallery columns must be at least 1")
    for label, path in normalized:
        if not label:
            raise RenderValidationError("Gallery labels must be non-empty")
        if not path.is_file():
            raise RenderValidationError(f"Gallery thumbnail does not exist: {path}")

    card_size = (
        int(tokens["canvas"]["card_preview_width"]),
        int(tokens["canvas"]["card_preview_height"]),
    )
    margin = 28
    gap_x = 20
    gap_y = 22
    heading_height = 56
    label_height = 42
    rows = (len(normalized) + columns - 1) // columns
    width = (2 * margin) + (columns * card_size[0]) + ((columns - 1) * gap_x)
    height = (2 * margin) + heading_height + (rows * (card_size[1] + label_height)) + ((rows - 1) * gap_y)
    sheet = Image.new("RGB", (width, height), "#E9EFEE")
    draw = ImageDraw.Draw(sheet)
    heading_font, _ = _font_with_path(tokens, 26, bold=True)
    label_font, _ = _font_with_path(tokens, 18, bold=True)
    draw.text((margin, 18), "KOLLILABS THUMBNAILS · VISUAL REVIEW", font=heading_font, fill="#0A2425")

    for index, (label, path) in enumerate(normalized):
        row, column = divmod(index, columns)
        x = margin + column * (card_size[0] + gap_x)
        y = margin + heading_height + row * (card_size[1] + label_height + gap_y)
        with Image.open(path) as source:
            card = source.convert("RGB").resize(card_size, Image.Resampling.LANCZOS)
        sheet.paste(card, (x, y))
        draw.text((x, y + card_size[1] + 10), label, font=label_font, fill="#234243")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path, format="PNG", optimize=True)


def create_preview_sheets(
    first_thumbnail: Path,
    second_thumbnail: Path,
    output_dir: Path,
    *,
    tokens: Mapping[str, Any] | None = None,
) -> dict[str, str]:
    tokens = tokens or load_tokens()
    reference_path, _ = validate_reference(tokens)
    output_dir.mkdir(parents=True, exist_ok=True)

    def versioned_card_path(thumbnail: Path, candidate_dir: str) -> Path:
        version_match = re.fullmatch(r"thumbnail-(v\d+)", thumbnail.stem, re.IGNORECASE)
        version_suffix = f"-{version_match.group(1).lower()}" if version_match else ""
        return output_dir.parent / candidate_dir / f"thumbnail-card-360{version_suffix}.webp"

    card_paths = [
        versioned_card_path(first_thumbnail, "pilot-50pct"),
        versioned_card_path(second_thumbnail, "pilot-700-tests"),
    ]
    create_card_preview(first_thumbnail, card_paths[0], tokens=tokens)
    create_card_preview(second_thumbnail, card_paths[1], tokens=tokens)

    regular, _ = _font_with_path(tokens, 24, bold=False)
    bold, _ = _font_with_path(tokens, 28, bold=True)
    small_bold, _ = _font_with_path(tokens, 18, bold=True)
    sheet_background = "#E9EFEE"

    cards_sheet = Image.new("RGB", (800, 292), sheet_background)
    cards_draw = ImageDraw.Draw(cards_sheet)
    cards_draw.text((32, 18), "PILOT CARD-WIDTH PREVIEWS · 360 × 203", font=bold, fill="#0A2425")
    for index, (path, label) in enumerate(zip(card_paths, ("+50% improvement", "700-test benchmark"))):
        with Image.open(path) as image:
            cards_sheet.paste(image.convert("RGB"), (32 + index * 384, 62))
        cards_draw.text((32 + index * 384, 269), label, font=small_bold, fill="#234243")
    cards_path = output_dir / "pilot-card-width-previews.png"
    cards_sheet.save(cards_path, format="PNG", optimize=True)

    with Image.open(first_thumbnail) as image:
        first = image.convert("RGB").resize((480, 270), Image.Resampling.LANCZOS)
    with Image.open(second_thumbnail) as image:
        second = image.convert("RGB").resize((480, 270), Image.Resampling.LANCZOS)
    with Image.open(reference_path) as board:
        improvement = board.convert("RGB").crop(tuple(tokens["reference"]["nearby_crops"]["improvement"]))
        benchmark = board.convert("RGB").crop(tuple(tokens["reference"]["nearby_crops"]["benchmark"]))
    improvement = ImageOps.fit(improvement, (480, 270), Image.Resampling.LANCZOS)
    benchmark = ImageOps.fit(benchmark, (480, 270), Image.Resampling.LANCZOS)

    contact = Image.new("RGB", (1032, 742), sheet_background)
    contact_draw = ImageDraw.Draw(contact)
    contact_draw.text((36, 18), "PILOTS · OWNER APPROVAL REQUIRED", font=bold, fill="#0A2425")
    contact.paste(first, (36, 62))
    contact.paste(second, (516, 62))
    contact_draw.text((36, 339), "New · +50% improvement", font=small_bold, fill="#234243")
    contact_draw.text((516, 339), "New · 700-test benchmark", font=small_bold, fill="#234243")
    contact_draw.text((36, 382), "NEARBY CROPS FROM THE APPROVED NINE-TILE REFERENCE", font=bold, fill="#0A2425")
    contact.paste(improvement, (36, 426))
    contact.paste(benchmark, (516, 426))
    contact_draw.text((36, 704), "Reference · improvement", font=small_bold, fill="#234243")
    contact_draw.text((516, 704), "Reference · benchmark", font=small_bold, fill="#234243")
    contact_path = output_dir / "pilot-contact-sheet.png"
    contact.save(contact_path, format="PNG", optimize=True)

    return {
        "first_card_preview": card_paths[0].as_posix(),
        "second_card_preview": card_paths[1].as_posix(),
        "card_previews": cards_path.as_posix(),
        "contact_sheet": contact_path.as_posix(),
    }
