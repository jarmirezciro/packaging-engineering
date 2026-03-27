from __future__ import annotations

import itertools
import math
import os
import uuid
from dataclasses import dataclass
from typing import List, Tuple

import matplotlib
matplotlib.use("Agg")  # important for server rendering
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import to_rgba
from mpl_toolkits.mplot3d.art3d import Poly3DCollection


Dims = Tuple[float, float, float]
Point = Tuple[float, float, float]


@dataclass(frozen=True)
class PackingResult:
    quantity: int
    orientation: Dims
    counts_xyz: Tuple[int, int, int]  # (nx, ny, nz)
    image_rel_path: str  # relative to MEDIA_ROOT (so you can build MEDIA_URL + rel_path)


def _draw_cuboid(ax, x, y, z, dx, dy, dz, color="orange", edge_color="black", alpha=0.85, alpha_edges=0.4):
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


def _best_grid_packing(product: Dims, box: Dims, allow_rotations: bool) -> Tuple[int, Dims, Tuple[int, int, int]]:
    pl, pw, ph = product
    bl, bw, bh = box

    orientations = set(itertools.permutations((pl, pw, ph), 3)) if allow_rotations else {(pl, pw, ph)}

    best_qty = 0
    best_ori = (pl, pw, ph)
    best_counts = (0, 0, 0)

    for dx, dy, dz in orientations:
        nx = int(math.floor(bl / dx))
        ny = int(math.floor(bw / dy))
        nz = int(math.floor(bh / dz))
        qty = nx * ny * nz
        if qty > best_qty:
            best_qty = qty
            best_ori = (dx, dy, dz)
            best_counts = (nx, ny, nz)

    return best_qty, best_ori, best_counts


def _render_packing_png(
    product_ori: Dims,
    box: Dims,
    counts: Tuple[int, int, int],
    out_abs_path: str,
):
    dx, dy, dz = product_ori
    bl, bw, bh = box
    nx, ny, nz = counts

    fig = plt.figure(figsize=(10, 7))
    ax = fig.add_subplot(111, projection="3d")
    ax.set_box_aspect([bl, bw, bh])

    # Draw container as translucent cuboid
    _draw_cuboid(ax, 0, 0, 0, bl, bw, bh, color="lightgrey", edge_color="black", alpha=0.15, alpha_edges=0.25)

    # Draw items as a simple grid (origin at 0,0,0)
    for i in range(nx):
        for j in range(ny):
            for k in range(nz):
                x = i * dx
                y = j * dy
                z = k * dz
                _draw_cuboid(ax, x, y, z, dx, dy, dz, color="orange", edge_color="blue", alpha=0.9, alpha_edges=0.35)

    ax.set_xlim([0, bl])
    ax.set_ylim([0, bw])
    ax.set_zlim([0, bh])
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_zlabel("Z")
    ax.view_init(elev=25, azim=35)

    plt.tight_layout()
    os.makedirs(os.path.dirname(out_abs_path), exist_ok=True)
    plt.savefig(out_abs_path, dpi=160)
    plt.close(fig)


def compute_and_render(product: Dims, box: Dims, allow_rotations: bool, media_root: str) -> PackingResult:
    qty, ori, counts = _best_grid_packing(product, box, allow_rotations)

    # If nothing fits, still render an empty container image (or you can skip rendering)
    file_name = f"packing_{uuid.uuid4().hex}.png"
    rel_dir = "box_selection"
    rel_path = os.path.join(rel_dir, file_name)
    abs_path = os.path.join(media_root, rel_path)

    _render_packing_png(ori, box, counts, abs_path)

    return PackingResult(
        quantity=qty,
        orientation=ori,
        counts_xyz=counts,
        image_rel_path=rel_path,
    )
