import math

from django.conf import settings

from .state import default_product_rows
from .modes import (
    DEFAULT_TRANSPORT_PACKING_MODE,
    normalize_transport_packing_mode,
    transport_sequence_is_locked,
)
from .serializers import (
    sanitize_transport_rows_for_session,
    serialize_transport_result,
    serialize_transport_threejs_scene,
)
from .presenter import attach_transport_result_presentation
from ...units import (
    LENGTH_UNITS,
    MASS_UNITS,
    UnsupportedUnitError,
    convert_length,
    convert_mass,
)
from ...units.input import convert_optional, validate_unit
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
    physical_sources = post_data.getlist("item_physical_source[]")
    canonical_lengths = post_data.getlist("item_canonical_length[]")
    canonical_widths = post_data.getlist("item_canonical_width[]")
    canonical_heights = post_data.getlist("item_canonical_height[]")
    canonical_weights = post_data.getlist("item_canonical_weight[]")

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
        len(physical_sources),
        len(canonical_lengths),
        len(canonical_widths),
        len(canonical_heights),
        len(canonical_weights),
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
                "physical_source": (
                    physical_sources[i].strip()
                    if i < len(physical_sources)
                    else "manual"
                ) or "manual",
                "canonical_length": (
                    canonical_lengths[i].strip()
                    if i < len(canonical_lengths)
                    else ""
                ),
                "canonical_width": (
                    canonical_widths[i].strip()
                    if i < len(canonical_widths)
                    else ""
                ),
                "canonical_height": (
                    canonical_heights[i].strip()
                    if i < len(canonical_heights)
                    else ""
                ),
                "canonical_weight": (
                    canonical_weights[i].strip()
                    if i < len(canonical_weights)
                    else ""
                ),
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
                "physical_source": raw.get("physical_source", "manual"),
                "canonical_length": raw.get("canonical_length", ""),
                "canonical_width": raw.get("canonical_width", ""),
                "canonical_height": raw.get("canonical_height", ""),
                "canonical_weight": raw.get("canonical_weight", ""),
                "canonicalized": bool(raw.get("canonicalized", False)),
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


_TRANSPORT_UNIT_FIELDS = (
    ("load_unit_dimension_unit", LENGTH_UNITS, "mm", "load-unit dimension"),
    ("load_unit_mass_unit", MASS_UNITS, "kg", "load-unit mass"),
    ("transport_dimension_unit", LENGTH_UNITS, "mm", "transport-unit dimension"),
    ("transport_mass_unit", MASS_UNITS, "kg", "transport-unit mass"),
)


def validate_transport_unit_state(cfg):
    """Validate explicit unit metadata while retaining legacy metric defaults."""
    state = {}
    messages = []
    for key, definitions, default, label in _TRANSPORT_UNIT_FIELDS:
        try:
            state[key] = validate_unit(
                (cfg or {}).get(key), definitions, default, label
            )
        except UnsupportedUnitError as exc:
            state[key] = None
            messages.append(str(exc))
    return state, messages


def _canonical_row_quantity(row, key, unit, converter, canonical_unit):
    if row.get("canonicalized") and row.get(key) not in (None, "", "None"):
        return float(row[key])
    source = row.get("physical_source")
    canonical_key = f"canonical_{key}"
    if source in {"catalogue", "inherited"} and row.get(canonical_key) not in (
        None,
        "",
        "None",
    ):
        return float(row[canonical_key])
    return convert_optional(row.get(key), unit, converter, canonical_unit)


def normalize_transport_rows_for_calculation(raw_rows, unit_state):
    """Convert editable row values to engine mm/kg before row validation.

    Catalogue and inherited rows may carry exact canonical scalars.  Those
    values remain authoritative while the visible inputs change units.
    """
    safe_rows = sanitize_transport_rows_for_session(raw_rows or [])
    messages = []
    if not safe_rows:
        return safe_rows, messages

    dimension_unit = unit_state.get("load_unit_dimension_unit")
    mass_unit = unit_state.get("load_unit_mass_unit")
    if dimension_unit is None or mass_unit is None:
        return safe_rows, messages

    normalized = []
    for index, row in enumerate(safe_rows):
        converted = dict(row)
        try:
            converted["length"] = _canonical_row_quantity(
                row, "length", dimension_unit, convert_length, "mm"
            )
            converted["width"] = _canonical_row_quantity(
                row, "width", dimension_unit, convert_length, "mm"
            )
            converted["height"] = _canonical_row_quantity(
                row, "height", dimension_unit, convert_length, "mm"
            )
            converted["weight"] = _canonical_row_quantity(
                row, "weight", mass_unit, convert_mass, "kg"
            )
            converted["canonicalized"] = True
        except (TypeError, ValueError, UnsupportedUnitError):
            messages.append(f"Row {index + 1}: invalid numeric values.")
        normalized.append(converted)
    return sanitize_transport_rows_for_session(normalized), messages


def transport_rows_for_display(rows, dimension_unit="mm", mass_unit="kg"):
    """Adapt canonical session rows to one coherent editable display context."""
    try:
        display_dimension_unit = validate_unit(
            dimension_unit, LENGTH_UNITS, "mm", "load-unit dimension"
        )
    except UnsupportedUnitError:
        display_dimension_unit = "mm"
    try:
        display_mass_unit = validate_unit(
            mass_unit, MASS_UNITS, "kg", "load-unit mass"
        )
    except UnsupportedUnitError:
        display_mass_unit = "kg"

    display_rows = []
    for row in sanitize_transport_rows_for_session(rows or []):
        display = dict(row)
        if row.get("canonicalized"):
            for key in ("length", "width", "height"):
                if row.get(key) not in (None, "", "None"):
                    display[key] = float(
                        convert_length(
                            float(row[key]), "mm", display_dimension_unit
                        )
                    )
            if row.get("weight") not in (None, "", "None"):
                display["weight"] = float(
                    convert_mass(float(row["weight"]), "kg", display_mass_unit)
                )
        display["canonicalized"] = False
        display_rows.append(display)
    return sanitize_transport_rows_for_session(display_rows)


def build_container_from_config(cfg, selected_material=None, unit_state=None):
    messages = []

    if unit_state is None:
        unit_state, unit_messages = validate_transport_unit_state(cfg)
        messages.extend(unit_messages)
    if messages:
        return None, messages

    source = (cfg.get("container_source") or "manual")
    dimension_unit = unit_state["transport_dimension_unit"]
    mass_unit = unit_state["transport_mass_unit"]

    max_weight = _parse_optional_non_negative(
        cfg.get("max_weight"), "max payload", messages
    )
    tare_weight = _parse_optional_non_negative(
        cfg.get("tare_weight"), "tare weight", messages
    )
    if source == "manual":
        try:
            max_weight = convert_optional(
                max_weight, mass_unit, convert_mass, "kg"
            )
            tare_weight = convert_optional(
                tare_weight, mass_unit, convert_mass, "kg"
            )
        except (TypeError, ValueError, UnsupportedUnitError):
            messages.append("Please enter valid manual transport-unit mass values.")

    if source == "catalogue" and selected_material is not None:
        try:
            tare_weight = (
                float(selected_material.part_weight)
                if selected_material.part_weight is not None
                else tare_weight
            )
        except Exception:
            pass
    elif tare_weight is None and selected_material is not None:
        try:
            tare_weight = float(selected_material.part_weight) if selected_material.part_weight is not None else None
        except Exception:
            tare_weight = None

    packing_mode = normalize_transport_packing_mode(
        cfg.get("packing_mode"),
        default=DEFAULT_TRANSPORT_PACKING_MODE,
    )

    if source == "catalogue":
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
                "L": float(convert_length(float(cfg.get("container_l")), dimension_unit, "mm")),
                "W": float(convert_length(float(cfg.get("container_w")), dimension_unit, "mm")),
                "H": float(convert_length(float(cfg.get("container_h")), dimension_unit, "mm")),
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


def _safe_floor_ratio(numerator, denominator):
    """Floor a positive float ratio without losing an exact integer to noise."""
    numerator = float(numerator)
    denominator = float(denominator)
    if numerator <= 0 or denominator <= 0:
        return 0
    return max(0, int(math.floor((numerator / denominator) + 1e-9)))


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
    Return a physical upper bound for one product row.

    Volume and payload are necessary conditions only. The final
    quantity is confirmed with the real packing heuristic.
    """
    item_volume = float(product["length"] * product["width"] * product["height"])
    container_volume = float(container["L"] * container["W"] * container["H"])
    if item_volume <= 0 or container_volume <= 0:
        return 0

    orientations = [
        (l, w, h)
        for l, w, h in _allowed_orientation_count(product)
        if l > 0
        and w > 0
        and h > 0
        and l <= float(container["L"])
        and w <= float(container["W"])
        and h <= float(container["H"])
    ]
    if not orientations:
        return 0

    geometry_upper = _safe_floor_ratio(container_volume, item_volume)

    weight_upper = geometry_upper
    try:
        max_weight = container.get("max_weight")
        item_weight = float(product.get("weight", 0) or 0)
        if max_weight is not None and float(max_weight) > 0 and item_weight > 0:
            weight_upper = _safe_floor_ratio(max_weight, item_weight)
    except Exception:
        weight_upper = geometry_upper

    return max(0, min(geometry_upper, weight_upper))


def _remaining_auto_qty_upper(container, products, row_index, upper):
    """Tighten an upper bound by reserving fixed-row volume and payload."""
    candidate = products[row_index]
    item_volume = float(
        candidate["length"] * candidate["width"] * candidate["height"]
    )
    fixed_volume = sum(
        float(product["length"] * product["width"] * product["height"])
        * int(product.get("qty", 0) or 0)
        for index, product in enumerate(products)
        if index != row_index
    )
    remaining_volume = max(
        0.0,
        float(container["L"] * container["W"] * container["H"]) - fixed_volume,
    )
    if item_volume > 0:
        upper = min(upper, _safe_floor_ratio(remaining_volume, item_volume))

    other_requested_rows = [
        product
        for index, product in enumerate(products)
        if index != row_index and int(product.get("qty", 0) or 0) > 0
    ]
    if not bool(candidate.get("stackable", True)) and not other_requested_rows:
        fitting_orientations = [
            (l, w, h)
            for l, w, h in _allowed_orientation_count(candidate)
            if l > 0
            and w > 0
            and h > 0
            and l <= float(container["L"])
            and w <= float(container["W"])
            and h <= float(container["H"])
        ]
        if fitting_orientations:
            minimum_floor_area = min(
                float(l * w) for l, w, _h in fitting_orientations
            )
            upper = min(
                upper,
                _safe_floor_ratio(
                    float(container["L"] * container["W"]), minimum_floor_area
                ),
            )

    try:
        max_weight = container.get("max_weight")
        item_weight = float(candidate.get("weight", 0) or 0)
        if max_weight is not None and float(max_weight) > 0 and item_weight > 0:
            fixed_weight = sum(
                float(product.get("weight", 0) or 0)
                * int(product.get("qty", 0) or 0)
                for index, product in enumerate(products)
                if index != row_index
            )
            remaining_payload = max(0.0, float(max_weight) - fixed_weight)
            upper = min(upper, _safe_floor_ratio(remaining_payload, item_weight))
    except Exception:
        pass

    return max(0, int(upper))


def _pack_count_by_marker(
    container,
    products,
    *,
    max_lane_transitions=None,
):
    kwargs = {}
    if max_lane_transitions is not None:
        kwargs["max_lane_transitions"] = max_lane_transitions
    pack_result = pack_container(container, products, **kwargs)
    counts = {}
    for placement in pack_result.get("placements", []):
        counts[placement.product_name] = counts.get(placement.product_name, 0) + 1
    return counts


def _can_pack_requested_quantities(
    container,
    products,
    required_counts,
    *,
    max_lane_transitions=None,
):
    counts = _pack_count_by_marker(
        container,
        products,
        max_lane_transitions=max_lane_transitions,
    )
    for marker, qty in required_counts.items():
        if counts.get(marker, 0) < int(qty or 0):
            return False
    return True


def _mono_transition_feasible_lower_bound(container, products, row_index, upper):
    """Return a validated mono-plan count reusable by the descending search."""
    if any(
        index != row_index and int(product.get("qty", 0) or 0) > 0
        for index, product in enumerate(products)
    ):
        return 0
    def probe_quantity(quantity):
        probe = [dict(product) for product in products]
        probe[row_index]["qty"] = int(quantity)
        result = pack_container(container, probe)
        metadata = result.get("mono_lane_transition") or {}
        return metadata

    metadata = probe_quantity(upper)
    if not metadata.get("eligible"):
        return 0
    packed_quantity = int(metadata.get("packed_quantity", 0) or 0)
    placement_cap = int(metadata.get("placement_cap", 0) or 0)
    if packed_quantity <= 0 and 0 < placement_cap < int(upper):
        metadata = probe_quantity(placement_cap)
        packed_quantity = int(metadata.get("packed_quantity", 0) or 0)
    return max(0, min(packed_quantity, int(upper)))


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

        upper = _remaining_auto_qty_upper(container, resolved, row_index, upper)

        marked, marker_by_row = _with_internal_markers(resolved)
        required_counts = {
            marker_by_row[i]: int(p.get("qty", 0) or 0)
            for i, p in enumerate(marked)
            if i != row_index and int(p.get("qty", 0) or 0) > 0
        }
        candidate_marker = marker_by_row[row_index]

        best = 0
        mono_lower_bound = _mono_transition_feasible_lower_bound(
            container,
            marked,
            row_index,
            upper,
        )

        # Packing feasibility is not monotonic in the requested quantity. A
        # synchronized block can be incomplete at q and complete at q + 1, so
        # binary search can discard a larger feasible result. Search downward
        # from the bounded physical upper instead; the first fully packed trial
        # is the exact maximum produced by the current deterministic heuristic.
        search_floor = mono_lower_bound if mono_lower_bound > 0 else 0
        for quantity in range(upper, search_floor, -1):
            trial = []
            for i, product in enumerate(marked):
                clone = dict(product)
                clone["qty"] = (
                    quantity if i == row_index else int(clone.get("qty", 0) or 0)
                )
                trial.append(clone)

            required = dict(required_counts)
            required[candidate_marker] = quantity

            if mono_lower_bound > 0:
                feasible = _can_pack_requested_quantities(
                    container,
                    trial,
                    required,
                    max_lane_transitions=0,
                )
            else:
                feasible = _can_pack_requested_quantities(
                    container,
                    trial,
                    required,
                )
            if feasible:
                best = quantity
                break

        if best <= 0 and mono_lower_bound > 0:
            # The mono plan at the original upper request was fully validated
            # and materialized with this many units. Candidate feasibility is
            # prefix-closed because each support column is emitted bottom-up.
            best = mono_lower_bound

        candidate["qty"] = max(best, 0)
        if best <= 0:
            messages.append(f"Row {row_index + 1}: no additional units fit after respecting the other rows.")
        else:
            if capped and best >= MAX_AUTO_QTY_FOR_RENDER:
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
            "physical_source": product.get("physical_source", "manual"),
            "canonical_length": product.get("canonical_length", ""),
            "canonical_width": product.get("canonical_width", ""),
            "canonical_height": product.get("canonical_height", ""),
            "canonical_weight": product.get("canonical_weight", ""),
            "canonicalized": True,
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
    cfg = dict(cfg or {})
    cfg["packing_mode"] = normalize_transport_packing_mode(
        cfg.get("packing_mode"),
        default=DEFAULT_TRANSPORT_PACKING_MODE,
    )
    unit_state, unit_messages = validate_transport_unit_state(cfg)
    safe_rows, normalization_messages = normalize_transport_rows_for_calculation(
        raw_rows or default_product_rows(), unit_state
    )
    if transport_sequence_is_locked(cfg["packing_mode"]):
        safe_rows = [{**row, "sequence": 1} for row in safe_rows]
    products, row_errors = validate_transport_rows(safe_rows)
    container, container_errors = build_container_from_config(
        cfg, selected_material, unit_state=unit_state
    ) if not unit_messages else (None, [])

    messages = (
        list(unit_messages)
        + list(normalization_messages)
        + list(row_errors)
        + list(container_errors)
    )
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
            "packing_mode": pack_result.get(
                "packing_mode", DEFAULT_TRANSPORT_PACKING_MODE
            ),
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
    serialized_result = attach_transport_result_presentation(serialized_result, cfg)

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
