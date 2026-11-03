"""Tool-independent rectangular mosaic pattern generation.

Stage 1 intentionally leaves the Palletization runtime on its established
implementation.  Container Selection consumes this package directly; a later
Stage 2 can move Palletization to the same API after benchmark approval.
"""

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
    "PatternCandidate",
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
