"""Translate original product permissions into the selected bag's axes."""

from collections.abc import Mapping
from math import isclose, isfinite

from ...utils.box_selection.box_selection_tool_arrays_2_origin_coordinates import allowed_product_orientations
from .state import BAG_ROTATION_KEYS


BAG_ROTATION_MAPPING_SOURCE = "bag_design_orientation_mapping"
AXES = ("length", "width", "height")

# Distinct axis tokens expose the authoritative permutations without using or
# comparing product dimensions. Equal real dimensions do not erase provenance.
_ORIENTATION_AXES = {
    row["index"]: tuple(int(axis) - 1 for axis in row["dimensions"])
    for row in allowed_product_orientations((1, 2, 3), True, True, True)
}


def rotation_tuple(rotations):
    if isinstance(rotations, Mapping):
        rotations = tuple(rotations.get(key) for key in BAG_ROTATION_KEYS)
    if (not isinstance(rotations, (tuple, list)) or len(rotations) != 3
            or any(type(value) not in (bool, int) or value not in (0, 1) for value in rotations)):
        return None
    return tuple(bool(value) for value in rotations)


def derive_bag_load_unit_rotations(original_rotations, orientation_index):
    original = rotation_tuple(original_rotations)
    axes = _ORIENTATION_AXES.get(orientation_index) if type(orientation_index) is int else None
    if axes is None or not original or not any(original):
        return None
    return tuple(original[axis] for axis in axes)


def bag_design_rotation_metadata(candidate, payload, original_rotations):
    original = rotation_tuple(original_rotations)
    index = candidate.get("orientation_index")
    if type(index) is not int or index not in _ORIENTATION_AXES:
        index = None
    mapped = derive_bag_load_unit_rotations(original, index)
    return {
        "orientation_index": index,
        "original_product_rotations": dict(zip(BAG_ROTATION_KEYS, original)) if original else None,
        "load_unit_rotation_defaults": (
            {**dict(zip(BAG_ROTATION_KEYS, mapped)), "source": BAG_ROTATION_MAPPING_SOURCE}
            if mapped and _outer_dimensions_preserve_axes(candidate, payload) else None
        ),
    }


def _outer_dimensions_preserve_axes(candidate, payload):
    if payload.get("outer_dimension_source") != "tight_fit_film_estimate" or not candidate.get("film_two_wall"):
        return False
    caliper = candidate.get("film_caliper_mm")
    if not isinstance(caliper, (int, float)) or not isfinite(caliper) or caliper <= 0:
        return False
    for axis in AXES:
        bundle, external, inherited = (payload.get(key) for key in (f"bundle_{axis}_mm", f"external_{axis}_mm", axis))
        if not all(isinstance(span, (int, float)) and isfinite(span) and span > 0 for span in (bundle, external, inherited)):
            return False
        if external != inherited or not isclose(external, bundle + 2 * caliper, rel_tol=0, abs_tol=1e-9):
            return False
    return True
