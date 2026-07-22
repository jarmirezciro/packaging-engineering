"""Canonical regular-grid arrangements shared by package Design Mode tools."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Tuple

from packagingapp.utils.box_selection.box_selection_tool_arrays_2_origin_coordinates import (
    allowed_product_orientations,
)
from packagingapp.utils.quantity_decomposition import (
    generate_factor_arrangements,
    next_smooth_quantity,
)


DIMENSION_PRECISION = 6
ORIENTATION_LABELS = [
    "L × W × H",
    "L × H × W",
    "W × L × H",
    "W × H × L",
    "H × W × L",
    "H × L × W",
]
HORIZONTAL_ORIENTATION_SWAP = {0: 2, 2: 0, 1: 5, 5: 1, 3: 4, 4: 3}


def _dimension(value: float) -> float:
    return round(float(value), DIMENSION_PRECISION)


def _arrangement_id(payload: Dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    return f"design-arrangement-{digest}"


def _product_cuboid(x: float, y: float, z: float, dx: float, dy: float, dz: float) -> Dict[str, Any]:
    return {
        "kind": "product",
        "x": _dimension(x),
        "y": _dimension(y),
        "z": _dimension(z),
        "dx": _dimension(dx),
        "dy": _dimension(dy),
        "dz": _dimension(dz),
        "color": "#f59e0b",
        "opacity": 1.0,
    }


def build_canonical_design_arrangements(
    product: Tuple[float, float, float],
    desired_quantity: int,
    r1: int,
    r2: int,
    r3: int,
) -> Dict[str, Any]:
    """Generate the approved normalized 3D arrangement set.

    Horizontal axes are normalized so bundle length is never shorter than
    bundle width. Height/layer direction remains physically distinct. Exact
    duplicate bundle bounds are represented by the earliest authoritative
    orientation, then the smallest normalized arrangement tuple.
    """
    product = tuple(float(value) for value in product)
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
            "generated_candidate_count": 0,
            "arrangements": [],
        }

    canonical_arrangements: Dict[Tuple[float, float, float], Dict[str, Any]] = {}
    generated_candidate_count = 0
    for rows, columns, layers in generate_factor_arrangements(design_quantity, 3):
        for orientation in orientations:
            generated_candidate_count += 1
            unit_l, unit_w, unit_h = (float(value) for value in orientation["dimensions"])
            bundle_l = float(rows) * unit_l
            bundle_w = float(columns) * unit_w
            bundle_h = float(layers) * unit_h
            normalized_rows = int(rows)
            normalized_columns = int(columns)
            normalized_orientation_index = int(orientation["index"])

            if bundle_l < bundle_w:
                bundle_l, bundle_w = bundle_w, bundle_l
                unit_l, unit_w = unit_w, unit_l
                normalized_rows, normalized_columns = normalized_columns, normalized_rows
                normalized_orientation_index = HORIZONTAL_ORIENTATION_SWAP[normalized_orientation_index]

            products = []
            for row in range(normalized_rows):
                for column in range(normalized_columns):
                    for layer in range(int(layers)):
                        products.append(_product_cuboid(
                            row * unit_l,
                            column * unit_w,
                            layer * unit_h,
                            unit_l,
                            unit_w,
                            unit_h,
                        ))

            canonical_key = (_dimension(bundle_l), _dimension(bundle_w), _dimension(bundle_h))
            representative_key = (
                normalized_orientation_index,
                normalized_rows,
                normalized_columns,
                int(layers),
                generated_candidate_count,
            )
            volume = bundle_l * bundle_w * bundle_h
            cubicity = min(bundle_l, bundle_w, bundle_h) / max(bundle_l, bundle_w, bundle_h)
            arrangement = {
                "desired_quantity": desired,
                "design_quantity": design_quantity,
                "additional_capacity": additional_capacity,
                "arrangement": f"{normalized_rows} × {normalized_columns} × {int(layers)}",
                "product_orientation": ORIENTATION_LABELS[normalized_orientation_index],
                "orientation_index": normalized_orientation_index,
                "rows": normalized_rows,
                "columns": normalized_columns,
                "layers": int(layers),
                "unit_length": _dimension(unit_l),
                "unit_width": _dimension(unit_w),
                "unit_height": _dimension(unit_h),
                "bundle_length": _dimension(bundle_l),
                "bundle_width": _dimension(bundle_w),
                "bundle_height": _dimension(bundle_h),
                "bundle_volume": round(volume, 2),
                "bundle_cubicity_score": round(cubicity, DIMENSION_PRECISION),
                "products": products,
                "canonical_arrangement_key": canonical_key,
                "representative_key": representative_key,
            }
            retained = canonical_arrangements.get(canonical_key)
            if retained is None or representative_key < retained["representative_key"]:
                canonical_arrangements[canonical_key] = arrangement

    arrangements = list(canonical_arrangements.values())
    arrangements.sort(key=lambda item: (
        -item["bundle_cubicity_score"],
        item["additional_capacity"],
        item["bundle_volume"],
        item["canonical_arrangement_key"],
        item["representative_key"],
    ))
    for arrangement in arrangements:
        arrangement["arrangement_id"] = _arrangement_id({
            "design_quantity": design_quantity,
            "bundle_dimensions": arrangement["canonical_arrangement_key"],
            "arrangement": (
                arrangement["rows"],
                arrangement["columns"],
                arrangement["layers"],
            ),
            "orientation_index": arrangement["orientation_index"],
        })
    return {
        "desired_quantity": desired,
        "design_quantity": design_quantity,
        "additional_capacity": additional_capacity,
        "generated_candidate_count": generated_candidate_count,
        "arrangements": arrangements,
    }
