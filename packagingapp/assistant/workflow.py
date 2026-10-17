"""Application-owned references for assistant access to Packaging Flow steps."""

from __future__ import annotations

import re
import secrets


ASSISTANT_STEP_REF_KEY = "assistant_step_ref"
_STEP_REF_PATTERN = re.compile(r"[A-Za-z0-9_-]{20,64}\Z")


def is_valid_assistant_step_ref(value) -> bool:
    return isinstance(value, str) and bool(_STEP_REF_PATTERN.fullmatch(value))


def ensure_workflow_step_refs(workflow) -> bool:
    """Give every session-owned workflow step a unique opaque reference."""
    if not isinstance(workflow, dict):
        return False

    changed = False
    seen = set()
    for step in workflow.get("steps") or []:
        if not isinstance(step, dict):
            continue
        step_ref = step.get(ASSISTANT_STEP_REF_KEY)
        if not is_valid_assistant_step_ref(step_ref) or step_ref in seen:
            step_ref = secrets.token_urlsafe(18)
            while step_ref in seen:  # pragma: no cover - defensive entropy guard.
                step_ref = secrets.token_urlsafe(18)
            step[ASSISTANT_STEP_REF_KEY] = step_ref
            changed = True
        seen.add(step_ref)
    return changed


def find_workflow_step_by_ref(workflow, step_ref):
    """Return ``(step, zero_based_index)`` only for a valid opaque reference."""
    if not is_valid_assistant_step_ref(step_ref) or not isinstance(workflow, dict):
        return None, None
    for index, step in enumerate(workflow.get("steps") or []):
        if (
            isinstance(step, dict)
            and step.get(ASSISTANT_STEP_REF_KEY) == step_ref
        ):
            return step, index
    return None, None
