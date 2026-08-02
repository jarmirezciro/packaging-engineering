"""Shared pallet-height rules for every palletization surface."""

DEFAULT_PALLET_HEIGHT_MM = 150.0


def resolve_pallet_height(value, *, fallback_on_invalid=False):
    """Return a positive pallet height, using the shared default when absent.

    Catalogue records can contain incomplete legacy dimensions, so callers may
    opt into treating a non-numeric or non-positive catalogue height as absent.
    Explicit manual values remain validated input and therefore raise
    ``ValueError`` when invalid.
    """
    if value in (None, "", "None"):
        return DEFAULT_PALLET_HEIGHT_MM

    try:
        height = float(value)
    except (TypeError, ValueError):
        if fallback_on_invalid:
            return DEFAULT_PALLET_HEIGHT_MM
        raise ValueError("Pallet height must be a number.")

    if height <= 0:
        if fallback_on_invalid:
            return DEFAULT_PALLET_HEIGHT_MM
        raise ValueError("Pallet height must be greater than 0.")

    return height


def pallet_render_components(pallet_height_mm):
    """Keep the existing pallet proportions while matching its total height."""
    height = float(pallet_height_mm)
    deck_thickness = height / 6.0
    return deck_thickness, height - deck_thickness
