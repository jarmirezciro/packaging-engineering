# packagingapp/utils/container_tool/engine.py

import os
import uuid
from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection


# =========================================================
# DATA STRUCTURES
# =========================================================

@dataclass
class Space:
    x: float
    y: float
    z: float
    L: float
    W: float
    H: float

    @property
    def volume(self) -> float:
        return self.L * self.W * self.H

    def fits(self, dims: Tuple[float, float, float]) -> bool:
        l, w, h = dims
        return l <= self.L and w <= self.W and h <= self.H


@dataclass
class Placement:
    product_name: str
    item_index: int
    sequence: int
    weight: float
    x: float
    y: float
    z: float
    l: float
    w: float
    h: float


# =========================================================
# ROTATIONS
# =========================================================

def allowed_orientations(
    dims: Tuple[float, float, float],
    r1: bool,
    r2: bool,
    r3: bool
) -> List[Tuple[float, float, float]]:
    """
    Rotation groups aligned with the typical 3-rotation logic used in your app.

    r1 => standing on height H:
        (L, W, H), (W, L, H)

    r2 => standing on width W:
        (L, H, W), (H, L, W)

    r3 => standing on length L:
        (W, H, L), (H, W, L)
    """
    L, W, H = dims
    rots = []

    if r1:
        rots.extend([
            (L, W, H),
            (W, L, H),
        ])

    if r2:
        rots.extend([
            (L, H, W),
            (H, L, W),
        ])

    if r3:
        rots.extend([
            (W, H, L),
            (H, W, L),
        ])

    # remove duplicates while preserving order
    seen = set()
    unique = []
    for r in rots:
        key = (round(r[0], 6), round(r[1], 6), round(r[2], 6))
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique


# =========================================================
# SPACE SPLIT
# =========================================================

def split_space(space: Space, dims: Tuple[float, float, float]) -> List[Space]:
    """
    Residual-space split after placing one box at the lower-left-bottom corner
    of the selected space.
    """
    l, w, h = dims
    x, y, z = space.x, space.y, space.z

    new_spaces = []

    # Right residual
    if space.L - l > 1e-9:
        new_spaces.append(
            Space(
                x=x + l,
                y=y,
                z=z,
                L=space.L - l,
                W=space.W,
                H=space.H,
            )
        )

    # Front residual
    if space.W - w > 1e-9:
        new_spaces.append(
            Space(
                x=x,
                y=y + w,
                z=z,
                L=l,
                W=space.W - w,
                H=space.H,
            )
        )

    # Top residual
    if space.H - h > 1e-9:
        new_spaces.append(
            Space(
                x=x,
                y=y,
                z=z + h,
                L=l,
                W=w,
                H=space.H - h,
            )
        )

    return new_spaces


def can_space_contain_any_item(space: Space, remaining_items: List[Dict]) -> bool:
    for item in remaining_items:
        for rot in item["orientations"]:
            if space.fits(rot):
                return True
    return False


def prune_spaces(spaces: List[Space], remaining_items: List[Dict]) -> List[Space]:
    pruned = []
    for s in spaces:
        if s.L <= 1e-9 or s.W <= 1e-9 or s.H <= 1e-9:
            continue
        if remaining_items:
            if can_space_contain_any_item(s, remaining_items):
                pruned.append(s)
        else:
            pruned.append(s)

    # remove spaces fully contained inside another space
    final_spaces = []
    for i, a in enumerate(pruned):
        contained = False
        for j, b in enumerate(pruned):
            if i == j:
                continue
            if (
                a.x >= b.x and a.y >= b.y and a.z >= b.z and
                a.x + a.L <= b.x + b.L and
                a.y + a.W <= b.y + b.W and
                a.z + a.H <= b.z + b.H
            ):
                contained = True
                break
        if not contained:
            final_spaces.append(a)

    final_spaces.sort(key=lambda s: (s.z, s.x, s.y, s.volume))
    return final_spaces


# =========================================================
# PACKING HEURISTIC
# =========================================================

def choose_best_placement(
    spaces: List[Space],
    item: Dict
) -> Optional[Dict]:
    """
    Best-fit heuristic:
    - minimize leftover volume in selected free space
    - then prefer lower z, lower x, lower y
    """
    best = None

    for i, sp in enumerate(spaces):
        for rot in item["orientations"]:
            if sp.fits(rot):
                used_vol = rot[0] * rot[1] * rot[2]
                waste = sp.volume - used_vol

                score = (
                    waste,
                    sp.z,
                    sp.x,
                    sp.y,
                )

                if best is None or score < best["score"]:
                    best = {
                        "score": score,
                        "space_index": i,
                        "space": sp,
                        "rotation": rot,
                    }

    return best


def expand_items(products: List[Dict]) -> List[Dict]:
    items = []
    item_index = 0

    for p in products:
        dims = (p["length"], p["width"], p["height"])
        orientations = allowed_orientations(dims, p["r1"], p["r2"], p["r3"])

        for _ in range(p["qty"]):
            items.append({
                "product_name": p["name"],
                "dims": dims,
                "orientations": orientations,
                "weight": p["weight"],
                "sequence": p["sequence"],
                "item_index": item_index,
            })
            item_index += 1

    # loading sequence first, then larger volume first, then heavier first
    items.sort(
        key=lambda x: (
            x["sequence"],
            -(x["dims"][0] * x["dims"][1] * x["dims"][2]),
            -x["weight"],
        )
    )
    return items


def pack_container(container: Dict, products: List[Dict]) -> Dict:
    items = expand_items(products)

    spaces = [Space(0, 0, 0, container["L"], container["W"], container["H"])]
    placements: List[Placement] = []
    unplaced: List[Dict] = []

    loaded_weight = 0.0

    for idx, item in enumerate(items):
        if loaded_weight + item["weight"] > container["max_weight"]:
            unplaced.append({**item, "reason": "Container max weight exceeded"})
            continue

        best = choose_best_placement(spaces, item)
        if best is None:
            unplaced.append({**item, "reason": "No fitting free space"})
            continue

        sp = best["space"]
        rot = best["rotation"]
        i = best["space_index"]

        placements.append(
            Placement(
                product_name=item["product_name"],
                item_index=item["item_index"],
                sequence=item["sequence"],
                weight=item["weight"],
                x=sp.x,
                y=sp.y,
                z=sp.z,
                l=rot[0],
                w=rot[1],
                h=rot[2],
            )
        )
        loaded_weight += item["weight"]

        used_space = spaces.pop(i)
        spaces.extend(split_space(used_space, rot))

        remaining_items = items[idx + 1:]
        spaces = prune_spaces(spaces, remaining_items)

    return {
        "placements": placements,
        "unplaced": unplaced,
        "spaces": spaces,
        "loaded_weight": loaded_weight,
    }


# =========================================================
# SUMMARIES
# =========================================================

def summarize(container: Dict, products: List[Dict], pack_result: Dict) -> Dict:
    placements: List[Placement] = pack_result["placements"]
    unplaced = pack_result["unplaced"]
    loaded_weight = pack_result["loaded_weight"]

    container_volume = container["L"] * container["W"] * container["H"]
    packed_volume = sum(p.l * p.w * p.h for p in placements)

    requested_by_product = {}
    packed_by_product = {}

    for p in products:
        requested_by_product[p["name"]] = requested_by_product.get(p["name"], 0) + p["qty"]

    for pl in placements:
        packed_by_product[pl.product_name] = packed_by_product.get(pl.product_name, 0) + 1

    rows = []
    for p in products:
        rows.append({
            "name": p["name"],
            "length": p["length"],
            "width": p["width"],
            "height": p["height"],
            "qty_requested": p["qty"],
            "qty_packed": packed_by_product.get(p["name"], 0),
            "weight_each": p["weight"],
            "sequence": p["sequence"],
        })

    if placements:
        occupied_length = max(p.x + p.l for p in placements)
        occupied_width = max(p.y + p.w for p in placements)
        occupied_height = max(p.z + p.h for p in placements)
    else:
        occupied_length = occupied_width = occupied_height = 0.0

    return {
        "container_volume": container_volume,
        "packed_volume": packed_volume,
        "utilization_volume_pct": (100.0 * packed_volume / container_volume) if container_volume > 0 else 0.0,
        "container_max_weight": container["max_weight"],
        "loaded_weight": loaded_weight,
        "utilization_weight_pct": (100.0 * loaded_weight / container["max_weight"]) if container["max_weight"] > 0 else 0.0,
        "placed_units": len(placements),
        "unplaced_units": len(unplaced),
        "occupied_length": occupied_length,
        "occupied_width": occupied_width,
        "occupied_height": occupied_height,
        "residual_length": max(container["L"] - occupied_length, 0.0),
        "residual_width": max(container["W"] - occupied_width, 0.0),
        "residual_height": max(container["H"] - occupied_height, 0.0),
        "product_rows": rows,
    }


# =========================================================
# DRAWING
# =========================================================

def cuboid_faces(x, y, z, l, w, h):
    p0 = [x,     y,     z]
    p1 = [x + l, y,     z]
    p2 = [x + l, y + w, z]
    p3 = [x,     y + w, z]
    p4 = [x,     y,     z + h]
    p5 = [x + l, y,     z + h]
    p6 = [x + l, y + w, z + h]
    p7 = [x,     y + w, z + h]

    return [
        [p0, p1, p2, p3],
        [p4, p5, p6, p7],
        [p0, p1, p5, p4],
        [p1, p2, p6, p5],
        [p2, p3, p7, p6],
        [p3, p0, p4, p7],
    ]


def _color_for_index(idx: int):
    palette = [
        "#4C78A8", "#F58518", "#54A24B", "#E45756", "#72B7B2",
        "#EECA3B", "#B279A2", "#FF9DA6", "#9D755D", "#BAB0AC",
    ]
    return palette[idx % len(palette)]


def draw_container(container: Dict, placements: List[Placement], output_path: str):
    scale = 1000.0  # mm -> m

    fig = plt.figure(figsize=(16, 9))
    ax = fig.add_subplot(111, projection="3d")

    L = container["L"] / scale
    W = container["W"] / scale
    H = container["H"] / scale

    product_names = []
    for p in placements:
        if p.product_name not in product_names:
            product_names.append(p.product_name)

    color_map = {name: _color_for_index(i) for i, name in enumerate(product_names)}

    for pl in placements:
        x = pl.x / scale
        y = pl.y / scale
        z = pl.z / scale
        l = pl.l / scale
        w = pl.w / scale
        h = pl.h / scale

        faces = cuboid_faces(x, y, z, l, w, h)
        poly = Poly3DCollection(
            faces,
            facecolors=color_map.get(pl.product_name, "#AAAAAA"),
            edgecolors="black",
            linewidths=0.2,
            alpha=0.65,
        )
        ax.add_collection3d(poly)

    container_faces = cuboid_faces(0, 0, 0, L, W, H)
    wire = Poly3DCollection(
        container_faces,
        facecolors=(0, 0, 0, 0),
        edgecolors="black",
        linewidths=0.8,
    )
    ax.add_collection3d(wire)

    ax.set_xlim(0, L)
    ax.set_ylim(0, W)
    ax.set_zlim(0, H)

    ax.set_xlabel("Length (m)")
    ax.set_ylabel("Width (m)")
    ax.set_zlabel("Height (m)")
    ax.set_title("Container Tool - 3D Loading Result")

    try:
        ax.set_box_aspect((L, W, H))
    except Exception:
        pass

    legend_handles = []
    for name, color in color_map.items():
        legend_handles.append(
            plt.Line2D(
                [0], [0],
                marker="s",
                color="w",
                label=name,
                markerfacecolor=color,
                markersize=10
            )
        )
    if legend_handles:
        ax.legend(handles=legend_handles, loc="upper right")

    plt.tight_layout()
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


# =========================================================
# MAIN WRAPPER
# =========================================================

def run_container_tool(container: Dict, products: List[Dict], media_root: str) -> Dict:
    pack_result = pack_container(container, products)
    summary = summarize(container, products, pack_result)

    rel_dir = os.path.join("generated", "container_tool")
    abs_dir = os.path.join(media_root, rel_dir)
    os.makedirs(abs_dir, exist_ok=True)

    file_name = f"container_tool_{uuid.uuid4().hex[:12]}.png"
    abs_path = os.path.join(abs_dir, file_name)
    rel_path = os.path.join(rel_dir, file_name).replace("\\", "/")

    draw_container(container, pack_result["placements"], abs_path)

    return {
        "summary": summary,
        "placements": pack_result["placements"],
        "unplaced": pack_result["unplaced"],
        "image_rel_path": rel_path,
    }