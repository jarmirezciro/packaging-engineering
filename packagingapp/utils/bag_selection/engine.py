# packagingapp/utils/bag_selection/engine.py
from dataclasses import dataclass
from typing import List, Tuple, Dict, Any, Set, Optional
import os
import uuid

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection


# ---------------------------
# Your bag math helpers
# ---------------------------

def is_smooth(n: int) -> bool:
    if n <= 0:
        return False
    temp = n
    for p in (2, 3, 5):
        while temp % p == 0:
            temp //= p
    return temp == 1


def get_prime_factors(n: int) -> List[int]:
    factors = []
    d = 2
    temp = n
    while d * d <= temp:
        while temp % d == 0:
            factors.append(d)
            temp //= d
        d += 1
    if temp > 1:
        factors.append(temp)
    return factors


def bag_formula(bl: float, bw: float, bh: float) -> Set[Tuple[float, float]]:
    """
    Calculates the two possible bag sizes for a given arrangement box.

    Rule:
      bag_length = arrangement_length + arrangement_height + tolerance
      bag_width  = arrangement_width  + arrangement_height + tolerance + sealing_area

    Sealing area is applied to WIDTH, not LENGTH.
    """
    tolerance = 2
    sealing_area = 10

    # Option 1: arrangement length goes to bag length
    length_alt_1 = bl + bh + tolerance
    width_alt_1 = bw + bh + tolerance + sealing_area

    # Option 2: arrangement width goes to bag length
    length_alt_2 = bw + bh + tolerance
    width_alt_2 = bl + bh + tolerance + sealing_area

    return {
        (float(length_alt_1), float(width_alt_1)),
        (float(length_alt_2), float(width_alt_2)),
    }


# ---------------------------
# Build required options + keep layouts
# ---------------------------

def get_final_packing_solution(target_qty: int, p_l: float, p_w: float, p_h: float):
    """
    Returns:
      smooth_qty,
      solutions: [
        {
          "layout": (nx, ny, nz),
          "box": (bl, bw, bh),   # bounding box of product grid
          "bags": set((bag_len, bag_w), ...)
        }, ...
      ]
    """
    current = target_qty
    while not is_smooth(current):
        current += 1
    smooth_qty = current

    factors = get_prime_factors(smooth_qty)
    layouts = set()

    def distribute(idx, nx, ny, nz):
        if idx == len(factors):
            layouts.add((nx, ny, nz))
            return
        distribute(idx + 1, nx * factors[idx], ny, nz)
        distribute(idx + 1, nx, ny * factors[idx], nz)
        distribute(idx + 1, nx, ny, nz * factors[idx])

    distribute(0, 1, 1, 1)

    final_results = []
    seen_boxes = set()

    for (nx, ny, nz) in layouts:
        # IMPORTANT: no rotation -> fixed orientation assignment:
        # x axis uses p_l, y uses p_w, z uses p_h
        x_dim = nx * p_l
        y_dim = ny * p_w
        z_dim = nz * p_h

        # For bag formula, we still interpret (bl,bw,bh) as sorted by size (as your original script),
        # because the formula assumes "L/W/H by size".
        dims_sorted = sorted((x_dim, y_dim, z_dim))
        bl, bw, bh = dims_sorted[2], dims_sorted[1], dims_sorted[0]

        box_tuple = (bl, bw, bh)
        if box_tuple in seen_boxes:
            continue
        seen_boxes.add(box_tuple)

        bags = bag_formula(bl, bw, bh)
        final_results.append({
            "layout": (nx, ny, nz),
            "box": box_tuple,
            "bags": bags
        })

    return smooth_qty, final_results


def build_required_bag_options(product_l: float, product_w: float, product_h: float, desired_qty: int) -> Dict[str, Any]:
    smooth_qty, solutions = get_final_packing_solution(desired_qty, product_l, product_w, product_h)

    required_set = set()
    for sol in solutions:
        for (blen, bwid) in sol["bags"]:
            required_set.add((float(blen), float(bwid)))

    required = sorted(required_set, key=lambda x: (x[0] * x[1], x[0], x[1]))
    return {"smooth_qty": smooth_qty, "solutions": solutions, "required": required}


# ---------------------------
# Fit + scoring for catalogue bags
# ---------------------------

def _fits(bag_len: float, bag_w: float, req_len: float, req_w: float) -> bool:
    return (bag_len >= req_len and bag_w >= req_w) or (bag_len >= req_w and bag_w >= req_len)


def best_usage_for_bag(bag_len: float, bag_w: float, required_bags: List[Tuple[float, float]]) -> Optional[Dict[str, Any]]:
    if bag_len <= 0 or bag_w <= 0:
        return None

    bag_area = bag_len * bag_w
    best = None

    for (req_len, req_w) in required_bags:
        if req_len <= 0 or req_w <= 0:
            continue
        if _fits(bag_len, bag_w, req_len, req_w):
            req_area = req_len * req_w
            usage = req_area / bag_area if bag_area > 0 else 0.0
            if best is None or usage > best["usage"]:
                best = {
                    "req_len": req_len,
                    "req_w": req_w,
                    "usage": usage,
                    "bag_area": bag_area,
                }
    return best


# ---------------------------
# 3D rendering (bag-as-container)
# ---------------------------

@dataclass
class BagRenderResult:
    image_rel_path: str
    used_layout: Tuple[int, int, int]
    inner_box: Tuple[float, float, float]   # bl,bw,bh
    required_bag: Tuple[float, float]       # req_len, req_w


def _cuboid_faces(x, y, z, dx, dy, dz):
    # 8 corners
    p = [
        (x, y, z),
        (x + dx, y, z),
        (x + dx, y + dy, z),
        (x, y + dy, z),
        (x, y, z + dz),
        (x + dx, y, z + dz),
        (x + dx, y + dy, z + dz),
        (x, y + dy, z + dz),
    ]
    # 6 faces
    return [
        [p[0], p[1], p[2], p[3]],  # bottom
        [p[4], p[5], p[6], p[7]],  # top
        [p[0], p[1], p[5], p[4]],  # front
        [p[2], p[3], p[7], p[6]],  # back
        [p[1], p[2], p[6], p[5]],  # right
        [p[0], p[3], p[7], p[4]],  # left
    ]


def _set_axes_equal(ax):
    x_limits = ax.get_xlim3d()
    y_limits = ax.get_ylim3d()
    z_limits = ax.get_zlim3d()

    x_range = abs(x_limits[1] - x_limits[0])
    x_middle = sum(x_limits) / 2
    y_range = abs(y_limits[1] - y_limits[0])
    y_middle = sum(y_limits) / 2
    z_range = abs(z_limits[1] - z_limits[0])
    z_middle = sum(z_limits) / 2

    plot_radius = 0.5 * max([x_range, y_range, z_range])
    ax.set_xlim3d([x_middle - plot_radius, x_middle + plot_radius])
    ax.set_ylim3d([y_middle - plot_radius, y_middle + plot_radius])
    ax.set_zlim3d([z_middle - plot_radius, z_middle + plot_radius])


def run_bag_mode1_and_render(
    product: Tuple[float, float, float],
    selected_bag: Tuple[float, float],
    desired_qty: int,
    solutions: List[Dict[str, Any]],
    media_root: str,
    draw_limit: Optional[int] = None,
) -> BagRenderResult:
    """
    Visualize the selected bag as ONE box.

    The bag formula is based on sorted arrangement dimensions (bl, bw, bh),
    so the rendering must also use that same sorted dimensional system.

    Result:
    - one outer cuboid = visual bag box
    - product cuboids visible inside
    - empty space visible as remaining volume
    """
    p_l, p_w, p_h = product
    bag_len, bag_w = selected_bag
    draw_limit = draw_limit or desired_qty

    tolerance = 2.0
    sealing_area = 10.0

    # 1) Find best fitting solution for this selected bag
    best = None
    best_sol = None
    for sol in solutions:
        for (req_len, req_w) in sol["bags"]:
            if _fits(bag_len, bag_w, req_len, req_w):
                usage = (req_len * req_w) / (bag_len * bag_w)
                if best is None or usage > best["usage"]:
                    best = {
                        "req_len": float(req_len),
                        "req_w": float(req_w),
                        "usage": float(usage),
                    }
                    best_sol = sol

    if best is None or best_sol is None:
        raise ValueError("Selected bag does not fit any required bag option for this quantity/product.")

    nx, ny, nz = best_sol["layout"]

    # Actual layout axis sizes before sorting
    axis_data = [
        ("x", nx, p_l, nx * p_l),
        ("y", ny, p_w, ny * p_w),
        ("z", nz, p_h, nz * p_h),
    ]

    # Sort descending to match best_sol["box"] = (bl, bw, bh)
    axis_sorted = sorted(axis_data, key=lambda t: t[3], reverse=True)

    # Sorted arrangement dimensions used by bag_formula()
    bl, bw, bh = best_sol["box"]

    # 2) Resolve the visual bag box using the same sorted dims
    candidates = []

    # Orientation A
    box_length_a = bag_len - tolerance - bh
    box_width_a = bag_w - tolerance - sealing_area - bh
    if box_length_a > 0 and box_width_a > 0:
        candidates.append((box_length_a, box_width_a))

    # Orientation B
    box_length_b = bag_w - tolerance - bh
    box_width_b = bag_len - tolerance - sealing_area - bh
    if box_length_b > 0 and box_width_b > 0:
        candidates.append((box_length_b, box_width_b))

    if not candidates:
        raise ValueError(
            "Resolved bag box dimensions are not positive. "
            "Selected bag fits the 2D requirement list, but not the visual box resolution."
        )

    # Pick the smallest valid bag box that still contains the sorted arrangement footprint
    valid_candidates = [(L, W) for (L, W) in candidates if bl <= L and bw <= W]

    if valid_candidates:
        bag_box_length, bag_box_width = min(
            valid_candidates,
            key=lambda t: (t[0] * t[1], t[0] + t[1])
        )
    else:
        bag_box_length, bag_box_width = min(
            candidates,
            key=lambda t: (t[0] * t[1], t[0] + t[1])
        )

    bag_box_height = bh

    # 3) Render path
    rel_dir = os.path.join("bag_selection")
    out_dir = os.path.join(media_root, rel_dir)
    os.makedirs(out_dir, exist_ok=True)
    filename = f"bag_{uuid.uuid4().hex}.png"
    abs_path = os.path.join(out_dir, filename)

    fig = plt.figure(figsize=(9, 7))
    ax = fig.add_subplot(111, projection="3d")

    # Outer bag box (only one container box)
    outer_faces = _cuboid_faces(0, 0, 0, bag_box_length, bag_box_width, bag_box_height)
    outer_pc = Poly3DCollection(outer_faces, alpha=0.10, edgecolor="k", linewidths=0.9)
    ax.add_collection3d(outer_pc)

    # 4) Draw products using the sorted axis mapping
    #
    # axis_sorted[0] -> visual X
    # axis_sorted[1] -> visual Y
    # axis_sorted[2] -> visual Z
    #
    # Each tuple is: (axis_name, count, unit_size, total_size)
    x_axis_name, x_count, x_unit, _ = axis_sorted[0]
    y_axis_name, y_count, y_unit, _ = axis_sorted[1]
    z_axis_name, z_count, z_unit, _ = axis_sorted[2]

    drawn = 0
    for kz in range(z_count):
        for ky in range(y_count):
            for kx in range(x_count):
                if drawn >= draw_limit:
                    break

                x = kx * x_unit
                y = ky * y_unit
                z = kz * z_unit

                if x + x_unit > bag_box_length or y + y_unit > bag_box_width or z + z_unit > bag_box_height:
                    continue

                prod_faces = _cuboid_faces(x, y, z, x_unit, y_unit, z_unit)
                prod_pc = Poly3DCollection(prod_faces, alpha=0.38, edgecolor="k", linewidths=0.35)
                ax.add_collection3d(prod_pc)
                drawn += 1

            if drawn >= draw_limit:
                break
        if drawn >= draw_limit:
            break

    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_zlabel("Z")

    ax.set_xlim(0, bag_box_length)
    ax.set_ylim(0, bag_box_width)
    ax.set_zlim(0, bag_box_height)
    _set_axes_equal(ax)

    ax.set_title(
        f"Bag box: {bag_box_length:.2f} × {bag_box_width:.2f} × {bag_box_height:.2f} | "
        f"Arrangement: {bl:.2f} × {bw:.2f} × {bh:.2f} | "
        f"Drawn: {drawn}/{desired_qty}"
    )

    plt.tight_layout()
    plt.savefig(abs_path, dpi=160)
    plt.close(fig)

    image_rel_path = os.path.join(rel_dir, filename).replace("\\", "/")
    return BagRenderResult(
        image_rel_path=image_rel_path,
        used_layout=(nx, ny, nz),
        inner_box=(bl, bw, bh),
        required_bag=(best["req_len"], best["req_w"]),
    )