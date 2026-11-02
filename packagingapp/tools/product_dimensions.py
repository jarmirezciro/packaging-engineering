"""Shared product-dimension allowance helpers.

Product catalogue dimensions and manual product dimensions remain nominal
physical values.  The allowance is a user-input transformation applied once
per product, immediately before a packing engine is called.
"""

import math

from ..units import convert_length


PRODUCT_ALLOWANCE_KEYS = (
    "product_allowance_l",
    "product_allowance_w",
    "product_allowance_h",
)


def normalize_product_allowances(values, unit="mm"):
    """Return non-negative product allowances in canonical millimetres.

    Blank or missing values are deliberately treated as zero for backwards
    compatibility with saved sessions and older callers that do not know
    about this optional input.
    """
    normalized = []
    for value in values:
        if value in (None, "", "None"):
            normalized.append(0.0)
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("Product dimensional allowances must be numeric.") from exc
        if not math.isfinite(numeric) or numeric < 0:
            raise ValueError(
                "Product dimensional allowances must be finite and non-negative."
            )
        normalized.append(float(convert_length(numeric, unit or "mm", "mm")))
    return tuple(normalized)


def apply_product_allowances(nominal_dimensions, allowances):
    """Return effective dimensions without mutating the nominal tuple."""
    if nominal_dimensions is None:
        return None
    return tuple(
        float(nominal) + float(allowance)
        for nominal, allowance in zip(nominal_dimensions, allowances)
    )
