"""JSON-safe metadata for the shared manual-input unit selector."""

from .definitions import LENGTH_UNIT_OPTIONS, MASS_UNIT_OPTIONS


def build_unit_selector_contract(
    *,
    quantity,
    label,
    group,
    hidden_name,
    hidden_id,
    menu_id,
    storage_key=None,
    url_param=None,
):
    options = LENGTH_UNIT_OPTIONS if quantity == "length" else MASS_UNIT_OPTIONS
    return {
        "quantity": quantity,
        "label": label,
        "group": group,
        "hidden_name": hidden_name,
        "hidden_id": hidden_id,
        "menu_id": menu_id,
        "storage_key": storage_key,
        "url_param": url_param,
        "options": options,
    }
