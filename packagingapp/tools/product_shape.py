"""Shared visualization-only product-shape contracts."""

from __future__ import annotations

from math import isclose


PRODUCT_SHAPE_CHOICES = (
    ("cuboid", "Rectangular / cuboid"),
    ("cylinder", "Cylinder"),
    ("bottle", "Bottle"),
    ("pillow_bag", "Pillow bag"),
)

ALLOWED_PRODUCT_SHAPES = frozenset(
    value for value, _label in PRODUCT_SHAPE_CHOICES
)

ORIENTATION_AXIS_ORDERS = (
    ("product_length", "product_width", "product_height"),
    ("product_length", "product_height", "product_width"),
    ("product_width", "product_length", "product_height"),
    ("product_width", "product_height", "product_length"),
    ("product_height", "product_width", "product_length"),
    ("product_height", "product_length", "product_width"),
)

AXIS_ORDER_TO_ORIENTATION_INDEX = {
    axis_order: index for index, axis_order in enumerate(ORIENTATION_AXIS_ORDERS)
}


def normalize_product_shape(value):
    normalized = str(value or "").strip().lower()
    return normalized if normalized in ALLOWED_PRODUCT_SHAPES else "cuboid"


def orientation_index_from_axis_order(axis_order):
    return AXIS_ORDER_TO_ORIENTATION_INDEX.get(tuple(axis_order), 0)


def _orientation_dimensions(product):
    length, width, height = (float(value) for value in product)
    return (
        (length, width, height),
        (length, height, width),
        (width, length, height),
        (width, height, length),
        (height, width, length),
        (height, length, width),
    )


def _dimensions_match(left, right, tolerance):
    try:
        return all(
            isclose(float(a), float(b), rel_tol=0.0, abs_tol=tolerance)
            for a, b in zip(left, right, strict=True)
        )
    except (TypeError, ValueError):
        return False


def orientation_index_from_dimensions(
    product,
    oriented_dimensions,
    allowed_orientations=None,
    tolerance=1e-6,
):
    """Return the authoritative orientation index for placed dimensions.

    Allowed orientation records are checked first so symmetrical products retain
    the same deterministic index chosen by the packing engine.
    """
    orientations = _orientation_dimensions(product)

    for allowed in allowed_orientations or ():
        if isinstance(allowed, dict):
            index = allowed.get("index")
            dimensions = allowed.get("dimensions")
        else:
            index = allowed if isinstance(allowed, int) else None
            dimensions = orientations[index] if index in range(6) else allowed

        try:
            normalized_index = int(index)
        except (TypeError, ValueError):
            normalized_index = None

        if (
            normalized_index in range(6)
            and dimensions is not None
            and _dimensions_match(dimensions, oriented_dimensions, tolerance)
        ):
            return normalized_index

    for index, dimensions in enumerate(orientations):
        if _dimensions_match(dimensions, oriented_dimensions, tolerance):
            return index

    return 0


def decorate_product_scene(scene, *, product_shape, product):
    """Attach JSON-safe visualization metadata to an existing product scene."""
    if not scene or not product:
        return scene

    scene["productShape"] = normalize_product_shape(product_shape)
    scene["productDefinition"] = {
        "length": round(float(product[0]), 6),
        "width": round(float(product[1]), 6),
        "height": round(float(product[2]), 6),
    }
    return scene
