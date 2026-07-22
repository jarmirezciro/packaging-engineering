# packagingapp/utils/box_selection/engine.py
from __future__ import annotations

import os
import uuid
import hashlib
import json
from dataclasses import dataclass
from typing import Tuple, Optional, List

import matplotlib
matplotlib.use("Agg")  # server-safe (no display needed)

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import to_rgba
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

# IMPORTANT: this must match where you placed the file
from packagingapp.utils.box_selection.box_selection_tool_arrays_2_origin_coordinates import MainBox, allowed_product_orientations
from packagingapp.utils.quantity_decomposition import generate_factor_arrangements, next_smooth_quantity


Dims = Tuple[float, float, float]
Point = Tuple[float, float, float]


@dataclass(frozen=True)
class Placement:
    """One axis-aligned product placement in container coordinates."""

    origin: Point
    dimensions: Dims
    level: int
    region_type: str


@dataclass(frozen=True)
class Mode1Result:
    max_quantity: int
    image_rel_path: str
    threejs_scene: Optional[dict] = None
    placements: Tuple[Placement, ...] = ()


@dataclass(frozen=True)
class _MainBoxSolution:
    """Normalized geometry returned by one unchanged ``MainBox`` call."""

    max_quantity: int
    residual_dimensions: Tuple[Dims, Dims, Dims]
    residual_orientations: Tuple[Dims, Dims, Dims]
    main_orientation: Dims
    residual_origins: Tuple[Point, Point, Point]
    main_dimensions: Dims


@dataclass(frozen=True)
class _PackedRegion:
    """A grid-filled region retained for optional debug wireframes."""

    origin: Point
    dimensions: Dims
    level: int
    region_type: str


def draw_cube(ax, x, y, z, dx, dy, dz,
              color="cyan", edge_color="black",
              alpha=0.7, alpha_edges=0.7):
    """Draw a filled cuboid at (x,y,z) with size (dx,dy,dz)."""
    edge_color = to_rgba(edge_color, alpha=alpha_edges)

    vertices = [
        [(x, y, z), (x + dx, y, z), (x + dx, y + dy, z), (x, y + dy, z)],
        [(x, y, z + dz), (x + dx, y, z + dz), (x + dx, y + dy, z + dz), (x, y + dy, z + dz)],
        [(x, y, z), (x, y + dy, z), (x, y + dy, z + dz), (x, y, z + dz)],
        [(x + dx, y, z), (x + dx, y + dy, z), (x + dx, y + dy, z + dz), (x + dx, y, z + dz)],
        [(x, y, z), (x + dx, y, z), (x + dx, y, z + dz), (x, y, z + dz)],
        [(x, y + dy, z), (x + dx, y + dy, z), (x + dx, y + dy, z + dz), (x, y + dy, z + dz)],
    ]

    poly3d = Poly3DCollection(vertices, facecolors=color, edgecolors=edge_color, alpha=alpha)
    ax.add_collection3d(poly3d)


def draw_open_box_shell(ax, lc, ac, hc,
                        color="#d8c3a5",
                        edge_color="black",
                        alpha=0.16,
                        alpha_edges=0.45):
    """
    Draw a lightweight open-top box shell.
    """
    edge_color = to_rgba(edge_color, alpha=alpha_edges)

    faces = [
        [(0, 0, 0), (lc, 0, 0), (lc, ac, 0), (0, ac, 0)],
        [(0, 0, 0), (0, ac, 0), (0, ac, hc), (0, 0, hc)],
        [(lc, 0, 0), (lc, ac, 0), (lc, ac, hc), (lc, 0, hc)],
        [(0, 0, 0), (lc, 0, 0), (lc, 0, hc), (0, 0, hc)],
        [(0, ac, 0), (lc, ac, 0), (lc, ac, hc), (0, ac, hc)],
    ]

    poly3d = Poly3DCollection(faces, facecolors=color, edgecolors=edge_color, alpha=alpha)
    ax.add_collection3d(poly3d)


def draw_rsc_top_flaps(ax, lc, ac, hc,
                       color="#c9a66b",
                       edge_color="black",
                       alpha=0.26,
                       alpha_edges=0.45,
                       opening_angle_deg=130.0):
    """
    Draw a simplified regular slotted container (RSC) top closure.

    Visual intent:
      - 2 major flaps: L x (W/2)
      - 2 minor flaps: attached to the width panels

    opening_angle_deg is used as a visual opening control.
    130° gives a much more opened look than the previous flatter version.
    """
    edge_color = to_rgba(edge_color, alpha=alpha_edges)

    # Major flaps: L x (W/2)
    major_len = max(ac * 0.5, 1.0)

    # Minor flaps: visually shorter, attached to the width sides
    minor_len = max(min(lc * 0.22, ac * 0.48), 1.0)

    # Convert the desired visual opening into an upward/outward tilt.
    # 130° opening -> 50° tilt above the top rim plane.
    tilt_deg = max(5.0, min(opening_angle_deg - 80.0, 75.0))
    theta = np.deg2rad(tilt_deg)

    major_run = major_len * np.cos(theta)
    major_rise = major_len * np.sin(theta)

    minor_run = minor_len * np.cos(theta)
    minor_rise = minor_len * np.sin(theta)

    flaps = [
        # Front major flap (hinge at y = 0, opens outward to negative y)
        [(0, 0, hc), (lc, 0, hc), (lc, -major_run, hc + major_rise), (0, -major_run, hc + major_rise)],

        # Back major flap (hinge at y = ac, opens outward to positive y)
        [(0, ac, hc), (lc, ac, hc), (lc, ac + major_run, hc + major_rise), (0, ac + major_run, hc + major_rise)],

        # Left minor flap (hinge at x = 0, opens outward to negative x)
        [(0, 0, hc), (0, ac, hc), (-minor_run, ac, hc + minor_rise), (-minor_run, 0, hc + minor_rise)],

        # Right minor flap (hinge at x = lc, opens outward to positive x)
        [(lc, 0, hc), (lc, ac, hc), (lc + minor_run, ac, hc + minor_rise), (lc + minor_run, 0, hc + minor_rise)],
    ]

    poly3d = Poly3DCollection(flaps, facecolors=color, edgecolors=edge_color, alpha=alpha)
    ax.add_collection3d(poly3d)



def _mainbox(product: Dims, region: Dims, origin: Point, r1: int, r2: int, r3: int):
    """
    Thin wrapper around MainBox so the tuple unpack is centralized and consistent.
    MainBox signature used in your pilot:
      MainBox(l,a,h, lc,ac,hc, r1,r2,r3, origin_coordinates)
    """
    l, a, h = product
    lc, ac, hc = region
    origin_coordinates = [origin[0], origin[1], origin[2]]
    raw = MainBox(l, a, h, lc, ac, hc, r1, r2, r3, origin_coordinates)
    (
        max_quantity,
        cl_max,
        ca_max,
        ch_max,
        cl_xyz_max,
        ca_xyz_max,
        ch_xyz_max,
        b_xyz_max,
        coordinates_subbox_max,
        dimensions_subbox_max,
    ) = raw
    return _MainBoxSolution(
        max_quantity=int(max_quantity or 0),
        residual_dimensions=tuple(tuple(float(value) for value in dims) for dims in (cl_max, ca_max, ch_max)),
        residual_orientations=tuple(
            tuple(float(value) for value in dims)
            for dims in (cl_xyz_max, ca_xyz_max, ch_xyz_max)
        ),
        main_orientation=tuple(float(value) for value in b_xyz_max),
        residual_origins=tuple(
            tuple(float(value) for value in point)
            for point in coordinates_subbox_max
        ),
        main_dimensions=tuple(float(value) for value in dimensions_subbox_max),
    )


def _grid_placements(
    origin: Point,
    region: Dims,
    orientation: Dims,
    *,
    level: int,
    region_type: str,
) -> List[Placement]:
    """Materialize the regular grid represented by one ``MainBox`` region."""
    if not all(value > 0 for value in (*region, *orientation)):
        return []

    counts = tuple(int(region[index] / orientation[index]) for index in range(3))
    placements = []
    for ix in range(counts[0]):
        for iy in range(counts[1]):
            for iz in range(counts[2]):
                placements.append(
                    Placement(
                        origin=(
                            origin[0] + ix * orientation[0],
                            origin[1] + iy * orientation[1],
                            origin[2] + iz * orientation[2],
                        ),
                        dimensions=orientation,
                        level=level,
                        region_type=region_type,
                    )
                )
    return placements


def _materialize_mainbox_solution(
    solution: _MainBoxSolution,
    origin: Point,
    *,
    level: int,
) -> Tuple[List[Placement], List[_PackedRegion]]:
    """Materialize a selected main grid and its three direct residual fills."""
    placements = _grid_placements(
        origin,
        solution.main_dimensions,
        solution.main_orientation,
        level=level,
        region_type="main",
    )
    regions = []
    if placements:
        regions.append(_PackedRegion(origin, solution.main_dimensions, level, "main"))

    for residual_origin, residual_dimensions, residual_orientation in zip(
        solution.residual_origins,
        solution.residual_dimensions,
        solution.residual_orientations,
    ):
        residual_placements = _grid_placements(
            residual_origin,
            residual_dimensions,
            residual_orientation,
            level=level,
            region_type="residual",
        )
        placements.extend(residual_placements)
        if residual_placements:
            regions.append(
                _PackedRegion(residual_origin, residual_dimensions, level, "residual")
            )

    return placements, regions


def _calculate_pilot_solution(
    product: Dims,
    container: Dims,
    r1: int,
    r2: int,
    r3: int,
) -> Tuple[List[Placement], List[_PackedRegion]]:
    """
    Reproduce the original pilot's bounded residual-space sequence.

    The complete container is evaluated once. Its provisional direct residual
    fills are discarded: only the selected root main grid is retained. Each of
    the root's three residual regions then receives one complete ``MainBox``
    analysis, whose selected main grid and direct residual fills are retained.
    The process stops there. Therefore the root ``MainBox.max_quantity`` must
    not be added to the child results; doing that would count its provisional
    residual fills twice.
    """
    product = tuple(float(value) for value in product)
    container = tuple(float(value) for value in container)
    if not all(value > 0 for value in (*product, *container)):
        return [], []

    root_origin = (0.0, 0.0, 0.0)
    root = _mainbox(product, container, root_origin, r1, r2, r3)
    if root.max_quantity <= 0:
        return [], []

    placements = _grid_placements(
        root_origin,
        root.main_dimensions,
        root.main_orientation,
        level=0,
        region_type="main",
    )
    regions = []
    if placements:
        regions.append(_PackedRegion(root_origin, root.main_dimensions, 0, "main"))

    for residual_dimensions, residual_origin in zip(
        root.residual_dimensions,
        root.residual_origins,
    ):
        if not all(value > 0 for value in residual_dimensions):
            continue
        child = _mainbox(product, residual_dimensions, residual_origin, r1, r2, r3)
        if child.max_quantity <= 0:
            continue
        child_placements, child_regions = _materialize_mainbox_solution(
            child,
            residual_origin,
            level=1,
        )
        placements.extend(child_placements)
        regions.extend(child_regions)

    return placements, regions


def calculate_placements(product: Dims, container: Dims, r1: int, r2: int, r3: int) -> List[Placement]:
    """Return the authoritative pilot-parity product placement collection."""
    placements, _regions = _calculate_pilot_solution(product, container, r1, r2, r3)
    return placements


def compute_max_quantity_only(product: Dims, container: Dims, r1: int, r2: int, r3: int) -> int:
    """
    Return the capacity from the same placements used by both renderers.

    This remains the non-plotting path used for Optimal/Top-5 ranking.
    """
    return len(calculate_placements(product, container, r1, r2, r3))



def _scene_number(value):
    """Return a JSON-safe float for the browser 3D scene."""
    return round(float(value), 6)


def _build_threejs_scene(container: Dims) -> dict:
    """
    Build the browser-render payload for the experimental Three.js preview.

    Python remains the packing source of truth. Three.js only receives
    cuboid coordinates/dimensions and renders them interactively.
    """
    lc, ac, hc = container
    return {
        "version": 1,
        "units": "mm",
        "container": {
            "length": _scene_number(lc),
            "width": _scene_number(ac),
            "height": _scene_number(hc),
        },
        "rsc": {
            "enabled": True,
            "openingAngleDeg": 130,
        },
        "products": [],
        "subboxes": [],
    }


def _append_threejs_cuboid(
    collection,
    origin: Point,
    dimensions: Dims,
    *,
    kind: str,
    color: str,
    opacity: float = 1.0,
    level: Optional[int] = None,
    region_type: Optional[str] = None,
):
    if collection is None:
        return

    x, y, z = origin
    dx, dy, dz = dimensions
    if dx <= 0 or dy <= 0 or dz <= 0:
        return

    item = {
        "kind": kind,
        "x": _scene_number(x),
        "y": _scene_number(y),
        "z": _scene_number(z),
        "dx": _scene_number(dx),
        "dy": _scene_number(dy),
        "dz": _scene_number(dz),
        "color": color,
        "opacity": float(opacity),
    }
    if level is not None:
        item["level"] = int(level)
    if region_type is not None:
        item["region_type"] = region_type
    collection.append(item)


def _stable_container_design_id(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    return f"container-design-{digest}"


def build_container_design_candidates(
    product: Dims,
    desired_quantity: int,
    r1: int,
    r2: int,
    r3: int,
) -> dict:
    """Build and rank distinct regular-grid container design alternatives."""
    product = (float(product[0]), float(product[1]), float(product[2]))
    if any(value <= 0 for value in product):
        raise ValueError("Product dimensions must be greater than zero.")
    desired = int(desired_quantity)
    design_quantity = next_smooth_quantity(desired)
    additional_capacity = design_quantity - desired
    orientations = allowed_product_orientations(product, r1, r2, r3)
    if not orientations:
        return {
            "desired_quantity": desired,
            "design_quantity": design_quantity,
            "additional_capacity": additional_capacity,
            "candidates": [],
        }

    canonical_candidates = {}
    generated_candidate_count = 0
    horizontal_orientation_swap = {0: 2, 2: 0, 1: 5, 5: 1, 3: 4, 4: 3}
    orientation_labels = ["L × W × H", "L × H × W", "W × L × H", "W × H × L", "H × W × L", "H × L × W"]
    for rows, columns, layers in generate_factor_arrangements(design_quantity, 3):
        for orientation in orientations:
            generated_candidate_count += 1
            unit_l, unit_w, unit_h = orientation["dimensions"]
            container_l = rows * unit_l
            container_w = columns * unit_w
            container_h = layers * unit_h
            normalized_rows = int(rows)
            normalized_columns = int(columns)
            normalized_orientation_index = int(orientation["index"])
            if container_l < container_w:
                container_l, container_w = container_w, container_l
                unit_l, unit_w = unit_w, unit_l
                normalized_rows, normalized_columns = normalized_columns, normalized_rows
                normalized_orientation_index = horizontal_orientation_swap[normalized_orientation_index]

            scene = _build_threejs_scene((container_l, container_w, container_h))
            scene["mode"] = "design"
            scene["products"] = []
            for row in range(normalized_rows):
                for column in range(normalized_columns):
                    for layer in range(layers):
                        _append_threejs_cuboid(
                            scene["products"],
                            (row * unit_l, column * unit_w, layer * unit_h),
                            (unit_l, unit_w, unit_h),
                            kind="product",
                            color="#f59e0b",
                            opacity=1.0,
                        )

            canonical_key = (round(container_l, 6), round(container_w, 6), round(container_h, 6))
            required_volume = container_l * container_w * container_h
            cubicity = min(container_l, container_w, container_h) / max(container_l, container_w, container_h)
            representative_key = (
                normalized_orientation_index,
                normalized_rows,
                normalized_columns,
                int(layers),
                generated_candidate_count,
            )
            candidate = {
                "desired_quantity": desired,
                "design_quantity": design_quantity,
                "additional_capacity": additional_capacity,
                "arrangement": f"{normalized_rows} × {normalized_columns} × {layers}",
                "product_orientation": orientation_labels[normalized_orientation_index],
                "orientation_index": normalized_orientation_index,
                "rows": normalized_rows,
                "columns": normalized_columns,
                "layers": int(layers),
                "container_length": round(container_l, 2),
                "container_width": round(container_w, 2),
                "container_height": round(container_h, 2),
                "container_cubicity_score": round(cubicity, 6),
                "required_container_volume": round(required_volume, 2),
                "volumetric_efficiency": 1.0,
                "render_data": scene,
                "_canonical_key": canonical_key,
                "_representative_key": representative_key,
            }
            retained = canonical_candidates.get(canonical_key)
            if retained is None or representative_key < retained["_representative_key"]:
                canonical_candidates[canonical_key] = candidate

    candidates = list(canonical_candidates.values())
    candidates.sort(key=lambda item: (
        -item["container_cubicity_score"],
        item["additional_capacity"],
        item["required_container_volume"],
        item["_canonical_key"],
        item["_representative_key"],
    ))
    for rank, candidate in enumerate(candidates, start=1):
        identity = {
            "mode": "design",
            "design_quantity": design_quantity,
            "container_dimensions": candidate["_canonical_key"],
            "arrangement": (candidate["rows"], candidate["columns"], candidate["layers"]),
            "orientation_index": candidate["orientation_index"],
        }
        candidate["candidate_id"] = _stable_container_design_id(identity)
        candidate["rank"] = rank
        candidate.pop("_canonical_key", None)
        candidate.pop("_representative_key", None)
    return {
        "desired_quantity": desired,
        "design_quantity": design_quantity,
        "additional_capacity": additional_capacity,
        "generated_candidate_count": generated_candidate_count,
        "candidates": candidates,
    }


def run_mode1_and_render(product: Dims,
                         container: Dims,
                         r1: int, r2: int, r3: int,
                         media_root: str,
                         draw_limit: Optional[int] = None,
                         render_style: str = "debug") -> Mode1Result:
    """
    Mode render:
      - Draw container wireframe
      - Calculate the bounded pilot-parity placements once
      - Draw the same placement slice in Matplotlib and Three.js
      - Save image to MEDIA_ROOT/box_selection/<uuid>.png

    ``draw_limit`` affects only the rendered slice. ``max_quantity`` and the
    returned placement collection always describe the full calculated capacity.
    """
    product = (float(product[0]), float(product[1]), float(product[2]))
    container = (float(container[0]), float(container[1]), float(container[2]))

    lc, ac, hc = container
    clean_render = str(render_style or "").lower() == "clean"
    show_debug_subboxes = not clean_render
    threejs_scene = _build_threejs_scene(container)
    placements, packed_regions = _calculate_pilot_solution(product, container, r1, r2, r3)
    max_qty = len(placements)
    rendered_placements = placements
    if draw_limit is not None:
        rendered_placements = placements[:max(int(draw_limit), 0)]

    fig = plt.figure(figsize=(7.6, 4.8))
    ax = fig.add_subplot(111, projection="3d")
    ax.set_position([0.02, 0.03, 0.96, 0.94])
    ax.set_box_aspect([lc, ac, hc])

    flap_margin = max(min(lc, ac) * 0.22, 1.0) if clean_render else 0.0

    if clean_render:
        draw_open_box_shell(ax, lc, ac, hc)
        draw_rsc_top_flaps(ax, lc, ac, hc)
    else:
        draw_cube(ax, 0, 0, 0, lc, ac, hc, color="lightgrey", edge_color="black", alpha=0.20, alpha_edges=0.35)

    for region in packed_regions:
        color = "blue" if region.region_type == "main" else "green"
        scene_color = "#2563eb" if region.region_type == "main" else "#22c55e"
        if show_debug_subboxes:
            draw_cube(
                ax,
                *region.origin,
                *region.dimensions,
                color=color,
                edge_color="black",
                alpha=0.08,
                alpha_edges=0.08,
            )
        _append_threejs_cuboid(
            threejs_scene["subboxes"],
            region.origin,
            region.dimensions,
            kind=region.region_type,
            color=scene_color,
            opacity=0.10,
            level=region.level,
            region_type=region.region_type,
        )

    for placement in rendered_placements:
        draw_cube(
            ax,
            *placement.origin,
            *placement.dimensions,
            color="orange",
            edge_color="blue",
            alpha=0.9,
            alpha_edges=0.7,
        )
        _append_threejs_cuboid(
            threejs_scene["products"],
            placement.origin,
            placement.dimensions,
            kind="product",
            color="#f59e0b",
            opacity=0.9,
            level=placement.level,
            region_type=placement.region_type,
        )

    ax.set_xlim([-flap_margin, lc + flap_margin])
    ax.set_ylim([-flap_margin, ac + flap_margin])
    ax.set_zlim([0, hc + flap_margin])
    ax.view_init(elev=28, azim=30)

    if clean_render:
        # Final product view: remove matplotlib chart elements and keep only
        # the packaging/product representation.
        ax.set_axis_off()
        ax.grid(False)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_zticks([])
        for axis in (ax.xaxis, ax.yaxis, ax.zaxis):
            axis.pane.set_alpha(0.0)
            axis.line.set_alpha(0.0)
    else:
        # Development/debug view keeps axes and grid for visual analysis.
        ax.set_xlabel("X")
        ax.set_ylabel("Y")
        ax.set_zlabel("Z")

    rel_dir = "box_selection"
    file_name = f"mode1_{uuid.uuid4().hex}.png"
    rel_path = os.path.join(rel_dir, file_name)
    abs_path = os.path.join(media_root, rel_path)

    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    plt.savefig(abs_path, dpi=160, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)

    return Mode1Result(
        max_quantity=max_qty,
        image_rel_path=rel_path,
        threejs_scene=threejs_scene,
        placements=tuple(placements),
    )

def render_product_base_unit(product: Dims, media_root: str) -> str:
    """
    Render a clean matplotlib 3D view of the base product unit.

    The labels follow the tool input convention:
      - Length = X direction
      - Width  = Y direction
      - Height = Z direction

    Returns the relative image path below MEDIA_ROOT.
    """
    length, width, height = (float(product[0]), float(product[1]), float(product[2]))

    fig = plt.figure(figsize=(6.2, 3.9))
    ax = fig.add_subplot(111, projection="3d")
    ax.set_position([0.01, 0.08, 0.98, 0.86])
    ax.set_box_aspect([max(length, 1.0), max(width, 1.0), max(height, 1.0)])

    draw_cube(
        ax,
        0,
        0,
        0,
        length,
        width,
        height,
        color="#f59e0b",
        edge_color="#111827",
        alpha=0.60,
        alpha_edges=0.82,
    )

    max_dim = max(length, width, height, 1.0)
    margin = max(max_dim * 0.12, 1.0)

    # Clean edge guides: letters on the 3D view, exact values in badges.
    line_color = "#475569"
    text_color = "#0f172a"

    ax.plot([0, length], [-margin * 0.16, -margin * 0.16], [0, 0], color=line_color, linewidth=1.6)
    ax.text(length / 2, -margin * 0.23, 0, "L", color=text_color, fontsize=11, fontweight="bold", ha="center")

    ax.plot([length + margin * 0.12, length + margin * 0.12], [0, width], [0, 0], color=line_color, linewidth=1.6)
    ax.text(length + margin * 0.19, width / 2, 0, "W", color=text_color, fontsize=11, fontweight="bold", ha="center")

    ax.plot([-margin * 0.10, -margin * 0.10], [-margin * 0.10, -margin * 0.10], [0, height], color=line_color, linewidth=1.6)
    ax.text(-margin * 0.16, -margin * 0.12, height / 2, "H", color=text_color, fontsize=11, fontweight="bold", ha="center")

    ax.set_xlim([-margin, length + margin])
    ax.set_ylim([-margin, width + margin])
    ax.set_zlim([-margin * 0.12, height + margin * 0.45])
    ax.view_init(elev=22, azim=35)

    ax.set_axis_off()
    ax.grid(False)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_zticks([])
    for axis in (ax.xaxis, ax.yaxis, ax.zaxis):
        axis.pane.set_alpha(0.0)
        axis.line.set_alpha(0.0)

    badge_style = dict(boxstyle="round,pad=0.25", facecolor="#f8fafc", edgecolor="#cbd5e1", linewidth=0.8)
    ax.text2D(0.20, 0.02, f"L: {length:g} mm", transform=ax.transAxes, ha="center", va="center", fontsize=9, color=text_color, bbox=badge_style)
    ax.text2D(0.50, 0.02, f"W: {width:g} mm", transform=ax.transAxes, ha="center", va="center", fontsize=9, color=text_color, bbox=badge_style)
    ax.text2D(0.80, 0.02, f"H: {height:g} mm", transform=ax.transAxes, ha="center", va="center", fontsize=9, color=text_color, bbox=badge_style)

    rel_dir = "box_selection"
    file_name = f"product_base_{uuid.uuid4().hex}.png"
    rel_path = os.path.join(rel_dir, file_name)
    abs_path = os.path.join(media_root, rel_path)

    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    plt.savefig(abs_path, dpi=160, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)

    return rel_path

