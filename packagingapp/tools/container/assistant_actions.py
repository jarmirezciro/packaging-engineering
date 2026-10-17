"""Container-specific validation for reviewed Assistant input proposals."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import math
from typing import Any

from ...assistant.actions import (
    NoEffectiveProposalChanges,
    PROPOSAL_NOT_APPLIED_NOTICE,
    PROPOSAL_PREVIEW_SCHEMA_VERSION,
    PROPOSAL_PREVIEW_TYPE,
    ProposalCandidateValidationError,
    ProviderProposalCandidate,
    validate_proposal_state_fingerprint,
)
from ...assistant.contracts import ToolContext, canonical_json
from .serializers import sanitize_container_config_for_session
from .service import build_container_form, inspect_container_readiness


_FIELD_SPECS = {
    "product.dimensions.length": {
        "config_key": "product_l",
        "kind": "number",
        "unit": "mm",
        "units": {"mm": Decimal("1"), "cm": Decimal("10"), "m": Decimal("1000")},
        "input_path": ("product", "dimensions", "length"),
    },
    "product.dimensions.width": {
        "config_key": "product_w",
        "kind": "number",
        "unit": "mm",
        "units": {"mm": Decimal("1"), "cm": Decimal("10"), "m": Decimal("1000")},
        "input_path": ("product", "dimensions", "width"),
    },
    "product.dimensions.height": {
        "config_key": "product_h",
        "kind": "number",
        "unit": "mm",
        "units": {"mm": Decimal("1"), "cm": Decimal("10"), "m": Decimal("1000")},
        "input_path": ("product", "dimensions", "height"),
    },
    "product.weight": {
        "config_key": "product_weight",
        "kind": "number",
        "unit": "g",
        "units": {"g": Decimal("1"), "kg": Decimal("1000")},
        "input_path": ("product", "weight"),
    },
    "request.desired_quantity": {
        "config_key": "desired_qty",
        "kind": "integer",
        "unit": "pcs",
        "units": {"pcs": Decimal("1")},
        "input_path": ("request", "desired_quantity"),
    },
    "product.allowed_vertical_axes": {
        "config_key": None,
        "kind": "axes",
        "unit": None,
        "units": {"none": None},
        "input_path": ("product", "allowed_vertical_axes"),
    },
    "container.internal_dimensions.length": {
        "config_key": "box_l",
        "kind": "number",
        "unit": "mm",
        "units": {"mm": Decimal("1"), "cm": Decimal("10"), "m": Decimal("1000")},
        "input_path": ("container", "internal_dimensions", "length"),
    },
    "container.internal_dimensions.width": {
        "config_key": "box_w",
        "kind": "number",
        "unit": "mm",
        "units": {"mm": Decimal("1"), "cm": Decimal("10"), "m": Decimal("1000")},
        "input_path": ("container", "internal_dimensions", "width"),
    },
    "container.internal_dimensions.height": {
        "config_key": "box_h",
        "kind": "number",
        "unit": "mm",
        "units": {"mm": Decimal("1"), "cm": Decimal("10"), "m": Decimal("1000")},
        "input_path": ("container", "internal_dimensions", "height"),
    },
    "container.thickness": {
        "config_key": "box_thickness_mm",
        "kind": "number",
        "unit": "mm",
        "units": {"mm": Decimal("1"), "cm": Decimal("10"), "m": Decimal("1000")},
        "input_path": ("container", "thickness"),
    },
    "container.tare_weight": {
        "config_key": "box_weight",
        "kind": "number",
        "unit": "g",
        "units": {"g": Decimal("1"), "kg": Decimal("1000")},
        "input_path": ("container", "tare_weight"),
    },
    "container.max_payload": {
        "config_key": "box_max_payload",
        "kind": "number",
        "unit": "g",
        "units": {"g": Decimal("1"), "kg": Decimal("1000")},
        "input_path": ("container", "max_payload"),
    },
}

CONTAINER_PROPOSAL_FIELDS = tuple(_FIELD_SPECS)
_AXES = ("length", "width", "height")


@dataclass(frozen=True)
class ContainerProposalReview:
    """Application-owned result of validating a proposal against copied state."""

    preview: dict[str, Any]
    proposed_config: dict[str, Any]
    normalized_changes: list[dict[str, Any]]
    applied_fields: list[dict[str, Any]]


def _nested_value(source: dict[str, Any], path: tuple[str, ...]):
    value: Any = source
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _before_value(tool_context: ToolContext, spec: dict[str, Any]):
    current = _nested_value(tool_context["inputs"], spec["input_path"])
    if spec["kind"] == "axes":
        return {"value": list(current or []), "unit": None}
    if isinstance(current, dict):
        return {"value": current.get("value"), "unit": spec["unit"]}
    return {"value": None, "unit": spec["unit"]}


def _normalize_value(change, spec):
    unit = change["unit"]
    if unit not in spec["units"]:
        return None, "unsupported_unit", (
            f"Use one of these units: {', '.join(spec['units'])}."
        )

    value = change["value"]
    if spec["kind"] == "axes":
        if not isinstance(value, list) or any(axis not in _AXES for axis in value):
            return None, "invalid", (
                "Allowed vertical axes must use length, width, or height."
            )
        normalized = [axis for axis in _AXES if axis in value]
        return normalized, "valid", None

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        expected = "a whole number" if spec["kind"] == "integer" else "a number"
        return None, "invalid", f"This input must be {expected}."
    try:
        normalized_decimal = Decimal(str(value)) * spec["units"][unit]
    except (InvalidOperation, ValueError, TypeError):
        return None, "invalid", "This input must be a finite number."
    normalized = float(normalized_decimal)
    if not math.isfinite(normalized):
        return None, "invalid", "This input must be a finite number."
    if spec["kind"] == "integer":
        if not normalized.is_integer():
            return None, "invalid", "Desired quantity must be a whole number."
        return int(normalized), "valid", None
    return normalized, "valid", None


def _source_message(field: str, tool_context: ToolContext) -> str:
    workflow = tool_context.get("workflow") or {}
    if field.startswith("product.") and workflow.get("input_origin") == "inherited":
        return (
            "This product input is inherited from the upstream Packaging Flow "
            "step and cannot be directly edited here."
        )
    product_source = tool_context["inputs"]["product"].get("source")
    if field.startswith("product.") and product_source == "catalogue":
        return (
            "This product input comes from the selected catalogue product and "
            "cannot be directly edited while the catalogue source is active."
        )
    container_source = tool_context["inputs"]["container"].get("source")
    if field.startswith("container.") and container_source == "catalogue":
        return (
            "This container input comes from the selected catalogue item and "
            "cannot be directly edited while the catalogue source is active."
        )
    if field == "request.desired_quantity":
        return (
            "Desired quantity comes from the selected catalogue product in the "
            "current Optimal mode and cannot be directly edited."
        )
    return "This input is not editable in the current tool state."


def _same_value(before, after) -> bool:
    if isinstance(before, list) or isinstance(after, list):
        return before == after
    if before is None or after is None:
        return before is after
    try:
        return math.isclose(float(before), float(after), rel_tol=0.0, abs_tol=1e-9)
    except (TypeError, ValueError):
        return before == after


def _config_number(value):
    if isinstance(value, int):
        return str(value)
    return format(float(value), ".15g")


def _merge_value(config, spec, value):
    if spec["kind"] == "axes":
        allowed = set(value)
        config["r1"] = "length" in allowed
        config["r2"] = "width" in allowed
        config["r3"] = "height" in allowed
        return
    config[spec["config_key"]] = _config_number(value)


def _build_proposed_form(
    config,
    *,
    current_form,
    selected_product,
    selected_material,
):
    request_stub = type(
        "AssistantContainerProposalRequest",
        (),
        {"method": "POST", "POST": dict(config)},
    )()
    form = build_container_form(
        request=request_stub,
        config=config,
        selected_product=selected_product,
        selected_material=selected_material,
    )
    for field_name in ("catalogue_id", "product_catalogue_id"):
        form.fields[field_name].choices = list(current_form.fields[field_name].choices)
    form.is_valid()
    return form


def _first_form_error(form, field_name):
    errors = form.errors.get(field_name)
    if not errors:
        return None
    return str(errors[0])


def build_container_proposal_review(
    candidate: ProviderProposalCandidate,
    *,
    tool_context: ToolContext,
    current_config: dict[str, Any],
    current_form,
    selected_product=None,
    selected_material=None,
) -> ContainerProposalReview:
    """Validate a proposal against copied state without running an engine."""
    candidate = validate_proposal_state_fingerprint(
        candidate, tool_context=tool_context
    )
    definitions = tool_context["input_definitions"]
    allowed = set(tool_context["allowed_proposals"])
    proposed_config = deepcopy(current_config)
    rows = []

    for change in candidate["changes"]:
        field = change["field"]
        spec = _FIELD_SPECS.get(field)
        definition = definitions.get(field) or {}
        if spec is None:
            # Keep future Tool Context additions fail-closed until this adapter
            # has an explicitly reviewed mapping for them.
            raise ProposalCandidateValidationError(
                "Container proposal field has no authoritative mapping."
            )

        before = _before_value(tool_context, spec)
        normalized, status, message = _normalize_value(change, spec)
        editable = bool(definition.get("editable")) and field in allowed
        if not editable:
            status = "not_editable"
            message = _source_message(field, tool_context)

        after = {"value": normalized, "unit": spec["unit"]}
        if status == "valid" and _same_value(before["value"], normalized):
            status = "no_change"
            message = "This input already has the requested value."
        elif status == "valid":
            _merge_value(proposed_config, spec, normalized)

        rows.append(
            {
                "field": field,
                "label": str(definition.get("label") or field),
                "before": before,
                "after": after,
                "status": status,
                "message": message,
                "config_key": spec["config_key"],
            }
        )

    effective_rows = [row for row in rows if row["status"] != "no_change"]
    if not effective_rows:
        raise NoEffectiveProposalChanges()

    normalized_config = sanitize_container_config_for_session(proposed_config)
    proposed_form = _build_proposed_form(
        normalized_config,
        current_form=current_form,
        selected_product=selected_product,
        selected_material=selected_material,
    )
    readiness = inspect_container_readiness(
        proposed_form,
        normalized_config,
        selected_product=selected_product,
        selected_material=selected_material,
    )

    for row in effective_rows:
        if row["status"] != "valid":
            continue
        if row["config_key"]:
            form_error = _first_form_error(proposed_form, row["config_key"])
            if form_error:
                row["status"] = "invalid"
                row["message"] = form_error
                continue
        matching_issue = next(
            (
                issue
                for issue in readiness["issues"]
                if issue.get("field") == row["field"]
            ),
            None,
        )
        if matching_issue:
            row["status"] = "invalid"
            row["message"] = str(matching_issue.get("message") or "Invalid input.")

    has_invalid_change = any(row["status"] != "valid" for row in effective_rows)
    if has_invalid_change or proposed_form.errors:
        validation_status = "invalid"
        resulting_status = "invalid"
    elif readiness["issues"]:
        validation_status = "incomplete"
        resulting_status = "incomplete"
    else:
        validation_status = "valid"
        resulting_status = "ready"

    public_rows = []
    for row in effective_rows:
        public_rows.append(
            {
                key: row[key]
                for key in (
                    "field",
                    "label",
                    "before",
                    "after",
                    "status",
                    "message",
                )
            }
        )

    can_apply = resulting_status != "invalid"
    normalized_changes = []
    applied_fields = []
    if can_apply:
        for row in effective_rows:
            spec = _FIELD_SPECS[row["field"]]
            value = row["after"]["value"]
            normalized_changes.append(
                {
                    "field": row["field"],
                    "value": deepcopy(value),
                    "unit": spec["unit"] or "none",
                }
            )
            if spec["kind"] == "axes":
                enabled = set(value)
                for axis, field_key in zip(_AXES, ("r1", "r2", "r3")):
                    applied_fields.append(
                        {
                            "field": row["field"],
                            "field_key": field_key,
                            "value": axis in enabled,
                            "unit": None,
                        }
                    )
            else:
                applied_fields.append(
                    {
                        "field": row["field"],
                        "field_key": spec["config_key"],
                        "value": value,
                        "unit": spec["unit"],
                    }
                )

    preview = {
        "schema_version": PROPOSAL_PREVIEW_SCHEMA_VERSION,
        "type": PROPOSAL_PREVIEW_TYPE,
        "summary": "Review the proposed input changes below.",
        "state_fingerprint": tool_context["tool"]["state_fingerprint"],
        "valid": resulting_status != "invalid",
        "can_apply": can_apply,
        "changes": public_rows,
        "resulting_state": {
            "validation": validation_status,
            "calculation_status": resulting_status,
        },
        "notice": PROPOSAL_NOT_APPLIED_NOTICE,
    }
    canonical_json(preview)
    return ContainerProposalReview(
        preview=preview,
        proposed_config=normalized_config,
        normalized_changes=normalized_changes,
        applied_fields=applied_fields,
    )


def build_container_proposal_preview(
    candidate: ProviderProposalCandidate,
    *,
    tool_context: ToolContext,
    current_config: dict[str, Any],
    current_form,
    selected_product=None,
    selected_material=None,
) -> dict[str, Any]:
    """Compatibility wrapper returning the application-owned preview only."""
    return build_container_proposal_review(
        candidate,
        tool_context=tool_context,
        current_config=current_config,
        current_form=current_form,
        selected_product=selected_product,
        selected_material=selected_material,
    ).preview


__all__ = [
    "CONTAINER_PROPOSAL_FIELDS",
    "ContainerProposalReview",
    "build_container_proposal_preview",
    "build_container_proposal_review",
]
