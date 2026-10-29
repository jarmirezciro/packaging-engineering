"""Privacy-safe Tool Context adapter for Container / Box Selection.

This module selects semantic fields from existing Container form and service
outputs.  It does not calculate capacity, placements, candidate ranking, or
external carton geometry.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any

from ...assistant.contracts import (
    MAX_ALTERNATIVES,
    MAX_VALIDATION_ERRORS,
    TOOL_CONTEXT_SCHEMA_VERSION,
    ToolContext,
    ToolContextValidationError,
    canonical_json,
    state_fingerprint,
    validate_tool_context,
)
from ...forms import ContainerSelectionMode1Form
from ...units import kg_to_g
from ...utils.box_selection.box_selection_tool_arrays_2_origin_coordinates import (
    allowed_product_orientations,
)
from ..selection_mode import normalize_selection_mode
from .serializers import sanitize_container_config_for_session
from .service import inspect_container_readiness
from .state import default_container_config


TOOL_ID = "container_selection"
CONTAINER_RESULT_SNAPSHOT_VERSION = "1.0"
MAX_CONTAINER_RESULT_SNAPSHOT_BYTES = 32 * 1024
STANDALONE_CONTAINER_RESULT_SESSION_KEY = "container_assistant_result_snapshot"

_RESULT_SNAPSHOT_KEYS = frozenset(
    {
        "snapshot_version",
        "context_schema_version",
        "tool",
        "mode",
        "state_fingerprint",
        "result",
        "alternatives",
    }
)
_FINGERPRINT_PATTERN = re.compile(r"sha256:[0-9a-f]{64}\Z")

_SURFACE_ALIASES = {
    "seo": "public",
    "public": "public",
    "standalone": "standalone",
    "workflow": "workflow",
}

_ATTEMPT_ACTIONS = frozenset(
    {
        "run_single",
        "find_top5",
        "select_candidate",
        "run_design",
        "select_design_candidate",
    }
)

_FORM_FIELD_PATHS = {
    "mode": "tool.mode",
    "product_source": "product.source",
    "product_l": "product.dimensions.length",
    "product_w": "product.dimensions.width",
    "product_h": "product.dimensions.height",
    "product_weight": "product.weight",
    "desired_qty": "request.desired_quantity",
    "product_shape": "product.shape",
    "r1": "product.allowed_vertical_axes",
    "r2": "product.allowed_vertical_axes",
    "r3": "product.allowed_vertical_axes",
    "container_source": "container.source",
    "box_l": "container.internal_dimensions.length",
    "box_w": "container.internal_dimensions.width",
    "box_h": "container.internal_dimensions.height",
    "box_thickness_mm": "container.thickness",
    "box_weight": "container.tare_weight",
    "box_max_payload": "container.max_payload",
    "__all__": "tool",
}


def _finite_number(value: Any) -> float | None:
    if value in (None, "", "None"):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _integer(value: Any) -> int | None:
    number = _finite_number(value)
    if number is None:
        return None
    return int(number)


def _normalized_form_data(config: dict[str, Any]) -> dict[str, Any]:
    data = dict(config)
    data["mode"] = normalize_selection_mode(config)
    return data


def _prepare_form(form, config):
    if form is not None and form.is_bound:
        form.is_valid()
        return form

    prepared = ContainerSelectionMode1Form(data=_normalized_form_data(config))
    if form is not None:
        for field_name in ("catalogue_id", "product_catalogue_id"):
            prepared.fields[field_name].choices = list(form.fields[field_name].choices)

    # A current catalogue selection is already visibility-scoped by the caller.
    # Add only its opaque current value to ChoiceField validation; it is never
    # copied to Tool Context or its fingerprint.
    for field_name in ("catalogue_id", "product_catalogue_id"):
        current = str(config.get(field_name) or "")
        choices = list(prepared.fields[field_name].choices)
        choice_values = {str(value) for value, _label in choices}
        if current and current not in choice_values:
            choices.append((current, "Current visible selection"))
            prepared.fields[field_name].choices = choices
    prepared.is_valid()
    return prepared


def _field_has_error(form, field_name: str) -> bool:
    return field_name in form.errors


def _measurement(value, unit, *, invalid=False, assumed=False):
    if invalid:
        return {"value": None, "unit": unit, "status": "invalid"}
    number = _finite_number(value)
    if number is None:
        return {"value": None, "unit": unit, "status": "missing"}
    return {
        "value": number,
        "unit": unit,
        "status": "assumed" if assumed else "valid",
    }


def _quantity(value, *, invalid=False):
    if invalid:
        return {"value": None, "unit": "pcs", "status": "invalid"}
    integer = _integer(value)
    if integer is None:
        return {"value": None, "unit": "pcs", "status": "missing"}
    return {"value": integer, "unit": "pcs", "status": "valid"}


def _dimension_group(length, width, height, *, statuses=None):
    statuses = statuses or {}
    return {
        "length": _measurement(length, "mm", invalid=statuses.get("length", False)),
        "width": _measurement(width, "mm", invalid=statuses.get("width", False)),
        "height": _measurement(height, "mm", invalid=statuses.get("height", False)),
    }


def _allowed_vertical_axes(product, r1, r2, r3):
    """Translate R1/R2/R3 through the authoritative orientation helper."""
    probe_product = product or (101.0, 103.0, 107.0)
    axes = []
    for axis, enabled, flags in (
        ("length", bool(r1), (1, 0, 0)),
        ("width", bool(r2), (0, 1, 0)),
        ("height", bool(r3), (0, 0, 1)),
    ):
        if enabled and allowed_product_orientations(probe_product, *flags):
            axes.append(axis)
    return axes


def _effective_product_values(form, selected_product, readiness):
    if readiness["product_source"] == "catalogue":
        if selected_product is None:
            return (None, None, None, None)
        return (
            _finite_number(getattr(selected_product, "product_length", None)),
            _finite_number(getattr(selected_product, "product_width", None)),
            _finite_number(getattr(selected_product, "product_height", None)),
            _finite_number(
                kg_to_g(selected_product.weight)
                if getattr(selected_product, "weight", None) is not None
                else None
            ),
        )
    return (
        _finite_number(form.cleaned_data.get("product_l")),
        _finite_number(form.cleaned_data.get("product_w")),
        _finite_number(form.cleaned_data.get("product_h")),
        _finite_number(form.cleaned_data.get("product_weight")),
    )


def _effective_container_values(form, selected_material, readiness):
    if readiness["container_source"] == "catalogue":
        if selected_material is None:
            return (None, None, None, None)
        return (
            _finite_number(getattr(selected_material, "part_length", None)),
            _finite_number(getattr(selected_material, "part_width", None)),
            _finite_number(getattr(selected_material, "part_height", None)),
            _finite_number(getattr(selected_material, "box_thickness_mm", None)),
        )
    return (
        _finite_number(form.cleaned_data.get("box_l")),
        _finite_number(form.cleaned_data.get("box_w")),
        _finite_number(form.cleaned_data.get("box_h")),
        _finite_number(form.cleaned_data.get("box_thickness_mm")),
    )


def _catalogue_scope(available_materials):
    if available_materials is None:
        return None
    candidate_digests = []
    for material in available_materials:
        semantic_candidate = {
            "internal_dimensions": [
                _finite_number(getattr(material, "part_length", None)),
                _finite_number(getattr(material, "part_width", None)),
                _finite_number(getattr(material, "part_height", None)),
            ],
            "external_dimensions": [
                _finite_number(getattr(material, "external_length", None)),
                _finite_number(getattr(material, "external_width", None)),
                _finite_number(getattr(material, "external_height", None)),
            ],
            "thickness": _finite_number(getattr(material, "box_thickness_mm", None)),
            "ranking_volume": _finite_number(getattr(material, "part_volume", None)),
        }
        candidate_digests.append(state_fingerprint(semantic_candidate))
    candidate_digests.sort()
    combined = "\n".join(candidate_digests).encode("ascii")
    return {
        "candidate_count": len(candidate_digests),
        "engineering_digest": f"sha256:{hashlib.sha256(combined).hexdigest()}",
    }


def _build_inputs(
    form,
    config,
    readiness,
    selected_product,
    selected_material,
    available_materials,
):
    product_l, product_w, product_h, product_weight = _effective_product_values(
        form, selected_product, readiness
    )
    product = readiness.get("product")
    axes = _allowed_vertical_axes(
        product,
        readiness.get("r1"),
        readiness.get("r2"),
        readiness.get("r3"),
    )
    product_inputs = {
        "source": readiness["product_source"],
        "dimensions": _dimension_group(
            product_l,
            product_w,
            product_h,
            statuses={
                "length": _field_has_error(form, "product_l"),
                "width": _field_has_error(form, "product_w"),
                "height": _field_has_error(form, "product_h"),
            },
        ),
        "weight": _measurement(
            product_weight,
            "g",
            invalid=_field_has_error(form, "product_weight"),
        ),
        "shape": form.cleaned_data.get("product_shape") or config.get("product_shape") or "cuboid",
        "allowed_vertical_axes": axes,
    }

    desired_quantity = readiness.get("desired_quantity")
    request_inputs = {
        "desired_quantity": _quantity(
            desired_quantity,
            invalid=_field_has_error(form, "desired_qty"),
        )
    }
    selected_design_candidate_id = str(
        form.cleaned_data.get("selected_design_candidate_id")
        or config.get("selected_design_candidate_id")
        or ""
    )
    if readiness["mode"] == "design" and selected_design_candidate_id:
        request_inputs["selected_design_candidate"] = selected_design_candidate_id

    container_inputs = {
        "source": "designed" if readiness["mode"] == "design" else readiness["container_source"]
    }
    box_l, box_w, box_h, thickness = _effective_container_values(
        form, selected_material, readiness
    )
    if readiness["mode"] != "design":
        container_inputs["internal_dimensions"] = _dimension_group(
            box_l,
            box_w,
            box_h,
            statuses={
                "length": _field_has_error(form, "box_l"),
                "width": _field_has_error(form, "box_w"),
                "height": _field_has_error(form, "box_h"),
            },
        )
    if readiness["container_source"] == "catalogue" and selected_material is not None:
        external_values = (
            _finite_number(getattr(selected_material, "external_length", None)),
            _finite_number(getattr(selected_material, "external_width", None)),
            _finite_number(getattr(selected_material, "external_height", None)),
        )
        if all(value is not None for value in external_values):
            container_inputs["external_dimensions"] = _dimension_group(*external_values)
    if readiness["mode"] == "optimal":
        catalogue_scope = _catalogue_scope(available_materials)
        if catalogue_scope is not None:
            container_inputs["catalogue_scope"] = catalogue_scope
    container_inputs["thickness"] = _measurement(
        thickness,
        "mm",
        invalid=_field_has_error(form, "box_thickness_mm"),
    )
    if readiness["container_source"] == "manual" and readiness["mode"] != "design":
        container_inputs["tare_weight"] = _measurement(
            form.cleaned_data.get("box_weight"),
            "g",
            invalid=_field_has_error(form, "box_weight"),
        )
        container_inputs["max_payload"] = _measurement(
            form.cleaned_data.get("box_max_payload"),
            "g",
            invalid=_field_has_error(form, "box_max_payload"),
        )

    return {
        "product": product_inputs,
        "request": request_inputs,
        "container": container_inputs,
    }


def _definition(form, field_name, label, value_type, *, editable, unit=None):
    definition = {
        "label": label,
        "type": value_type,
        "editable": bool(editable),
    }
    if unit:
        definition["canonical_unit"] = unit
    field = form.fields.get(field_name)
    minimum = _finite_number(getattr(field, "min_value", None)) if field else None
    if minimum is not None:
        if minimum > 0 and value_type == "number":
            definition["minimum_exclusive"] = 0.0
        else:
            definition["minimum_inclusive"] = minimum
    return definition


def _build_input_definitions(form, readiness, workflow):
    inherited_product = bool(workflow and workflow.get("input_origin") == "inherited")
    manual_product = readiness["product_source"] == "manual" and not inherited_product
    manual_container = readiness["container_source"] == "manual"
    mode = readiness["mode"]
    definitions = {
        "product.dimensions.length": _definition(
            form, "product_l", "Product length", "number", editable=manual_product, unit="mm"
        ),
        "product.dimensions.width": _definition(
            form, "product_w", "Product width", "number", editable=manual_product, unit="mm"
        ),
        "product.dimensions.height": _definition(
            form, "product_h", "Product height", "number", editable=manual_product, unit="mm"
        ),
        "product.weight": _definition(
            form, "product_weight", "Product weight", "number", editable=manual_product, unit="g"
        ),
        "product.allowed_vertical_axes": {
            "label": "Allowed vertical axes",
            "type": "string_list",
            "choices": ["length", "width", "height"],
            "editable": manual_product,
        },
        "request.desired_quantity": _definition(
            form,
            "desired_qty",
            "Desired quantity",
            "integer",
            editable=not (
                mode == "optimal" and readiness["product_source"] == "catalogue"
            ),
            unit="pcs",
        ),
    }
    if mode != "design":
        definitions.update(
            {
                "container.internal_dimensions.length": _definition(
                    form, "box_l", "Container internal length", "number", editable=manual_container, unit="mm"
                ),
                "container.internal_dimensions.width": _definition(
                    form, "box_w", "Container internal width", "number", editable=manual_container, unit="mm"
                ),
                "container.internal_dimensions.height": _definition(
                    form, "box_h", "Container internal height", "number", editable=manual_container, unit="mm"
                ),
            }
        )
    definitions["container.thickness"] = _definition(
        form,
        "box_thickness_mm",
        "Container wall thickness",
        "number",
        editable=(manual_container or mode == "design"),
        unit="mm",
    )
    if mode != "design" and manual_container:
        definitions["container.tare_weight"] = _definition(
            form, "box_weight", "Container tare weight", "number", editable=manual_container, unit="g"
        )
        definitions["container.max_payload"] = _definition(
            form, "box_max_payload", "Container maximum payload", "number", editable=manual_container, unit="g"
        )
    return definitions


def _normalize_form_errors(form):
    normalized = []
    for field_name, error_list in form.errors.as_data().items():
        semantic_field = _FORM_FIELD_PATHS.get(field_name, "tool")
        for error in error_list:
            messages = error.messages or [str(error)]
            for message in messages:
                normalized.append(
                    {
                        "field": semantic_field,
                        "code": error.code or "invalid",
                        "message": str(message),
                    }
                )
    return normalized


def _normalized_dimensions(source, prefix):
    values = (
        _finite_number(source.get(f"{prefix}_length")),
        _finite_number(source.get(f"{prefix}_width")),
        _finite_number(source.get(f"{prefix}_height")),
    )
    if any(value is None for value in values):
        return None
    return {
        "length": {"value": values[0], "unit": "mm"},
        "width": {"value": values[1], "unit": "mm"},
        "height": {"value": values[2], "unit": "mm"},
    }


def _selection_result(report, mode, container_source):
    if not isinstance(report, dict):
        return None
    max_quantity = _integer(report.get("max_quantity"))
    requested_quantity = _integer(report.get("requested_qty"))
    if max_quantity is None:
        return None
    result = {
        "kind": "optimal_selection" if mode == "optimal" else "selection",
        "max_quantity": {"value": max_quantity, "unit": "pcs"},
    }
    if requested_quantity is not None:
        result["requested_quantity"] = {"value": requested_quantity, "unit": "pcs"}
    remaining = _integer(report.get("remaining_capacity"))
    if remaining is not None:
        result["remaining_geometric_capacity"] = {"value": remaining, "unit": "pcs"}
    utilization_pct = _finite_number(report.get("volumetric_efficiency_current_pct"))
    if utilization_pct is not None:
        result["volume_utilization"] = {
            "value": utilization_pct / 100.0,
            "scale": "ratio",
        }
    internal_dimensions = _normalized_dimensions(report, "internal")
    external_dimensions = _normalized_dimensions(report, "external")
    if internal_dimensions:
        result["internal_dimensions"] = internal_dimensions
    if external_dimensions:
        result["external_dimensions"] = external_dimensions
    thickness = _finite_number(report.get("box_thickness_mm"))
    if thickness is not None:
        result["thickness"] = {
            "value": thickness,
            "unit": "mm",
            "status": "assumed" if report.get("box_thickness_assumed") else "provided",
            "source": report.get("external_dimension_source") or "service_output",
        }

    product_weight = _finite_number(report.get("product_weight"))
    net_weight = _finite_number(report.get("net_weight"))
    if product_weight is not None:
        result["product_weight"] = {"value": product_weight, "unit": "g"}
    if net_weight is not None:
        result["net_weight"] = {"value": net_weight, "unit": "g"}

    for source_key, output_key in (
        ("container_tare", "container_tare"),
        ("payload_capacity", "payload_capacity"),
        ("total_weight_current", "total_weight"),
    ):
        number = _finite_number(report.get(source_key))
        if number is not None:
            result[output_key] = {
                "value": number,
                "unit": "g",
                "status": "informational",
            }
    payload_usage = _finite_number(report.get("payload_usage_pct"))
    if payload_usage is not None:
        result["payload_usage"] = {
            "value": payload_usage / 100.0,
            "scale": "ratio",
            "status": "informational",
        }
    return result


def _design_candidate(candidate, *, selected):
    if not isinstance(candidate, dict):
        return None
    candidate_id = str(candidate.get("candidate_id") or "")
    if not candidate_id:
        return None
    row = {
        "rank": _integer(candidate.get("rank")),
        "candidate_id": candidate_id,
        "label": f"Candidate {_integer(candidate.get('rank')) or 1}",
        "desired_quantity": {"value": _integer(candidate.get("desired_quantity")), "unit": "pcs"},
        "design_quantity": {"value": _integer(candidate.get("design_quantity")), "unit": "pcs"},
        "additional_capacity": {"value": _integer(candidate.get("additional_capacity")), "unit": "pcs"},
        "arrangement": candidate.get("arrangement"),
        "orientation": candidate.get("product_orientation"),
        "rows": _integer(candidate.get("rows")),
        "columns": _integer(candidate.get("columns")),
        "layers": _integer(candidate.get("layers")),
        "internal_dimensions": {
            "length": {"value": _finite_number(candidate.get("container_length")), "unit": "mm"},
            "width": {"value": _finite_number(candidate.get("container_width")), "unit": "mm"},
            "height": {"value": _finite_number(candidate.get("container_height")), "unit": "mm"},
        },
        "cubicity": {"value": _finite_number(candidate.get("container_cubicity_score")), "scale": "ratio"},
        "volume": {"value": _finite_number(candidate.get("required_container_volume")), "unit": "mm^3"},
        "volumetric_efficiency": {"value": _finite_number(candidate.get("volumetric_efficiency")), "scale": "ratio"},
        "selected": bool(selected),
    }
    external = _normalized_dimensions(candidate, "external")
    if external:
        row["external_dimensions"] = external
    thickness = _finite_number(candidate.get("box_thickness_mm"))
    if thickness is not None:
        row["thickness"] = {
            "value": thickness,
            "unit": "mm",
            "status": "assumed" if candidate.get("box_thickness_assumed") else "provided",
            "source": candidate.get("external_dimension_source") or "service_output",
        }
    net_weight = _finite_number(candidate.get("net_content_weight"))
    if net_weight is not None:
        row["net_content_weight"] = {"value": net_weight, "unit": "g"}
    return row


def _top5_alternative(row, rank, selected_material, selected_container_id):
    if not isinstance(row, dict):
        return None
    material = row.get("material")
    selected = bool(material is not None and material is selected_material)
    if not selected and material is not None and selected_material is not None:
        material_pk = getattr(material, "pk", getattr(material, "id", None))
        selected_pk = getattr(
            selected_material, "pk", getattr(selected_material, "id", None)
        )
        selected = bool(
            material_pk is not None
            and selected_pk is not None
            and str(material_pk) == str(selected_pk)
        )
    if not selected and row.get("material_id") is not None:
        selected = str(row.get("material_id")) == str(selected_container_id or "")
    max_quantity = _integer(row.get("max_qty"))
    if max_quantity is None:
        return None
    return {
        "rank": rank,
        "label": f"Candidate {rank}",
        "geometric_capacity": {"value": max_quantity, "unit": "pcs"},
        "desired_quantity_volume_usage": {
            "value": _finite_number(row.get("usage")),
            "scale": "ratio",
        },
        "container_volume": {
            "value": _finite_number(row.get("container_vol")),
            "unit": "mm^3",
        },
        "selected": selected,
    }


def _bounded_candidates(candidates, selected_id):
    candidates = list(candidates or [])
    if len(candidates) <= MAX_ALTERNATIVES:
        return candidates, False
    bounded = candidates[:MAX_ALTERNATIVES]
    selected = next(
        (row for row in candidates if str(row.get("candidate_id") or "") == str(selected_id or "")),
        None,
    )
    if selected is not None and selected not in bounded:
        bounded[-1] = selected
        bounded.sort(key=lambda row: _integer(row.get("rank")) or 10**9)
    return bounded, True


def _build_result_and_alternatives(analysis, config, readiness, selected_material):
    analysis = analysis or {}
    mode = readiness["mode"]
    result_object = analysis.get("result")
    analysis_report = analysis.get("analysis_report")
    if not analysis_report and isinstance(result_object, dict):
        analysis_report = result_object.get("analysis_report")

    alternatives = []
    truncated = False
    if mode == "design":
        result_candidate_id = (
            result_object.get("candidate_id")
            if isinstance(result_object, dict)
            else ""
        )
        selected_id = str(
            analysis.get("selected_design_candidate_id")
            or result_candidate_id
            or ""
        )
        raw_candidates, truncated = _bounded_candidates(
            analysis.get("design_candidates") or [], selected_id
        )
        for candidate in raw_candidates:
            normalized = _design_candidate(
                candidate,
                selected=str(candidate.get("candidate_id") or "") == selected_id,
            )
            if normalized:
                alternatives.append(normalized)
        result = _design_candidate(result_object, selected=True)
        if result:
            result["kind"] = "design"
        return result, alternatives, truncated

    raw_top5 = list(analysis.get("top5") or [])
    if len(raw_top5) > MAX_ALTERNATIVES:
        raw_top5 = raw_top5[:MAX_ALTERNATIVES]
        truncated = True
    for rank, row in enumerate(raw_top5, start=1):
        normalized = _top5_alternative(
            row,
            rank,
            selected_material,
            config.get("container_id"),
        )
        if normalized:
            alternatives.append(normalized)

    result = _selection_result(
        analysis_report,
        mode,
        readiness["container_source"],
    )
    if mode == "optimal" and result is None and analysis.get("search_completed"):
        result = {
            "kind": "optimal_search",
            "desired_quantity": {
                "value": _integer(readiness.get("desired_quantity")),
                "unit": "pcs",
            },
            "feasible_alternative_count": len(alternatives),
        }
    return result, alternatives, truncated


def _meaningful_state(config):
    current = sanitize_container_config_for_session(config)
    defaults = sanitize_container_config_for_session(default_container_config())
    ignored = {"action"}
    return any(
        current.get(key) != defaults.get(key)
        for key in defaults
        if key not in ignored
    )


def _has_authoritative_result(analysis, mode, workflow_payload):
    if workflow_payload:
        return True
    if not analysis:
        return False
    if analysis.get("result") is not None:
        return True
    if mode == "optimal" and analysis.get("search_completed"):
        return True
    return False


def validate_container_result_snapshot(snapshot):
    """Validate one compact, assistant-safe retained Container result.

    This is deliberately narrower than a page, report, workflow, or assistant
    conversation snapshot.  It contains only the already-validated compact
    result sections and the semantic fingerprint that produced them.
    """
    if not isinstance(snapshot, dict) or frozenset(snapshot) != _RESULT_SNAPSHOT_KEYS:
        raise ToolContextValidationError(
            "Container result snapshot does not match the expected schema."
        )
    if snapshot.get("snapshot_version") != CONTAINER_RESULT_SNAPSHOT_VERSION:
        raise ToolContextValidationError("Unsupported Container result snapshot version.")
    if snapshot.get("context_schema_version") != TOOL_CONTEXT_SCHEMA_VERSION:
        raise ToolContextValidationError("Unsupported Tool Context snapshot version.")
    if snapshot.get("tool") != TOOL_ID:
        raise ToolContextValidationError("Container result snapshot has the wrong tool.")
    if snapshot.get("mode") not in {"single", "optimal", "design"}:
        raise ToolContextValidationError("Container result snapshot has an invalid mode.")
    fingerprint = snapshot.get("state_fingerprint")
    if not isinstance(fingerprint, str) or not _FINGERPRINT_PATTERN.fullmatch(
        fingerprint
    ):
        raise ToolContextValidationError(
            "Container result snapshot has an invalid state fingerprint."
        )
    if not isinstance(snapshot.get("result"), dict):
        raise ToolContextValidationError("Container result snapshot requires a result.")
    alternatives = snapshot.get("alternatives")
    if not isinstance(alternatives, list) or len(alternatives) > MAX_ALTERNATIVES:
        raise ToolContextValidationError(
            f"Container result snapshot permits at most {MAX_ALTERNATIVES} alternatives."
        )

    encoded = canonical_json(snapshot).encode("utf-8")
    if len(encoded) > MAX_CONTAINER_RESULT_SNAPSHOT_BYTES:
        raise ToolContextValidationError(
            "Container result snapshot exceeds the application size limit."
        )
    # Return a detached primitive copy so callers never retain references to a
    # mutable page/workflow context.
    return json.loads(encoded.decode("utf-8"))


def build_container_result_snapshot(context):
    """Create the compact retained-result lifecycle object from Tool Context."""
    validated = validate_tool_context(context)
    tool = validated["tool"]
    if tool["id"] != TOOL_ID or tool["calculation_status"] != "complete":
        raise ToolContextValidationError(
            "Only a complete Container Tool Context can create a result snapshot."
        )
    return validate_container_result_snapshot(
        {
            "snapshot_version": CONTAINER_RESULT_SNAPSHOT_VERSION,
            "context_schema_version": TOOL_CONTEXT_SCHEMA_VERSION,
            "tool": TOOL_ID,
            "mode": tool["mode"],
            "state_fingerprint": tool["state_fingerprint"],
            "result": validated["result"],
            "alternatives": validated["alternatives"],
        }
    )


def _build_assumptions(inputs, result):
    assumptions = []
    if inputs["product"].get("shape") != "cuboid":
        assumptions.append({"code": "product_shape_uses_cuboid_envelope"})
    thickness = (result or {}).get("thickness") if isinstance(result, dict) else None
    if thickness and thickness.get("status") == "assumed":
        assumptions.append(
            {
                "code": "external_dimensions_default_thickness",
                "value": thickness["value"],
                "unit": "mm",
            }
        )
    return assumptions


def _build_restrictions(mode):
    restrictions = [{"code": "orthogonal_placements_only"}]
    if mode in {"single", "optimal"}:
        restrictions.extend(
            [
                {"code": "bounded_residual_heuristic"},
                {"code": "payload_not_capacity_constraint"},
            ]
        )
    else:
        restrictions.extend(
            [
                {"code": "regular_grid_design"},
                {"code": "design_efficiency_is_bounding_box_ratio"},
            ]
        )
    return restrictions


def _build_explanation_facts(inputs, result, workflow):
    facts = [
        {
            "code": "allowed_vertical_axes",
            "value": list(inputs["product"]["allowed_vertical_axes"]),
            "basis": "authoritative_orientation_mapping",
        }
    ]
    if isinstance(result, dict) and result.get("kind") in {"selection", "optimal_selection"}:
        maximum = (result.get("max_quantity") or {}).get("value")
        requested = (result.get("requested_quantity") or {}).get("value")
        remaining = (result.get("remaining_geometric_capacity") or {}).get("value")
        if maximum is not None:
            facts.append(
                {
                    "code": "maximum_geometric_quantity",
                    "value": maximum,
                    "unit": "pcs",
                    "basis": "engine_output",
                }
            )
        if requested is not None:
            facts.append(
                {
                    "code": "requested_quantity",
                    "value": requested,
                    "unit": "pcs",
                    "basis": "service_output",
                }
            )
        if maximum is not None and requested is not None:
            facts.extend(
                [
                    {
                        "code": "requested_quantity_fits_geometrically",
                        "value": requested <= maximum,
                        "basis": "service_derivation",
                    },
                    {
                        "code": "geometric_shortfall",
                        "value": max(requested - maximum, 0),
                        "unit": "pcs",
                        "basis": "service_derivation",
                    },
                ]
            )
        if remaining is not None:
            facts.append(
                {
                    "code": "remaining_geometric_capacity",
                    "value": remaining,
                    "unit": "pcs",
                    "basis": "service_output",
                }
            )
        thickness = result.get("thickness") or {}
        facts.append(
            {
                "code": "external_dimensions_are_estimated",
                "value": thickness.get("status") == "assumed",
                "basis": "service_output",
            }
        )
        payload_usage = (result.get("payload_usage") or {}).get("value")
        if payload_usage is not None:
            facts.append(
                {
                    "code": "payload_check_status",
                    "value": "within" if payload_usage <= 1.0 else "exceeded",
                    "basis": "service_derivation",
                }
            )
        if result.get("kind") == "optimal_selection" and maximum is not None and requested is not None:
            facts.append(
                {
                    "code": "result_visualization_is_limited",
                    "value": requested < maximum,
                    "basis": "service_derivation",
                }
            )
    elif isinstance(result, dict) and result.get("kind") == "design":
        desired = (result.get("desired_quantity") or {}).get("value")
        designed = (result.get("design_quantity") or {}).get("value")
        if desired is not None and designed is not None:
            facts.append(
                {
                    "code": "design_quantity_exceeds_request",
                    "value": designed > desired,
                    "basis": "service_derivation",
                }
            )
    if workflow:
        facts.append(
            {
                "code": "result_state_is_pending",
                "value": workflow.get("result_state") == "pending",
                "basis": "workflow_state",
            }
        )
    return facts


def _workflow_fallback_result(payload):
    if not isinstance(payload, dict):
        return None
    result = {"kind": "workflow_container"}
    units = _integer(payload.get("units_per_parent"))
    if units is not None:
        result["requested_quantity"] = {"value": units, "unit": "pcs"}
    internal = _normalized_dimensions(payload, "internal")
    if internal:
        result["internal_dimensions"] = internal
    external_source = {
        "external_length": payload.get("external_length", payload.get("length")),
        "external_width": payload.get("external_width", payload.get("width")),
        "external_height": payload.get("external_height", payload.get("height")),
    }
    external = _normalized_dimensions(external_source, "external")
    if external:
        result["external_dimensions"] = external
    return result if len(result) > 1 else None


def build_container_tool_context(
    *,
    config,
    form=None,
    analysis=None,
    selected_product=None,
    selected_material=None,
    available_materials=None,
    surface="standalone",
    workflow=None,
    workflow_result_payload=None,
    result_state_fingerprint=None,
    result_snapshot=None,
):
    """Build and validate one Container Selection Tool Context.

    ``result_state_fingerprint`` must accompany a raw result retained beyond
    the request that produced it.  ``result_snapshot`` is the preferred
    retained-result form and carries that fingerprint itself.  A mismatch
    produces ``stale`` and suppresses the old result and alternatives.
    """
    normalized_surface = _SURFACE_ALIASES.get(str(surface or "").lower())
    if normalized_surface is None:
        raise ValueError(f"Unsupported Container Tool Context surface: {surface!r}")
    normalized_config = sanitize_container_config_for_session(config or {})
    prepared_form = _prepare_form(form, normalized_config)
    readiness = inspect_container_readiness(
        prepared_form,
        normalized_config,
        selected_product=selected_product,
        selected_material=selected_material,
    )
    mode = readiness["mode"]
    workflow_metadata = dict(workflow) if workflow else None
    inputs = _build_inputs(
        prepared_form,
        normalized_config,
        readiness,
        selected_product,
        selected_material,
        available_materials,
    )
    fingerprint = state_fingerprint(
        {"tool": TOOL_ID, "mode": mode, "inputs": inputs}
    )

    retained_snapshot = (
        validate_container_result_snapshot(result_snapshot)
        if result_snapshot is not None
        else None
    )

    analysis_payload = dict(analysis or {})
    if mode == "optimal" and analysis is not None:
        action = normalized_config.get("action") or ""
        analysis_payload["search_completed"] = bool(
            analysis_payload.get("search_completed")
            or action in {"find_top5", "select_candidate"}
        )

    form_errors = _normalize_form_errors(prepared_form)
    readiness_issues = list(readiness.get("issues") or [])
    service_messages = [
        {
            "field": "tool",
            "code": "service_validation",
            "message": str(message),
        }
        for message in (analysis_payload.get("messages") or [])
    ]
    attempted = normalized_config.get("action") in _ATTEMPT_ACTIONS
    invalid = bool(form_errors or service_messages or (attempted and readiness_issues))
    incomplete = bool(readiness_issues)
    result_available = _has_authoritative_result(
        analysis_payload, mode, workflow_result_payload
    ) or retained_snapshot is not None
    retained_fingerprint = result_state_fingerprint
    if retained_snapshot is not None:
        retained_fingerprint = retained_snapshot["state_fingerprint"]
    stale = bool(
        result_available
        and retained_fingerprint is not None
        and retained_fingerprint != fingerprint
    )

    result, alternatives, alternatives_truncated = _build_result_and_alternatives(
        analysis_payload,
        normalized_config,
        readiness,
        selected_material,
    )
    if retained_snapshot is not None and not stale:
        result = retained_snapshot["result"]
        alternatives = retained_snapshot["alternatives"]
        alternatives_truncated = False
    if result is None and workflow_result_payload:
        result = _workflow_fallback_result(workflow_result_payload)

    if invalid:
        calculation_status = "invalid"
    elif stale:
        calculation_status = "stale"
    elif incomplete:
        calculation_status = "partial" if _meaningful_state(normalized_config) else "empty"
    elif result_available and result is not None:
        calculation_status = "complete"
    else:
        calculation_status = "ready"

    if calculation_status != "complete":
        result = None
        alternatives = []

    validation_errors = form_errors + (service_messages if service_messages else readiness_issues)
    validation_truncated = len(validation_errors) > MAX_VALIDATION_ERRORS
    validation_errors = validation_errors[:MAX_VALIDATION_ERRORS]
    validation_status = (
        "invalid" if invalid else "incomplete" if incomplete else "valid"
    )

    warnings = []
    if alternatives_truncated:
        warnings.append(
            {
                "code": "alternatives_limited",
                "value": MAX_ALTERNATIVES,
                "unit": "candidates",
            }
        )
    if validation_truncated:
        warnings.append(
            {
                "code": "validation_errors_limited",
                "value": MAX_VALIDATION_ERRORS,
                "unit": "errors",
            }
        )
    if stale:
        warnings.append({"code": "previous_result_is_stale"})

    input_definitions = _build_input_definitions(
        prepared_form, readiness, workflow_metadata
    )
    allowed_proposals = [
        path
        for path, definition in input_definitions.items()
        if definition.get("editable")
    ]

    context: ToolContext = {
        "schema_version": TOOL_CONTEXT_SCHEMA_VERSION,
        "tool": {
            "id": TOOL_ID,
            "surface": normalized_surface,
            "mode": mode,
            "state_fingerprint": fingerprint,
            "calculation_status": calculation_status,
        },
        "inputs": inputs,
        "input_definitions": input_definitions,
        "validation": {
            "status": validation_status,
            "errors": validation_errors,
        },
        "assumptions": _build_assumptions(inputs, result),
        "restrictions": _build_restrictions(mode),
        "result": result,
        "alternatives": alternatives,
        "workflow": workflow_metadata,
        "warnings": warnings,
        "explanation_facts": _build_explanation_facts(
            inputs, result, workflow_metadata
        ),
        "allowed_proposals": allowed_proposals,
    }
    return validate_tool_context(context)


def build_container_tool_context_from_page_context(
    page_context,
    *,
    surface="standalone",
    result_state_fingerprint=None,
    result_snapshot=None,
):
    """Adapt the existing standalone/public page context without export state."""
    form = page_context.get("container_form") or page_context.get("form")
    analysis = {
        "result": page_context.get("result"),
        "analysis_report": page_context.get("analysis_report"),
        "top5": page_context.get("top5") or [],
        "design_candidates": page_context.get("design_candidates") or [],
        "selected_design_candidate_id": page_context.get("selected_design_candidate_id") or "",
        "messages": [],
    }
    return build_container_tool_context(
        config=page_context.get("container_config") or {},
        form=form,
        analysis=analysis,
        selected_product=page_context.get("selected_product"),
        selected_material=page_context.get("selected_material"),
        available_materials=page_context.get("materials"),
        surface=surface,
        result_state_fingerprint=result_state_fingerprint,
        result_snapshot=result_snapshot,
    )


def build_container_tool_context_from_workflow_step(
    step,
    *,
    form=None,
    selected_product=None,
    selected_material=None,
    available_materials=None,
    step_ordinal=None,
    input_origin=None,
    result_state_fingerprint=None,
    result_snapshot=None,
):
    """Adapt one JSON-safe Packaging Flow Container step and nothing else."""
    config = step.get("config") or {}
    pending = step.get("pending_result")
    selected = step.get("selected")
    if pending is not None and selected == pending:
        result_state = "selected"
    elif pending is not None:
        result_state = "pending"
    elif selected is not None:
        result_state = "selected"
    else:
        result_state = "none"
    ordinal = int(step_ordinal) if step_ordinal is not None else 1
    origin = input_origin or ("inherited" if ordinal > 1 else config.get("product_source") or "manual")
    workflow = {
        "input_origin": origin,
        "result_state": result_state,
        "step_type": "container_selection",
        "step_ordinal": ordinal,
    }
    result_payload = pending if pending is not None else selected
    analysis = {
        "result": step.get("result"),
        "analysis_report": step.get("analysis_report"),
        "top5": step.get("top5") or [],
        "design_candidates": step.get("design_candidates") or [],
        "selected_design_candidate_id": step.get("selected_design_candidate_id") or "",
        "messages": step.get("messages") or [],
    }
    return build_container_tool_context(
        config=config,
        form=form,
        analysis=analysis,
        selected_product=selected_product,
        selected_material=selected_material,
        available_materials=available_materials,
        surface="workflow",
        workflow=workflow,
        workflow_result_payload=result_payload,
        result_state_fingerprint=result_state_fingerprint,
        result_snapshot=result_snapshot,
    )
