"""Regenerate benchmark article figures with current Transport product names."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[4]
SUMMARY_PATH = (
    ROOT
    / "engine_development_notes"
    / "transport_container_selection"
    / "kollipack_br1_br7_benchmark_summary_20260818.json"
)
ASSET_DIR = (
    ROOT
    / "static"
    / "img"
    / "blog"
    / "container-loading-benchmark-kollipack-br1-br7"
)

BACKGROUND = "#f4f6fa"
PLOT_BACKGROUND = "#ffffff"
INK = "#101827"
NAVY = "#123b52"
MUTED = "#667085"
BASELINE = "#94a3b8"
GREEN = "#16a085"
DARK_GREEN = "#0f7f69"
VENDOR = "#4d5d73"


def _figure() -> tuple[plt.Figure, plt.Axes]:
    figure, axes = plt.subplots(figsize=(14.4, 8.1), dpi=100)
    figure.patch.set_facecolor(BACKGROUND)
    axes.set_facecolor(PLOT_BACKGROUND)
    return figure, axes


def _finish(figure: plt.Figure, filename: str) -> None:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    figure.savefig(
        ASSET_DIR / filename,
        format="webp",
        dpi=100,
        pil_kwargs={"quality": 92, "method": 6},
    )
    plt.close(figure)


def figure_one(summary: dict) -> None:
    labels = [
        "Balanced Spread",
        "Balanced Spread – Mixed Cargo Infill",
        "Progressive Fill",
        "Progressive Fill – Mixed Cargo Infill",
    ]
    values = [
        summary["space_evenly"]["avg_util_pct"],
        summary["space_evenly_infill"]["avg_util_pct"],
        summary["front_to_back"]["avg_util_pct"],
        summary["front_to_back_infill"]["avg_util_pct"],
    ]
    colors = [BASELINE, GREEN, BASELINE, DARK_GREEN]

    figure, axes = _figure()
    figure.subplots_adjust(left=0.235, right=0.975, top=0.81, bottom=0.10)
    y = np.arange(len(labels))
    bars = axes.barh(y, values, color=colors, height=0.56)
    axes.invert_yaxis()
    axes.set_xlim(0, 100)
    axes.set_yticks(y, labels, fontsize=11, color=INK)
    axes.set_xlabel("Average volume utilization (%)", color=MUTED)
    axes.grid(axis="x", color="#d8dee8", linewidth=0.8)
    axes.set_axisbelow(True)
    axes.tick_params(axis="x", colors=MUTED)
    for spine in ("top", "right", "left"):
        axes.spines[spine].set_visible(False)
    axes.spines["bottom"].set_color("#d8dee8")
    for bar, value in zip(bars, values):
        axes.text(
            value + 1.1,
            bar.get_y() + bar.get_height() / 2,
            f"{value:.3f}%",
            va="center",
            fontsize=11,
            fontweight="bold",
            color=INK,
        )
    axes.axvline(94.2, color=NAVY, linewidth=2, linestyle=(0, (6, 4)))
    axes.text(94.2, 3.62, "94.2%\nCLTRS packing reference", ha="center", va="top", fontsize=9, color=NAVY)
    figure.text(0.025, 0.945, "One benchmark, four KolliPack modes", fontsize=23, fontweight="bold", color=INK)
    figure.text(0.025, 0.91, "Average container-volume utilization across 700 BR1–BR7 cases", fontsize=11, color=MUTED)
    figure.text(0.025, 0.02, "Green = Mixed Cargo Infill. The dashed line is a published academic reference, not a KolliPack mode.", fontsize=9, color=MUTED)
    _finish(figure, "figure-1-700-case-utilization.webp")


def figure_two(per_class: dict) -> None:
    classes = list(per_class)
    balanced = [per_class[name]["space_evenly_infill"] for name in classes]
    progressive = [per_class[name]["front_to_back_infill"] for name in classes]
    cltrs = [94.51, 94.73, 94.74, 94.41, 94.13, 93.85, 93.20]

    figure, axes = _figure()
    figure.subplots_adjust(left=0.075, right=0.985, top=0.82, bottom=0.14)
    axes.plot(classes, balanced, color=GREEN, marker="o", linewidth=2.5, label="KolliPack Balanced Spread Infill")
    axes.plot(classes, progressive, color=DARK_GREEN, marker="o", linewidth=2.5, label="KolliPack Progressive Fill Infill")
    axes.plot(classes, cltrs, color=NAVY, marker="o", linewidth=2, linestyle=(0, (6, 4)), label="CLTRS full-support packing reference")
    axes.set_ylim(77, 97)
    axes.set_ylabel("Average utilization (%)", color=MUTED)
    axes.grid(axis="y", color="#d8dee8", linewidth=0.8)
    axes.tick_params(colors=MUTED)
    for spine in ("top", "right"):
        axes.spines[spine].set_visible(False)
    axes.spines["left"].set_color("#d8dee8")
    axes.spines["bottom"].set_color("#d8dee8")
    axes.legend(loc="lower left", frameon=True, facecolor="white", edgecolor="#d8dee8", fontsize=9)
    figure.text(0.025, 0.945, "More box types expose more internal loss", fontsize=23, fontweight="bold", color=INK)
    figure.text(0.025, 0.91, "Mean utilization by BR class; each class contains 100 cases", fontsize=11, color=MUTED)
    figure.text(0.025, 0.02, "The trend is diagnostic evidence, not proof of a single failure mechanism.", fontsize=9, color=MUTED)
    _finish(figure, "figure-2-heterogeneity-curve.webp")


def figure_three(per_class: dict) -> None:
    classes = ["BR1", "BR5", "BR7"]
    balanced = [per_class[name]["space_evenly_infill"] for name in classes]
    vendor = [86.4, 85.3, 82.6]
    x = np.arange(len(classes))
    width = 0.34

    figure, axes = _figure()
    figure.subplots_adjust(left=0.08, right=0.985, top=0.82, bottom=0.14)
    bars_a = axes.bar(x - width / 2, balanced, width, color=GREEN, label="KolliPack Balanced Spread Infill")
    bars_b = axes.bar(x + width / 2, vendor, width, color=VENDOR, label="LoadingMCP vendor-published")
    axes.set_ylim(77, 89)
    axes.set_xticks(x, classes)
    axes.set_ylabel("Average utilization (%)", color=MUTED)
    axes.grid(axis="y", color="#d8dee8", linewidth=0.8)
    axes.set_axisbelow(True)
    axes.tick_params(colors=MUTED)
    for spine in ("top", "right"):
        axes.spines[spine].set_visible(False)
    axes.spines["left"].set_color("#d8dee8")
    axes.spines["bottom"].set_color("#d8dee8")
    for bars in (bars_a, bars_b):
        for bar in bars:
            axes.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.15,
                f"{bar.get_height():.2f}%" if bar in bars_a else f"{bar.get_height():.1f}%",
                ha="center",
                va="bottom",
                fontsize=10,
                fontweight="bold",
                color=INK,
            )
    axes.legend(loc="lower left", frameon=True, facecolor="white", edgecolor="#d8dee8", fontsize=9)
    figure.text(0.025, 0.945, "A narrow commercial reference", fontsize=23, fontweight="bold", color=INK)
    figure.text(0.025, 0.91, "Only the BR1, BR5, and BR7 values published by LoadingMCP are shown", fontsize=11, color=MUTED)
    figure.text(0.025, 0.02, "The LoadingMCP figures were not independently reproduced by KolliLabs; no missing classes are interpolated.", fontsize=9, color=MUTED)
    _finish(figure, "figure-3-commercial-reference.webp")


def _font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont:
    windows_font = Path(
        "C:/Windows/Fonts/seguisb.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"
    )
    name = str(windows_font) if windows_font.is_file() else (
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    )
    return ImageFont.truetype(name, size=size)


def thumbnail() -> None:
    image = Image.new("RGB", (1440, 810), BACKGROUND)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((32, 26, 1408, 784), radius=28, fill="white", outline="#d8dee8", width=2)
    draw.text((120, 90), "KolliLabs / KolliPack", font=_font(22, bold=True), fill=DARK_GREEN)
    draw.text((120, 225), "700 CASES", font=_font(55, bold=True), fill=INK)
    draw.text((120, 355), "HONEST BENCHMARK", font=_font(32, bold=True), fill=NAVY)
    draw.text((120, 520), "83.7%", font=_font(78, bold=True), fill=GREEN)
    draw.multiline_text((470, 548), "Balanced Spread\nwith Mixed Cargo Infill", font=_font(20), fill=MUTED, spacing=2)
    draw.line((840, 285, 1280, 285), fill=NAVY, width=3)
    for x, height, color in ((875, 170, BASELINE), (980, 250, GREEN), (1085, 85, BASELINE), (1190, 235, GREEN)):
        draw.rounded_rectangle((x, 650 - height, x + 72, 650), radius=12, fill=color)
    draw.text((855, 710), "BR1–BR7 · 2,800 solves · 94.2% published reference", font=_font(14), fill=MUTED)
    image.save(ASSET_DIR / "thumbnail.webp", format="WEBP", quality=92, method=6)


def main() -> None:
    payload = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    figure_one(payload["summary"])
    figure_two(payload["per_class"])
    figure_three(payload["per_class"])
    thumbnail()


if __name__ == "__main__":
    main()
