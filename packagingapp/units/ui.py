"""JSON-safe metadata for the shared manual-input unit selector."""

from .definitions import FILM_THICKNESS_UNIT_OPTIONS, LENGTH_UNIT_OPTIONS, MASS_UNIT_OPTIONS


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
    options = {
        "length": LENGTH_UNIT_OPTIONS,
        "mass": MASS_UNIT_OPTIONS,
        "film": FILM_THICKNESS_UNIT_OPTIONS,
    }[quantity]
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
