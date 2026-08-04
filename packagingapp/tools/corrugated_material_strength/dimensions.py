from dataclasses import dataclass
from decimal import Decimal


EXTERNAL_DIMENSION_METHOD = "CALIPER_TWO_SIDES_ESTIMATE"
EXTERNAL_DIMENSION_WARNING = (
    "Estimated external dimensions use internal dimensions plus twice the selected "
    "finished-board caliper. Supplier manufacturing allowances may differ."
)
MISSING_CALIPER_WARNING = (
    "Enter actual finished-board caliper or select a reference grade containing a target caliper."
)


def _decimal(value):
    return Decimal(str(value))


@dataclass(frozen=True)
class BoxDimensionInput:
    internal_length_mm: Decimal
    internal_width_mm: Decimal
    internal_height_mm: Decimal
    caliper_mm: Decimal | None
    caliper_source_type: str | None
    caliper_source_label: str | None
    caliper_is_reference: bool = False


@dataclass(frozen=True)
class BoxDimensionResult:
    internal_length_mm: Decimal
    internal_width_mm: Decimal
    internal_height_mm: Decimal
    external_length_mm: Decimal | None
    external_width_mm: Decimal | None
    external_height_mm: Decimal | None
    caliper_used_mm: Decimal | None
    caliper_source_type: str | None
    caliper_source_label: str | None
    caliper_is_reference: bool
    external_dimension_method: str
    external_dimensions_available: bool
    external_dimensions_are_estimated: bool
    warning: str | None


def calculate_external_dimensions(inputs: BoxDimensionInput) -> BoxDimensionResult:
    internal = (
        _decimal(inputs.internal_length_mm),
        _decimal(inputs.internal_width_mm),
        _decimal(inputs.internal_height_mm),
    )
    if any(value <= 0 for value in internal):
        raise ValueError("Internal box dimensions must be greater than zero.")
    caliper = None if inputs.caliper_mm is None else _decimal(inputs.caliper_mm)
    if caliper is not None and caliper <= 0:
        raise ValueError("Finished-board caliper must be greater than zero.")

    if caliper is None:
        return BoxDimensionResult(
            *internal,
            external_length_mm=None,
            external_width_mm=None,
            external_height_mm=None,
            caliper_used_mm=None,
            caliper_source_type=None,
            caliper_source_label=None,
            caliper_is_reference=False,
            external_dimension_method="UNAVAILABLE",
            external_dimensions_available=False,
            external_dimensions_are_estimated=False,
            warning=MISSING_CALIPER_WARNING,
        )

    return BoxDimensionResult(
        *internal,
        external_length_mm=internal[0] + Decimal("2") * caliper,
        external_width_mm=internal[1] + Decimal("2") * caliper,
        external_height_mm=internal[2] + Decimal("2") * caliper,
        caliper_used_mm=caliper,
        caliper_source_type=inputs.caliper_source_type,
        caliper_source_label=inputs.caliper_source_label,
        caliper_is_reference=bool(inputs.caliper_is_reference),
        external_dimension_method=EXTERNAL_DIMENSION_METHOD,
        external_dimensions_available=True,
        external_dimensions_are_estimated=True,
        warning=EXTERNAL_DIMENSION_WARNING,
    )
