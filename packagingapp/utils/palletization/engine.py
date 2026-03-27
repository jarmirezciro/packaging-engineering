from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import Rectangle
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401


# ============================================================
# DATA STRUCTURES
# ============================================================

@dataclass
class Placement2D:
    x: float
    y: float
    l: float
    w: float
    orientation: str  # "LxW" or "WxL"


@dataclass
class Placement3D:
    x: float
    y: float
    z: float
    l: float
    w: float
    h: float
    orientation: str
    layer_kind: str   # "base" or "interlock"
    layer_index: int


@dataclass(frozen=True)
class PalletizationRenderResult:
    image_rel_path: str


# ============================================================
# BASIC HELPERS
# ============================================================

def box_volume(l: float, w: float, h: float) -> float:
    return l * w * h


def orientation_name(l: float, w: float, base_l: float, base_w: float) -> str:
    if abs(l - base_l) < 1e-9 and abs(w - base_w) < 1e-9:
        return "LxW"
    return "WxL"


def effective_pallet_size(
    pallet_l: float,
    pallet_w: float,
    stick_l: float,
    stick_w: float,
) -> Tuple[float, float]:
    return pallet_l + stick_l, pallet_w + stick_w


def rect_overlap_area(a: Placement2D, b: Placement2D) -> float:
    x_overlap = max(0, min(a.x + a.l, b.x + b.l) - max(a.x, b.x))
    y_overlap = max(0, min(a.y + a.w, b.y + b.w) - max(a.y, b.y))
    return x_overlap * y_overlap


def within_area(p: Placement2D, area_l: float, area_w: float) -> bool:
    return (
        p.x >= 0 and p.y >= 0 and
        p.x + p.l <= area_l + 1e-9 and
        p.y + p.w <= area_w + 1e-9
    )


def grid_fill(
    area_l: float,
    area_w: float,
    box_l: float,
    box_w: float,
    base_l: float,
    base_w: float,
    x0: float = 0,
    y0: float = 0,
) -> List[Placement2D]:
    placements: List[Placement2D] = []
    nx = int(area_l // box_l)
    ny = int(area_w // box_w)
    ori = orientation_name(box_l, box_w, base_l, base_w)

    for j in range(ny):
        for i in range(nx):
            placements.append(
                Placement2D(
                    x=x0 + i * box_l,
                    y=y0 + j * box_w,
                    l=box_l,
                    w=box_w,
                    orientation=ori,
                )
            )
    return placements


def try_two_orientations_grid(
    area_l: float,
    area_w: float,
    box_l: float,
    box_w: float,
    base_l: float,
    base_w: float,
    x0: float = 0,
    y0: float = 0,
) -> List[Placement2D]:
    p1 = grid_fill(area_l, area_w, box_l, box_w, base_l, base_w, x0, y0)
    p2 = grid_fill(area_l, area_w, box_w, box_l, base_l, base_w, x0, y0)
    return p1 if len(p1) >= len(p2) else p2


# ============================================================
# PATTERN GENERATORS - SINGLE LAYER
# ============================================================

def pattern_block(area_l, area_w, box_l, box_w):
    p1 = grid_fill(area_l, area_w, box_l, box_w, box_l, box_w)
    p2 = grid_fill(area_l, area_w, box_w, box_l, box_l, box_w)
    return p1 if len(p1) >= len(p2) else p2


def pattern_row(area_l, area_w, box_l, box_w):
    p1 = grid_fill(area_l, area_w, box_l, box_w, box_l, box_w)
    p2 = grid_fill(area_l, area_w, box_w, box_l, box_l, box_w)

    rows1 = int(area_w // box_w)
    rows2 = int(area_w // box_l)

    if rows1 > rows2:
        return p1
    if rows2 > rows1:
        return p2
    return p1 if len(p1) >= len(p2) else p2


def pattern_brick(area_l, area_w, box_l, box_w, rotated=False):
    if rotated:
        box_l, box_w = box_w, box_l

    placements: List[Placement2D] = []
    rows = int(area_w // box_w)
    half = box_l / 2.0
    ori = orientation_name(box_l, box_w, box_l if not rotated else box_w, box_w if not rotated else box_l)

    for j in range(rows):
        y = j * box_w
        offset = 0 if j % 2 == 0 else half
        i = 0
        while True:
            x = offset + i * box_l
            if x + box_l <= area_l + 1e-9:
                placements.append(Placement2D(x=x, y=y, l=box_l, w=box_w, orientation=ori))
            else:
                break
            i += 1

    plain = grid_fill(area_l, area_w, box_l, box_w, box_l, box_w)
    return placements if len(placements) >= len(plain) else plain


def pinwheel_motif(x0, y0, box_l, box_w, base_l, base_w):
    t = box_l + box_w
    placements = [
        Placement2D(x0 + 0,     y0 + 0,     box_l, box_w, orientation_name(box_l, box_w, base_l, base_w)),
        Placement2D(x0 + box_l, y0 + 0,     box_w, box_l, orientation_name(box_w, box_l, base_l, base_w)),
        Placement2D(x0 + box_w, y0 + box_l, box_l, box_w, orientation_name(box_l, box_w, base_l, base_w)),
        Placement2D(x0 + 0,     y0 + box_w, box_w, box_l, orientation_name(box_w, box_l, base_l, base_w)),
    ]
    return placements, t, t


def pattern_pinwheel(area_l, area_w, box_l, box_w, rotated=False):
    base_l, base_w = box_l, box_w
    if rotated:
        box_l, box_w = box_w, box_l

    placements: List[Placement2D] = []
    _, tile_l, tile_w = pinwheel_motif(0, 0, box_l, box_w, base_l, base_w)

    nx = int(area_l // tile_l)
    ny = int(area_w // tile_w)

    for j in range(ny):
        for i in range(nx):
            x0 = i * tile_l
            y0 = j * tile_w
            motif, _, _ = pinwheel_motif(x0, y0, box_l, box_w, base_l, base_w)
            placements.extend(motif)

    used_l = nx * tile_l
    used_w = ny * tile_w

    if area_l - used_l > 0:
        right_fill = try_two_orientations_grid(
            area_l - used_l, area_w, box_l, box_w, base_l, base_w, x0=used_l, y0=0
        )
        placements.extend(right_fill)

    if area_w - used_w > 0:
        top_fill = try_two_orientations_grid(
            used_l, area_w - used_w, box_l, box_w, base_l, base_w, x0=0, y0=used_w
        )
        placements.extend(top_fill)

    placements = [p for p in placements if within_area(p, area_l, area_w)]
    plain = pattern_block(area_l, area_w, base_l, base_w)
    return placements if len(placements) >= len(plain) else plain


def pattern_splitrow(area_l, area_w, box_l, box_w, swapped=False):
    best: List[Placement2D] = []

    if not swapped:
        a_l, a_w = box_l, box_w
        b_l, b_w = box_w, box_l
    else:
        a_l, a_w = box_w, box_l
        b_l, b_w = box_l, box_w

    max_rows_a = int(area_w // a_w)

    for rows_a in range(max_rows_a + 1):
        band_a_w = rows_a * a_w
        band_b_w = area_w - band_a_w

        placements: List[Placement2D] = []
        if band_a_w > 0:
            placements.extend(grid_fill(area_l, band_a_w, a_l, a_w, box_l, box_w, x0=0, y0=0))
        if band_b_w > 0:
            placements.extend(grid_fill(area_l, band_b_w, b_l, b_w, box_l, box_w, x0=0, y0=band_a_w))

        if len(placements) > len(best):
            best = placements

    plain = pattern_block(area_l, area_w, box_l, box_w)
    return best if len(best) >= len(plain) else plain


def pattern_hybrid_pinwheel(area_l, area_w, box_l, box_w, rotated=False):
    base_l, base_w = box_l, box_w
    if rotated:
        box_l, box_w = box_w, box_l

    placements: List[Placement2D] = []
    _, tile_l, tile_w = pinwheel_motif(0, 0, box_l, box_w, base_l, base_w)

    nx = int(area_l // tile_l)
    ny = int(area_w // tile_w)

    for j in range(ny):
        for i in range(nx):
            x0 = i * tile_l
            y0 = j * tile_w
            motif_boxes, _, _ = pinwheel_motif(x0, y0, box_l, box_w, base_l, base_w)
            placements.extend(motif_boxes)

    used_l = nx * tile_l
    used_w = ny * tile_w

    if area_l - used_l > 0:
        right_strip = pattern_brick(area_l - used_l, area_w, box_l, box_w, rotated=False)
        for p in right_strip:
            placements.append(
                Placement2D(x=p.x + used_l, y=p.y, l=p.l, w=p.w, orientation=p.orientation)
            )

    if area_w - used_w > 0:
        top_strip = try_two_orientations_grid(
            used_l, area_w - used_w, box_l, box_w, base_l, base_w, x0=0, y0=used_w
        )
        placements.extend(top_strip)

    placements = [p for p in placements if within_area(p, area_l, area_w)]
    plain = pattern_block(area_l, area_w, base_l, base_w)
    return placements if len(placements) >= len(plain) else plain


# ============================================================
# STACKING BUILDERS
# ============================================================

def build_layers(
    base_layer: List[Placement2D],
    interlock_layer: List[Placement2D],
    box_h: float,
    max_stack_height: float,
    stacking_mode: str,
) -> Tuple[List[Placement3D], int, List[List[Placement2D]]]:
    max_layers = int(max_stack_height // box_h)
    placements3d: List[Placement3D] = []
    layers_2d: List[List[Placement2D]] = []

    for layer_idx in range(max_layers):
        z = layer_idx * box_h

        if stacking_mode == "column":
            layer = base_layer
            layer_kind = "base"
        else:
            if layer_idx % 2 == 0:
                layer = base_layer
                layer_kind = "base"
            else:
                layer = interlock_layer
                layer_kind = "interlock"

        layers_2d.append(layer)

        for p in layer:
            placements3d.append(
                Placement3D(
                    x=p.x,
                    y=p.y,
                    z=z,
                    l=p.l,
                    w=p.w,
                    h=box_h,
                    orientation=p.orientation,
                    layer_kind=layer_kind,
                    layer_index=layer_idx,
                )
            )

    return placements3d, max_layers, layers_2d


# ============================================================
# LOAD CHECK
# ============================================================

def compute_bottom_loads(layers_2d: List[List[Placement2D]], box_weight: Optional[float]) -> List[float]:
    if box_weight is None or len(layers_2d) == 0:
        return [0.0] * (len(layers_2d[0]) if layers_2d else 0)

    n_layers = len(layers_2d)
    transmitted_loads = [[0.0] * len(layer) for layer in layers_2d]

    for upper_idx in range(n_layers - 1, 0, -1):
        upper_layer = layers_2d[upper_idx]
        lower_layer = layers_2d[upper_idx - 1]

        for ui, ub in enumerate(upper_layer):
            load_to_transfer = box_weight + transmitted_loads[upper_idx][ui]

            overlaps = []
            total_overlap = 0.0
            for li, lb in enumerate(lower_layer):
                ov = rect_overlap_area(ub, lb)
                if ov > 0:
                    overlaps.append((li, ov))
                    total_overlap += ov

            if total_overlap > 0:
                lower_idx = upper_idx - 1
                for li, ov in overlaps:
                    transmitted_loads[lower_idx][li] += load_to_transfer * (ov / total_overlap)

    return transmitted_loads[0]


def evaluate_weight_feasibility(layers_2d, box_weight, max_weight_on_bottom_box):
    if box_weight is None or max_weight_on_bottom_box is None:
        return True, 0.0, 0.0, []

    bottom_loads = compute_bottom_loads(layers_2d, box_weight)
    max_bottom_load = max(bottom_loads) if bottom_loads else 0.0
    avg_bottom_load = sum(bottom_loads) / len(bottom_loads) if bottom_loads else 0.0
    feasible = max_bottom_load <= max_weight_on_bottom_box + 1e-9

    return feasible, max_bottom_load, avg_bottom_load, bottom_loads


def result_metrics(
    name,
    stacking_mode,
    area_l,
    area_w,
    max_stack_height,
    box_l,
    box_w,
    box_h,
    base_layer,
    interlock_layer,
    placements3d,
    layers_2d,
    box_weight,
    max_weight_on_bottom_box,
):
    max_layers = int(max_stack_height // box_h)

    if max_layers <= 0:
        counts = []
    elif stacking_mode == "column":
        counts = [len(base_layer)] * max_layers
    else:
        counts = [len(base_layer) if i % 2 == 0 else len(interlock_layer) for i in range(max_layers)]

    total_boxes = sum(counts)
    used_height = max_layers * box_h
    footprint_area = area_l * area_w
    layer_avg = sum(counts) / len(counts) if counts else 0.0

    layer_footprint_util = (layer_avg * box_l * box_w) / footprint_area if footprint_area > 0 else 0.0
    volumetric_util = (
        (total_boxes * box_volume(box_l, box_w, box_h)) / (area_l * area_w * max_stack_height)
        if area_l > 0 and area_w > 0 and max_stack_height > 0 else 0.0
    )

    feasible, max_bottom_load, avg_bottom_load, bottom_loads = evaluate_weight_feasibility(
        layers_2d, box_weight, max_weight_on_bottom_box
    )

    return {
        "pattern": name,
        "stacking": stacking_mode,
        "boxes_layer_A": len(base_layer),
        "boxes_layer_B": len(interlock_layer),
        "layers": max_layers,
        "total_boxes": total_boxes,
        "used_height_mm": used_height,
        "layer_footprint_util_pct": round(layer_footprint_util * 100, 2),
        "volumetric_util_pct": round(volumetric_util * 100, 2),
        "feasible_weight": feasible,
        "max_bottom_load_kg": round(max_bottom_load, 2),
        "avg_bottom_load_kg": round(avg_bottom_load, 2),
        "weight_limit_kg": max_weight_on_bottom_box,
        "placements3d": placements3d,
        "layer_A_2d": base_layer,
        "layer_B_2d": interlock_layer,
        "layers_2d": layers_2d,
        "bottom_loads": bottom_loads,
    }


def get_base_and_interlock_layers(pattern_name, area_l, area_w, box_l, box_w):
    if pattern_name == "Block":
        base = pattern_block(area_l, area_w, box_l, box_w)
        interlock = pattern_block(area_l, area_w, box_w, box_l)
    elif pattern_name == "Row":
        base = pattern_row(area_l, area_w, box_l, box_w)
        interlock = pattern_row(area_l, area_w, box_w, box_l)
    elif pattern_name == "Brick":
        base = pattern_brick(area_l, area_w, box_l, box_w, rotated=False)
        interlock = pattern_brick(area_l, area_w, box_l, box_w, rotated=True)
    elif pattern_name == "Pinwheel":
        base = pattern_pinwheel(area_l, area_w, box_l, box_w, rotated=False)
        interlock = pattern_pinwheel(area_l, area_w, box_l, box_w, rotated=True)
    elif pattern_name == "Splitrow":
        base = pattern_splitrow(area_l, area_w, box_l, box_w, swapped=False)
        interlock = pattern_splitrow(area_l, area_w, box_l, box_w, swapped=True)
    elif pattern_name == "Hybrid pinwheel":
        base = pattern_hybrid_pinwheel(area_l, area_w, box_l, box_w, rotated=False)
        interlock = pattern_hybrid_pinwheel(area_l, area_w, box_l, box_w, rotated=True)
    else:
        raise ValueError(f"Unknown pattern: {pattern_name}")

    return base, interlock


# ============================================================
# MAIN ANALYSIS
# ============================================================

PATTERNS = [
    "Block",
    "Row",
    "Brick",
    "Pinwheel",
    "Splitrow",
    "Hybrid pinwheel",
]

STACKINGS = [
    "column",
    "interlock",
]


def run_palletization_analysis(
    box_l: float,
    box_w: float,
    box_h: float,
    pallet_l: float,
    pallet_w: float,
    max_stack_height: float,
    max_width_stickout: float = 0.0,
    max_length_stickout: float = 0.0,
    box_weight: Optional[float] = None,
    max_weight_on_bottom_box: Optional[float] = None,
) -> List[Dict]:
    area_l, area_w = effective_pallet_size(
        pallet_l, pallet_w, max_length_stickout, max_width_stickout
    )

    results: List[Dict] = []

    for pattern_name in PATTERNS:
        base_layer, interlock_layer = get_base_and_interlock_layers(
            pattern_name, area_l, area_w, box_l, box_w
        )

        for stacking_mode in STACKINGS:
            placements3d, max_layers, layers_2d = build_layers(
                base_layer=base_layer,
                interlock_layer=interlock_layer,
                box_h=box_h,
                max_stack_height=max_stack_height,
                stacking_mode=stacking_mode,
            )

            results.append(
                result_metrics(
                    pattern_name,
                    stacking_mode,
                    area_l,
                    area_w,
                    max_stack_height,
                    box_l,
                    box_w,
                    box_h,
                    base_layer,
                    interlock_layer,
                    placements3d,
                    layers_2d,
                    box_weight,
                    max_weight_on_bottom_box,
                )
            )

    results.sort(
        key=lambda r: (
            0 if r["feasible_weight"] else 1,
            -r["total_boxes"],
            -r["volumetric_util_pct"],
            -r["layer_footprint_util_pct"],
        )
    )
    return results


# ============================================================
# VISUALIZATION
# ============================================================

def get_3d_color(orientation, layer_kind):
    if orientation == "LxW" and layer_kind == "base":
        return "#4C78A8"
    if orientation == "WxL" and layer_kind == "base":
        return "#54A24B"
    if orientation == "LxW" and layer_kind == "interlock":
        return "#E45756"
    return "#F58518"


def plot_3d_result(ax, placements3d, pallet_l, pallet_w, max_h, title):
    deck_thickness = 18
    runner_height = 90
    pallet_total_height = deck_thickness + runner_height

    # top deck
    ax.bar3d(
        0, 0, runner_height,
        pallet_l, pallet_w, deck_thickness,
        color="#C8A26A",
        alpha=0.45,
        shade=True,
        edgecolor="black",
        linewidth=0.4,
    )

    # three runners
    runner_width = 100
    runner_positions_y = [
        0,
        (pallet_w - runner_width) / 2,
        pallet_w - runner_width,
    ]

    for y0 in runner_positions_y:
        ax.bar3d(
            0, y0, 0,
            pallet_l, runner_width, runner_height,
            color="#A67C52",
            alpha=0.55,
            shade=True,
            edgecolor="black",
            linewidth=0.4,
        )

    for p in placements3d:
        color = get_3d_color(p.orientation, p.layer_kind)
        ax.bar3d(
            p.x, p.y, p.z + pallet_total_height,
            p.l, p.w, p.h,
            color=color,
            alpha=0.72,
            shade=True,
            edgecolor="black",
            linewidth=0.2,
        )

    ax.set_xlim(0, pallet_l)
    ax.set_ylim(0, pallet_w)
    ax.set_zlim(0, max_h + pallet_total_height)
    ax.set_xlabel("Length")
    ax.set_ylabel("Width")
    ax.set_zlabel("Height")
    ax.set_title(title, fontsize=10)
    ax.view_init(elev=24, azim=-58)


def render_selected_result(
    selected_result: Dict,
    pallet_l: float,
    pallet_w: float,
    max_stack_height: float,
    media_root: str,
) -> PalletizationRenderResult:
    rel_dir = "palletization"
    file_name = f"pallet_{uuid.uuid4().hex}.png"
    rel_path = os.path.join(rel_dir, file_name)
    abs_path = os.path.join(media_root, rel_path)

    os.makedirs(os.path.dirname(abs_path), exist_ok=True)

    fig = plt.figure(figsize=(8, 6))
    ax = fig.add_subplot(111, projection="3d")

    title = (
        f'{selected_result["pattern"]} - {selected_result["stacking"]}\n'
        f'Total={selected_result["total_boxes"]} | Layers={selected_result["layers"]}\n'
        f'Feasible={selected_result["feasible_weight"]} | '
        f'Max bottom load={selected_result["max_bottom_load_kg"]} kg'
    )
    plot_3d_result(ax, selected_result["placements3d"], pallet_l, pallet_w, max_stack_height, title)

    plt.tight_layout()
    plt.savefig(abs_path, dpi=150)
    plt.close(fig)

    return PalletizationRenderResult(image_rel_path=rel_path)