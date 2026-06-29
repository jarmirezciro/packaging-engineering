# packagingapp/utils/bag_selection/engine.py
from dataclasses import dataclass
from typing import List, Tuple, Dict, Any, Set, Optional
import os
import uuid

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection, Line3DCollection


# ---------------------------
# Bag math constants
# ---------------------------

TOLERANCE = 2.0
SEALING_AREA = 10.0
EPSILON = 1e-9
# When two orientations have almost the same bag usage, prefer the orientation
# that respects the bag L/W convention instead of chasing a tiny area difference.
USAGE_ORIENTATION_TOLERANCE = 0.005


# ---------------------------
# Your bag math helpers
# ---------------------------

def is_smooth(n: int) -> bool:
    if n <= 0:
        return False
    temp = n
    for p_factor in (2, 3, 5):
        while temp % p_factor == 0:
            temp //= p_factor
    return temp == 1


def get_prime_factors(n: int) -> List[int]:
    factors = []
    divisor = 2
    temp = n
    while divisor * divisor <= temp:
        while temp % divisor == 0:
            factors.append(divisor)
            temp //= divisor
        divisor += 1
    if temp > 1:
        factors.append(temp)
    return factors


def bag_formula(bl: float, bw: float, bh: float) -> Set[Tuple[float, float]]:
    """
    Calculates the two possible flat-bag sizes for a given arrangement box.

    Rule:
      bag_length = arrangement_length + arrangement_height + tolerance + sealing_area
      bag_width  = arrangement_width  + arrangement_height + tolerance

    Sealing area is applied to LENGTH, not WIDTH. The opening/mouth is the
    width side, and that width side is perpendicular to the bag length.
    The two options below already represent rotating the product arrangement inside
    the flat bag. Therefore bag L/W matching must stay strict later; otherwise we
    double-rotate the bag and the graphic can contradict the selected bag.
    """
    option_1 = (float(bl + bh + TOLERANCE + SEALING_AREA), float(bw + bh + TOLERANCE))
    option_2 = (float(bw + bh + TOLERANCE + SEALING_AREA), float(bl + bh + TOLERANCE))
    return {option_1, option_2}


def _axis_record(axis_name: str, count: int, unit_size: float) -> Dict[str, Any]:
    return {
        "axis": axis_name,
        "count": int(count),
        "unit": float(unit_size),
        "total": float(count) * float(unit_size),
    }


def _solution_bag_options(visual_axes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Build bag options while preserving the product arrangement orientation.

    visual_axes are sorted by arrangement size:
      [largest footprint side, second footprint side, smallest height side]

    Option 1 places the largest footprint side along bag length.
    Option 2 rotates the arrangement 90 degrees in the bag footprint, placing the
    largest footprint side along bag width/opening.
    """
    length_axis = visual_axes[0]
    width_axis = visual_axes[1]
    height_axis = visual_axes[2]

    bl = float(length_axis["total"])
    bw = float(width_axis["total"])
    bh = float(height_axis["total"])

    return [
        {
            "orientation": "length_to_bag_length",
            "req_len": float(bl + bh + TOLERANCE + SEALING_AREA),
            "req_w": float(bw + bh + TOLERANCE),
            "body_box": (bl, bw, bh),
            "axes": [length_axis, width_axis, height_axis],
        },
        {
            "orientation": "length_to_bag_width",
            "req_len": float(bw + bh + TOLERANCE + SEALING_AREA),
            "req_w": float(bl + bh + TOLERANCE),
            "body_box": (bw, bl, bh),
            "axes": [width_axis, length_axis, height_axis],
        },
    ]


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
          "box": (bl, bw, bh),             # sorted bounding box of product grid
          "visual_axes": [...],            # orientation-preserving axes
          "bag_options": [...],            # required bags with matching axis order
          "bags": set((bag_len, bag_w), ...)
        }, ...
      ]
    """
    current = int(target_qty or 1)
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
    seen_signatures = set()

    for (nx, ny, nz) in sorted(layouts):
        # Fixed product orientation before the arrangement is placed in the bag.
        # The entire arrangement may then be rotated in the bag footprint through
        # the two bag options created below.
        axis_data = [
            _axis_record("product_length", nx, p_l),
            _axis_record("product_width", ny, p_w),
            _axis_record("product_height", nz, p_h),
        ]

        visual_axes = sorted(
            axis_data,
            key=lambda item: (-float(item["total"]), -float(item["unit"]), str(item["axis"])),
        )

        bl = float(visual_axes[0]["total"])
        bw = float(visual_axes[1]["total"])
        bh = float(visual_axes[2]["total"])
        box_tuple = (bl, bw, bh)

        # Do not deduplicate only by box dimensions. Different layouts can lead
        # to the same sorted box but a different product orientation/order. Keep
        # the orientation signature so the graphic can match the selected option.
        signature = tuple(
            (axis["axis"], axis["count"], round(float(axis["unit"]), 9), round(float(axis["total"]), 9))
            for axis in visual_axes
        )
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)

        bag_options = _solution_bag_options(visual_axes)
        bags = {(option["req_len"], option["req_w"]) for option in bag_options}

        final_results.append({
            "layout": (nx, ny, nz),
            "box": box_tuple,
            "visual_axes": visual_axes,
            "bag_options": bag_options,
            "bags": bags,
        })

    return smooth_qty, final_results


def build_required_bag_options(product_l: float, product_w: float, product_h: float, desired_qty: int) -> Dict[str, Any]:
    smooth_qty, solutions = get_final_packing_solution(desired_qty, product_l, product_w, product_h)

    required_set = set()
    for sol in solutions:
        for option in sol.get("bag_options") or []:
            required_set.add((float(option["req_len"]), float(option["req_w"])))

        # Backwards compatibility for any older solution dicts.
        if not sol.get("bag_options"):
            for (blen, bwid) in sol.get("bags", set()):
                required_set.add((float(blen), float(bwid)))

    required = sorted(required_set, key=lambda x: (x[0] * x[1], x[0], x[1]))
    return {"smooth_qty": smooth_qty, "solutions": solutions, "required": required}


# ---------------------------
# Fit + scoring for catalogue bags
# ---------------------------

def _fits(bag_len: float, bag_w: float, req_len: float, req_w: float) -> bool:
    """
    Strict flat-bag fit.

    Bag L and W are not interchangeable here because the sealing allowance is
    applied to bag LENGTH. The product arrangement rotation is already handled
    by bag_formula/_solution_bag_options through two required-bag options.
    """
    return bag_len + EPSILON >= req_len and bag_w + EPSILON >= req_w


def _same_required_bag(a: Optional[Tuple[float, float]], b: Optional[Tuple[float, float]]) -> bool:
    if not a or not b:
        return False
    return abs(float(a[0]) - float(b[0])) <= 1e-6 and abs(float(a[1]) - float(b[1])) <= 1e-6


def _orientation_preference(bag_len: float, bag_w: float, req_len: float, req_w: float) -> int:
    """Prefer the required-bag orientation that follows the physical L/W convention.

    If the selected bag is square or length-dominant, prefer required L >= W.
    If the selected bag is width-dominant, prefer required W >= L.

    This avoids visually rotating the arrangement just to gain a tiny area-usage
    difference when both orientations fit the same physical bag.
    """
    if bag_len + EPSILON >= bag_w:
        return 1 if req_len + EPSILON >= req_w else 0
    return 1 if req_w + EPSILON >= req_len else 0


def _is_better_bag_candidate(candidate: Dict[str, Any], best: Optional[Dict[str, Any]]) -> bool:
    if best is None:
        return True

    usage_delta = float(candidate["usage"]) - float(best["usage"])
    if usage_delta > USAGE_ORIENTATION_TOLERANCE:
        return True
    if usage_delta < -USAGE_ORIENTATION_TOLERANCE:
        return False

    candidate_pref = int(candidate.get("orientation_preference") or 0)
    best_pref = int(best.get("orientation_preference") or 0)
    if candidate_pref != best_pref:
        return candidate_pref > best_pref

    # If the orientation preference is the same, keep the tighter candidate.
    if usage_delta > EPSILON:
        return True
    if usage_delta < -EPSILON:
        return False

    # Final deterministic tie-breaker.
    return (float(candidate["req_len"]), float(candidate["req_w"])) < (float(best["req_len"]), float(best["req_w"]))


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
            candidate = {
                "req_len": req_len,
                "req_w": req_w,
                "usage": usage,
                "bag_area": bag_area,
                "orientation_preference": _orientation_preference(bag_len, bag_w, req_len, req_w),
            }
            if _is_better_bag_candidate(candidate, best):
                best = candidate
    return best


def _quantity_fits_in_bag(product_l: float, product_w: float, product_h: float, bag_len: float, bag_w: float, quantity: int) -> bool:
    if quantity <= 0:
        return True
    req = build_required_bag_options(product_l, product_w, product_h, quantity)
    return best_usage_for_bag(bag_len, bag_w, req["required"]) is not None


def compute_max_quantity_for_bag(
    product_l: float,
    product_w: float,
    product_h: float,
    bag_len: float,
    bag_w: float,
    *,
    max_search_qty: int = 10000,
) -> Dict[str, Any]:
    """
    Compute the maximum quantity supported by the existing bag formula.

    The bag algorithm rounds requested quantities to smooth layout quantities
    (prime factors 2, 3 and 5). To stay consistent with the current rendering
    and Top 5 logic, this function finds the largest smooth-layout quantity
    that fits the selected flat bag dimensions.
    """
    dims = (product_l, product_w, product_h, bag_len, bag_w)
    if any(v is None or float(v) <= 0 for v in dims):
        return {
            "max_quantity": 0,
            "smooth_qty": 0,
            "required_bags": [],
            "solutions": [],
            "best": None,
            "capped": False,
        }

    product_l, product_w, product_h = float(product_l), float(product_w), float(product_h)
    bag_len, bag_w = float(bag_len), float(bag_w)

    if not _quantity_fits_in_bag(product_l, product_w, product_h, bag_len, bag_w, 1):
        return {
            "max_quantity": 0,
            "smooth_qty": 0,
            "required_bags": [],
            "solutions": [],
            "best": None,
            "capped": False,
        }

    low = 1
    high = 2
    capped = False

    while high <= max_search_qty and _quantity_fits_in_bag(product_l, product_w, product_h, bag_len, bag_w, high):
        low = high
        high *= 2

    if high > max_search_qty:
        high = max_search_qty
        capped = True

    while low < high:
        mid = (low + high + 1) // 2
        if _quantity_fits_in_bag(product_l, product_w, product_h, bag_len, bag_w, mid):
            low = mid
        else:
            high = mid - 1

    req = build_required_bag_options(product_l, product_w, product_h, low)
    best = best_usage_for_bag(bag_len, bag_w, req["required"])

    return {
        "max_quantity": int(req["smooth_qty"]),
        "smooth_qty": int(req["smooth_qty"]),
        "required_bags": req["required"],
        "solutions": req["solutions"],
        "best": best,
        "capped": capped and low >= max_search_qty,
    }


# ---------------------------
# 3D rendering (bag-as-container)
# ---------------------------

@dataclass
class BagRenderResult:
    image_rel_path: str
    used_layout: Tuple[int, int, int]
    inner_box: Tuple[float, float, float]   # visual arrangement body as placed in bag: L,W,H
    required_bag: Tuple[float, float]       # req_len, req_w


def _cuboid_points(x, y, z, dx, dy, dz):
    return [
        (x, y, z),
        (x + dx, y, z),
        (x + dx, y + dy, z),
        (x, y + dy, z),
        (x, y, z + dz),
        (x + dx, y, z + dz),
        (x + dx, y + dy, z + dz),
        (x, y + dy, z + dz),
    ]


def _cuboid_face_map(x, y, z, dx, dy, dz):
    p = _cuboid_points(x, y, z, dx, dy, dz)
    return {
        "bottom": [p[0], p[1], p[2], p[3]],
        "top": [p[4], p[5], p[6], p[7]],
        "front": [p[0], p[1], p[5], p[4]],
        "back": [p[2], p[3], p[7], p[6]],
        # x_max face. This face has W × H dimensions and represents the bag mouth/opening.
        "opening": [p[1], p[2], p[6], p[5]],
        "left": [p[0], p[3], p[7], p[4]],
    }


def _cuboid_faces(x, y, z, dx, dy, dz, omitted_faces: Optional[Set[str]] = None):
    omitted_faces = omitted_faces or set()
    face_map = _cuboid_face_map(x, y, z, dx, dy, dz)
    return [face for name, face in face_map.items() if name not in omitted_faces]


def _face_edges(face):
    return [[face[i], face[(i + 1) % len(face)]] for i in range(len(face))]


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


def _clean_3d_axes(ax):
    ax.set_axis_off()
    ax.grid(False)
    ax.set_xlabel("")
    ax.set_ylabel("")
    ax.set_zlabel("")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_zticks([])
    for axis in (ax.xaxis, ax.yaxis, ax.zaxis):
        try:
            axis.pane.set_visible(False)
        except Exception:
            pass
        try:
            axis.line.set_visible(False)
        except Exception:
            pass


def _fallback_bag_options_for_solution(sol: Dict[str, Any], product: Tuple[float, float, float]) -> List[Dict[str, Any]]:
    """Support older solution dictionaries that do not yet carry bag_options."""
    p_l, p_w, p_h = product
    nx, ny, nz = sol["layout"]
    axis_data = [
        _axis_record("product_length", nx, p_l),
        _axis_record("product_width", ny, p_w),
        _axis_record("product_height", nz, p_h),
    ]
    visual_axes = sorted(
        axis_data,
        key=lambda item: (-float(item["total"]), -float(item["unit"]), str(item["axis"])),
    )
    return _solution_bag_options(visual_axes)


def _iter_solution_bag_options(sol: Dict[str, Any], product: Tuple[float, float, float]):
    options = sol.get("bag_options")
    if options:
        for option in options:
            yield option
        return
    for option in _fallback_bag_options_for_solution(sol, product):
        yield option


def _select_render_solution(
    *,
    product: Tuple[float, float, float],
    selected_bag: Tuple[float, float],
    solutions: List[Dict[str, Any]],
    selected_required_bag: Optional[Tuple[float, float]] = None,
):
    bag_len, bag_w = selected_bag
    bag_area = bag_len * bag_w

    best = None
    best_sol = None
    best_option = None

    def consider(require_exact: bool):
        nonlocal best, best_sol, best_option
        for sol_index, sol in enumerate(solutions):
            for option_index, option in enumerate(_iter_solution_bag_options(sol, product)):
                req_pair = (float(option["req_len"]), float(option["req_w"]))
                if require_exact and not _same_required_bag(req_pair, selected_required_bag):
                    continue
                if not _fits(bag_len, bag_w, req_pair[0], req_pair[1]):
                    continue
                usage = (req_pair[0] * req_pair[1]) / bag_area if bag_area > 0 else 0.0
                candidate = {
                    "req_len": req_pair[0],
                    "req_w": req_pair[1],
                    "usage": float(usage),
                    "bag_area": bag_area,
                    "orientation_preference": _orientation_preference(bag_len, bag_w, req_pair[0], req_pair[1]),
                    "score": (
                        -float(option["body_box"][2]),
                        -float(option["body_box"][0]) * float(option["body_box"][1]),
                        -sol_index,
                        -option_index,
                    ),
                }
                if _is_better_bag_candidate(candidate, best):
                    best = candidate
                    best_sol = sol
                    best_option = option

    if selected_required_bag:
        consider(require_exact=True)
    if best is None:
        consider(require_exact=False)

    return best, best_sol, best_option


def run_bag_mode1_and_render(
    product: Tuple[float, float, float],
    selected_bag: Tuple[float, float],
    desired_qty: int,
    solutions: List[Dict[str, Any]],
    media_root: str,
    draw_limit: Optional[int] = None,
    clean: bool = True,
    selected_required_bag: Optional[Tuple[float, float]] = None,
) -> BagRenderResult:
    """
    Visualize the selected bag as ONE open bag body.

    The calculation creates two required flat-bag options per arrangement. Those
    options are not just dimensions; they also define which product-arrangement
    side is placed along bag length and which side is placed along bag width.
    Rendering must use the same selected option, otherwise the best bag can be
    correct while the graphic shows the arrangement rotated incorrectly.

    Result:
    - one outer cuboid = selected physical bag body
    - W × H mouth/opening face removed at one L-end
    - product cuboids visible inside in the selected orientation
    - extra physical bag capacity remains visible around the arrangement
    """
    product = (float(product[0]), float(product[1]), float(product[2]))
    bag_len, bag_w = float(selected_bag[0]), float(selected_bag[1])
    draw_limit = draw_limit or desired_qty

    best, best_sol, best_option = _select_render_solution(
        product=product,
        selected_bag=(bag_len, bag_w),
        solutions=solutions,
        selected_required_bag=selected_required_bag,
    )

    if best is None or best_sol is None or best_option is None:
        raise ValueError("Selected bag does not fit any required bag option for this quantity/product.")

    nx, ny, nz = best_sol["layout"]

    body_length, body_width, body_height = (
        float(best_option["body_box"][0]),
        float(best_option["body_box"][1]),
        float(best_option["body_box"][2]),
    )
    body_axes = best_option["axes"]

    # Draw the actual selected physical/catalogue bag, not the minimum required
    # bag. The selected required option is used only to preserve the product
    # orientation that won the calculation. The physical flat bag is resolved
    # with the same convention used by the calculation:
    #   bag L = usable product body length + arrangement height + tolerance + sealing
    #   bag W = usable product body width  + arrangement height + tolerance
    #
    # Important for the graphic:
    # - products may only occupy the usable body area
    # - the sealing allowance is a reserved strip on the LENGTH direction
    # - width/opening receives tolerance only, not sealing
    usable_body_length = bag_len - TOLERANCE - SEALING_AREA - body_height
    usable_body_width = bag_w - TOLERANCE - body_height
    bag_box_height = body_height

    if usable_body_length <= 0 or usable_body_width <= 0 or bag_box_height <= 0:
        raise ValueError(
            "Resolved physical bag body dimensions are not positive. "
            "Selected bag fits the 2D requirement list, but not the visual body resolution."
        )

    # Guard against tiny floating precision differences while preserving the
    # physical selected bag dimensions for visible extra capacity. If the
    # selected required option fits, this normally does not change anything.
    if usable_body_length + EPSILON < body_length or usable_body_width + EPSILON < body_width:
        usable_body_length = max(usable_body_length, body_length)
        usable_body_width = max(usable_body_width, body_width)

    # The outer 3D body represents only the usable filled volume of the bag.
    # A separate flat sealing strip is drawn after the usable body so users can
    # see that products are not consuming the sealing allowance.
    bag_box_length = usable_body_length
    bag_box_width = usable_body_width
    seal_strip_length = SEALING_AREA
    visual_length_with_seal = bag_box_length + seal_strip_length

    # 3) Render path
    rel_dir = os.path.join("bag_selection")
    out_dir = os.path.join(media_root, rel_dir)
    os.makedirs(out_dir, exist_ok=True)
    filename = f"bag_{uuid.uuid4().hex}.png"
    abs_path = os.path.join(out_dir, filename)

    fig = plt.figure(figsize=(9, 7))
    ax = fig.add_subplot(111, projection="3d")

    # Outer physical bag body. Flat bag L is drawn as the bag depth, and flat
    # bag W is the mouth/opening direction. The W × H face at the open end is omitted.
    outer_faces = _cuboid_faces(
        0,
        0,
        0,
        bag_box_length,
        bag_box_width,
        bag_box_height,
        omitted_faces={"opening"},
    )
    outer_pc = Poly3DCollection(outer_faces, alpha=0.10, edgecolor="k", linewidths=0.9)
    ax.add_collection3d(outer_pc)

    opening_face = _cuboid_face_map(0, 0, 0, bag_box_length, bag_box_width, bag_box_height)["opening"]
    opening_lip = Line3DCollection(_face_edges(opening_face), colors="k", linewidths=2.2, alpha=0.95)
    ax.add_collection3d(opening_lip)

    # Reserved sealing strip on the length direction. This is deliberately flat
    # rather than a cuboid: it is bag material left free for closing/sealing, not
    # product-usable volume.
    seal_x0 = bag_box_length
    seal_x1 = bag_box_length + seal_strip_length
    seal_bottom = [[
        (seal_x0, 0, 0),
        (seal_x1, 0, 0),
        (seal_x1, bag_box_width, 0),
        (seal_x0, bag_box_width, 0),
    ]]
    seal_top = [[
        (seal_x0, 0, bag_box_height),
        (seal_x1, 0, bag_box_height),
        (seal_x1, bag_box_width, bag_box_height),
        (seal_x0, bag_box_width, bag_box_height),
    ]]
    seal_pc = Poly3DCollection(seal_bottom + seal_top, facecolor="#F59E0B", alpha=0.35, edgecolor="k", linewidths=0.8)
    ax.add_collection3d(seal_pc)
    seal_edges = [
        [(seal_x0, 0, 0), (seal_x0, bag_box_width, 0)],
        [(seal_x0, 0, bag_box_height), (seal_x0, bag_box_width, bag_box_height)],
        [(seal_x1, 0, 0), (seal_x1, bag_box_width, 0)],
        [(seal_x1, 0, bag_box_height), (seal_x1, bag_box_width, bag_box_height)],
    ]
    ax.add_collection3d(Line3DCollection(seal_edges, colors="k", linewidths=1.4, alpha=0.9))

    # 4) Draw products using the selected required-bag option orientation.
    x_axis, y_axis, z_axis = body_axes
    x_count, x_unit = int(x_axis["count"]), float(x_axis["unit"])
    y_count, y_unit = int(y_axis["count"]), float(y_axis["unit"])
    z_count, z_unit = int(z_axis["count"]), float(z_axis["unit"])

    drawn = 0
    for kz in range(z_count):
        for ky in range(y_count):
            for kx in range(x_count):
                if drawn >= draw_limit:
                    break

                x = kx * x_unit
                y = ky * y_unit
                z = kz * z_unit

                if x + x_unit > bag_box_length + EPSILON or y + y_unit > bag_box_width + EPSILON or z + z_unit > bag_box_height + EPSILON:
                    continue

                prod_faces = _cuboid_faces(x, y, z, x_unit, y_unit, z_unit)
                prod_pc = Poly3DCollection(prod_faces, alpha=0.38, edgecolor="k", linewidths=0.35)
                ax.add_collection3d(prod_pc)
                drawn += 1

            if drawn >= draw_limit:
                break
        if drawn >= draw_limit:
            break

    ax.set_xlim(0, visual_length_with_seal)
    ax.set_ylim(0, bag_box_width)
    ax.set_zlim(0, bag_box_height)
    ax.view_init(elev=22, azim=-55)
    _set_axes_equal(ax)

    if clean:
        _clean_3d_axes(ax)
    else:
        ax.set_xlabel("Bag length / depth")
        ax.set_ylabel("Bag width / opening")
        ax.set_zlabel("Arrangement height")
        ax.set_title(
            f"Usable body: {bag_box_length:.2f} × {bag_box_width:.2f} × {bag_box_height:.2f} | "
            f"Seal strip on L: {seal_strip_length:.2f} | "
            f"Arrangement: {body_length:.2f} × {body_width:.2f} × {body_height:.2f} | "
            f"Physical bag: {bag_len:.2f} × {bag_w:.2f} | Required bag: {best['req_len']:.2f} × {best['req_w']:.2f} | "
            f"Drawn: {drawn}/{desired_qty}"
        )

    plt.tight_layout(pad=0)
    plt.savefig(abs_path, dpi=160, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)

    image_rel_path = os.path.join(rel_dir, filename).replace("\\", "/")
    return BagRenderResult(
        image_rel_path=image_rel_path,
        used_layout=(nx, ny, nz),
        inner_box=(round(body_length, 2), round(body_width, 2), round(body_height, 2)),
        required_bag=(best["req_len"], best["req_w"]),
    )
