"""Compose the TOPS MaxLoad / KolliPack benchmark article assets.

The script uses the real screenshots supplied with the article task. It adds only
editorial framing outside the source images; source values and geometry are not
redrawn or altered.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[4]
DEFAULT_OUTPUT_DIR = (
    ROOT
    / "static"
    / "img"
    / "blog"
    / "tops-maxload-kollipack-container-loading-benchmark"
)

BACKGROUND = "#f4f6fa"
SURFACE = "#ffffff"
INK = "#0f172a"
NAVY = "#12344d"
MUTED = "#64748b"
BORDER = "#dbe4ee"
GREEN = "#10a37f"
DARK_GREEN = "#0b7a60"
SOFT_GREEN = "#ecfdf5"
TOPS_ACCENT = "#d97706"


SOURCE_FILES = {
    "original_manifest": "top_original_loading_list (1).png",
    "algorithms": "tops_algorithms.png",
    "container": "tops_container_selection.png",
    "tops_original_front": "tops_original_loading_list_front_to_back.png",
    "tops_original_even": "tops_space_evenly.png",
    "tops_optimized_manifest": "tops_optimizaed_load_list.png",
    "tops_optimized_load": "tops_load_optimized_front_to_back.png",
    "kolli_original_progressive": "kollipack_progressive_spread.png",
    "kolli_same_manifest": "kollipack_front_to_back_optimized_same_tops.png",
    "probe_a": "kollipack_progressive_spread_optimized_v1.png",
    "probe_b": "kollipack_progressive_spread_optimized_v2.png",
}


def font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont:
    windows_font = Path(
        "C:/Windows/Fonts/seguisb.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"
    )
    fallback = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    return ImageFont.truetype(
        str(windows_font) if windows_font.is_file() else fallback,
        size=size,
    )


def load_sources(source_dir: Path) -> dict[str, Image.Image]:
    sources: dict[str, Image.Image] = {}
    missing: list[str] = []
    for key, filename in SOURCE_FILES.items():
        path = source_dir / filename
        if not path.is_file():
            missing.append(str(path))
            continue
        sources[key] = Image.open(path).convert("RGB")
    if missing:
        raise SystemExit("Missing source screenshots:\n" + "\n".join(missing))
    return sources


def canvas(size: tuple[int, int]) -> Image.Image:
    return Image.new("RGB", size, BACKGROUND)


def rounded_card(
    image: Image.Image,
    box: tuple[int, int, int, int],
    *,
    fill: str = SURFACE,
    outline: str = BORDER,
    radius: int = 22,
) -> None:
    ImageDraw.Draw(image).rounded_rectangle(
        box,
        radius=radius,
        fill=fill,
        outline=outline,
        width=2,
    )


def place_contained(
    target: Image.Image,
    source: Image.Image,
    box: tuple[int, int, int, int],
    *,
    padding: int = 12,
    background: str = "#f8fafc",
) -> None:
    left, top, right, bottom = box
    inner_w = max(right - left - 2 * padding, 1)
    inner_h = max(bottom - top - 2 * padding, 1)
    fitted = ImageOps.contain(source, (inner_w, inner_h), Image.Resampling.LANCZOS)
    x = left + (right - left - fitted.width) // 2
    y = top + (bottom - top - fitted.height) // 2
    ImageDraw.Draw(target).rectangle(box, fill=background)
    target.paste(fitted, (x, y))


def header(
    target: Image.Image,
    title: str,
    subtitle: str,
    *,
    eyebrow: str = "TOPS MAXLOAD × KOLLIPACK",
) -> None:
    draw = ImageDraw.Draw(target)
    draw.text((58, 34), eyebrow, font=font(19, bold=True), fill=DARK_GREEN)
    draw.text((58, 69), title, font=font(35, bold=True), fill=INK)
    draw.text((58, 119), subtitle, font=font(20), fill=MUTED)


def panel(
    target: Image.Image,
    box: tuple[int, int, int, int],
    title: str,
    source_label: str,
    source: Image.Image,
    *,
    accent: str,
) -> None:
    left, top, right, bottom = box
    rounded_card(target, box)
    draw = ImageDraw.Draw(target)
    draw.rounded_rectangle(
        (left + 18, top + 18, left + 33, top + 67),
        radius=7,
        fill=accent,
    )
    draw.text((left + 50, top + 17), title, font=font(22, bold=True), fill=INK)
    draw.text((left + 50, top + 47), source_label, font=font(16), fill=MUTED)
    image_box = (left + 18, top + 85, right - 18, bottom - 18)
    place_contained(target, source, image_box)


def stat_card(
    target: Image.Image,
    box: tuple[int, int, int, int],
    value: str,
    label: str,
    *,
    fill: str = SOFT_GREEN,
    value_color: str = DARK_GREEN,
) -> None:
    rounded_card(target, box, fill=fill, outline=fill, radius=18)
    draw = ImageDraw.Draw(target)
    left, top, _, _ = box
    draw.text((left + 24, top + 18), value, font=font(30, bold=True), fill=value_color)
    draw.text((left + 24, top + 60), label, font=font(17), fill=MUTED)


def save(target: Image.Image, output_dir: Path, filename: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    target.save(
        output_dir / filename,
        format="WEBP",
        quality=90,
        method=6,
    )


def benchmark_setup(sources: dict[str, Image.Image], output_dir: Path) -> None:
    target = canvas((1600, 920))
    header(
        target,
        "The published reference fixture",
        "Four load-unit rows, one 40-ft high-cube sea van, and two TOPS loading strategies",
    )
    panel(
        target,
        (50, 175, 1020, 485),
        "Original manifest",
        "TOPS source screenshot",
        sources["original_manifest"],
        accent=TOPS_ACCENT,
    )
    panel(
        target,
        (1050, 175, 1550, 710),
        "Selected vehicle",
        "TOPS source screenshot",
        sources["container"],
        accent=TOPS_ACCENT,
    )
    panel(
        target,
        (50, 515, 1020, 710),
        "Algorithms shown",
        "TOPS source screenshot",
        sources["algorithms"],
        accent=TOPS_ACCENT,
    )
    stat_card(target, (50, 745, 500, 875), "1,228", "load units in the original manifest")
    stat_card(target, (525, 745, 975, 875), "2,271 ft³", "reported cargo cube")
    stat_card(target, (1000, 745, 1550, 875), "84%", "reported cube utilization")
    save(target, output_dir, "tops-kollipack-benchmark-setup.webp")


def original_comparison(sources: dict[str, Image.Image], output_dir: Path) -> None:
    target = canvas((1600, 1260))
    header(
        target,
        "The same 1,228 load units can form different geometries",
        "TOPS source outputs above; independent KolliPack reproductions below",
    )
    positions = [
        ((50, 175, 780, 680), "TOPS — Load Front to Back", "Public source output", "tops_original_front", TOPS_ACCENT),
        ((820, 175, 1550, 680), "TOPS — Space Evenly", "Public source output", "tops_original_even", TOPS_ACCENT),
        ((250, 720, 1350, 1225), "KolliPack — Progressive Fill", "Independent reproduction of the same four-row manifest", "kolli_original_progressive", GREEN),
    ]
    for box, title, label, key, accent in positions:
        panel(target, box, title, label, sources[key], accent=accent)
    save(target, output_dir, "tops-kollipack-original-1228-comparison.webp")


def tops_optimization(sources: dict[str, Image.Image], output_dir: Path) -> None:
    target = canvas((1600, 920))
    header(
        target,
        "TOPS extends the example to 1,285 load units",
        "Case 1 is introduced and SKU302473 increases from 375 to 400",
    )
    panel(
        target,
        (50, 175, 700, 545),
        "Optimized manifest",
        "TOPS source screenshot",
        sources["tops_optimized_manifest"],
        accent=TOPS_ACCENT,
    )
    panel(
        target,
        (730, 175, 1550, 875),
        "Optimized load",
        "TOPS source screenshot",
        sources["tops_optimized_load"],
        accent=TOPS_ACCENT,
    )
    stat_card(target, (50, 585, 360, 715), "1,285", "load units")
    stat_card(target, (390, 585, 700, 715), "2,388.3 ft³", "cargo cube")
    stat_card(target, (50, 745, 700, 875), "88.3%", "reported cube utilization")
    save(target, output_dir, "tops-maxload-optimized-1285.webp")


def same_manifest(sources: dict[str, Image.Image], output_dir: Path) -> None:
    target = canvas((1600, 1060))
    header(
        target,
        "The exact 1,285-unit manifest loads in both systems",
        "Same quantities and container geometry; different calculated arrangements",
    )
    panel(
        target,
        (50, 175, 780, 820),
        "TOPS optimized result",
        "Public source output",
        sources["tops_optimized_load"],
        accent=TOPS_ACCENT,
    )
    panel(
        target,
        (820, 175, 1550, 820),
        "KolliPack Progressive Fill",
        "Current-backend reproduction",
        sources["kolli_same_manifest"],
        accent=GREEN,
    )
    rounded_card(target, (50, 855, 1550, 1015), fill=SURFACE)
    draw = ImageDraw.Draw(target)
    draw.text((78, 878), "Manifest held constant", font=font(21, bold=True), fill=INK)
    quantities = [
        ("P1 · SKU302473", "400"),
        ("P2 · SKU503739", "405"),
        ("P3 · Case Pack 12", "288"),
        ("P4 · Case Pack", "160"),
        ("P5 · Case 1", "32"),
    ]
    for index, (label, value) in enumerate(quantities):
        x = 78 + index * 292
        draw.text((x, 925), label, font=font(15), fill=MUTED)
        draw.text((x, 957), value, font=font(25, bold=True), fill=DARK_GREEN)
    save(target, output_dir, "tops-kollipack-same-1285-manifest.webp")


def residual_capacity(sources: dict[str, Image.Image], output_dir: Path) -> None:
    target = canvas((1600, 1080))
    header(
        target,
        "The remaining geometry was tested with more cargo",
        "Two separate Progressive Fill probes; the increases were not combined",
    )
    panel(
        target,
        (50, 300, 780, 1035),
        "Probe A — more SKU302473",
        "KolliPack current-backend result",
        sources["probe_a"],
        accent=GREEN,
    )
    panel(
        target,
        (820, 300, 1550, 1035),
        "Probe B — more Case 1",
        "KolliPack current-backend result",
        sources["probe_b"],
        accent=GREEN,
    )
    stat_card(target, (50, 175, 780, 275), "+34 SKU302473 · 1,319 total", "400 → 434; all other benchmark quantities unchanged")
    stat_card(target, (820, 175, 1550, 275), "+8 Case 1 · 1,293 total", "32 → 40; all other benchmark quantities unchanged")
    save(target, output_dir, "kollipack-residual-capacity-test.webp")


def thumbnail(sources: dict[str, Image.Image], output_dir: Path) -> None:
    size = (1440, 810)
    target = canvas(size)
    render = ImageOps.fit(
        sources["probe_a"],
        (860, 810),
        method=Image.Resampling.LANCZOS,
        centering=(0.58, 0.66),
    )
    target.paste(render, (580, 0))
    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    pixels = overlay.load()
    for x in range(size[0]):
        if x < 660:
            alpha = 245
        elif x < 930:
            alpha = round(245 * (930 - x) / 270)
        else:
            alpha = 0
        for y in range(size[1]):
            pixels[x, y] = (15, 23, 42, alpha)
    target = Image.alpha_composite(target.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(target)
    draw.text((70, 56), "KolliLabs · KolliPack", font=font(22, bold=True), fill="#a7f3d0")
    draw.text((70, 190), "1,285 UNITS", font=font(58, bold=True), fill="#ffffff")
    draw.text((70, 285), "ROOM STILL LEFT", font=font(38, bold=True), fill="#ffffff")
    draw.rounded_rectangle((70, 415, 505, 530), radius=18, fill=GREEN)
    draw.text((102, 437), "+34 MORE", font=font(44, bold=True), fill="#ffffff")
    draw.text((70, 575), "IN THIS SPECIFIC CASE", font=font(22, bold=True), fill="#d1fae5")
    draw.text((70, 660), "40-ft high-cube loading benchmark", font=font(20), fill="#cbd5e1")
    save(target, output_dir, "thumbnail.webp")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    sources = load_sources(args.source_dir)
    benchmark_setup(sources, args.output_dir)
    original_comparison(sources, args.output_dir)
    tops_optimization(sources, args.output_dir)
    same_manifest(sources, args.output_dir)
    residual_capacity(sources, args.output_dir)
    thumbnail(sources, args.output_dir)
    print(f"Wrote six WebP assets to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
