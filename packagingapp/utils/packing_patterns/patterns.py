"""Public shared mosaic API and bounded cross-family enumeration.

All reusable family construction delegates to :mod:`core`.  Container
Selection keeps its Stage 1 numerical/search policy by default; Palletization
passes the wider compatibility policy through its stable wrappers.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Sequence, Tuple

from . import core as _core
from .core import (
    CONTAINER_SEARCH_POLICY,
    PALLETIZATION_SEARCH_POLICY,
    PatternSearchPolicy,
)
from .geometry import (
    Placement2D,
    PlacementBudgetExceeded,
    best_grid,
    count_fitting_units,
)
from .validation import layout_signature, validate_placements


MAX_PINWHEEL_PARAMETER = CONTAINER_SEARCH_POLICY.max_pinwheel_parameter
MAX_PINWHEEL_CANDIDATES = CONTAINER_SEARCH_POLICY.max_pinwheel_candidates
MAX_REGIONAL_CUTS_PER_AXIS = 16
DEFAULT_CANDIDATE_BUDGET = 96

PATTERN_FAMILIES = (
    "block",
    "row",
    "splitrow",
    "brick",
    "pinwheel",
    "hybrid_pinwheel",
    "nested_pinwheel",
    "centre_filled_pinwheel",
    "regional_mosaic",
)


@dataclass(frozen=True)
class PatternCandidate:
    family: str
    variant: str
    placements: Tuple[Placement2D, ...]

    @property
    def quantity(self) -> int:
        return len(self.placements)


def pattern_block(
    area_l,
    area_w,
    box_l,
    box_w,
    *,
    policy: PatternSearchPolicy = CONTAINER_SEARCH_POLICY,
):
    return _core.pattern_block(
        area_l, area_w, box_l, box_w, policy=policy
    )


def pattern_row(
    area_l,
    area_w,
    box_l,
    box_w,
    *,
    policy: PatternSearchPolicy = CONTAINER_SEARCH_POLICY,
):
    return _core.pattern_row(
        area_l, area_w, box_l, box_w, policy=policy
    )


def pattern_splitrow(
    area_l,
    area_w,
    box_l,
    box_w,
    swapped=False,
    *,
    policy: PatternSearchPolicy = CONTAINER_SEARCH_POLICY,
):
    return _core.pattern_splitrow(
        area_l, area_w, box_l, box_w, swapped=swapped, policy=policy
    )


def pattern_brick_best(
    area_l,
    area_w,
    box_l,
    box_w,
    *,
    policy: PatternSearchPolicy = CONTAINER_SEARCH_POLICY,
):
    return _core.pattern_brick_best(
        area_l, area_w, box_l, box_w, policy=policy
    )


def pattern_pinwheel(
    area_l,
    area_w,
    box_l,
    box_w,
    rotated=False,
    *,
    policy: PatternSearchPolicy = CONTAINER_SEARCH_POLICY,
):
    return _core.pattern_pinwheel(
        area_l, area_w, box_l, box_w, rotated=rotated, policy=policy
    )


def pattern_hybrid_pinwheel(
    area_l,
    area_w,
    box_l,
    box_w,
    rotated=False,
    *,
    policy: PatternSearchPolicy = CONTAINER_SEARCH_POLICY,
):
    return _core.pattern_hybrid_pinwheel(
        area_l, area_w, box_l, box_w, rotated=rotated, policy=policy
    )


def pattern_nested_pinwheel(
    area_l,
    area_w,
    box_l,
    box_w,
    rotated=False,
    *,
    policy: PatternSearchPolicy = CONTAINER_SEARCH_POLICY,
):
    return _core.pattern_nested_pinwheel(
        area_l, area_w, box_l, box_w, rotated=rotated, policy=policy
    )


def pattern_center_filled_pinwheel(
    area_l,
    area_w,
    box_l,
    box_w,
    *,
    policy: PatternSearchPolicy = CONTAINER_SEARCH_POLICY,
):
    return _core.pattern_center_filled_pinwheel(
        area_l, area_w, box_l, box_w, policy=policy
    )


def _valid(
    placements: Sequence[Placement2D],
    area_l: float,
    area_w: float,
    box_l: float,
    box_w: float,
) -> bool:
    return bool(placements) and validate_placements(
        placements,
        area_l,
        area_w,
        expected_footprint=(box_l, box_w),
    ).valid


def _regional_candidates(area_l, area_w, box_l, box_w):
    """Bounded two-region mosaics with cuts derived from carton multiples."""
    candidates = []
    x_cuts = sorted(
        {
            value
            for step in (box_l, box_w)
            for index in range(
                1,
                min(
                    count_fitting_units(area_l, step),
                    MAX_REGIONAL_CUTS_PER_AXIS,
                )
                + 1,
            )
            if (value := index * step) < area_l
        }
    )[:MAX_REGIONAL_CUTS_PER_AXIS]
    y_cuts = sorted(
        {
            value
            for step in (box_l, box_w)
            for index in range(
                1,
                min(
                    count_fitting_units(area_w, step),
                    MAX_REGIONAL_CUTS_PER_AXIS,
                )
                + 1,
            )
            if (value := index * step) < area_w
        }
    )[:MAX_REGIONAL_CUTS_PER_AXIS]
    for cut in x_cuts:
        layer = best_grid(cut, area_w, box_l, box_w)
        layer += best_grid(area_l - cut, area_w, box_l, box_w, cut, 0.0)
        if _valid(layer, area_l, area_w, box_l, box_w):
            candidates.append(("length", cut, layer))
    for cut in y_cuts:
        layer = best_grid(area_l, cut, box_l, box_w)
        layer += best_grid(area_l, area_w - cut, box_l, box_w, 0.0, cut)
        if _valid(layer, area_l, area_w, box_l, box_w):
            candidates.append(("width", cut, layer))
    return candidates


@lru_cache(maxsize=256)
def enumerate_pattern_candidates(
    area_l: float,
    area_w: float,
    box_l: float,
    box_w: float,
    *,
    candidate_budget: int = DEFAULT_CANDIDATE_BUDGET,
    search_policy: PatternSearchPolicy = CONTAINER_SEARCH_POLICY,
) -> Tuple[PatternCandidate, ...]:
    """Enumerate valid, distinct candidates in stable family/variant order."""
    values = (float(area_l), float(area_w), float(box_l), float(box_w))
    if not all(value > 0 for value in values) or candidate_budget <= 0:
        return ()
    candidates = []
    seen = set()

    def add(family, variant, layer):
        if (
            len(candidates) >= candidate_budget
            or not _valid(layer, area_l, area_w, box_l, box_w)
        ):
            return
        signature = layout_signature(layer)
        if signature in seen:
            return
        seen.add(signature)
        candidates.append(PatternCandidate(family, variant, tuple(layer)))

    try:
        add("block", "best", pattern_block(*values, policy=search_policy))
        add("row", "best", pattern_row(*values, policy=search_policy))
        add(
            "splitrow",
            "primary",
            pattern_splitrow(*values, policy=search_policy),
        )
        add(
            "splitrow",
            "swapped",
            pattern_splitrow(*values, swapped=True, policy=search_policy),
        )
        add("brick", "best", pattern_brick_best(*values, policy=search_policy))
        add(
            "pinwheel",
            "primary",
            pattern_pinwheel(*values, policy=search_policy),
        )
        add(
            "pinwheel",
            "rotated",
            pattern_pinwheel(*values, rotated=True, policy=search_policy),
        )
        add(
            "hybrid_pinwheel",
            "primary",
            pattern_hybrid_pinwheel(*values, policy=search_policy),
        )
        add(
            "hybrid_pinwheel",
            "rotated",
            pattern_hybrid_pinwheel(
                *values, rotated=True, policy=search_policy
            ),
        )
        add(
            "nested_pinwheel",
            "primary",
            pattern_nested_pinwheel(*values, policy=search_policy),
        )
        add(
            "nested_pinwheel",
            "rotated",
            pattern_nested_pinwheel(
                *values, rotated=True, policy=search_policy
            ),
        )
        add(
            "centre_filled_pinwheel",
            "best",
            pattern_center_filled_pinwheel(*values, policy=search_policy),
        )
        for axis, cut, layer in _regional_candidates(*values):
            add("regional_mosaic", f"{axis}:{cut:.9g}", layer)
            if len(candidates) >= candidate_budget:
                break
    except PlacementBudgetExceeded:
        # Return only a fully valid bounded prefix; Container Selection will
        # retain its legacy solution if this prefix cannot improve it.
        pass
    return tuple(candidates)
