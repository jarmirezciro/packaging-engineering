"""Editable rotation defaults for steps that directly consume a Bag Design."""

from ..bag.state import BAG_ROTATION_KEYS
from ..bag.workflow_rotation import BAG_ROTATION_MAPPING_SOURCE, rotation_tuple


def is_bag_design(payload):
    return bool(
        payload and payload.get("mode") == "design"
        and (payload.get("source_step_type") or payload.get("package_type")) == "bag"
    )


def bag_rotation_defaults(payload):
    if not is_bag_design(payload):
        return None
    metadata = payload.get("load_unit_rotation_defaults")
    if not isinstance(metadata, dict) or metadata.get("source") != BAG_ROTATION_MAPPING_SOURCE:
        return None
    defaults = rotation_tuple(metadata)
    return defaults if defaults and any(defaults) else None


def refresh_bag_rotation_inheritance(step, controls, upstream, *, other_defaults=None):
    """Refresh recommendations while retaining a deliberate edit on this step."""
    previous = step.get("bag_rotation_inheritance") or {}
    override = rotation_tuple(previous.get("override"))
    fallback = rotation_tuple(previous.get("fallback")) or rotation_tuple(controls)
    if not is_bag_design(upstream):
        if previous:
            step.pop("bag_rotation_inheritance", None)
            controls.update(zip(BAG_ROTATION_KEYS, override or other_defaults or fallback))
        return

    defaults = bag_rotation_defaults(upstream)
    step["bag_rotation_inheritance"] = {
        "candidate_id": str(upstream.get("selected_candidate_id") or ""),
        "defaults": list(defaults) if defaults is not None else None,
        "fallback": list(fallback),
        "override": list(override) if override is not None else None,
    }
    controls.update(zip(BAG_ROTATION_KEYS, override or defaults or fallback))


def apply_bag_rotation_submission(state, controls, *, submitted=None, displayed="", restore=False):
    """Treat a submitted value as an edit only if it differs from the rendered controls."""
    defaults = rotation_tuple(state["defaults"])
    was_displayed = (
        tuple(value == "1" for value in displayed)
        if len(displayed) == 3 and set(displayed) <= {"0", "1"}
        else rotation_tuple(controls)
    )
    if restore and defaults is not None:
        state["override"] = None
    elif submitted is not None and submitted != was_displayed:
        state["override"] = None if submitted == defaults else list(submitted)
    effective = state["override"] or state["defaults"] or state["fallback"]
    controls.update(zip(BAG_ROTATION_KEYS, effective))
