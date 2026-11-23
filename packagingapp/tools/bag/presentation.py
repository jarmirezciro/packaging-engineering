from math import isfinite, prod

from ...utils.package_design_arrangements import DIMENSION_PRECISION


AXES = ("length", "width", "height")


def _flat_dimensions(row):
    bag = (row.get("render_data") or {}).get("bag") or {}
    return (
        row.get("flat_bag_length_mm", bag.get("flatLength")),
        row.get("flat_bag_width_mm", bag.get("flatWidth")),
    )


def _positive_dimensions(values):
    return all(isinstance(value, (int, float)) and isfinite(value) and value > 0 for value in values)


def _bundle_and_opening(row):
    scene = row.get("render_data") or {}
    bag = scene.get("bag") or {}
    film = bag.get("film") or {}
    depth_axis = film.get("depthAxis") or (bag.get("insertion") or {}).get("axis")
    products = scene.get("products") or []
    counts = tuple(row.get(key) for key in ("rows", "columns", "layers"))
    quantity = row.get("design_quantity")
    if (scene.get("mode") != "design" or scene.get("packageType") != "bag"
            or scene.get("units") != "mm" or depth_axis not in AXES
            or not all(type(count) is int and count > 0 for count in counts)
            or not products or prod(counts) != quantity or len(products) != quantity):
        return None, None

    # The canonical arrangement generator supplies a uniform grid. The first
    # product's extents and the counts identify the unit and its original grid axis.
    units = tuple(products[0].get(key) for key in ("dx", "dy", "dz"))
    spans = tuple(film.get("bundleDimensions") or (row.get(f"bundle_{axis}") for axis in AXES))
    flat = _flat_dimensions(row)
    if len(spans) != 3 or not _positive_dimensions((*units, *spans, *flat)):
        return None, None
    tolerance = 10 ** -DIMENSION_PRECISION
    if any(abs(unit * count - span) > (count + 1) * tolerance for unit, count, span in zip(units, counts, spans)):
        return None, None

    grid = tuple(zip(units, counts, spans))
    depth = AXES.index(depth_axis)
    # The film opens at positive depth and folds across the short opening span.
    # Preserve the renderer's long/short axis order, including equal-span ties.
    opening = sorted((axis for axis in range(3) if axis != depth), key=lambda axis: -spans[axis])
    construction = (
        bag.get("openingSide"), bag.get("openingAt"), bag.get("sealingAllowance"), bag.get("fitTolerance"),
        row.get("film_material_family"), row.get("film_caliper_mm"), row.get("film_grammage_g_m2"), row.get("film_two_wall"),
    )
    key = (quantity, flat, tuple(grid[axis] for axis in (depth, *opening)), construction)
    return key, depth_axis


def _terminal_order(row):
    length, width = _flat_dimensions(row)
    area = length * width if _positive_dimensions((length, width)) else row.get("bag_area")
    return (area if area is not None else float("inf"), -(row.get("bundle_cubicity_score") or 0))


def select_bag_design_display_candidates(candidates, *, has_downstream, selected_candidate_id=None):
    """Build terminal presentation rows without changing the engineering candidates."""
    if has_downstream:
        return candidates

    groups = {}
    for index, row in enumerate(candidates):
        key, depth_axis = _bundle_and_opening(row)
        if key is None:
            key = index  # Missing geometry cannot establish equivalence.
        priority = (row["candidate_id"] == selected_candidate_id, depth_axis == "height")
        group = groups.get(key)
        if group is None or priority > group[0]:
            groups[key] = (priority, row)

    ordered = sorted((row for _, row in groups.values()), key=_terminal_order)
    return [{**row, "display_rank": rank} for rank, row in enumerate(ordered, start=1)]
