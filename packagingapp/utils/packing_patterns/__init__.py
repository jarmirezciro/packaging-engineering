"""Tool-independent rectangular mosaic pattern generation.

Container Selection and Palletization share one constructive geometry core and
select explicit policies for their established numerical and search contracts.
"""

from .core import (
    CONTAINER_SEARCH_POLICY,
    PALLETIZATION_SEARCH_POLICY,
    PatternSearchPolicy,
)
from .geometry import Placement2D
from .patterns import (
    PATTERN_FAMILIES,
    PatternCandidate,
    enumerate_pattern_candidates,
    pattern_block,
    pattern_brick_best,
    pattern_center_filled_pinwheel,
    pattern_hybrid_pinwheel,
    pattern_nested_pinwheel,
    pattern_pinwheel,
    pattern_row,
    pattern_splitrow,
)
from .validation import ValidationResult, layout_signature, validate_placements

__all__ = [
    "PATTERN_FAMILIES",
    "CONTAINER_SEARCH_POLICY",
    "PALLETIZATION_SEARCH_POLICY",
    "PatternCandidate",
    "PatternSearchPolicy",
    "Placement2D",
    "ValidationResult",
    "enumerate_pattern_candidates",
    "layout_signature",
    "pattern_block",
    "pattern_brick_best",
    "pattern_center_filled_pinwheel",
    "pattern_hybrid_pinwheel",
    "pattern_nested_pinwheel",
    "pattern_pinwheel",
    "pattern_row",
    "pattern_splitrow",
    "validate_placements",
]
