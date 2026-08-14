from django.conf import settings

from .state import default_product_rows
from .serializers import (
    sanitize_transport_rows_for_session,
    serialize_transport_result,
    serialize_transport_threejs_scene,
)
from ...utils.container_tool.engine import pack_container, run_container_tool, summarize


def read_product_rows_raw(post_data):
    names = post_data.getlist("item_name[]")
    lengths = post_data.getlist("item_length[]")
    widths = post_data.getlist("item_width[]")
    heights = post_data.getlist("item_height[]")
    qtys = post_data.getlist("item_qty[]")
    max_qtys = post_data.getlist("item_max_qty[]")
    stackable_vals = post_data.getlist("item_stackable[]")
    max_qty_checked_indices = set()
    for value in post_data.getlist("item_max_qty_checked[]"):
        try:
            max_qty_checked_indices.add(int(value))
        except Exception:
            continue
    weights = post_data.getlist("item_weight[]")
    seqs = post_data.getlist("item_sequence[]")
    r1_vals = post_data.getlist("item_r1[]")
    r2_vals = post_data.getlist("item_r2[]")
    r3_vals = post_data.getlist("item_r3[]")

    row_count = max(
        len(names),
        len(lengths),
        len(widths),
        len(heights),
        len(qtys),
        len(max_qtys),
        len(stackable_vals),
        len(weights),
        len(seqs),
        len(r1_vals),
        len(r2_vals),
        len(r3_vals),
    )

    rows = []

    def checked(value):
        return str(value).lower() in {"1", "true", "on", "yes"}

    for i in range(row_count):
        name = names[i].strip() if i < len(names) else f"Product {i+1}"
        length_raw = lengths[i].strip() if i < len(lengths) else ""
        width_raw = widths[i].strip() if i < len(widths) else ""
        height_raw = heights[i].strip() if i < len(heights) else ""
        qty_raw = qtys[i].strip() if i < len(qtys) else "1"
        max_qty_raw = max_qtys[i].strip() if i < len(max_qtys) else "0"
        weight_raw = weights[i].strip() if i < len(weights) else "0"
        seq_raw = seqs[i].strip() if i < len(seqs) else "1"

        rows.append(
            {
                "name": name or f"Product {i+1}",
                "length": length_raw,
                "width": width_raw,
                "height": height_raw,
                "qty": qty_raw if qty_raw != "" else 1,
                "max_qty": checked(max_qty_raw) or i in max_qty_checked_indices,
                "stackable": checked(stackable_vals[i]) if i < len(stackable_vals) else True,
                "weight": weight_raw if weight_raw != "" else 0,
                "sequence": seq_raw if seq_raw != "" else 1,
                "r1": checked(r1_vals[i]) if i < len(r1_vals) else False,
                "r2": checked(r2_vals[i]) if i < len(r2_vals) else False,
                "r3": checked(r3_vals[i]) if i < len(r3_vals) else False,
            }
        )

    return rows


def validate_transport_rows(raw_rows):
    rows = []
    errors = []

    if not raw_rows:
        return rows, ["Please add at least one valid product row."]

    for i, raw in enumerate(raw_rows):
        name = str(raw.get("name", "")).strip() or f"Product {i+1}"

        try:
            length = float(raw.get("length"))
            width = float(raw.get("width"))
            height = float(raw.get("height"))
            max_qty = bool(raw.get("max_qty", False))
            qty = 1 if max_qty else int(float(raw.get("qty", 1)))
            weight = float(raw.get("weight", 0) or 0)
            sequence = int(float(raw.get("sequence", 1) or 1))
        except Exception:
            errors.append(f"Row {i+1}: invalid numeric values.")
            continue

        stackable = bool(raw.get("stackable", True))
        r1 = bool(raw.get("r1"))
        r2 = bool(raw.get("r2"))
        r3 = bool(raw.get("r3"))

        if length <= 0 or width <= 0 or height <= 0:
            errors.append(f"Row {i+1}: dimensions must be greater than 0.")
            continue
        if not max_qty and qty <= 0:
            errors.append(f"Row {i+1}: quantity must be greater than 0.")
            continue
        if weight < 0:
            errors.append(f"Row {i+1}: weight cannot be negative.")
            continue
        if sequence <= 0:
            errors.append(f"Row {i+1}: loading sequence must be greater than 0.")
            continue
        if not (r1 or r2 or r3):
            errors.append(f"Row {i+1}: enable at least one rotation.")
            continue

        rows.append(
            {
                "name": name,
                "length": length,
                "width": width,
                "height": height,
                "qty": qty,
                "max_qty": max_qty,
                "stackable": stackable,
                "weight": weight,
                "sequence": sequence,
                "r1": r1,
                "r2": r2,
                "r3": r3,
            }
        )

    if not rows:
        errors.append("Please add at least one valid product row.")

    return rows, errors


def _parse_optional_non_negative(value, label, messages):
    raw = "" if value is None else str(value).strip()
    if raw == "":
        return None
    try:
        parsed = float(raw)
    except Exception:
        messages.append(f"Please enter a valid {label}.")
        return None
    if parsed < 0:
        messages.append(f"{label.capitalize()} cannot be negative.")
        return None
    return parsed


def build_container_from_config(cfg, selected_material=None):
    messages = []

    max_weight = _parse_optional_non_negative(cfg.get("max_weight"), "max payload", messages)
    tare_weight = _parse_optional_non_negative(cfg.get("tare_weight"), "tare weight", messages)

    if tare_weight is None and selected_material is not None:
        try:
            tare_weight = float(selected_material.part_weight) if selected_material.part_weight is not None else None
        except Exception:
            tare_weight = None

    packing_mode = str(cfg.get("packing_mode") or "maximum_utilization")

    if (cfg.get("container_source") or "manual") == "catalogue":
        if not selected_material:
            messages.append("Please select a packaging item from the catalogue table.")
            return None, messages

        try:
            container = {
                "L": float(selected_material.part_length),
                "W": float(selected_material.part_width),
                "H": float(selected_material.part_height),
                "max_weight": max_weight,
                "tare_weight": tare_weight,
                "type": str(selected_material.packaging_type or "TRANSPORT_UNIT"),
                "packing_mode": packing_mode,
            }
        except Exception:
            messages.append("Selected packaging item has invalid dimensions.")
            return None, messages
    else:
        try:
            container = {
                "L": float(cfg.get("container_l")),
                "W": float(cfg.get("container_w")),
                "H": float(cfg.get("container_h")),
                "max_weight": max_weight,
                "tare_weight": tare_weight,
                "type": "MANUAL",
                "packing_mode": packing_mode,
            }
        except Exception:
            messages.append("Please enter all manual container dimensions.")
            return None, messages

    for label, value in [
        ("length", container["L"]),
        ("width", container["W"]),
        ("height", container["H"]),
    ]:
        if value <= 0:
            messages.append(f"Container {label} must be greater than 0.")

    return container, messages



MAX_AUTO_QTY_FOR_RENDER = 5000


def _allowed_orientation_count(product):
    try:
        from ...utils.container_tool.engine import allowed_orientations
        return allowed_orientations(
            (product["length"], product["width"], product["height"]),
            product.get("r1"),
            product.get("r2"),
            product.get("r3"),
        )
    except Exception:
        return []


def _theoretical_auto_qty_upper(container, product):
    """
    Practical upper bound used for binary search.
    The final quantity is still confirmed with the real packing heuristic.
    """
    item_volume = float(product["length"] * product["width"] * product["height"])
    container_volume = float(container["L"] * container["W"] * container["H"])
    if item_volume <= 0 or container_volume <= 0:
        return 0

    volume_upper = int(container_volume // item_volume)
    weight_upper = volume_upper
    try:
        max_weight = container.get("max_weight")
        item_weight = float(product.get("weight", 0) or 0)
        if max_weight is not None and float(max_weight) > 0 and item_weight > 0:
            weight_upper = int(float(max_weight) // item_weight)
    except Exception:
        weight_upper = volume_upper

    grid_upper = 0
    for l, w, h in _allowed_orientation_count(product):
        if l <= 0 or w <= 0 or h <= 0:
            continue
        vertical_layers = int(container["H"] // h)
        if not bool(product.get("stackable", True)):
            vertical_layers = min(vertical_layers, 1)
        grid_upper = max(
            grid_upper,
            int(container["L"] // l) * int(container["W"] // w) * vertical_layers,
        )

    candidates = [value for value in (volume_upper, weight_upper) if value is not None and value > 0]
    if grid_upper > 0:
        # Use a little headroom above uniform-grid capacity in case mixed rotations help.
        candidates.append(max(grid_upper * 2, grid_upper + 25))

    upper = min(candidates) if candidates else 0
    return max(0, int(upper))


def _pack_count_by_marker(container, products):
    pack_result = pack_container(container, products)
    counts = {}
    for placement in pack_result.get("placements", []):
        counts[placement.product_name] = counts.get(placement.product_name, 0) + 1
    return counts


def _can_pack_requested_quantities(container, products, required_counts):
    counts = _pack_count_by_marker(container, products)
    for marker, qty in required_counts.items():
        if counts.get(marker, 0) < int(qty or 0):
            return False
    return True


def _with_internal_markers(products):
    marked = []
    marker_by_row = {}
    for row_index, product in enumerate(products):
        marker = f"__transport_row_{row_index}__"
        marker_by_row[row_index] = marker
        clone = dict(product)
        clone["_display_name"] = product.get("name") or f"Row {row_index + 1}"
        clone["name"] = marker
        clone["_row_index"] = row_index
        marked.append(clone)
    return marked, marker_by_row


def _resolve_auto_max_quantities(container, products):
    """
    Replace rows marked max_qty=True with the maximum quantity that the current
    transport heuristic can load, while respecting manually entered rows.

    Multiple max rows are resolved in row order. Earlier resolved rows become
    fixed inputs for later max rows.
    """
    messages = []
    resolved = [dict(p) for p in products]

    auto_indices = [i for i, product in enumerate(resolved) if product.get("max_qty")]
    if not auto_indices:
        return resolved, messages

    for row_index in auto_indices:
        candidate = resolved[row_index]
        upper = _theoretical_auto_qty_upper(container, candidate)

        if upper <= 0:
            candidate["qty"] = 0
            messages.append(f"Row {row_index + 1}: this load unit cannot fit in the selected transport unit.")
            continue

        capped = False
        if upper > MAX_AUTO_QTY_FOR_RENDER:
            upper = MAX_AUTO_QTY_FOR_RENDER
            capped = True

        marked, marker_by_row = _with_internal_markers(resolved)
        required_counts = {
            marker_by_row[i]: int(p.get("qty", 0) or 0)
            for i, p in enumerate(marked)
            if i != row_index and int(p.get("qty", 0) or 0) > 0
        }
        candidate_marker = marker_by_row[row_index]

        low = 0
        high = upper
        best = 0

        while low <= high:
            mid = (low + high) // 2
            trial = []
            for i, product in enumerate(marked):
                clone = dict(product)
                clone["qty"] = mid if i == row_index else int(clone.get("qty", 0) or 0)
                trial.append(clone)

            required = dict(required_counts)
            required[candidate_marker] = mid

            if _can_pack_requested_quantities(container, trial, required):
                best = mid
                low = mid + 1
            else:
                high = mid - 1

        candidate["qty"] = max(best, 0)
        if best <= 0:
            messages.append(f"Row {row_index + 1}: no additional units fit after respecting the other rows.")
        else:
            if capped and best >= upper:
                messages.append(
                    f"Row {row_index + 1}: automatic max quantity was capped at {MAX_AUTO_QTY_FOR_RENDER:,} units to keep the render responsive."
                )

    # Restore user-facing names and keep the max flag for display/session.
    for product in resolved:
        product["qty"] = int(product.get("qty", 0) or 0)

    return resolved, messages


def _rows_from_products(products):
    return [
        {
            "name": product.get("name", ""),
            "length": product.get("length", ""),
            "width": product.get("width", ""),
            "height": product.get("height", ""),
            "qty": product.get("qty", 1),
            "max_qty": bool(product.get("max_qty", False)),
            "stackable": bool(product.get("stackable", True)),
            "weight": product.get("weight", 0),
            "sequence": product.get("sequence", 1),
            "r1": bool(product.get("r1", False)),
            "r2": bool(product.get("r2", False)),
            "r3": bool(product.get("r3", False)),
        }
        for product in products
    ]

def run_transport_analysis(container, products, media_root=None):
    result = run_container_tool(
        container=container,
        products=products,
        media_root=media_root or settings.MEDIA_ROOT,
    )
    image_rel_paths = result.get("image_rel_paths") or {}
    image_urls = {key: settings.MEDIA_URL + rel_path for key, rel_path in image_rel_paths.items() if rel_path}
    threejs_scene = serialize_transport_threejs_scene(
        container,
        result.get("placements") or [],
        result.get("summary") or {},
    )
    return {
        "result": result,
        "serialized_result": serialize_transport_result(result, threejs_scene=threejs_scene),
        "threejs_scene": threejs_scene,
        "image_url": settings.MEDIA_URL + result["image_rel_path"],
        "image_urls": image_urls,
    }


def _prepare_transport_analysis(cfg, raw_rows, selected_material=None):
    """Validate and normalize authoritative transport calculation inputs."""
    safe_rows = sanitize_transport_rows_for_session(raw_rows or default_product_rows())
    if str(cfg.get("packing_mode") or "") == "space_evenly":
        safe_rows = [{**row, "sequence": 1} for row in safe_rows]
    products, row_errors = validate_transport_rows(safe_rows)
    container, container_errors = build_container_from_config(cfg, selected_material)

    messages = list(row_errors) + list(container_errors)
    if messages:
        return {
            "ok": False,
            "messages": messages,
            "safe_rows": safe_rows,
            "products": products,
            "container": container,
        }

    products, auto_messages = _resolve_auto_max_quantities(container, products)
    safe_rows = sanitize_transport_rows_for_session(_rows_from_products(products))
    if any(int(product.get("qty", 0) or 0) <= 0 for product in products):
        return {
            "ok": False,
            "messages": auto_messages or ["No load units could be placed with the selected settings."],
            "safe_rows": safe_rows,
            "products": products,
            "container": container,
        }

    return {
        "ok": True,
        "messages": auto_messages,
        "safe_rows": safe_rows,
        "products": products,
        "container": container,
    }


def analyze_transport_capacity(cfg, raw_rows, selected_material=None):
    """Run transport packing without generating PNGs or Three.js presentation."""
    prepared = _prepare_transport_analysis(cfg, raw_rows, selected_material)
    if not prepared["ok"]:
        return {**prepared, "result": None, "summary": None}

    container = prepared["container"]
    products = prepared["products"]
    pack_result = pack_container(container, products)
    summary = summarize(container, products, pack_result)
    return {
        **prepared,
        "result": {
            "summary": summary,
            "placements": pack_result.get("placements") or [],
            "unplaced": pack_result.get("unplaced") or [],
            "packing_mode": pack_result.get("packing_mode", "maximum_utilization"),
            "strategy": pack_result.get("strategy", ""),
            **{
                key: value
                for key, value in pack_result.items()
                if key.startswith("space_evenly_")
                or key.startswith("front_to_back_")
                or key.startswith("floor_first_")
            },
        },
        "summary": summary,
    }


def analyze_transport_config(cfg, raw_rows, selected_material=None, media_root=None):
    prepared = _prepare_transport_analysis(cfg, raw_rows, selected_material)
    if not prepared["ok"]:
        return {
            "ok": False,
            "messages": prepared["messages"],
            "safe_rows": prepared["safe_rows"],
            "products": prepared["products"],
            "container": prepared["container"],
            "result": None,
            "serialized_result": None,
            "threejs_scene": None,
            "image_url": None,
            "image_urls": None,
        }

    analysis = run_transport_analysis(
        container=prepared["container"],
        products=prepared["products"],
        media_root=media_root,
    )

    serialized_result = analysis["serialized_result"]
    summary_rows = (serialized_result.get("summary") or {}).get("product_rows") or []
    for row, product in zip(summary_rows, prepared["products"]):
        row["max_qty"] = bool(product.get("max_qty", False))

    return {
        "ok": True,
        "messages": prepared["messages"],
        "safe_rows": prepared["safe_rows"],
        "products": prepared["products"],
        "container": prepared["container"],
        "result": analysis["result"],
        "serialized_result": serialized_result,
        "threejs_scene": analysis["threejs_scene"],
        "image_url": analysis["image_url"],
        "image_urls": analysis.get("image_urls") or {},
    }
