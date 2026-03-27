# packagingapp/utils/box_selection/engine.py
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from typing import Tuple, Optional, List

import matplotlib
matplotlib.use("Agg")  # server-safe (no display needed)

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import to_rgba
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

# IMPORTANT: this must match where you placed the file
from packagingapp.utils.box_selection.box_selection_tool_arrays_2_origin_coordinates import MainBox


Dims = Tuple[float, float, float]
Point = Tuple[float, float, float]


@dataclass(frozen=True)
class Mode1Result:
    max_quantity: int
    image_rel_path: str


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


def fill_subbox(ax,
                subbox_origin: Point,
                subbox_dimensions: Dims,
                cube_dimensions: Dims,
                cube_color="orange",
                cube_edge_color="blue",
                cube_alpha=0.9,
                cube_alpha_edges=0.7,
                remaining: Optional[List[int]] = None):
    """
    Fill a subbox volume with a regular grid of cubes (rectangular items) of cube_dimensions.

    NEW: If remaining is a mutable one-item list like [N], we stop drawing once remaining[0] reaches 0.
         This lets Optimal mode draw only 'desired_qty' units, while Single mode draws maximum.
    """
    subbox_x, subbox_y, subbox_z = subbox_origin
    subbox_dx, subbox_dy, subbox_dz = subbox_dimensions
    cube_dx, cube_dy, cube_dz = cube_dimensions

    # Guard against zeros to avoid infinite loops
    if cube_dx <= 0 or cube_dy <= 0 or cube_dz <= 0:
        return

    for x in np.arange(subbox_x, subbox_x + subbox_dx, cube_dx):
        for y in np.arange(subbox_y, subbox_y + subbox_dy, cube_dy):
            for z in np.arange(subbox_z, subbox_z + subbox_dz, cube_dz):
                if remaining is not None and remaining[0] <= 0:
                    return

                if (
                    x + cube_dx <= subbox_x + subbox_dx
                    and y + cube_dy <= subbox_y + subbox_dy
                    and z + cube_dz <= subbox_z + subbox_dz
                ):
                    draw_cube(
                        ax, x, y, z, cube_dx, cube_dy, cube_dz,
                        color=cube_color, edge_color=cube_edge_color,
                        alpha=cube_alpha, alpha_edges=cube_alpha_edges
                    )
                    if remaining is not None:
                        remaining[0] -= 1


def _mainbox(product: Dims, region: Dims, origin: Point, r1: int, r2: int, r3: int):
    """
    Thin wrapper around MainBox so the tuple unpack is centralized and consistent.
    MainBox signature used in your pilot:
      MainBox(l,a,h, lc,ac,hc, r1,r2,r3, origin_coordinates)
    """
    l, a, h = product
    lc, ac, hc = region
    origin_coordinates = [origin[0], origin[1], origin[2]]
    return MainBox(l, a, h, lc, ac, hc, r1, r2, r3, origin_coordinates)


def compute_max_quantity_only(product: Dims, container: Dims, r1: int, r2: int, r3: int) -> int:
    """
    Fast: returns max_quantity from MainBox without any plotting.
    Useful for Optimal Top-5 ranking.
    """
    product = (float(product[0]), float(product[1]), float(product[2]))
    container = (float(container[0]), float(container[1]), float(container[2]))

    origin = (0.0, 0.0, 0.0)
    l, a, h = product
    lc, ac, hc = container
    origin_coordinates = [origin[0], origin[1], origin[2]]

    max_quantity, *_rest = MainBox(l, a, h, lc, ac, hc, r1, r2, r3, origin_coordinates)
    return int(max_quantity)


def _draw_region_solution(ax, product: Dims, region: Dims, origin: Point, r1: int, r2: int, r3: int,
                          draw_wireframes: bool = True,
                          remaining: Optional[List[int]] = None):
    """
    Matches your pilot behavior per MainBox call:
      1) Fill the chosen main subbox (dimensions_subbox_max) with b_xyz_max
      2) ALSO fill the 3 leftover regions: cl_max, ca_max, ch_max using cl_xyz_max, ca_xyz_max, ch_xyz_max

    NEW: pass 'remaining' to limit drawn items when desired.
    """
    (
        max_quantity,
        cl_max, ca_max, ch_max,
        cl_xyz_max, ca_xyz_max, ch_xyz_max,
        b_xyz_max,
        coordinates_subbox_max,
        dimensions_subbox_max
    ) = _mainbox(product, region, origin, r1, r2, r3)

    # Main chosen subbox is at the region origin in your pilot usage
    main_origin = origin
    main_dims = tuple(dimensions_subbox_max)
    main_cube = tuple(b_xyz_max)

    if draw_wireframes:
        draw_cube(ax, *main_origin, *main_dims, color="blue", edge_color="black", alpha=0.08, alpha_edges=0.08)
    fill_subbox(ax, main_origin, main_dims, main_cube, cube_color="orange", cube_edge_color="blue", remaining=remaining)

    # Stop early if we hit the draw limit
    if remaining is not None and remaining[0] <= 0:
        return int(max_quantity), []

    leftovers = [
        (tuple(coordinates_subbox_max[0]), tuple(cl_max), tuple(cl_xyz_max), "green"),
        (tuple(coordinates_subbox_max[1]), tuple(ca_max), tuple(ca_xyz_max), "red"),
        (tuple(coordinates_subbox_max[2]), tuple(ch_max), tuple(ch_xyz_max), "yellow"),
    ]

    for sub_origin, sub_dims, sub_cube, wire_color in leftovers:
        if remaining is not None and remaining[0] <= 0:
            break
        if sub_dims[0] > 0 and sub_dims[1] > 0 and sub_dims[2] > 0:
            if draw_wireframes:
                draw_cube(ax, *sub_origin, *sub_dims, color=wire_color, edge_color="black",
                          alpha=0.08, alpha_edges=0.08)
            fill_subbox(ax, sub_origin, sub_dims, sub_cube, cube_color="orange", cube_edge_color="blue", remaining=remaining)

    return int(max_quantity), leftovers


def _recurse(ax, product: Dims, region: Dims, origin: Point, r1: int, r2: int, r3: int,
             depth: int, max_depth: int,
             remaining: Optional[List[int]] = None):
    """
    Recursive continuation similar to your pilot's repeated MainBox calls on leftover regions.
    We keep it bounded by max_depth for safety.

    NEW: If 'remaining' hits 0, we stop recursing/drawing.
    """
    if depth >= max_depth:
        return
    if remaining is not None and remaining[0] <= 0:
        return

    _, leftovers = _draw_region_solution(ax, product, region, origin, r1, r2, r3,
                                         draw_wireframes=True, remaining=remaining)

    if remaining is not None and remaining[0] <= 0:
        return

    for sub_origin, sub_dims, _sub_cube, _wire_color in leftovers:
        if remaining is not None and remaining[0] <= 0:
            return
        if sub_dims[0] > 0 and sub_dims[1] > 0 and sub_dims[2] > 0:
            _recurse(ax, product, sub_dims, sub_origin, r1, r2, r3, depth + 1, max_depth, remaining=remaining)


def run_mode1_and_render(product: Dims,
                         container: Dims,
                         r1: int, r2: int, r3: int,
                         media_root: str,
                         draw_limit: Optional[int] = None) -> Mode1Result:
    """
    Mode render:
      - Draw container wireframe
      - Draw + fill main subbox AND leftover subboxes (pilot parity)
      - Recursively repeat on leftovers (bounded)
      - Save image to MEDIA_ROOT/box_selection/<uuid>.png

    NEW:
      - draw_limit=None (default) => draw maximum packed items (Single mode)
      - draw_limit=N              => draw only N items (Optimal mode, desired quantity)
    """
    # Normalize to float (important if inputs are Decimal)
    product = (float(product[0]), float(product[1]), float(product[2]))
    container = (float(container[0]), float(container[1]), float(container[2]))

    lc, ac, hc = container
    origin = (0.0, 0.0, 0.0)

    remaining = [int(draw_limit)] if draw_limit is not None else None

    # Render figure (small/fast)
    fig = plt.figure(figsize=(7.2, 4.6))
    ax = fig.add_subplot(111, projection="3d")
    ax.set_box_aspect([lc, ac, hc])

    # Outer container
    draw_cube(ax, 0, 0, 0, lc, ac, hc, color="lightgrey", edge_color="black", alpha=0.20, alpha_edges=0.35)

    # First level solve + draw
    max_qty, _leftovers = _draw_region_solution(ax, product, container, origin, r1, r2, r3,
                                               draw_wireframes=True, remaining=remaining)

    # Recurse further like the pilot's chained subboxes (but stop if we reach draw limit)
    _recurse(ax, product, container, origin, r1, r2, r3, depth=0, max_depth=6, remaining=remaining)

    # Axes / view
    ax.set_xlim([0, lc])
    ax.set_ylim([0, ac])
    ax.set_zlim([0, hc])
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_zlabel("Z")
    ax.view_init(elev=28, azim=30)

    # Save
    rel_dir = "box_selection"
    file_name = f"mode1_{uuid.uuid4().hex}.png"
    rel_path = os.path.join(rel_dir, file_name)
    abs_path = os.path.join(media_root, rel_path)

    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    plt.tight_layout()
    plt.savefig(abs_path, dpi=150)
    plt.close(fig)

    return Mode1Result(max_quantity=max_qty, image_rel_path=rel_path)
