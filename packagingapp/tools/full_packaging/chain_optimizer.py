"""Packaging Flow orchestration for Design Mode final-capacity ranking."""

from copy import deepcopy
import json
import logging

from ..container.dimensions import (
    EXTERNAL_DIMENSION_SOURCE_CATALOGUE_THICKNESS,
    EXTERNAL_DIMENSION_SOURCE_PROVIDED_THICKNESS,
    resolve_external_carton_dimensions,
)


logger = logging.getLogger(__name__)


FINAL_STEP_LABELS = {
    "container": ("box", "Max base units / box"),
    "bag": ("bag", "Max base units / bag"),
    "pallet": ("pallet", "Max base units / pallet"),
    "transport": ("transport container", "Max base units / transport container"),
}

STEP_NAMES = {
    "container": "Container Selection",
    "bag": "Bag Selection",
    "pallet": "Palletization",
    "transport": "Transport Container",
}

SOURCE_TYPES = {"container", "bag"}


def _positive_int(value, default=None):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _effective_output(step):
    return (step or {}).get("pending_result") or (step or {}).get("selected")


def terminal_capacity_labels(step_type):
    """Return the short terminal label and exact table heading."""
    return FINAL_STEP_LABELS.get(step_type, (str(step_type or "step"), "Max base units / final step"))


def build_design_candidate_payload(source_type, candidate, upstream=None):
    """Build the same workflow payload used by a selected Design candidate."""
    if source_type not in SOURCE_TYPES:
        raise ValueError("Final-capacity optimization requires a Container or Bag Design step.")

    design_quantity = _positive_int(candidate.get("design_quantity"))
    if design_quantity is None:
        raise ValueError("The Design candidate has no usable design quantity.")

    upstream_units = _positive_int((upstream or {}).get("total_base_units"), 1)
    common = {
        "units_per_parent": design_quantity,
        "total_base_units": design_quantity * upstream_units,
        "transport_qty": 1,
        "source_step_type": source_type,
        "package_type": source_type,
        "mode": "design",
        "desired_quantity": _positive_int(candidate.get("desired_quantity"), design_quantity),
        "design_quantity": design_quantity,
        "additional_capacity": int(candidate.get("additional_capacity") or 0),
        "selected_candidate_id": str(candidate.get("candidate_id") or ""),
        "selected_arrangement": candidate.get("arrangement"),
        "selected_orientation": candidate.get("product_orientation"),
        "render_data": candidate.get("render_data"),
    }

    if source_type == "container":
        thickness = candidate.get("box_thickness_mm")
        if candidate.get("box_thickness_assumed"):
            thickness = None
        thickness_source = candidate.get("external_dimension_source")
        if thickness_source not in (
            EXTERNAL_DIMENSION_SOURCE_CATALOGUE_THICKNESS,
            EXTERNAL_DIMENSION_SOURCE_PROVIDED_THICKNESS,
        ):
            thickness_source = EXTERNAL_DIMENSION_SOURCE_PROVIDED_THICKNESS
        dimensions = resolve_external_carton_dimensions(
            candidate.get("container_length"),
            candidate.get("container_width"),
            candidate.get("container_height"),
            thickness_mm=thickness,
            thickness_source=thickness_source,
        )
        common.update({
            "label": "Designed Container",
            **dimensions,
            "length": dimensions["external_length"],
            "width": dimensions["external_width"],
            "height": dimensions["external_height"],
            "metrics": {
                "cubicity": candidate.get("container_cubicity_score"),
                "volume": candidate.get("required_container_volume"),
            },
        })
    else:
        common.update({
            "label": "Designed bag",
            "length": candidate.get("bag_length"),
            "width": candidate.get("bag_width"),
            "height": candidate.get("bundle_height"),
            "selected_arrangement_id": candidate.get("arrangement_id"),
            "metrics": {
                "cubicity": candidate.get("bundle_cubicity_score"),
                "bag_area": candidate.get("bag_area"),
                "bundle_volume": (
                    float(candidate.get("bundle_length") or 0)
                    * float(candidate.get("bundle_width") or 0)
                    * float(candidate.get("bundle_height") or 0)
                ),
            },
        })

    if candidate.get("net_content_weight") is not None:
        common["net_content_weight_g"] = candidate.get("net_content_weight")
    return common


def _signature_value(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {
            str(key): _signature_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_signature_value(item) for item in value]
    return str(value)


def _evaluation_signature(step, step_index, inherited):
    physical_input = {
        key: (inherited or {}).get(key)
        for key in (
            "length", "width", "height", "weight_g", "weight_kg",
            "total_base_units", "transport_qty", "transport_max_qty",
            "transport_stackable", "transport_r1", "transport_r2", "transport_r3",
        )
    }
    signature = {
        "step_index": step_index,
        "step_type": step.get("type"),
        "config": step.get("config") or {},
        "selected_design_candidate_id": step.get("selected_design_candidate_id") or "",
        "selected_result_key": step.get("selected_result_key") or "",
        "inherited": physical_input,
    }
    return json.dumps(_signature_value(signature), sort_keys=True, separators=(",", ":"))


def _unavailable_result(step_index, step_type, message=None):
    step_name = STEP_NAMES.get(step_type, "downstream")
    return {
        "status": "unavailable",
        "final_base_units": None,
        "failed_step_index": int(step_index),
        "failed_step_type": str(step_type or ""),
        "message": message or f"Complete or correct the {step_name} step.",
    }


def optimize_design_chain(workflow, source_step_index, evaluate_step):
    """Evaluate every source candidate through the actual ordered downstream chain.

    ``evaluate_step`` receives a temporary step list and an index. It may mutate
    that temporary list and must return the effective JSON-safe output, or None.
    The live workflow is never passed to the callback.
    """
    steps = (workflow or {}).get("steps") or []
    if not isinstance(source_step_index, int) or not 0 <= source_step_index < len(steps):
        raise ValueError("Choose a valid Packaging Flow step to optimize.")

    source = steps[source_step_index]
    source_type = source.get("type")
    candidates = source.get("design_candidates") or []
    if source_type not in SOURCE_TYPES or (source.get("config") or {}).get("mode") != "design":
        raise ValueError("Final-capacity optimization is available only for Container or Bag Design Mode.")
    if not candidates:
        raise ValueError("Run Design Mode before optimizing final capacity.")
    if source_step_index >= len(steps) - 1:
        raise ValueError("Add a downstream Packaging Flow step before optimizing final capacity.")

    terminal_index = len(steps) - 1
    terminal_type = steps[terminal_index].get("type")
    terminal_label, column_label = terminal_capacity_labels(terminal_type)
    upstream = _effective_output(steps[source_step_index - 1]) if source_step_index else None
    memo = {}
    candidate_results = {}
    original_ids = []

    for fallback_rank, candidate in enumerate(candidates, start=1):
        candidate_id = str(candidate.get("candidate_id") or "")
        if not candidate_id:
            continue
        original_ids.append(candidate_id)
        temporary_steps = deepcopy(steps)
        try:
            payload = build_design_candidate_payload(source_type, candidate, upstream)
        except (TypeError, ValueError) as exc:
            candidate_results[candidate_id] = _unavailable_result(
                source_step_index, source_type, str(exc)
            )
            continue

        temporary_source = temporary_steps[source_step_index]
        temporary_source["pending_result"] = payload
        temporary_source["selected"] = deepcopy(payload)

        failure = None
        for step_index in range(source_step_index + 1, len(temporary_steps)):
            downstream = temporary_steps[step_index]
            inherited = _effective_output(temporary_steps[step_index - 1])
            signature = _evaluation_signature(downstream, step_index, inherited)
            if signature in memo:
                output = deepcopy(memo[signature])
            else:
                downstream["pending_result"] = None
                downstream["selected"] = None
                try:
                    output = evaluate_step(temporary_steps, step_index)
                except Exception:
                    logger.exception(
                        "Final-capacity evaluation failed at workflow step %s (%s)",
                        step_index,
                        downstream.get("type"),
                    )
                    output = None
                if output:
                    output = deepcopy(output)
                    memo[signature] = deepcopy(output)

            if output:
                downstream["pending_result"] = deepcopy(output)
                downstream["selected"] = deepcopy(output)

            total_base_units = _positive_int((output or {}).get("total_base_units"))
            if output is None or total_base_units is None:
                failure = _unavailable_result(step_index, downstream.get("type"))
                break

        if failure:
            candidate_results[candidate_id] = failure
        else:
            candidate_results[candidate_id] = {
                "status": "ok",
                "final_base_units": int(total_base_units),
            }

    rank_by_id = {
        str(candidate.get("candidate_id") or ""): _positive_int(candidate.get("rank"), fallback_rank)
        for fallback_rank, candidate in enumerate(candidates, start=1)
    }
    successful_ids = [
        candidate_id for candidate_id in original_ids
        if candidate_results.get(candidate_id, {}).get("status") == "ok"
    ]
    unavailable_ids = [candidate_id for candidate_id in original_ids if candidate_id not in successful_ids]
    successful_ids.sort(key=lambda candidate_id: (
        -candidate_results[candidate_id]["final_base_units"],
        rank_by_id[candidate_id],
    ))
    sorted_ids = successful_ids + unavailable_ids if successful_ids else list(original_ids)

    message = ""
    if not successful_ids:
        failed = next(iter(candidate_results.values()), {})
        failed_name = STEP_NAMES.get(failed.get("failed_step_type"), "downstream")
        message = f"Complete or correct the {failed_name} step before optimizing final capacity."

    return {
        "active": True,
        "source_step_index": int(source_step_index),
        "terminal_step_index": int(terminal_index),
        "terminal_step_type": str(terminal_type or ""),
        "terminal_label": terminal_label,
        "column_label": column_label,
        "candidate_results": candidate_results,
        "sorted_candidate_ids": sorted_ids,
        "message": message,
    }


def invalidate_design_chain_optimizations(
    steps,
    changed_step_index=None,
    structural=False,
    preserve_source=False,
    message=None,
):
    """Clear stale optimization state after source, downstream, or structure changes."""
    for index, step in enumerate(steps or []):
        state = step.get("design_chain_optimization") or {}
        if not state:
            continue
        should_clear = structural or changed_step_index is not None
        if preserve_source and index == changed_step_index:
            should_clear = False
        if should_clear:
            step.pop("design_chain_optimization", None)
            step.pop("design_chain_optimization_message", None)
            if message:
                step["design_chain_optimization_message"] = str(message)


def build_design_chain_ui(step, steps, source_step_index):
    """Build transient workflow-only table/button context and display ordering."""
    candidates = step.get("design_candidates") or []
    is_design_source = (
        step.get("type") in SOURCE_TYPES
        and (step.get("config") or {}).get("mode") == "design"
    )
    has_downstream = source_step_index < len(steps or []) - 1
    show = bool(is_design_source and candidates and has_downstream)
    terminal_type = (steps[-1] or {}).get("type") if has_downstream else ""
    _terminal_label, default_column_label = terminal_capacity_labels(terminal_type)
    state = step.get("design_chain_optimization") or {}
    state_is_current = bool(
        state.get("active")
        and state.get("source_step_index") == source_step_index
        and state.get("terminal_step_index") == len(steps) - 1
        and state.get("terminal_step_type") == terminal_type
    )
    results = state.get("candidate_results") or {} if state_is_current else {}

    display_by_id = {}
    original_ids = []
    for candidate in candidates:
        row = dict(candidate)
        candidate_id = str(row.get("candidate_id") or "")
        original_ids.append(candidate_id)
        result = results.get(candidate_id) or {}
        final_base_units = result.get("final_base_units") if result.get("status") == "ok" else None
        row["design_chain_final_base_units"] = final_base_units
        row["design_chain_final_base_units_display"] = f"{final_base_units:,}" if final_base_units is not None else "—"
        display_by_id[candidate_id] = row

    ordered_ids = state.get("sorted_candidate_ids") or [] if state_is_current else []
    ordered_ids = [candidate_id for candidate_id in ordered_ids if candidate_id in display_by_id]
    ordered_ids.extend(candidate_id for candidate_id in original_ids if candidate_id not in ordered_ids)

    return {
        "show": show,
        "active": state_is_current,
        "column_label": state.get("column_label") if state_is_current else default_column_label,
        "message": (
            state.get("message") if state_is_current
            else step.get("design_chain_optimization_message", "")
        ),
        "display_candidates": [display_by_id[candidate_id] for candidate_id in ordered_ids],
    }
