"""Shared internal/external carton dimension contract for Container Selection."""


DEFAULT_BOX_THICKNESS_MM = 4.0

EXTERNAL_DIMENSION_SOURCE_CATALOGUE = "catalogue_external_dimensions"
EXTERNAL_DIMENSION_SOURCE_PROVIDED_THICKNESS = "provided_thickness"
EXTERNAL_DIMENSION_SOURCE_CATALOGUE_THICKNESS = "catalogue_thickness"
EXTERNAL_DIMENSION_SOURCE_DEFAULT_THICKNESS = "default_thickness"


def _positive_number(value, *, field_name, required=False):
    if value in (None, "", "None"):
        if required:
            raise ValueError(f"{field_name} must be greater than zero.")
        return None
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a positive number.") from exc
    if number <= 0:
        raise ValueError(f"{field_name} must be greater than zero.")
    return number


def _clean_number(value):
    """Keep dimension payloads stable, compact, and JSON-safe."""
    return round(float(value), 6)


def resolve_external_carton_dimensions(
    internal_length,
    internal_width,
    internal_height,
    *,
    external_length=None,
    external_width=None,
    external_height=None,
    thickness_mm=None,
    thickness_source=EXTERNAL_DIMENSION_SOURCE_PROVIDED_THICKNESS,
):
    """Resolve one complete external L/W/H triplet for a carton.

    Explicit external dimensions are authoritative only when all three axes are
    valid. Otherwise the complete triplet is calculated from a known positive
    thickness, or from the centralized 4 mm default.
    """
    internal = tuple(
        _positive_number(value, field_name=f"Internal {axis}", required=True)
        for value, axis in zip(
            (internal_length, internal_width, internal_height),
            ("length", "width", "height"),
        )
    )

    external = []
    for value in (external_length, external_width, external_height):
        try:
            external.append(_positive_number(value, field_name="External dimension"))
        except ValueError:
            external.append(None)

    if all(value is not None for value in external):
        try:
            known_thickness = _positive_number(
                thickness_mm,
                field_name="Box thickness",
            )
        except ValueError:
            # Explicit catalogue external dimensions are authoritative and do
            # not depend on a separate thickness value.
            known_thickness = None
        resolved_external = tuple(external)
        source = EXTERNAL_DIMENSION_SOURCE_CATALOGUE
        assumed = False
        thickness_used = known_thickness
    else:
        known_thickness = _positive_number(
            thickness_mm,
            field_name="Box thickness",
        )
        assumed = known_thickness is None
        thickness_used = (
            DEFAULT_BOX_THICKNESS_MM if assumed else known_thickness
        )
        source = (
            EXTERNAL_DIMENSION_SOURCE_DEFAULT_THICKNESS
            if assumed
            else thickness_source
        )
        resolved_external = tuple(
            value + (2 * thickness_used) for value in internal
        )

    return {
        "internal_length": _clean_number(internal[0]),
        "internal_width": _clean_number(internal[1]),
        "internal_height": _clean_number(internal[2]),
        "external_length": _clean_number(resolved_external[0]),
        "external_width": _clean_number(resolved_external[1]),
        "external_height": _clean_number(resolved_external[2]),
        "box_thickness_mm": (
            _clean_number(thickness_used) if thickness_used is not None else None
        ),
        "box_thickness_assumed": bool(assumed),
        "external_dimension_source": source,
    }
