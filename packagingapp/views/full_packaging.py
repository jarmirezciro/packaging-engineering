from copy import deepcopy

from packagingapp.access import visible_packaging_catalogues, visible_product_catalogues, get_visible_packaging_catalogue_or_404, get_visible_product_catalogue_or_404
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.utils import timezone

from ..models import PackagingCatalogue, PackagingMaterial, ProductCatalogue, Product
from ..utils.box_selection.engine import run_mode1_and_render, compute_max_quantity_only
from ..utils.bag_selection.engine import (
    SEALING_AREA,
    TOLERANCE,
    build_required_bag_options,
    best_usage_for_bag,
    run_bag_mode1_and_render,
)
from ..tools.palletization.presenter import (
    build_pallet_ui_contract,
    result_card_from_row,
    build_pallet_pending_result,
)
from ..tools.palletization.serializers import sanitize_palletization_config_for_session
from ..tools.palletization.service import (
    analyze_palletization_config,
    get_selected_box_material,
    get_selected_pallet_material,
)
from ..tools.palletization.state import default_palletization_config
from ..views.container_selection import _build_shared_container_ui_contract
from ..views.bag_selection import _build_shared_bag_ui_contract

from ..tools.bag.presenter import (
    selected_bag_summary as selected_bag_summary_bag,
    selected_product_summary as selected_product_summary_bag,
)
from ..tools.bag.serializers import sanitize_bag_config_for_session
from ..tools.selection_mode import normalize_selection_mode
from ..tools.bag.service import (
    analyze_bag_config as analyze_bag_config_shared,
    get_materials_for_catalogue as get_bag_materials_for_catalogue,
    get_products_for_catalogue as get_bag_products_for_catalogue,
    get_selected_material as get_bag_selected_material,
    get_selected_product as get_bag_selected_product,
)
from ..tools.bag.state import default_bag_config

from ..tools.container.presenter import (
    selected_container_summary as selected_container_summary_container,
    selected_product_summary as selected_product_summary_container,
)
from ..tools.container.serializers import sanitize_container_config_for_session
from ..tools.container.service import (
    analyze_container_form,
    apply_catalogue_choices as apply_container_catalogue_choices,
    build_container_form,
    get_materials_for_catalogue as get_container_materials_for_catalogue,
    get_packaging_catalogues as get_container_packaging_catalogues,
    get_product_catalogues as get_container_product_catalogues,
    get_products_for_catalogue as get_container_products_for_catalogue,
    get_selected_material as get_container_selected_material,
    get_selected_product as get_container_selected_product,
)
from ..tools.container.state import default_container_config

from ..tools.transport.presenter import (
    selected_container_summary,
    build_transport_pending_result,
)
from ..tools.transport.serializers import sanitize_transport_rows_for_session
from ..tools.transport.service import (
    analyze_transport_config,
    read_product_rows_raw,
)
from ..tools.transport.state import default_product_rows

from ..tools.full_packaging.export import (
    build_full_packaging_pdf,
    build_workflow_report_payload,
)


SESSION_KEY = "full_packaging_mode_session"
PALLETIZATION_VISUAL_SOURCE = "palletization_result"
PALLETIZATION_VISUAL_TOLERANCE_MM = 1e-6


def _init_workflow_session(request):
    if SESSION_KEY not in request.session:
        request.session[SESSION_KEY] = {
            "steps": [],
            "show_add_bar_after": None,
        }
        request.session.modified = True


def _get_workflow(request):
    _init_workflow_session(request)
    return request.session[SESSION_KEY]


def _save_workflow(request, workflow):
    for step in workflow.get("steps", []):
        step.pop("selected_box_material", None)
        step.pop("selected_pallet_material", None)
        step.pop("box_materials", None)
        step.pop("pallet_materials", None)
    request.session[SESSION_KEY] = workflow
    request.session.modified = True


def _new_container_step():
    return {
        "type": "container",
        "expanded": True,
        "selected": None,
        "summary": "",
        "messages": [],
        "result": None,
        "image_url": None,
        "analysis_report": None,
        "selected_result": None,
        "top5": [],
        "design_candidates": [],
        "selected_design_candidate_id": "",
        "pending_result": None,
        "config": default_container_config(),
    }


def _new_bag_step():
    return {
        "type": "bag",
        "expanded": True,
        "selected": None,
        "summary": "",
        "messages": [],
        "result": None,
        "image_url": None,
        "top5": [],
        "design_candidates": [],
        "selected_design_candidate_id": "",
        "pending_result": None,
        "config": default_bag_config(),
    }





def _new_transport_step():
    return {
        "type": "transport",
        "expanded": True,
        "selected": None,
        "summary": "",
        "messages": [],
        "result": None,
        "image_url": None,
        "image_urls": {},
        "threejs_scene": None,
        "top5": [],
        "pending_result": None,
        "analysis_ran": False,
        "auto_hide_product_catalogue": False,
        "config": {
            "container_source": "manual",
            "catalogue_id": "",
            "container_id": "",
            "container_l": 12032,
            "container_w": 2352,
            "container_h": 2698,
            "max_weight": 26000,
            "tare_weight": "",
            "product_catalogue_id": "",
            "product_id_to_fill": "",
            "selected_row_index": "",
            "product_rows": default_product_rows(),
        },
    }






def _new_pallet_step():
    return {
        "type": "pallet",
        "expanded": True,
        "selected": None,
        "summary": "",
        "messages": [],
        "result": None,
        "image_url": None,
        "threejs_scene": None,
        "top5": [],
        "pending_result": None,
        "results_table": [],
        "selected_result_key": "",
        "show_box_catalogue": False,
        "show_pallet_catalogue": False,
        "analysis_ran": False,
        "config": {
            "box_source": "manual",
            "box_catalogue_id": "",
            "selected_box_id": "",
            "box_l": "",
            "box_w": "",
            "box_h": "",
            "box_weight": "",
            "max_weight_on_bottom_box": "",
            "pallet_source": "manual",
            "pallet_catalogue_id": "",
            "pallet_id": "",
            "pallet_l": "",
            "pallet_w": "",
            "max_stack_height": "",
            "max_width_stickout": 0,
            "max_length_stickout": 0,
            "show_advanced": False,
        },
    }


def _extract_pallet_config_from_step(step):
    cfg = default_palletization_config()
    cfg.update(step.get("config") or {})
    return sanitize_palletization_config_for_session(cfg)


def _update_pallet_config_on_step(step, config):
    step["config"] = sanitize_palletization_config_for_session(config)


def _read_prefixed_pallet_post(step, idx, post):
    cfg = _extract_pallet_config_from_step(step)

    if idx == 0:
        cfg["box_source"] = post.get(f"box_source_{idx}", cfg.get("box_source", "manual"))
        cfg["box_catalogue_id"] = post.get(f"box_catalogue_id_{idx}", cfg.get("box_catalogue_id", ""))
        cfg["selected_box_id"] = post.get(f"selected_box_id_{idx}", cfg.get("selected_box_id", ""))
    else:
        cfg["box_source"] = "manual"
        cfg["box_catalogue_id"] = ""
        cfg["selected_box_id"] = ""

    cfg["box_l"] = post.get(f"box_l_{idx}", cfg.get("box_l", ""))
    cfg["box_w"] = post.get(f"box_w_{idx}", cfg.get("box_w", ""))
    cfg["box_h"] = post.get(f"box_h_{idx}", cfg.get("box_h", ""))
    cfg["box_weight"] = post.get(f"box_weight_{idx}", cfg.get("box_weight", ""))
    cfg["max_weight_on_bottom_box"] = post.get(
        f"max_weight_on_bottom_box_{idx}",
        cfg.get("max_weight_on_bottom_box", ""),
    )

    cfg["pallet_source"] = post.get(f"pallet_source_{idx}", cfg.get("pallet_source", "manual"))
    cfg["pallet_catalogue_id"] = post.get(
        f"pallet_catalogue_id_{idx}",
        cfg.get("pallet_catalogue_id", ""),
    )
    cfg["pallet_id"] = post.get(f"pallet_id_{idx}", cfg.get("pallet_id", ""))
    cfg["pallet_l"] = post.get(f"pallet_l_{idx}", cfg.get("pallet_l", ""))
    cfg["pallet_w"] = post.get(f"pallet_w_{idx}", cfg.get("pallet_w", ""))
    cfg["max_stack_height"] = post.get(f"max_stack_height_{idx}", cfg.get("max_stack_height", ""))
    cfg["max_width_stickout"] = post.get(
        f"max_width_stickout_{idx}",
        cfg.get("max_width_stickout", 0),
    )
    cfg["max_length_stickout"] = post.get(
        f"max_length_stickout_{idx}",
        cfg.get("max_length_stickout", 0),
    )

    cfg["show_advanced"] = post.get(
        f"show_advanced_{idx}",
        "1" if cfg.get("show_advanced") else "0",
    ) in ("1", "true", "True", "on", "yes")

    return sanitize_palletization_config_for_session(cfg)


def _run_pallet_analysis_shared(step, steps, idx):
    step["result"] = None
    step["image_url"] = None
    step["threejs_scene"] = None
    step["selected_result"] = None
    step["pending_result"] = None
    step["results_table"] = []

    if not step.get("analysis_ran"):
        step["messages"] = []
        return

    cfg = _extract_pallet_config_from_step(step)

    selected_box_material = get_selected_box_material(cfg) if idx == 0 else None
    selected_pallet_material = get_selected_pallet_material(cfg)
    cfg = _hydrate_pallet_catalogue_values(
        cfg,
        selected_box_material=selected_box_material,
        selected_pallet_material=selected_pallet_material,
    )
    _update_pallet_config_on_step(step, cfg)

    analysis = analyze_palletization_config(
        config=cfg,
        selected_result_key=step.get("selected_result_key") or "",
        selected_box_material=selected_box_material,
        selected_pallet_material=selected_pallet_material,
        media_root=settings.MEDIA_ROOT,
    )

    step["messages"] = analysis["messages"]

    if not analysis["ok"]:
        return

    serialized = analysis["serialized_result"] or {}
    effective = analysis["effective_config"] or {}

    step["results_table"] = serialized.get("results_table") or []
    step["selected_result_key"] = serialized.get("selected_result_key") or ""
    step["threejs_scene"] = serialized.get("threejs_scene")
    image_rel_path = serialized.get("image_rel_path")
    step["image_url"] = settings.MEDIA_URL + image_rel_path if image_rel_path else None

    selected_row = serialized.get("selected_result")
    step["selected_result"] = selected_row
    if not selected_row:
        return

    step["result"] = result_card_from_row(
        selected_row,
        effective.get("pallet_l"),
        effective.get("pallet_w"),
    )

    prev = _selected_input_for_step(steps, idx)
    upstream_units = prev.get("total_base_units", 1) if prev else 1

    step["pending_result"] = build_pallet_pending_result(
        effective.get("pallet_l"),
        effective.get("pallet_w"),
        selected_row,
        selected_pallet_material=selected_pallet_material,
        upstream_units=upstream_units,
    )
    if step["pending_result"]:
        prev_weight_g = _to_float((prev or {}).get("weight_g"), None)
        pallet_tare_g = _to_float(getattr(selected_pallet_material, "part_weight", None), None)
        total_boxes = _to_int(selected_row.get("total_boxes"), 1) or 1
        gross_weight_g = None
        if prev_weight_g is not None:
            gross_weight_g = prev_weight_g * total_boxes
        if pallet_tare_g is not None:
            gross_weight_g = (gross_weight_g or 0.0) + pallet_tare_g
        if gross_weight_g is not None:
            step["pending_result"]["weight_g"] = round(gross_weight_g, 3)
            step["pending_result"]["weight_kg"] = round(gross_weight_g / 1000.0, 3)
        step["pending_result"].setdefault("transport_qty", 1)
        step["pending_result"]["source_step_type"] = "pallet"
        step["pending_result"]["package_type"] = "pallet"
        step["pending_result"]["source_type"] = PALLETIZATION_VISUAL_SOURCE


def _compute_pallet_view_model(step, steps, idx):
    _run_pallet_analysis_shared(step, steps, idx)

def _new_step(step_type):
    if step_type == "bag":
        return _new_bag_step()
    if step_type == "pallet":
        return _new_pallet_step()
    if step_type == "transport":
        return _new_transport_step()
    return _new_container_step()


def _to_float(value, default=None):
    try:
        if value in (None, "", "None"):
            return default
        return float(value)
    except Exception:
        return default


def _to_int(value, default=None):
    try:
        if value in (None, "", "None"):
            return default
        return int(float(value))
    except Exception:
        return default


def _round_payload_value(value, digits=2):
    numeric = _to_float(value)
    if numeric is None:
        return None
    return round(numeric, digits)


def _format_mm_triplet(payload):
    if not payload:
        return "Not set"
    length = payload.get("length", "")
    width = payload.get("width", "")
    height = payload.get("height", "")
    if length in (None, "") or width in (None, "") or height in (None, ""):
        return "Not set"
    return f"{length} × {width} × {height} mm"


def _format_payload_units(payload):
    if not payload:
        return ""
    parts = []
    units_per_parent = payload.get("units_per_parent")
    total_base_units = payload.get("total_base_units")
    if units_per_parent not in (None, ""):
        parts.append(f"{units_per_parent} units per parent")
    if total_base_units not in (None, ""):
        parts.append(f"{total_base_units} total base units")
    weight_kg = payload.get("weight_kg")
    if weight_kg not in (None, ""):
        try:
            parts.append(f"{float(weight_kg):.2f} kg gross")
        except Exception:
            parts.append(f"{weight_kg} kg gross")
    return " | ".join(parts)


def _payload_overview_value(payload):
    if not payload:
        return "Not selected yet"
    label = payload.get("label") or "Workflow load unit"
    dims = _format_mm_triplet(payload)
    units = _format_payload_units(payload)
    if units:
        return f"{label} — {dims} — {units}"
    return f"{label} — {dims}"




def _material_dimension_for_workflow(material, external_attr, part_attr):
    """Return the physical outside dimension for chained workflow payloads.

    Catalogue items may store external_* as 0 when the usable dimension is in
    part_*. For workflow inheritance, prefer the first positive outside/part
    dimension and only keep 0 when no positive fallback exists.
    """
    if material is None:
        return 0.0

    first_numeric = None
    for attr in (external_attr, part_attr):
        value = _to_float(getattr(material, attr, None), None)
        if value is None:
            continue
        if first_numeric is None:
            first_numeric = value
        if value > 0:
            return value

    return first_numeric or 0.0


def _material_dimension_value(material, external_attr, part_attr):
    """Return a catalogue dimension while preserving empty values as empty.

    Prefer the first positive external/part dimension. This avoids workflow
    validation failures when external_* is stored as 0 but part_* contains the
    real catalogue dimension.
    """
    if material is None:
        return ""

    first_raw = ""
    for attr in (external_attr, part_attr):
        raw_value = getattr(material, attr, None)
        numeric_value = _to_float(raw_value, None)
        if raw_value not in (None, "", "None") and first_raw == "":
            first_raw = raw_value
        if numeric_value is not None and numeric_value > 0:
            return raw_value

    return first_raw


def _hydrate_pallet_catalogue_values(cfg, selected_box_material=None, selected_pallet_material=None):
    """Copy selected catalogue dimensions into the pallet workflow config.

    This is UI/state hydration only. It does not change the palletization
    calculation rules; the service layer still owns the effective calculation
    config. The copied values keep workflow forms and validation messages aligned
    after selecting carton/pallet rows from the shared catalogue tables.
    """
    cfg = dict(cfg or {})

    if cfg.get("box_source") == "catalogue" and selected_box_material is not None:
        cfg["box_l"] = _material_dimension_value(selected_box_material, "external_length", "part_length")
        cfg["box_w"] = _material_dimension_value(selected_box_material, "external_width", "part_width")
        cfg["box_h"] = _material_dimension_value(selected_box_material, "external_height", "part_height")
        if cfg.get("box_weight") in (None, "", "None"):
            material_weight = getattr(selected_box_material, "part_weight", None)
            if material_weight not in (None, "", "None"):
                cfg["box_weight"] = material_weight

    if cfg.get("pallet_source") == "catalogue" and selected_pallet_material is not None:
        cfg["pallet_l"] = _material_dimension_value(selected_pallet_material, "external_length", "part_length")
        cfg["pallet_w"] = _material_dimension_value(selected_pallet_material, "external_width", "part_width")

    return sanitize_palletization_config_for_session(cfg)


def _resolve_product_weight_g(cfg, selected_product=None):
    if (cfg or {}).get("product_source") == "catalogue" and selected_product is not None:
        return _to_float(getattr(selected_product, "weight", None))
    return _to_float((cfg or {}).get("product_weight"))


def _resolve_packaging_weight_g(cfg, manual_key, selected_material=None):
    manual_weight = _to_float((cfg or {}).get(manual_key))
    if manual_weight is not None:
        return manual_weight
    if selected_material is not None:
        return _to_float(getattr(selected_material, "part_weight", None))
    return None


def _enrich_package_payload_weight(payload, product_weight_g=None, packaging_weight_g=None):
    if not payload:
        return payload

    units_per_parent = _to_int(payload.get("units_per_parent"), 1) or 1
    gross_weight_g = None

    if product_weight_g is not None:
        gross_weight_g = float(product_weight_g) * units_per_parent
    if packaging_weight_g is not None:
        gross_weight_g = (gross_weight_g or 0.0) + float(packaging_weight_g)

    if gross_weight_g is not None:
        payload["weight_g"] = round(gross_weight_g, 3)
        payload["weight_kg"] = round(gross_weight_g / 1000.0, 3)

    payload.setdefault("transport_qty", 1)
    return payload


def _as_bool(post, key, default=False):
    val = post.get(key)
    if val is None:
        return default
    return val in ("1", "true", "True", "on", "yes")


def _invalidate_downstream(steps, start_idx):
    for i in range(start_idx + 1, len(steps)):
        steps[i]["selected"] = None
        steps[i]["summary"] = ""
        steps[i]["messages"] = ["This step was cleared because an upstream step changed."]
        steps[i]["result"] = None
        steps[i]["image_url"] = None
        steps[i]["image_urls"] = {}
        steps[i]["threejs_scene"] = None
        steps[i]["top5"] = []
        steps[i]["pending_result"] = None
        steps[i]["results_table"] = []
        steps[i]["selected_result_key"] = ""
        steps[i]["show_box_catalogue"] = False
        steps[i]["show_pallet_catalogue"] = False
        steps[i]["analysis_ran"] = False
        steps[i]["auto_hide_product_catalogue"] = False
        if steps[i].get("type") == "transport":
            steps[i]["config"]["selected_row_index"] = ""


def _effective_step_output(step):
    """Return the workflow payload that should feed the next step.

    A step can have a calculated result (`pending_result`) before the user has
    explicitly clicked "Use this result". For workflow inheritance, that
    pending result is still the freshest physical load unit and should be used
    to prefill the next step. `selected` is kept as the explicit/accepted
    payload and as a fallback for older sessions.
    """
    if not step:
        return None
    return step.get("pending_result") or step.get("selected")


def _selected_input_for_step(steps, idx):
    if idx <= 0:
        return None
    return _effective_step_output(steps[idx - 1])


def _build_summary(selected):
    if not selected:
        return ""
    return _payload_overview_value(selected)


def _build_step_overview(step, steps, idx):
    incoming = _selected_input_for_step(steps, idx)
    selected = step.get("selected")
    pending = step.get("pending_result")
    result = step.get("result")
    messages = step.get("messages") or []

    if messages:
        status_label = "Needs attention"
        status_class = "danger"
    elif selected:
        status_label = "Selected for next step"
        status_class = "success"
    elif pending:
        status_label = "Result ready"
        status_class = "ready"
    elif result:
        status_label = "Analysis complete"
        status_class = "ready"
    else:
        status_label = "Not run yet"
        status_class = "muted"

    rows = []
    if incoming:
        rows.append({
            "label": "Input inherited",
            "value": _payload_overview_value(incoming),
        })
    else:
        rows.append({
            "label": "Input",
            "value": "Manual input or catalogue selection",
        })

    if selected:
        rows.append({
            "label": "Passed forward",
            "value": _payload_overview_value(selected),
        })
    elif pending:
        rows.append({
            "label": "Ready to pass",
            "value": _payload_overview_value(pending),
        })
    elif result:
        rows.append({
            "label": "Result",
            "value": "Analysis result available. Use the result to pass it to the next workflow step.",
        })
    else:
        rows.append({
            "label": "Result",
            "value": "Run this step to calculate a workflow result.",
        })

    return {
        "status_label": status_label,
        "status_class": status_class,
        "rows": rows,
    }


def _apply_payload_to_config(cfg, step_type, payload):
    """Force inherited workflow payload into a step config.

    This is intentionally used both on normal page render and immediately after
    reading POST data. Otherwise stale/empty posted form fields can overwrite
    the inherited carton/package dimensions before the step is processed.
    """
    if not payload:
        return cfg

    length = payload.get("length")
    width = payload.get("width")
    height = payload.get("height")
    weight_g = payload.get("weight_g")

    has_dimensions = all(value not in (None, "", "None") for value in (length, width, height))

    if step_type == "pallet":
        cfg["box_source"] = "manual"
        cfg["box_catalogue_id"] = ""
        cfg["selected_box_id"] = ""
        if has_dimensions:
            cfg["box_l"] = length
            cfg["box_w"] = width
            cfg["box_h"] = height
        if weight_g not in (None, "", "None"):
            cfg["box_weight"] = weight_g
        return cfg

    if step_type == "transport":
        cfg["product_catalogue_id"] = ""
        cfg["product_id_to_fill"] = ""
        cfg["selected_row_index"] = ""

        # The inherited physical load unit must refresh dimensions/weight from
        # the previous step, but workflow-specific user choices made in the
        # transport row must survive normal page renders and POST processing.
        # In particular, the Max qty? checkbox lives in product_rows; replacing
        # the row here reset it to False before _run_transport_analysis().
        inherited_rows = _transport_rows_from_selected(payload)
        existing_rows = cfg.get("product_rows") or []
        cfg["product_rows"] = _merge_transport_inherited_rows(existing_rows, inherited_rows)
        return cfg

    cfg["product_source"] = "manual"
    cfg["product_catalogue_id"] = ""
    cfg["selected_product_id"] = ""
    if has_dimensions:
        cfg["product_l"] = length
        cfg["product_w"] = width
        cfg["product_h"] = height
    if weight_g not in (None, "", "None"):
        cfg["product_weight"] = weight_g
    return cfg


def _transport_rows_from_selected(selected):
    """Build a JSON-safe transport row from the previous workflow step."""
    if not selected:
        return default_product_rows()

    # The previous workflow result is one physical load unit.
    # units_per_parent describes how many base units it contains; it must not
    # become the number of cartons/pallets loaded into the transport unit.
    qty = _to_int(selected.get("transport_qty"), 1) or 1
    qty = max(qty, 1)

    weight_kg = _to_float(selected.get("weight_kg"), None)
    if weight_kg is None:
        weight_kg = _to_float(selected.get("weight"), 0) or 0

    return sanitize_transport_rows_for_session([
        {
            "name": selected.get("label") or "Previous workflow load unit",
            "length": selected.get("length", ""),
            "width": selected.get("width", ""),
            "height": selected.get("height", ""),
            "qty": qty,
            "max_qty": bool(selected.get("transport_max_qty", False)),
            "weight": round(float(weight_kg), 3),
            "sequence": 1,
            "r1": True,
            "r2": True,
            "r3": True,
        }
    ])


def _matches_dimensions(actual, expected):
    return all(
        abs(float(actual_value) - float(expected_value)) <= PALLETIZATION_VISUAL_TOLERANCE_MM
        for actual_value, expected_value in zip(actual, expected)
    )


def _pallet_placement_orientation(item, source_bounds):
    """Map an engine cuboid orientation back to the pallet assembly axes."""
    length = float(source_bounds["length"])
    width = float(source_bounds["width"])
    height = float(source_bounds["height"])
    placed = (
        float(item.get("dx") or 0),
        float(item.get("dy") or 0),
        float(item.get("dz") or 0),
    )
    orientations = (
        ("lwh", (length, width, height)),
        ("wlh", (width, length, height)),
        ("lhw", (length, height, width)),
        ("hlw", (height, length, width)),
        ("whl", (width, height, length)),
        ("hwl", (height, width, length)),
    )
    for name, dimensions in orientations:
        if _matches_dimensions(placed, dimensions):
            return name
    return None


def _normalize_pallet_visualization_for_transport(upstream):
    """Return a JSON-safe pallet scene aligned to the calculated load cuboid.

    Palletization's browser pallet is 108 mm high, while the established Flow
    handoff uses a 100 mm pallet allowance. Carton geometry is not scaled. The
    pallet base height and carton elevation are explicitly remapped to that
    existing calculation allowance, then the complete assembly is bounds
    checked. Unsupported overhang or malformed scenes retain the generic load
    cuboid instead of leaking outside the calculated placement.
    """
    if not upstream or upstream.get("source_type") != PALLETIZATION_VISUAL_SOURCE:
        return None

    source_scene = upstream.get("pallet_visualization")
    if not isinstance(source_scene, dict):
        return None

    try:
        bounds = {
            "length": float(upstream.get("length")),
            "width": float(upstream.get("width")),
            "height": float(upstream.get("height")),
        }
    except (TypeError, ValueError):
        return None
    if any(value <= 0 for value in bounds.values()):
        return None

    scene = deepcopy(source_scene)
    pallet = scene.get("pallet") or {}
    placements = scene.get("placements") or []
    if not pallet or not placements:
        return None

    try:
        original_base_height = float(pallet.get("height") or 0)
        cargo_height = max(
            float(placement.get("z") or 0) + float(placement.get("dz") or 0)
            for placement in placements
        ) - original_base_height
        target_base_height = bounds["height"] - cargo_height
        deck_thickness = min(
            float(pallet.get("deck_thickness") or 0),
            target_base_height,
        )
    except (TypeError, ValueError):
        return None
    if target_base_height <= 0 or deck_thickness <= 0:
        return None

    elevation_delta = target_base_height - original_base_height
    for placement in placements:
        placement["z"] = float(placement.get("z") or 0) + elevation_delta
    pallet["height"] = target_base_height
    pallet["deck_thickness"] = deck_thickness
    pallet["runner_height"] = max(target_base_height - deck_thickness, 0.0)

    metadata = scene.setdefault("metadata", {})
    metadata["total_render_height_mm"] = bounds["height"]
    metadata["transport_base_height_mm"] = target_base_height

    cuboids = [
        {
            "x": 0.0,
            "y": 0.0,
            "z": 0.0,
            "dx": float(pallet.get("length") or 0),
            "dy": float(pallet.get("width") or 0),
            "dz": target_base_height,
        },
        *placements,
    ]
    tolerance = PALLETIZATION_VISUAL_TOLERANCE_MM
    for cuboid in cuboids:
        try:
            minimums = (
                float(cuboid.get("x") or 0),
                float(cuboid.get("y") or 0),
                float(cuboid.get("z") or 0),
            )
            maximums = (
                minimums[0] + float(cuboid.get("dx") or 0),
                minimums[1] + float(cuboid.get("dy") or 0),
                minimums[2] + float(cuboid.get("dz") or 0),
            )
        except (TypeError, ValueError):
            return None
        if any(value < -tolerance for value in minimums):
            return None
        if (
            maximums[0] > bounds["length"] + tolerance
            or maximums[1] > bounds["width"] + tolerance
            or maximums[2] > bounds["height"] + tolerance
        ):
            return None

    return {"bounds": bounds, "scene": scene}


def _decorate_transport_scene_with_pallet_visualization(transport_scene, upstream):
    """Decorate only a direct Flow pallet-to-transport scene for rendering."""
    visualization = _normalize_pallet_visualization_for_transport(upstream)
    if not visualization or not isinstance(transport_scene, dict):
        return transport_scene

    detailed_items = 0
    for item in transport_scene.get("items") or []:
        orientation = _pallet_placement_orientation(item, visualization["bounds"])
        if not orientation:
            continue
        item["source_type"] = PALLETIZATION_VISUAL_SOURCE
        item["visualization_ref"] = "palletized_load"
        item["pallet_orientation"] = orientation
        detailed_items += 1

    if detailed_items:
        transport_scene["workflow_visualizations"] = {
            "palletized_load": visualization,
        }
        transport_scene.setdefault("metadata", {})["detailed_pallet_items"] = detailed_items
    return transport_scene


def _direct_pallet_visualization_input(steps, idx):
    """Join the direct upstream marker with its step-owned scene transiently."""
    upstream = _selected_input_for_step(steps, idx)
    if (
        not upstream
        or idx <= 0
        or steps[idx - 1].get("type") != "pallet"
        or upstream.get("source_type") != PALLETIZATION_VISUAL_SOURCE
    ):
        return upstream

    visual_input = dict(upstream)
    visual_input["pallet_visualization"] = steps[idx - 1].get("threejs_scene")
    return visual_input


def _merge_transport_inherited_rows(existing_rows, inherited_rows):
    """
    Keep the physical load unit inherited from the previous workflow step, while
    preserving user choices made inside the transport row, such as manual qty,
    auto-max checkbox and loading sequence.
    """
    inherited = sanitize_transport_rows_for_session(inherited_rows or default_product_rows())
    existing = sanitize_transport_rows_for_session(existing_rows or [])

    if not inherited:
        return existing or default_product_rows()

    merged = []
    for row_index, inherited_row in enumerate(inherited):
        current = existing[row_index] if row_index < len(existing) else {}
        row = dict(inherited_row)

        for key in ("qty", "max_qty", "sequence", "r1", "r2", "r3"):
            if key in current and current.get(key) not in (None, ""):
                row[key] = current.get(key)

        merged.append(row)

    return sanitize_transport_rows_for_session(merged)


def _apply_chained_defaults(step, steps, idx):
    prev = _selected_input_for_step(steps, idx)
    if not prev:
        return
    step["config"] = _apply_payload_to_config(
        step.get("config") or {},
        step.get("type"),
        prev,
    )


def _resolve_product_for_container(cfg, selected_product):
    if cfg["product_source"] == "catalogue":
        if selected_product:
            product = (
                float(selected_product.product_length),
                float(selected_product.product_width),
                float(selected_product.product_height),
            )
            r1 = 1 if selected_product.rotation_1 else 0
            r2 = 1 if selected_product.rotation_2 else 0
            r3 = 1 if selected_product.rotation_3 else 0
        else:
            product = None
            r1 = 1 if cfg.get("r1") else 0
            r2 = 1 if cfg.get("r2") else 0
            r3 = 1 if cfg.get("r3") else 0
    else:
        product = (
            _to_float(cfg.get("product_l")),
            _to_float(cfg.get("product_w")),
            _to_float(cfg.get("product_h")),
        )
        r1 = 1 if cfg.get("r1") else 0
        r2 = 1 if cfg.get("r2") else 0
        r3 = 1 if cfg.get("r3") else 0
    return product, r1, r2, r3


def _resolve_product_for_bag(cfg, selected_product):
    if cfg["product_source"] == "catalogue":
        if selected_product:
            return (
                float(selected_product.product_length),
                float(selected_product.product_width),
                float(selected_product.product_height),
            )
        return None
    return (
        _to_float(cfg.get("product_l")),
        _to_float(cfg.get("product_w")),
        _to_float(cfg.get("product_h")),
    )


def _resolve_visual_bag_box(selected_bag, inner_box):
    bag_len, bag_w = selected_bag
    bl, bw, bh = inner_box
    # Bag dimensions are physical L × W values and must not be swapped.
    # Length carries sealing; width is the opening side and carries tolerance only.
    bag_box_length = bag_len - TOLERANCE - SEALING_AREA - bh
    bag_box_width = bag_w - TOLERANCE - bh

    if bag_box_length <= 0 or bag_box_width <= 0:
        return None

    bag_box_length = max(float(bag_box_length), float(bl))
    bag_box_width = max(float(bag_box_width), float(bw))

    return (round(bag_box_length, 2), round(bag_box_width, 2), round(bh, 2))



def _inflate_container_top5_rows(top5_rows):
    hydrated = []
    for row in top5_rows or []:
        material = PackagingMaterial.objects.filter(
            id=row.get("material_id") or None
        ).select_related("catalogue").first()
        if material is None:
            continue
        hydrated.append({
            "material": material,
            "max_qty": row.get("max_qty"),
            "usage": row.get("usage", 0.0),
            "container_vol": row.get("container_vol"),
        })
    return hydrated


def _prepare_container_step_view_model(step, idx):
    cfg = sanitize_container_config_for_session(step.get("config") or {})
    if idx != 0:
        cfg["product_source"] = "manual"
        cfg["product_catalogue_id"] = ""
        cfg["selected_product_id"] = ""
        cfg = sanitize_container_config_for_session(cfg)

    packaging_catalogues = get_container_packaging_catalogues()
    product_catalogues = get_container_product_catalogues()

    selected_product = get_container_selected_product(cfg) if idx == 0 else None
    selected_material = get_container_selected_material(cfg)

    products = get_container_products_for_catalogue(cfg) if idx == 0 else Product.objects.none()
    materials = get_container_materials_for_catalogue(cfg)

    request_stub = type("ContainerWorkflowGetRequest", (), {"method": "GET"})()
    form = build_container_form(
        request=request_stub,
        config=cfg,
        selected_product=selected_product,
        selected_material=selected_material,
    )
    apply_container_catalogue_choices(form, packaging_catalogues, product_catalogues)

    step["config"] = cfg
    step["container_form"] = form
    step["container_values"] = {k: cfg.get(k) for k in default_container_config().keys()}
    step["container_ui"] = _build_shared_container_ui_contract(prefix=str(idx))
    step["mode"] = "workflow"
    step["prefix"] = str(idx)

    step["products"] = products
    step["materials"] = materials
    step["selected_product"] = selected_product
    step["selected_material"] = selected_material
    step["selected_product_summary"] = selected_product_summary_container(
        selected_product=selected_product,
        data=cfg,
        mode=cfg.get("mode") or "single",
    )
    step["selected_container_summary"] = selected_container_summary_container(
        selected_material=selected_material,
        data=cfg,
    )
    step["current_mode"] = cfg.get("mode") or "single"
    step["current_product_source"] = cfg.get("product_source") or "manual"
    step["current_container_source"] = cfg.get("container_source") or "manual"
    step["container_top5_rows"] = _inflate_container_top5_rows(step.get("top5", []))
    step["design_candidates"] = step.get("design_candidates") or []
    step["selected_design_candidate_id"] = step.get("selected_design_candidate_id") or cfg.get("selected_design_candidate_id") or ""
    step["notices"] = step.get("notices") or []
    step["analysis_report"] = step.get("analysis_report") or (step.get("result") or {}).get("analysis_report")
    step["threejs_scene"] = step.get("threejs_scene") or (step.get("result") or {}).get("threejs_scene")
    step["product_base_image_url"] = step.get("product_base_image_url") or (step.get("result") or {}).get("product_base_image_url")


def _prepare_bag_step_view_model(step, idx):
    cfg = sanitize_bag_config_for_session(step.get("config") or {})
    if idx != 0:
        cfg["product_source"] = "manual"
        cfg["product_catalogue_id"] = ""
        cfg["selected_product_id"] = ""
        cfg = sanitize_bag_config_for_session(cfg)

    selected_product = get_bag_selected_product(cfg) if idx == 0 else None
    selected_material = get_bag_selected_material(cfg)

    step["config"] = cfg
    step["bag_values"] = {k: cfg.get(k) for k in default_bag_config().keys()}
    step["bag_ui"] = _build_shared_bag_ui_contract(prefix=str(idx))
    step["mode"] = "workflow"
    step["prefix"] = str(idx)

    step["products"] = get_bag_products_for_catalogue(cfg) if idx == 0 else Product.objects.none()
    step["materials"] = get_bag_materials_for_catalogue(cfg)
    step["selected_product"] = selected_product
    step["selected_material"] = selected_material
    step["selected_product_summary"] = selected_product_summary_bag(
        selected_product=selected_product,
        data=cfg,
        mode=cfg.get("mode") or "single",
    )
    step["selected_bag_summary"] = selected_bag_summary_bag(
        selected_material=selected_material,
        data=cfg,
    )
    step["current_mode"] = cfg.get("mode") or "single"
    step["current_product_source"] = cfg.get("product_source") or "manual"
    step["current_bag_source"] = cfg.get("bag_source") or "manual"
    step["allow_product_catalogue"] = idx == 0
    step["analysis_report"] = step.get("analysis_report") or (step.get("result") or {}).get("analysis_report")
    step["threejs_scene"] = step.get("threejs_scene") or (step.get("result") or {}).get("render_data")
    step["design_candidates"] = step.get("design_candidates") or []
    step["selected_design_candidate_id"] = step.get("selected_design_candidate_id") or cfg.get("selected_design_candidate_id") or ""
    step["notices"] = step.get("notices") or []


def _process_container_step(step, steps, idx, post):
    existing_cfg = step.get("config") or {}
    cfg = default_container_config()
    cfg.update(existing_cfg)

    suffix = f"_{idx}"
    cfg["mode"] = normalize_selection_mode({
        "mode": post.get(f"mode{suffix}", post.get(f"mode_{idx}", normalize_selection_mode(cfg))),
        "tool_mode": post.get(f"tool_mode{suffix}", post.get(f"tool_mode_{idx}", "")),
    })
    cfg.pop("tool_mode", None)

    if idx == 0:
        cfg["product_source"] = post.get(
            f"product_source{suffix}",
            post.get(f"product_source_{idx}", cfg.get("product_source", "manual"))
        )
        cfg["product_catalogue_id"] = post.get(
            f"product_catalogue_id{suffix}",
            post.get(f"product_catalogue_id_{idx}", cfg.get("product_catalogue_id", ""))
        )
        cfg["selected_product_id"] = post.get(
            f"selected_product_id{suffix}",
            post.get(f"selected_product_id_{idx}", cfg.get("selected_product_id", ""))
        )
    else:
        cfg["product_source"] = "manual"
        cfg["product_catalogue_id"] = ""
        cfg["selected_product_id"] = ""

    cfg["container_source"] = post.get(
        f"container_source{suffix}",
        post.get(f"container_source_{idx}", cfg.get("container_source", "manual"))
    )
    cfg["product_l"] = post.get(f"product_l{suffix}", post.get(f"product_l_{idx}", cfg.get("product_l", "")))
    cfg["product_w"] = post.get(f"product_w{suffix}", post.get(f"product_w_{idx}", cfg.get("product_w", "")))
    cfg["product_h"] = post.get(f"product_h{suffix}", post.get(f"product_h_{idx}", cfg.get("product_h", "")))
    cfg["product_weight"] = post.get(
        f"product_weight{suffix}",
        post.get(f"product_weight_{idx}", cfg.get("product_weight", ""))
    )
    cfg["desired_qty"] = post.get(
        f"desired_qty{suffix}",
        post.get(f"desired_qty_{idx}", cfg.get("desired_qty", "1"))
    )

    has_prefixed_rotation_inputs = (
        f"r1{suffix}" in post or f"r2{suffix}" in post or f"r3{suffix}" in post
    )
    if has_prefixed_rotation_inputs:
        cfg["r1"] = post.get(f"r1{suffix}") is not None
        cfg["r2"] = post.get(f"r2{suffix}") is not None
        cfg["r3"] = post.get(f"r3{suffix}") is not None
    else:
        cfg["r1"] = _as_bool(post, f"r1_{idx}", cfg.get("r1", True))
        cfg["r2"] = _as_bool(post, f"r2_{idx}", cfg.get("r2", True))
        cfg["r3"] = _as_bool(post, f"r3_{idx}", cfg.get("r3", True))

    cfg["catalogue_id"] = post.get(
        f"catalogue_id{suffix}",
        post.get(f"catalogue_id_{idx}", cfg.get("catalogue_id", ""))
    )
    cfg["container_id"] = post.get(
        f"container_id{suffix}",
        post.get(f"container_id_{idx}", cfg.get("container_id", ""))
    )
    cfg["box_l"] = post.get(f"box_l{suffix}", post.get(f"box_l_{idx}", cfg.get("box_l", "")))
    cfg["box_w"] = post.get(f"box_w{suffix}", post.get(f"box_w_{idx}", cfg.get("box_w", "")))
    cfg["box_h"] = post.get(f"box_h{suffix}", post.get(f"box_h_{idx}", cfg.get("box_h", "")))
    cfg["box_weight"] = post.get(
        f"box_weight{suffix}",
        post.get(f"box_weight_{idx}", cfg.get("box_weight", ""))
    )
    cfg["box_max_payload"] = post.get(
        f"box_max_payload{suffix}",
        post.get(f"box_max_payload_{idx}", cfg.get("box_max_payload", ""))
    )
    cfg["action"] = post.get(
        f"action{suffix}",
        post.get(f"step_action_{idx}", cfg.get("action", "refresh"))
    )
    cfg["selected_design_candidate_id"] = post.get(
        f"selected_design_candidate_id{suffix}",
        post.get(f"selected_design_candidate_id_{idx}", cfg.get("selected_design_candidate_id", "")),
    )

    if idx != 0:
        cfg["product_source"] = "manual"
        cfg["product_catalogue_id"] = ""
        cfg["selected_product_id"] = ""
        cfg = _apply_payload_to_config(cfg, step.get("type"), _selected_input_for_step(steps, idx))

    cfg = sanitize_container_config_for_session(cfg)

    selected_product = get_container_selected_product(cfg) if idx == 0 else None
    selected_material = get_container_selected_material(cfg)
    materials = get_container_materials_for_catalogue(cfg)

    normalized_post = {
        "mode": cfg.get("mode", "single"),
        "action": cfg.get("action", "refresh"),
        "product_source": cfg.get("product_source", "manual"),
        "product_catalogue_id": cfg.get("product_catalogue_id", ""),
        "selected_product_id": cfg.get("selected_product_id", ""),
        "product_l": cfg.get("product_l", ""),
        "product_w": cfg.get("product_w", ""),
        "product_h": cfg.get("product_h", ""),
        "product_weight": cfg.get("product_weight", ""),
        "desired_qty": cfg.get("desired_qty", "1"),
        "container_source": cfg.get("container_source", "manual"),
        "catalogue_id": cfg.get("catalogue_id", ""),
        "container_id": cfg.get("container_id", ""),
        "box_l": cfg.get("box_l", ""),
        "box_w": cfg.get("box_w", ""),
        "box_h": cfg.get("box_h", ""),
        "box_weight": cfg.get("box_weight", ""),
        "box_max_payload": cfg.get("box_max_payload", ""),
        "selected_design_candidate_id": cfg.get("selected_design_candidate_id", ""),
    }
    if cfg.get("r1"):
        normalized_post["r1"] = "on"
    if cfg.get("r2"):
        normalized_post["r2"] = "on"
    if cfg.get("r3"):
        normalized_post["r3"] = "on"

    request_stub = type(
        "ContainerWorkflowPostRequest",
        (),
        {"method": "POST", "POST": normalized_post}
    )()

    form = build_container_form(
        request=request_stub,
        config=cfg,
        selected_product=selected_product,
        selected_material=selected_material,
    )
    apply_container_catalogue_choices(
        form,
        get_container_packaging_catalogues(),
        get_container_product_catalogues(),
    )

    result_payload = None
    image_url = None
    top5_payload = []
    messages = []
    pending_result = None
    analysis_report = None
    threejs_scene = None
    product_base_image_url = None

    if form.is_valid():
        analysis = analyze_container_form(
            form=form,
            config=cfg,
            selected_product=selected_product,
            selected_material=selected_material,
            materials=materials,
        )
        messages = list(analysis.get("messages") or [])
        render_result = analysis.get("result")
        image_url = analysis.get("image_url")
        analysis_report = analysis.get("analysis_report")
        threejs_scene = analysis.get("threejs_scene")
        product_base_image_url = analysis.get("product_base_image_url")
        top5_payload = [
            {
                "material_id": str(row["material"].id),
                "max_qty": row.get("max_qty"),
                "usage": row.get("usage", 0.0),
                "container_vol": row.get("container_vol"),
            }
            for row in (analysis.get("top5") or [])
            if row.get("material") is not None
        ]
        design_candidates = analysis.get("design_candidates") or []
        selected_design_candidate_id = analysis.get("selected_design_candidate_id") or ""

        if render_result is not None and cfg.get("mode") == "design":
            result_payload = dict(render_result)
            selected_design_candidate_id = render_result["candidate_id"]
            cfg["selected_design_candidate_id"] = selected_design_candidate_id
            desired_qty = int(render_result["desired_quantity"])
            units_per_parent = int(render_result["design_quantity"])
            prev = _selected_input_for_step(steps, idx)
            upstream_units = _to_int(prev.get("total_base_units"), 1) if prev else 1
            pending_result = {
                "label": "Designed Container",
                "length": render_result["container_length"],
                "width": render_result["container_width"],
                "height": render_result["container_height"],
                "units_per_parent": units_per_parent,
                "total_base_units": units_per_parent * int(upstream_units or 1),
                "transport_qty": 1,
                "source_step_type": "container",
                "package_type": "container",
                "mode": "design",
                "desired_quantity": desired_qty,
                "design_quantity": units_per_parent,
                "additional_capacity": render_result["additional_capacity"],
                "selected_candidate_id": selected_design_candidate_id,
                "selected_arrangement": render_result["arrangement"],
                "selected_orientation": render_result["product_orientation"],
                "metrics": {"cubicity": render_result["container_cubicity_score"], "volume": render_result["required_container_volume"]},
                "render_data": render_result["render_data"],
            }
            if render_result.get("net_content_weight") is not None:
                pending_result["net_content_weight_g"] = render_result["net_content_weight"]
        elif render_result is not None:
            result_payload = {
                "kind": "container",
                "max_quantity": getattr(render_result, "max_quantity", None),
                "analysis_report": analysis_report,
                "threejs_scene": threejs_scene,
                "product_base_image_url": product_base_image_url,
            }

            desired_qty = int(form.cleaned_data.get("desired_qty") or 1)
            if cfg.get("product_source") == "catalogue" and selected_product and cfg.get("mode") == "optimal":
                desired_qty = int(getattr(selected_product, "desired_qty", 1) or 1)

            if selected_material is not None:
                length = _material_dimension_for_workflow(selected_material, "external_length", "part_length")
                width = _material_dimension_for_workflow(selected_material, "external_width", "part_width")
                height = _material_dimension_for_workflow(selected_material, "external_height", "part_height")
                label = selected_material.part_number
            else:
                length = _to_float(cfg.get("box_l"), 0.0) or 0.0
                width = _to_float(cfg.get("box_w"), 0.0) or 0.0
                height = _to_float(cfg.get("box_h"), 0.0) or 0.0
                label = "Manual Container"

            max_quantity = int(getattr(render_result, "max_quantity", 0) or 0)
            units_per_parent = max_quantity if cfg.get("mode") == "single" else desired_qty
            units_per_parent = max(int(units_per_parent or 1), 1)
            prev = _selected_input_for_step(steps, idx)
            upstream_units = _to_int(prev.get("total_base_units"), 1) if prev else 1

            pending_result = {
                "label": label,
                "length": round(length, 2),
                "width": round(width, 2),
                "height": round(height, 2),
                "units_per_parent": units_per_parent,
                "total_base_units": units_per_parent * int(upstream_units or 1),
                "transport_qty": 1,
                "source_step_type": "container",
                "package_type": "container",
            }
            pending_result = _enrich_package_payload_weight(
                pending_result,
                product_weight_g=_resolve_product_weight_g(cfg, selected_product),
                packaging_weight_g=_resolve_packaging_weight_g(cfg, "box_weight", selected_material),
            )
    else:
        messages = [str(err) for err in form.non_field_errors()]

    step["config"] = cfg
    step["result"] = result_payload
    step["image_url"] = image_url
    step["analysis_report"] = analysis_report
    step["threejs_scene"] = threejs_scene
    step["product_base_image_url"] = product_base_image_url
    step["top5"] = top5_payload
    step["design_candidates"] = locals().get("design_candidates", [])
    step["selected_design_candidate_id"] = locals().get("selected_design_candidate_id", "")
    step["notices"] = analysis.get("notices") if form.is_valid() else []
    step["pending_result"] = pending_result
    step["messages"] = messages
    step["expanded"] = True


def _process_bag_step(step, steps, idx, post):
    existing_cfg = step.get("config") or {}
    cfg = default_bag_config()
    cfg.update(existing_cfg)

    suffix = f"_{idx}"
    cfg["mode"] = normalize_selection_mode({
        "mode": post.get(f"mode{suffix}", post.get(f"mode_{idx}", normalize_selection_mode(cfg))),
        "tool_mode": post.get(f"tool_mode{suffix}", post.get(f"tool_mode_{idx}", "")),
    })
    cfg.pop("tool_mode", None)

    if idx == 0:
        cfg["product_source"] = post.get(
            f"product_source{suffix}",
            post.get(f"product_source_{idx}", cfg.get("product_source", "manual")),
        )
        cfg["product_catalogue_id"] = post.get(
            f"product_catalogue_id{suffix}",
            post.get(f"product_catalogue_id_{idx}", cfg.get("product_catalogue_id", "")),
        )
        cfg["selected_product_id"] = post.get(
            f"selected_product_id{suffix}",
            post.get(f"selected_product_id_{idx}", cfg.get("selected_product_id", "")),
        )
    else:
        cfg["product_source"] = "manual"
        cfg["product_catalogue_id"] = ""
        cfg["selected_product_id"] = ""

    cfg["bag_source"] = post.get(
        f"bag_source{suffix}",
        post.get(f"bag_source_{idx}", cfg.get("bag_source", "manual")),
    )
    cfg["product_l"] = post.get(f"product_l{suffix}", post.get(f"product_l_{idx}", cfg.get("product_l", "")))
    cfg["product_w"] = post.get(f"product_w{suffix}", post.get(f"product_w_{idx}", cfg.get("product_w", "")))
    cfg["product_h"] = post.get(f"product_h{suffix}", post.get(f"product_h_{idx}", cfg.get("product_h", "")))
    cfg["product_weight"] = post.get(
        f"product_weight{suffix}",
        post.get(f"product_weight_{idx}", cfg.get("product_weight", "")),
    )
    cfg["desired_qty"] = post.get(
        f"desired_qty{suffix}",
        post.get(f"desired_qty_{idx}", cfg.get("desired_qty", "1")),
    )
    cfg["catalogue_id"] = post.get(
        f"catalogue_id{suffix}",
        post.get(f"catalogue_id_{idx}", cfg.get("catalogue_id", "")),
    )
    cfg["bag_id"] = post.get(
        f"bag_id{suffix}",
        post.get(f"bag_id_{idx}", cfg.get("bag_id", "")),
    )
    cfg["bag_length"] = post.get(f"bag_length{suffix}", post.get(f"bag_length_{idx}", cfg.get("bag_length", "")))
    cfg["bag_width"] = post.get(f"bag_width{suffix}", post.get(f"bag_width_{idx}", cfg.get("bag_width", "")))
    cfg["bag_weight"] = post.get(
        f"bag_weight{suffix}",
        post.get(f"bag_weight_{idx}", cfg.get("bag_weight", "")),
    )
    cfg["bag_max_payload"] = post.get(
        f"bag_max_payload{suffix}",
        post.get(f"bag_max_payload_{idx}", cfg.get("bag_max_payload", "")),
    )
    cfg["action"] = post.get(
        f"action{suffix}",
        post.get(f"step_action_{idx}", cfg.get("action", "refresh")),
    )
    cfg["selected_design_candidate_id"] = post.get(
        f"selected_design_candidate_id{suffix}",
        post.get(f"selected_design_candidate_id_{idx}", cfg.get("selected_design_candidate_id", "")),
    )

    if cfg["action"] == "browse_product" and idx == 0:
        cfg["selected_product_id"] = ""
    elif cfg["action"] == "clear_product" and idx == 0:
        cfg["selected_product_id"] = ""
    elif cfg["action"] == "browse_packaging":
        cfg["bag_id"] = ""
    elif cfg["action"] == "clear_packaging":
        cfg["bag_id"] = ""

    if idx != 0:
        cfg["product_source"] = "manual"
        cfg["product_catalogue_id"] = ""
        cfg["selected_product_id"] = ""
        cfg = _apply_payload_to_config(cfg, step.get("type"), _selected_input_for_step(steps, idx))

    cfg = sanitize_bag_config_for_session(cfg)

    selected_product = get_bag_selected_product(cfg) if idx == 0 else None
    selected_material = get_bag_selected_material(cfg)
    materials = get_bag_materials_for_catalogue(cfg)

    analysis = analyze_bag_config_shared(
        config=cfg,
        action=cfg.get("action") or "",
        selected_product=selected_product,
        selected_material=selected_material,
        materials=materials,
        media_root=settings.MEDIA_ROOT,
    )

    pending_result = analysis.get("pending_result")
    if pending_result:
        pending_result["source_step_type"] = "bag"
        pending_result["package_type"] = "bag"
        pending_result.setdefault("transport_qty", 1)
        if cfg.get("mode") != "design":
            pending_result = _enrich_package_payload_weight(
                pending_result,
                product_weight_g=_resolve_product_weight_g(cfg, selected_product),
                packaging_weight_g=_resolve_packaging_weight_g(cfg, "bag_weight", selected_material),
            )
        previous = _selected_input_for_step(steps, idx)
        upstream_units = _to_int(previous.get("total_base_units"), 1) if previous else 1
        pending_result["total_base_units"] = int(pending_result.get("units_per_parent") or 1) * int(upstream_units or 1)

    step["config"] = cfg
    step["result"] = analysis.get("result")
    step["image_url"] = analysis.get("image_url")
    step["top5"] = analysis.get("top5") or []
    step["design_candidates"] = analysis.get("design_candidates") or []
    step["selected_design_candidate_id"] = analysis.get("selected_design_candidate_id") or ""
    if step["selected_design_candidate_id"]:
        cfg["selected_design_candidate_id"] = step["selected_design_candidate_id"]
    step["threejs_scene"] = analysis.get("threejs_scene")
    step["notices"] = analysis.get("notices") or []
    step["pending_result"] = pending_result
    step["analysis_report"] = analysis.get("analysis_report")
    step["messages"] = analysis.get("messages") or []
    step["expanded"] = True

def _process_transport_step(step, steps, idx, post):
    cfg = step["config"]
    step["result"] = None
    step["image_url"] = None
    step["image_urls"] = {}
    step["threejs_scene"] = None
    step["pending_result"] = None
    step["auto_hide_product_catalogue"] = False

    cfg["container_source"] = post.get(f"container_source_{idx}", cfg.get("container_source", "manual"))
    cfg["catalogue_id"] = post.get(f"catalogue_id_{idx}", cfg.get("catalogue_id", ""))
    cfg["container_id"] = post.get(f"container_id_{idx}", cfg.get("container_id", ""))
    cfg["container_l"] = post.get(f"container_l_{idx}", cfg.get("container_l", ""))
    cfg["container_w"] = post.get(f"container_w_{idx}", cfg.get("container_w", ""))
    cfg["container_h"] = post.get(f"container_h_{idx}", cfg.get("container_h", ""))
    cfg["max_weight"] = post.get(f"max_weight_{idx}", cfg.get("max_weight", ""))
    cfg["tare_weight"] = post.get(f"tare_weight_{idx}", cfg.get("tare_weight", ""))

    action = post.get(f"step_action_{idx}", "refresh")

    if idx == 0:
        cfg["product_catalogue_id"] = post.get(
            f"transport_product_catalogue_id_{idx}",
            cfg.get("product_catalogue_id", ""),
        )
        cfg["product_id_to_fill"] = post.get(f"transport_product_id_to_fill_{idx}", "")
        cfg["selected_row_index"] = post.get(
            f"transport_selected_row_index_{idx}",
            cfg.get("selected_row_index", ""),
        )

        rows = read_product_rows_raw(post)
        if not rows:
            rows = default_product_rows()
        cfg["product_rows"] = sanitize_transport_rows_for_session(rows)
        step["messages"] = []

    else:
        cfg["product_catalogue_id"] = ""
        cfg["product_id_to_fill"] = ""
        cfg["selected_row_index"] = ""
        inherited_rows = _transport_rows_from_selected(_selected_input_for_step(steps, idx))
        posted_rows = read_product_rows_raw(post)
        cfg["product_rows"] = _merge_transport_inherited_rows(posted_rows or cfg.get("product_rows"), inherited_rows)
        step["messages"] = []

    if action == "select_product" and idx == 0:
        selected_product = Product.objects.filter(id=cfg.get("product_id_to_fill") or None).first()
        try:
            row_idx = int(cfg.get("selected_row_index"))
        except Exception:
            row_idx = None
        if selected_product is not None and row_idx is not None and 0 <= row_idx < len(cfg["product_rows"]):
            row = cfg["product_rows"][row_idx]
            row["name"] = selected_product.product_name or selected_product.product_id or f"Product {row_idx + 1}"
            row["length"] = float(selected_product.product_length)
            row["width"] = float(selected_product.product_width)
            row["height"] = float(selected_product.product_height)
            row["weight"] = float(selected_product.weight or 0)
            row["r1"] = bool(selected_product.rotation_1)
            row["r2"] = bool(selected_product.rotation_2)
            row["r3"] = bool(selected_product.rotation_3)
            cfg["product_rows"] = sanitize_transport_rows_for_session(cfg.get("product_rows") or [])
            cfg["selected_row_index"] = ""
            cfg["product_id_to_fill"] = ""
            step["auto_hide_product_catalogue"] = True

    if action in ("browse_packaging", "clear_packaging"):
        cfg["container_id"] = ""
    elif action == "select_container":
        cfg["container_id"] = post.get(f"container_id_{idx}", cfg.get("container_id", ""))
        selected_material = PackagingMaterial.objects.filter(id=cfg.get("container_id") or None).first()
        if selected_material is not None:
            cfg["container_l"] = float(selected_material.part_length)
            cfg["container_w"] = float(selected_material.part_width)
            cfg["container_h"] = float(selected_material.part_height)

    if cfg.get("container_source") != "catalogue":
        cfg["container_id"] = ""

    step["analysis_ran"] = (
        action == "run_analysis"
        or bool(step.get("analysis_ran") and action in ("refresh", "select_container", "select_product"))
    )
    if step.get("analysis_ran") and action in ("run_analysis", "select_container"):
        _run_transport_analysis(step, steps, idx)

    step["expanded"] = True


def _process_pallet_step(step, steps, idx, post):
    cfg = _read_prefixed_pallet_post(step, idx, post)
    if idx != 0:
        cfg = _apply_payload_to_config(cfg, step.get("type"), _selected_input_for_step(steps, idx))
    _update_pallet_config_on_step(step, cfg)

    action = post.get(f"step_action_{idx}", "refresh")
    step["selected_result_key"] = post.get(
        f"selected_result_key_{idx}",
        step.get("selected_result_key", ""),
    )

    if cfg.get("box_source") != "catalogue":
        step["show_box_catalogue"] = False
    if cfg.get("pallet_source") != "catalogue":
        step["show_pallet_catalogue"] = False

    if action == "browse_box_packaging" and idx == 0:
        step["config"]["selected_box_id"] = ""
        step["show_box_catalogue"] = True

    elif action == "clear_box_packaging" and idx == 0:
        step["config"]["selected_box_id"] = ""
        step["show_box_catalogue"] = True

    elif action == "select_box" and idx == 0:
        step["config"]["selected_box_id"] = post.get(f"selected_box_id_{idx}", "")
        step["show_box_catalogue"] = False

    elif action == "browse_pallet_packaging":
        step["config"]["pallet_id"] = ""
        step["show_pallet_catalogue"] = True

    elif action == "clear_pallet_packaging":
        step["config"]["pallet_id"] = ""
        step["show_pallet_catalogue"] = True

    elif action == "select_pallet":
        step["config"]["pallet_id"] = post.get(f"pallet_id_{idx}", "")
        step["show_pallet_catalogue"] = False

    if (
        idx == 0
        and step["config"].get("box_source") == "catalogue"
        and step["config"].get("box_catalogue_id")
        and not step["config"].get("selected_box_id")
    ):
        step["show_box_catalogue"] = True

    if (
        step["config"].get("pallet_source") == "catalogue"
        and step["config"].get("pallet_catalogue_id")
        and not step["config"].get("pallet_id")
    ):
        step["show_pallet_catalogue"] = True

    if action in ("run_analysis", "select_result"):
        step["analysis_ran"] = True
    else:
        # Catalogue browsing, row selection, source switching, and normal refreshes
        # change the input state. Do not keep re-validating an old incomplete
        # pallet analysis on every render, otherwise messages such as
        # "Please enter max stack height." stay visible while the user is still
        # selecting data.
        step["analysis_ran"] = False
        step["selected_result_key"] = ""

    step["expanded"] = True
    step["messages"] = []

    _run_pallet_analysis_shared(step, steps, idx)




def full_packaging_export_pdf(request):
    workflow = _get_workflow(request)
    report_payload = build_workflow_report_payload(workflow)
    pdf_buffer = build_full_packaging_pdf(report_payload)

    filename = f"packaging-flow-report-{timezone.now().strftime('%Y%m%d-%H%M')}.pdf"
    response = HttpResponse(pdf_buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response

def full_packaging_mode(request):
    workflow = _get_workflow(request)
    steps = workflow["steps"]

    if request.method == "POST":
        action = request.POST.get("action", "")

        if action == "show_add_bar":
            anchor = request.POST.get("after_index", "start")
            workflow["show_add_bar_after"] = anchor
            _save_workflow(request, workflow)
            return redirect("full_packaging_mode")

        if action == "hide_add_bar":
            workflow["show_add_bar_after"] = None
            _save_workflow(request, workflow)
            return redirect("full_packaging_mode")

        if action == "add_step":
            after_index = request.POST.get("after_index", "")
            step_type = request.POST.get("step_type", "container")
            new_step = _new_step(step_type)
            if after_index in ("", "start"):
                steps.append(new_step)
            else:
                idx = _to_int(after_index)
                if idx is not None and 0 <= idx < len(steps):
                    steps.insert(idx + 1, new_step)
                else:
                    steps.append(new_step)
            workflow["show_add_bar_after"] = None
            _save_workflow(request, workflow)
            return redirect("full_packaging_mode")

        if action == "remove_step":
            idx = _to_int(request.POST.get("index"))
            if idx is not None and 0 <= idx < len(steps):
                steps.pop(idx)
                workflow["show_add_bar_after"] = None
                _save_workflow(request, workflow)
            return redirect("full_packaging_mode")

        if action == "toggle_step":
            idx = _to_int(request.POST.get("index"))
            if idx is not None and 0 <= idx < len(steps):
                steps[idx]["expanded"] = not steps[idx]["expanded"]
                workflow["show_add_bar_after"] = None
                _save_workflow(request, workflow)
            return redirect("full_packaging_mode")

        if action == "reset_workflow":
            request.session[SESSION_KEY] = {"steps": [], "show_add_bar_after": None}
            request.session.modified = True
            return redirect("full_packaging_mode")

        if action == "run_step":
            idx = _to_int(request.POST.get("index"))
            if idx is not None and 0 <= idx < len(steps):
                _apply_chained_defaults(steps[idx], steps, idx)
                if steps[idx].get("type") == "bag":
                    _process_bag_step(steps[idx], steps, idx, request.POST)
                elif steps[idx].get("type") == "pallet":
                    _process_pallet_step(steps[idx], steps, idx, request.POST)
                elif steps[idx].get("type") == "transport":
                    _process_transport_step(steps[idx], steps, idx, request.POST)
                else:
                    _process_container_step(steps[idx], steps, idx, request.POST)
                workflow["show_add_bar_after"] = None
                _save_workflow(request, workflow)
            return redirect("full_packaging_mode")

        if action == "use_step_result":
            idx = _to_int(request.POST.get("index"))
            if idx is not None and 0 <= idx < len(steps):
                _apply_chained_defaults(steps[idx], steps, idx)

                if steps[idx].get("type") == "transport":
                    step = steps[idx]
                    step["messages"] = []
                    _run_transport_analysis(step, steps, idx)
                elif steps[idx].get("type") == "pallet":
                    step = steps[idx]
                    _run_pallet_analysis_shared(step, steps, idx)

                pending = _effective_step_output(steps[idx])
                if pending:
                    steps[idx]["selected"] = pending
                    steps[idx]["summary"] = _build_summary(pending)
                    _invalidate_downstream(steps, idx)
                    steps[idx]["selected"] = pending
                    steps[idx]["summary"] = _build_summary(pending)
                    steps[idx]["expanded"] = True
                    workflow["show_add_bar_after"] = None
                    _save_workflow(request, workflow)
            return redirect("full_packaging_mode")

    product_catalogues = visible_product_catalogues(request.user).order_by("name")
    packaging_catalogues = visible_packaging_catalogues(request.user).order_by("name")

    for idx, step in enumerate(steps):
        _apply_chained_defaults(step, steps, idx)
        cfg = step["config"]

        if idx == 0:
            if step.get("type") == "transport":
                step["products"] = Product.objects.filter(
                    catalogue_id=cfg.get("product_catalogue_id") or None
                ).select_related("catalogue").order_by("product_id", "product_name") if cfg.get("product_catalogue_id") else Product.objects.none()
                step["selected_product"] = None
            else:
                step["products"] = Product.objects.filter(
                    catalogue_id=cfg.get("product_catalogue_id") or None
                ).select_related("catalogue").order_by("-created_at") if cfg.get("product_catalogue_id") else Product.objects.none()
                step["selected_product"] = Product.objects.filter(
                    id=cfg.get("selected_product_id") or None
                ).select_related("catalogue").first()
        else:
            step["products"] = Product.objects.none()
            step["selected_product"] = None
            if step.get("type") != "transport":
                cfg["product_source"] = "manual"
                cfg["product_catalogue_id"] = ""
                cfg["selected_product_id"] = ""

        if step.get("type") == "transport":
            step["materials"] = PackagingMaterial.objects.filter(
                catalogue_id=cfg.get("catalogue_id") or None
            ).select_related("catalogue").order_by("part_number") if cfg.get("catalogue_id") else PackagingMaterial.objects.none()
            step["selected_material"] = PackagingMaterial.objects.filter(
                id=cfg.get("container_id") or None
            ).select_related("catalogue").first()
            if step["selected_material"] is not None:
                cfg["container_l"] = float(step["selected_material"].part_length)
                cfg["container_w"] = float(step["selected_material"].part_width)
                cfg["container_h"] = float(step["selected_material"].part_height)
            if idx == 0:
                step["product_rows"] = sanitize_transport_rows_for_session(cfg.get("product_rows") or default_product_rows())
                cfg["product_rows"] = step["product_rows"]
            else:
                inherited_rows = _transport_rows_from_selected(_selected_input_for_step(steps, idx))
                step["product_rows"] = _merge_transport_inherited_rows(cfg.get("product_rows"), inherited_rows)
                cfg["product_rows"] = step["product_rows"]
            step["container_summary"] = selected_container_summary(step["selected_material"], cfg)
            if step.get("analysis_ran"):
                _run_transport_analysis(step, steps, idx)
        elif step.get("type") == "bag":
            _prepare_bag_step_view_model(step, idx)
        elif step.get("type") == "pallet":
            step.setdefault("results_table", [])
            step.setdefault("show_box_catalogue", False)
            step.setdefault("show_pallet_catalogue", False)

            cfg = _extract_pallet_config_from_step(step)
            _update_pallet_config_on_step(step, cfg)

            if idx == 0:
                step["box_materials"] = PackagingMaterial.objects.filter(
                    catalogue_id=cfg.get("box_catalogue_id") or None,
                    packaging_type__in=["BOX", "CRATE"],
                ).select_related("catalogue").order_by("part_number") if cfg.get("box_catalogue_id") else PackagingMaterial.objects.none()

                step["selected_box_material"] = get_selected_box_material(cfg)
            else:
                step["box_materials"] = PackagingMaterial.objects.none()
                step["selected_box_material"] = None
                cfg["box_source"] = "manual"
                cfg["box_catalogue_id"] = ""
                cfg["selected_box_id"] = ""
                step["show_box_catalogue"] = False
                _update_pallet_config_on_step(step, cfg)

            step["pallet_materials"] = PackagingMaterial.objects.filter(
                catalogue_id=cfg.get("pallet_catalogue_id") or None,
                packaging_type="PALLET",
            ).select_related("catalogue").order_by("part_number") if cfg.get("pallet_catalogue_id") else PackagingMaterial.objects.none()

            step["selected_pallet_material"] = get_selected_pallet_material(cfg)

            cfg = _hydrate_pallet_catalogue_values(
                cfg,
                selected_box_material=step.get("selected_box_material"),
                selected_pallet_material=step.get("selected_pallet_material"),
            )
            _update_pallet_config_on_step(step, cfg)

            step["show_box_catalogue"] = bool(step.get("show_box_catalogue")) or (
                idx == 0
                and cfg.get("box_source") == "catalogue"
                and bool(cfg.get("box_catalogue_id"))
                and not cfg.get("selected_box_id")
            )

            step["show_pallet_catalogue"] = bool(step.get("show_pallet_catalogue")) or (
                cfg.get("pallet_source") == "catalogue"
                and bool(cfg.get("pallet_catalogue_id"))
                and not cfg.get("pallet_id")
            )

            step["pallet_ui"] = build_pallet_ui_contract(prefix=str(idx))
            step["pallet_values"] = {
                k: cfg.get(k)
                for k in default_palletization_config().keys()
            }
            step["mode"] = "workflow"
            step["prefix"] = str(idx)

            _compute_pallet_view_model(step, steps, idx)
        else:
            _prepare_container_step_view_model(step, idx)

        step["workflow_overview"] = _build_step_overview(step, steps, idx)

    return render(request, "full_packaging/full_packaging_mode.html", {
        "steps": steps,
        "show_add_bar_after": workflow.get("show_add_bar_after"),
        "product_catalogues": product_catalogues,
        "packaging_catalogues": packaging_catalogues,
    })

def _run_transport_analysis(step, steps, idx):
    cfg = step["config"]
    step["result"] = None
    step["image_url"] = None
    step["image_urls"] = {}
    step["threejs_scene"] = None
    step["pending_result"] = None

    selected_material = PackagingMaterial.objects.filter(
        id=cfg.get("container_id") or None
    ).select_related("catalogue").first()

    if idx == 0:
        raw_rows = cfg.get("product_rows") or default_product_rows()
    else:
        upstream = _selected_input_for_step(steps, idx)
        inherited_rows = _transport_rows_from_selected(upstream)
        raw_rows = _merge_transport_inherited_rows(cfg.get("product_rows"), inherited_rows)
        cfg["product_rows"] = sanitize_transport_rows_for_session(raw_rows)

    analysis = analyze_transport_config(
        cfg,
        raw_rows,
        selected_material=selected_material,
        media_root=settings.MEDIA_ROOT,
    )

    cfg["product_rows"] = analysis["safe_rows"]
    step["product_rows"] = analysis["safe_rows"]
    step["container_summary"] = selected_container_summary(selected_material, cfg)
    step["messages"] = analysis["messages"]

    if not analysis["ok"]:
        return

    step["result"] = analysis["serialized_result"]
    step["image_url"] = analysis["image_url"]
    step["image_urls"] = analysis.get("image_urls") or {}
    transport_scene = analysis["threejs_scene"]
    if idx > 0:
        transport_scene = _decorate_transport_scene_with_pallet_visualization(
            transport_scene,
            _direct_pallet_visualization_input(steps, idx),
        )
    step["threejs_scene"] = transport_scene

    prev = _selected_input_for_step(steps, idx)
    upstream_units = prev.get("total_base_units", 1) if prev else 1

    step["pending_result"] = build_transport_pending_result(
        analysis["container"],
        analysis["result"],
        selected_material=selected_material,
        upstream_units=upstream_units,
    )
    summary = (analysis.get("serialized_result") or {}).get("summary", {}) or {}
    gross_weight = _to_float(summary.get("gross_weight"), None)
    if gross_weight is not None and step.get("pending_result"):
        step["pending_result"]["weight_kg"] = round(gross_weight, 3)
        step["pending_result"]["weight_g"] = round(gross_weight * 1000.0, 3)
    if step.get("pending_result"):
        step["pending_result"].setdefault("transport_qty", 1)
        step["pending_result"]["source_step_type"] = "transport"
        step["pending_result"]["package_type"] = "transport_unit"
