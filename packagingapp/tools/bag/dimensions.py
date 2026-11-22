"""The selected packed bundle's outer dimensions for downstream logistics."""

from math import isfinite


def resolve_bag_outer_dimensions(flat, bundle, film, *, legacy=None):
    caliper = film.get("film_caliper_mm")
    tight_fit = (
        caliper is not None and film.get("film_two_wall")
        and all(value is not None and isfinite(value) and value > 0 for value in bundle)
    )
    if tight_fit:
        outer = tuple(float(value) + 2 * caliper for value in bundle)
        if not all(isfinite(value) for value in outer):
            raise ValueError("Calculated bag outer dimensions are outside the supported numeric range.")
        source = "tight_fit_film_estimate"
        label = "Estimated outer dimensions — tight-fit film assumption"
    else:
        outer = legacy if legacy is not None else bundle
        source = "legacy_bag_dimensions"
        label = "Legacy bag dimensions (fallback)"
    return {
        "flat_bag_length_mm": flat[0],
        "flat_bag_width_mm": flat[1],
        **{f"bundle_{axis}_mm": value for axis, value in zip(("length", "width", "height"), bundle)},
        **{f"external_{axis}_mm": value for axis, value in zip(("length", "width", "height"), outer)},
        **dict(zip(("length", "width", "height"), outer)),
        "outer_dimension_source": source,
        "outer_dimension_source_display": label,
    }
