# packagingapp/utils/container_tool/engine.py

import math
import os
import uuid
from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from PIL import Image, ImageChops


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


def _has_payload_limit(container: Dict) -> bool:
    try:
        return container.get("max_weight") is not None and float(container.get("max_weight")) > 0
    except Exception:
        return False


def pack_container(container: Dict, products: List[Dict]) -> Dict:
    items = expand_items(products)

    spaces = [Space(0, 0, 0, container["L"], container["W"], container["H"])]
    placements: List[Placement] = []
    unplaced: List[Dict] = []

    loaded_weight = 0.0
    payload_limit = float(container.get("max_weight")) if _has_payload_limit(container) else None

    for idx, item in enumerate(items):
        if payload_limit is not None and loaded_weight + item["weight"] > payload_limit:
            unplaced.append({**item, "reason": "Container max payload exceeded"})
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

    tare_weight = container.get("tare_weight")
    payload_limit = container.get("max_weight")
    has_payload_limit = _has_payload_limit(container)
    gross_weight = loaded_weight + (float(tare_weight) if tare_weight is not None else 0.0)

    return {
        "container_volume": container_volume,
        "packed_volume": packed_volume,
        "container_volume_m3": container_volume / 1_000_000_000.0,
        "packed_volume_m3": packed_volume / 1_000_000_000.0,
        "utilization_volume_pct": (100.0 * packed_volume / container_volume) if container_volume > 0 else 0.0,
        "container_max_weight": float(payload_limit) if has_payload_limit else None,
        "has_payload_limit": has_payload_limit,
        "loaded_weight": loaded_weight,
        "tare_weight": float(tare_weight) if tare_weight is not None else None,
        "gross_weight": gross_weight,
        "utilization_weight_pct": (100.0 * loaded_weight / float(payload_limit)) if has_payload_limit else None,
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


def _draw_line(ax, p1, p2, color="#333333", linewidth=1.0, alpha=1.0):
    ax.plot(
        [p1[0], p2[0]],
        [p1[1], p2[1]],
        [p1[2], p2[2]],
        color=color,
        linewidth=linewidth,
        alpha=alpha,
        solid_capstyle="round",
    )


def _draw_container_frame(ax, L, W, H):
    points = {
        "000": (0, 0, 0),
        "100": (L, 0, 0),
        "110": (L, W, 0),
        "010": (0, W, 0),
        "001": (0, 0, H),
        "101": (L, 0, H),
        "111": (L, W, H),
        "011": (0, W, H),
    }
    edges = [
        ("000", "100"), ("100", "110"), ("110", "010"), ("010", "000"),
        ("001", "101"), ("101", "111"), ("111", "011"), ("011", "001"),
        ("000", "001"), ("100", "101"), ("110", "111"), ("010", "011"),
    ]
    for a, b in edges:
        _draw_line(ax, points[a], points[b], color="#202020", linewidth=1.1, alpha=0.95)


def _draw_open_doors(ax, x_face, W, H, angle_deg=135):
    theta = math.radians(angle_deg)
    half_w = W / 2.0

    left_outer_x = x_face + (half_w * math.sin(theta))
    left_outer_y = half_w * math.cos(theta)
    right_outer_x = x_face + (half_w * math.sin(theta))
    right_outer_y = W - (half_w * math.cos(theta))

    left_door = [
        (x_face, 0, 0),
        (left_outer_x, left_outer_y, 0),
        (left_outer_x, left_outer_y, H),
        (x_face, 0, H),
    ]
    right_door = [
        (x_face, W, 0),
        (right_outer_x, right_outer_y, 0),
        (right_outer_x, right_outer_y, H),
        (x_face, W, H),
    ]

    door_poly = Poly3DCollection(
        [left_door, right_door],
        facecolors=["#d8d8d8", "#d8d8d8"],
        edgecolors="#5a5a5a",
        linewidths=1.0,
        alpha=0.35,
    )
    ax.add_collection3d(door_poly)

    for door in (left_door, right_door):
        for i in range(len(door)):
            _draw_line(ax, door[i], door[(i + 1) % len(door)], color="#555555", linewidth=1.0, alpha=0.9)

    # central opening edge for the door frame
    _draw_line(ax, (x_face, W / 2.0, 0), (x_face, W / 2.0, H), color="#444444", linewidth=0.9, alpha=0.8)

    return abs(left_outer_x - x_face), abs(left_outer_y)


def _camera_for_view(view: str):
    views = {
        "main": {"elev": 18, "azim": -58, "dist": 7.5},
        "opposite": {"elev": 18, "azim": 122, "dist": 7.5},
        "top": {"elev": 88, "azim": -90, "dist": 8.2},
        "side": {"elev": 12, "azim": 0, "dist": 7.8},
    }
    return views.get(view, views["main"])


def draw_container(container: Dict, placements: List[Placement], output_path: str, view: str = "main"):
    scale = 1000.0  # mm -> m

    fig = plt.figure(figsize=(16, 6), facecolor="white")
    ax = fig.add_axes([0.01, 0.01, 0.98, 0.98], projection="3d")
    ax.set_facecolor("white")

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
            edgecolors="#2c2c2c",
            linewidths=0.35,
            alpha=0.78,
        )
        ax.add_collection3d(poly)

    # subtle floor shading for better depth perception
    floor = Poly3DCollection(
        [[(0, 0, 0), (L, 0, 0), (L, W, 0), (0, W, 0)]],
        facecolors="#f2f2f2",
        edgecolors="none",
        alpha=0.25,
    )
    ax.add_collection3d(floor)

    _draw_container_frame(ax, L, W, H)
    door_x_span, door_y_span = _draw_open_doors(ax, L, W, H, angle_deg=135)

    x_pad_left = max(L * 0.015, 0.08)
    x_pad_right = max(door_x_span + 0.08, L * 0.015)
    y_pad = max(W * 0.03, 0.05)
    z_pad = max(H * 0.02, 0.04)

    ax.set_xlim(-x_pad_left, L + x_pad_right)
    ax.set_ylim(-y_pad, W + y_pad)
    ax.set_zlim(0, H + z_pad)

    try:
        ax.set_box_aspect((L + x_pad_left + x_pad_right, W + 2 * y_pad, H + z_pad))
    except Exception:
        pass

    camera = _camera_for_view(view)
    ax.view_init(elev=camera["elev"], azim=camera["azim"])
    try:
        ax.dist = camera["dist"]
    except Exception:
        pass
    ax.set_axis_off()
    ax.grid(False)

    plt.subplots_adjust(left=0, right=1, bottom=0, top=1)
    fig.savefig(output_path, dpi=180, bbox_inches="tight", pad_inches=0.0)
    plt.close(fig)
    _trim_and_fit_render(output_path)




def _trim_and_fit_render(output_path: str, canvas_size=(1600, 700), margin_ratio=0.04):
    img = Image.open(output_path).convert("RGB")
    bg = Image.new("RGB", img.size, "white")
    diff = ImageChops.difference(img, bg)
    bbox = diff.getbbox()

    if bbox:
        img = img.crop(bbox)

    canvas_w, canvas_h = canvas_size
    max_w = int(canvas_w * (1 - 2 * margin_ratio))
    max_h = int(canvas_h * (1 - 2 * margin_ratio))

    scale = min(max_w / img.width, max_h / img.height)
    new_size = (max(1, int(img.width * scale)), max(1, int(img.height * scale)))
    img = img.resize(new_size, Image.LANCZOS)

    canvas = Image.new("RGB", (canvas_w, canvas_h), "white")
    x = (canvas_w - img.width) // 2
    y = (canvas_h - img.height) // 2
    canvas.paste(img, (x, y))
    canvas.save(output_path)

# =========================================================
# MAIN WRAPPER
# =========================================================

def run_container_tool(container: Dict, products: List[Dict], media_root: str) -> Dict:
    pack_result = pack_container(container, products)
    summary = summarize(container, products, pack_result)

    rel_dir = os.path.join("generated", "container_tool")
    abs_dir = os.path.join(media_root, rel_dir)
    os.makedirs(abs_dir, exist_ok=True)

    file_stub = f"container_tool_{uuid.uuid4().hex[:12]}"
    view_order = ["main", "opposite", "top", "side"]
    image_rel_paths = {}

    for view_name in view_order:
        file_name = f"{file_stub}_{view_name}.png"
        abs_path = os.path.join(abs_dir, file_name)
        rel_path = os.path.join(rel_dir, file_name).replace("\\", "/")
        draw_container(container, pack_result["placements"], abs_path, view=view_name)
        image_rel_paths[view_name] = rel_path

    return {
        "summary": summary,
        "placements": pack_result["placements"],
        "unplaced": pack_result["unplaced"],
        "image_rel_path": image_rel_paths.get("main"),
        "image_rel_paths": image_rel_paths,
    }
