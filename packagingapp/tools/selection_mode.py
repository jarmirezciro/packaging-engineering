"""Shared mode normalization for Bag and Container Selection.

``tool_mode`` existed briefly as a second selector.  It is now read only as a
legacy compatibility signal; all newly-created state uses the authoritative
``mode`` value.
"""

VALID_SELECTION_MODES = {"design", "single", "optimal"}


def normalize_selection_mode(data, default="single"):
    source = data or {}
    if str(source.get("tool_mode") or "").strip().lower() == "design":
        return "design"

    mode = str(source.get("mode") or default).strip().lower()
    return mode if mode in VALID_SELECTION_MODES else default
