from django.conf import settings
from django.shortcuts import render, redirect

from ..models import PackagingCatalogue, PackagingMaterial, ProductCatalogue, Product
from ..utils.box_selection.engine import run_mode1_and_render, compute_max_quantity_only
from ..utils.bag_selection.engine import (
    build_required_bag_options,
    best_usage_for_bag,
    run_bag_mode1_and_render,
)
from ..tools.palletization.presenter import (
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
from ..views.palletization import _build_shared_pallet_ui_contract

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


SESSION_KEY = "full_packaging_mode_session"


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
        "top5": [],
        "pending_result": None,
        "config": {
            "mode": "single",
            "product_source": "manual",
            "container_source": "manual",
            "product_catalogue_id": "",
            "selected_product_id": "",
            "product_l": "",
            "product_w": "",
            "product_h": "",
            "product_weight": "",
            "desired_qty": 1,
            "r1": True,
            "r2": True,
            "r3": True,
            "catalogue_id": "",
            "container_id": "",
            "box_l": "",
            "box_w": "",
            "box_h": "",
        },
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
        "pending_result": None,
        "config": {
            "mode": "single",
            "product_source": "manual",
            "bag_source": "manual",
            "product_catalogue_id": "",
            "selected_product_id": "",
            "product_l": "",
            "product_w": "",
            "product_h": "",
            "desired_qty": 1,
            "catalogue_id": "",
            "bag_id": "",
            "bag_length": "",
            "bag_width": "",
        },
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
    step["pending_result"] = None
    step["results_table"] = []

    if not step.get("analysis_ran"):
        step["messages"] = []
        return

    cfg = _extract_pallet_config_from_step(step)
    _update_pallet_config_on_step(step, cfg)

    selected_box_material = get_selected_box_material(cfg) if idx == 0 else None
    selected_pallet_material = get_selected_pallet_material(cfg)

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
    image_rel_path = serialized.get("image_rel_path")
    step["image_url"] = settings.MEDIA_URL + image_rel_path if image_rel_path else None

    selected_row = serialized.get("selected_result")
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


def _selected_input_for_step(steps, idx):
    if idx <= 0:
        return None
    return steps[idx - 1].get("selected")


def _build_summary(selected):
    if not selected:
        return ""
    return (
        f'{selected.get("label", "")} | '
        f'{selected.get("length")} × {selected.get("width")} × {selected.get("height")} mm | '
        f'units per parent: {selected.get("units_per_parent", 1)} | '
        f'total base units: {selected.get("total_base_units", 1)}'
    )


def _apply_chained_defaults(step, steps, idx):
    prev = _selected_input_for_step(steps, idx)
    if not prev:
        return

    cfg = step["config"]
    if step.get("type") == "pallet":
        cfg["box_source"] = "manual"
        cfg["box_catalogue_id"] = ""
        cfg["selected_box_id"] = ""
        cfg["box_l"] = prev["length"]
        cfg["box_w"] = prev["width"]
        cfg["box_h"] = prev["height"]
        return

    if step.get("type") == "transport":
        cfg["product_catalogue_id"] = ""
        cfg["product_id_to_fill"] = ""
        cfg["selected_row_index"] = ""
        cfg["product_rows"] = _transport_rows_from_selected(prev)
        return

    cfg["product_source"] = "manual"
    cfg["product_catalogue_id"] = ""
    cfg["selected_product_id"] = ""
    cfg["product_l"] = prev["length"]
    cfg["product_w"] = prev["width"]
    cfg["product_h"] = prev["height"]


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
    tolerance = 2.0
    sealing_area = 10.0

    candidates = []

    box_length_a = bag_len - tolerance - bh
    box_width_a = bag_w - tolerance - sealing_area - bh
    if box_length_a > 0 and box_width_a > 0:
        candidates.append((box_length_a, box_width_a))

    box_length_b = bag_w - tolerance - bh
    box_width_b = bag_len - tolerance - sealing_area - bh
    if box_length_b > 0 and box_width_b > 0:
        candidates.append((box_length_b, box_width_b))

    if not candidates:
        return None

    valid_candidates = [(L, W) for (L, W) in candidates if bl <= L and bw <= W]
    if valid_candidates:
        bag_box_length, bag_box_width = min(valid_candidates, key=lambda t: (t[0] * t[1], t[0] + t[1]))
    else:
        bag_box_length, bag_box_width = min(candidates, key=lambda t: (t[0] * t[1], t[0] + t[1]))

    return (round(bag_box_length, 2), round(bag_box_width, 2), round(bh, 2))


def _process_container_step(step, steps, idx, post):
    cfg = step["config"]
    messages = []
    step["top5"] = []
    step["result"] = None
    step["image_url"] = None
    step["pending_result"] = None

    cfg["mode"] = post.get(f"mode_{idx}", cfg.get("mode", "single"))

    if idx == 0:
        cfg["product_source"] = post.get(f"product_source_{idx}", cfg.get("product_source", "manual"))
        cfg["product_catalogue_id"] = post.get(f"product_catalogue_id_{idx}", cfg.get("product_catalogue_id", ""))
        cfg["selected_product_id"] = post.get(f"selected_product_id_{idx}", cfg.get("selected_product_id", ""))
    else:
        cfg["product_source"] = "manual"
        cfg["product_catalogue_id"] = ""
        cfg["selected_product_id"] = ""

    cfg["container_source"] = post.get(f"container_source_{idx}", cfg.get("container_source", "manual"))
    cfg["product_l"] = post.get(f"product_l_{idx}", cfg.get("product_l", ""))
    cfg["product_w"] = post.get(f"product_w_{idx}", cfg.get("product_w", ""))
    cfg["product_h"] = post.get(f"product_h_{idx}", cfg.get("product_h", ""))
    cfg["product_weight"] = post.get(f"product_weight_{idx}", cfg.get("product_weight", ""))
    cfg["desired_qty"] = _to_int(post.get(f"desired_qty_{idx}"), cfg.get("desired_qty", 1)) or 1
    cfg["r1"] = _as_bool(post, f"r1_{idx}", cfg.get("r1", True))
    cfg["r2"] = _as_bool(post, f"r2_{idx}", cfg.get("r2", True))
    cfg["r3"] = _as_bool(post, f"r3_{idx}", cfg.get("r3", True))
    cfg["catalogue_id"] = post.get(f"catalogue_id_{idx}", cfg.get("catalogue_id", ""))
    cfg["container_id"] = post.get(f"container_id_{idx}", cfg.get("container_id", ""))
    cfg["box_l"] = post.get(f"box_l_{idx}", cfg.get("box_l", ""))
    cfg["box_w"] = post.get(f"box_w_{idx}", cfg.get("box_w", ""))
    cfg["box_h"] = post.get(f"box_h_{idx}", cfg.get("box_h", ""))

    action = post.get(f"step_action_{idx}", "refresh")

    if action == "browse_product" and idx == 0:
        cfg["selected_product_id"] = ""
    elif action == "clear_product" and idx == 0:
        cfg["selected_product_id"] = ""
    elif action == "select_product" and idx == 0:
        cfg["selected_product_id"] = post.get(f"selected_product_id_{idx}", "")
    elif action == "browse_packaging":
        cfg["container_id"] = ""
    elif action == "clear_packaging":
        cfg["container_id"] = ""
    elif action in ("select_container", "select_candidate"):
        cfg["container_id"] = post.get(f"container_id_{idx}", cfg.get("container_id", ""))

    mode = cfg["mode"]
    product_source = cfg["product_source"]
    container_source = cfg["container_source"]

    selected_product = Product.objects.filter(id=cfg.get("selected_product_id") or None).select_related("catalogue").first()
    selected_material = PackagingMaterial.objects.filter(id=cfg.get("container_id") or None).select_related("catalogue").first()

    product, r1, r2, r3 = _resolve_product_for_container(cfg, selected_product)

    if mode == "optimal" and product_source == "catalogue" and selected_product:
        desired_qty = int(selected_product.desired_qty or 1)
    else:
        desired_qty = int(cfg.get("desired_qty") or 1)

    if r1 == 0 and r2 == 0 and r3 == 0:
        messages.append("Please enable at least one rotation option.")

    if mode == "single" and action in ("run_single", "select_container") and not messages:
        container = None
        if product_source == "catalogue" and not selected_product:
            messages.append("Please select a product from the product catalogue.")
        elif product_source == "manual" and (not product or None in product):
            messages.append("Please enter product dimensions.")

        if not messages:
            if container_source == "manual":
                container = (_to_float(cfg.get("box_l")), _to_float(cfg.get("box_w")), _to_float(cfg.get("box_h")))
                if None in container:
                    messages.append("Please enter all manual container dimensions (L/W/H).")
            else:
                if not selected_material:
                    messages.append("Please select a packaging item from the catalogue table.")
                else:
                    container = (
                        float(selected_material.part_length),
                        float(selected_material.part_width),
                        float(selected_material.part_height),
                    )

        if not messages and container and product:
            result = run_mode1_and_render(product, container, r1, r2, r3, settings.MEDIA_ROOT)
            step["image_url"] = settings.MEDIA_URL + result.image_rel_path
            step["result"] = {"kind": "container", "max_quantity": result.max_quantity}
            label = selected_material.part_number if selected_material else "Manual Container"
            base_units = desired_qty if desired_qty else 1
            step["pending_result"] = {
                "label": label,
                "length": round(container[0], 2),
                "width": round(container[1], 2),
                "height": round(container[2], 2),
                "units_per_parent": desired_qty,
                "total_base_units": base_units,
            }

    if mode == "optimal" and action in ("find_top5", "select_candidate") and not messages:
        if product_source == "catalogue" and not selected_product:
            messages.append("Please select a product from the product catalogue.")
        elif product_source == "manual" and (not product or None in product):
            messages.append("Please enter product dimensions.")
        elif not cfg.get("catalogue_id"):
            messages.append("Please select a packaging catalogue.")

        materials = PackagingMaterial.objects.filter(catalogue_id=cfg.get("catalogue_id")).select_related("catalogue").order_by("part_number") if cfg.get("catalogue_id") else PackagingMaterial.objects.none()
        if not messages:
            product_vol = product[0] * product[1] * product[2]
            scored = []
            for m in materials:
                container = (float(m.part_length), float(m.part_width), float(m.part_height))
                max_qty = compute_max_quantity_only(product, container, r1, r2, r3)
                if max_qty >= desired_qty:
                    container_vol = float(m.part_volume) if m.part_volume is not None else (container[0] * container[1] * container[2])
                    usage = (desired_qty * product_vol) / container_vol if container_vol > 0 else 0.0
                    scored.append({"material": m, "max_qty": max_qty, "usage": usage, "container_vol": container_vol})

            scored.sort(key=lambda x: (-x["usage"], x["container_vol"]))
            step["top5"] = [{
                "id": str(row["material"].id),
                "part_number": row["material"].part_number,
                "length": round(float(row["material"].part_length), 2),
                "width": round(float(row["material"].part_width), 2),
                "height": round(float(row["material"].part_height), 2),
                "max_qty": row["max_qty"],
                "usage_pct": round(row["usage"] * 100, 2),
            } for row in scored[:5]]

            if action == "select_candidate":
                if not selected_material:
                    messages.append("Please select one of the Top 5 containers.")
                else:
                    container = (
                        float(selected_material.part_length),
                        float(selected_material.part_width),
                        float(selected_material.part_height),
                    )
                    result = run_mode1_and_render(product, container, r1, r2, r3, settings.MEDIA_ROOT, draw_limit=desired_qty)
                    step["image_url"] = settings.MEDIA_URL + result.image_rel_path
                    step["result"] = {"kind": "container", "max_quantity": result.max_quantity}
                    step["pending_result"] = {
                        "label": selected_material.part_number,
                        "length": round(container[0], 2),
                        "width": round(container[1], 2),
                        "height": round(container[2], 2),
                        "units_per_parent": desired_qty,
                        "total_base_units": desired_qty,
                    }

    step["messages"] = messages
    step["expanded"] = True


def _process_bag_step(step, steps, idx, post):
    cfg = step["config"]
    messages = []
    step["top5"] = []
    step["result"] = None
    step["image_url"] = None
    step["pending_result"] = None

    cfg["mode"] = post.get(f"mode_{idx}", cfg.get("mode", "single"))

    if idx == 0:
        cfg["product_source"] = post.get(f"product_source_{idx}", cfg.get("product_source", "manual"))
        cfg["product_catalogue_id"] = post.get(f"product_catalogue_id_{idx}", cfg.get("product_catalogue_id", ""))
        cfg["selected_product_id"] = post.get(f"selected_product_id_{idx}", cfg.get("selected_product_id", ""))
    else:
        cfg["product_source"] = "manual"
        cfg["product_catalogue_id"] = ""
        cfg["selected_product_id"] = ""

    cfg["bag_source"] = post.get(f"bag_source_{idx}", cfg.get("bag_source", "manual"))
    cfg["product_l"] = post.get(f"product_l_{idx}", cfg.get("product_l", ""))
    cfg["product_w"] = post.get(f"product_w_{idx}", cfg.get("product_w", ""))
    cfg["product_h"] = post.get(f"product_h_{idx}", cfg.get("product_h", ""))
    cfg["desired_qty"] = _to_int(post.get(f"desired_qty_{idx}"), cfg.get("desired_qty", 1)) or 1
    cfg["catalogue_id"] = post.get(f"catalogue_id_{idx}", cfg.get("catalogue_id", ""))
    cfg["bag_id"] = post.get(f"bag_id_{idx}", cfg.get("bag_id", ""))
    cfg["bag_length"] = post.get(f"bag_length_{idx}", cfg.get("bag_length", ""))
    cfg["bag_width"] = post.get(f"bag_width_{idx}", cfg.get("bag_width", ""))

    action = post.get(f"step_action_{idx}", "refresh")

    if action == "browse_product" and idx == 0:
        cfg["selected_product_id"] = ""
    elif action == "clear_product" and idx == 0:
        cfg["selected_product_id"] = ""
    elif action == "select_product" and idx == 0:
        cfg["selected_product_id"] = post.get(f"selected_product_id_{idx}", "")
    elif action == "browse_packaging":
        cfg["bag_id"] = ""
    elif action == "clear_packaging":
        cfg["bag_id"] = ""
    elif action in ("select_bag", "select_candidate"):
        cfg["bag_id"] = post.get(f"bag_id_{idx}", cfg.get("bag_id", ""))

    mode = cfg["mode"]
    product_source = cfg["product_source"]
    bag_source = cfg["bag_source"]

    selected_product = Product.objects.filter(id=cfg.get("selected_product_id") or None).select_related("catalogue").first()
    selected_material = PackagingMaterial.objects.filter(id=cfg.get("bag_id") or None).select_related("catalogue").first()

    product = _resolve_product_for_bag(cfg, selected_product)

    if mode == "optimal" and product_source == "catalogue" and selected_product:
        desired_qty = int(selected_product.desired_qty or 1)
    else:
        desired_qty = int(cfg.get("desired_qty") or 1)

    if mode == "single" and action in ("run_single", "select_bag"):
        bag = None

        if product_source == "catalogue" and not selected_product:
            messages.append("Please select a product from the product catalogue.")
        elif product_source == "manual" and (not product or None in product):
            messages.append("Please enter product dimensions.")

        if not messages:
            if bag_source == "manual":
                bag_l = _to_float(cfg.get("bag_length"))
                bag_w = _to_float(cfg.get("bag_width"))
                if bag_l is None or bag_w is None:
                    messages.append("Please enter bag length and width.")
                else:
                    bag = (bag_l, bag_w)
            else:
                if not selected_material:
                    messages.append("Please select a bag from the packaging catalogue.")
                else:
                    bag = (
                        float(selected_material.part_length),
                        float(selected_material.part_width),
                    )

        if not messages and bag is not None and product is not None:
            req = build_required_bag_options(product[0], product[1], product[2], desired_qty)
            required_bags = req["required"]
            best = best_usage_for_bag(bag[0], bag[1], required_bags)

            step["result"] = {
                "kind": "bag",
                "desired_qty": desired_qty,
                "smooth_qty": req["smooth_qty"],
                "fits": best is not None,
                "bag_len": bag[0],
                "bag_w": bag[1],
                "best_required": (best["req_len"], best["req_w"]) if best else None,
                "usage": best["usage"] if best else 0.0,
                "required_bags": required_bags,
                "usage_pct": round((best["usage"] if best else 0.0) * 100, 2),
            }

            if best is not None:
                render_res = run_bag_mode1_and_render(
                    product=product,
                    selected_bag=(bag[0], bag[1]),
                    desired_qty=desired_qty,
                    solutions=req["solutions"],
                    media_root=settings.MEDIA_ROOT,
                    draw_limit=desired_qty,
                )
                step["image_url"] = settings.MEDIA_URL + render_res.image_rel_path
                bag_box = _resolve_visual_bag_box((bag[0], bag[1]), render_res.inner_box)
                if bag_box:
                    length, width, height = bag_box
                else:
                    length, width, height = (
                        round(render_res.inner_box[0], 2),
                        round(render_res.inner_box[1], 2),
                        round(render_res.inner_box[2], 2),
                    )
                label = selected_material.part_number if selected_material else "Manual Bag"
                step["pending_result"] = {
                    "label": label,
                    "length": length,
                    "width": width,
                    "height": height,
                    "units_per_parent": desired_qty,
                    "total_base_units": desired_qty,
                }

    if mode == "optimal" and action in ("find_top5", "select_candidate"):
        if product_source == "catalogue" and not selected_product:
            messages.append("Please select a product from the product catalogue.")
        elif product_source == "manual" and (not product or None in product):
            messages.append("Please enter product dimensions.")
        elif not cfg.get("catalogue_id"):
            messages.append("Please select a packaging catalogue.")

        materials = PackagingMaterial.objects.filter(
            catalogue_id=cfg.get("catalogue_id") or None,
            packaging_type="BAG",
        ).select_related("catalogue").order_by("part_number") if cfg.get("catalogue_id") else PackagingMaterial.objects.none()

        if not messages:
            req = build_required_bag_options(product[0], product[1], product[2], desired_qty)
            required_bags = req["required"]
            scored = []

            for m in materials:
                bag_len = float(m.part_length or 0)
                bag_w = float(m.part_width or 0)
                if bag_len <= 0 or bag_w <= 0:
                    continue
                best = best_usage_for_bag(bag_len, bag_w, required_bags)
                if best is not None:
                    scored.append({
                        "material": m,
                        "bag_len": bag_len,
                        "bag_w": bag_w,
                        "usage": best["usage"],
                        "best_required": (best["req_len"], best["req_w"]),
                        "bag_area": bag_len * bag_w,
                    })

            scored.sort(key=lambda x: (-x["usage"], x["bag_area"]))
            step["top5"] = [{
                "id": str(row["material"].id),
                "part_number": row["material"].part_number,
                "description": row["material"].part_description,
                "branding": row["material"].branding,
                "bag_len": round(row["bag_len"], 2),
                "bag_w": round(row["bag_w"], 2),
                "usage": round(row["usage"], 4),
                "usage_pct": round(row["usage"] * 100, 2),
                "best_required": (round(row["best_required"][0], 2), round(row["best_required"][1], 2)),
            } for row in scored[:5]]

            if action == "select_candidate":
                if not selected_material:
                    messages.append("Please select one of the Top 5 bags.")
                else:
                    bag = (float(selected_material.part_length), float(selected_material.part_width))
                    best = best_usage_for_bag(bag[0], bag[1], required_bags)
                    step["result"] = {
                        "kind": "bag",
                        "desired_qty": desired_qty,
                        "smooth_qty": req["smooth_qty"],
                        "fits": best is not None,
                        "bag_len": bag[0],
                        "bag_w": bag[1],
                        "best_required": (best["req_len"], best["req_w"]) if best else None,
                        "usage": best["usage"] if best else 0.0,
                        "required_bags": required_bags,
                        "usage_pct": round((best["usage"] if best else 0.0) * 100, 2),
                    }
                    if best is not None:
                        render_res = run_bag_mode1_and_render(
                            product=product,
                            selected_bag=(bag[0], bag[1]),
                            desired_qty=desired_qty,
                            solutions=req["solutions"],
                            media_root=settings.MEDIA_ROOT,
                            draw_limit=desired_qty,
                        )
                        step["image_url"] = settings.MEDIA_URL + render_res.image_rel_path
                        bag_box = _resolve_visual_bag_box((bag[0], bag[1]), render_res.inner_box)
                        if bag_box:
                            length, width, height = bag_box
                        else:
                            length, width, height = (
                                round(render_res.inner_box[0], 2),
                                round(render_res.inner_box[1], 2),
                                round(render_res.inner_box[2], 2),
                            )
                        step["pending_result"] = {
                            "label": selected_material.part_number,
                            "length": length,
                            "width": width,
                            "height": height,
                            "units_per_parent": desired_qty,
                            "total_base_units": desired_qty,
                        }

    step["messages"] = messages
    step["expanded"] = True



def _process_transport_step(step, steps, idx, post):
    cfg = step["config"]
    step["result"] = None
    step["image_url"] = None
    step["pending_result"] = None
    step["auto_hide_product_catalogue"] = False

    cfg["container_source"] = post.get(f"container_source_{idx}", cfg.get("container_source", "manual"))
    cfg["catalogue_id"] = post.get(f"catalogue_id_{idx}", cfg.get("catalogue_id", ""))
    cfg["container_id"] = post.get(f"container_id_{idx}", cfg.get("container_id", ""))
    cfg["container_l"] = post.get(f"container_l_{idx}", cfg.get("container_l", ""))
    cfg["container_w"] = post.get(f"container_w_{idx}", cfg.get("container_w", ""))
    cfg["container_h"] = post.get(f"container_h_{idx}", cfg.get("container_h", ""))
    cfg["max_weight"] = post.get(f"max_weight_{idx}", cfg.get("max_weight", ""))

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
        cfg["product_rows"] = _transport_rows_from_selected(_selected_input_for_step(steps, idx))
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

    elif action in (
        "browse_box_packaging",
        "clear_box_packaging",
        "select_box",
        "browse_pallet_packaging",
        "clear_pallet_packaging",
        "select_pallet",
    ):
        step["analysis_ran"] = step.get("analysis_ran", False)

    elif action == "refresh":
        step["analysis_ran"] = step.get("analysis_ran", False)

    step["expanded"] = True
    step["messages"] = []

    _run_pallet_analysis_shared(step, steps, idx)



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

                pending = steps[idx].get("pending_result")
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

    product_catalogues = ProductCatalogue.objects.all().order_by("name")
    packaging_catalogues = PackagingCatalogue.objects.all().order_by("name")

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
                step["product_rows"] = _transport_rows_from_selected(_selected_input_for_step(steps, idx))
                cfg["product_rows"] = step["product_rows"]
            step["container_summary"] = selected_container_summary(step["selected_material"], cfg)
            if step.get("analysis_ran"):
                _run_transport_analysis(step, steps, idx)
        elif step.get("type") == "bag":
            step["materials"] = PackagingMaterial.objects.filter(
                catalogue_id=cfg.get("catalogue_id") or None,
                packaging_type="BAG",
            ).select_related("catalogue").order_by("part_number") if cfg.get("catalogue_id") else PackagingMaterial.objects.none()
            step["selected_material"] = PackagingMaterial.objects.filter(
                id=cfg.get("bag_id") or None
            ).select_related("catalogue").first()
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

            step["pallet_ui"] = _build_shared_pallet_ui_contract(prefix=str(idx))
            step["pallet_values"] = {
                k: cfg.get(k)
                for k in default_palletization_config().keys()
            }
            step["mode"] = "workflow"
            step["prefix"] = str(idx)

            _compute_pallet_view_model(step, steps, idx)
        else:
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
    step["pending_result"] = None

    selected_material = PackagingMaterial.objects.filter(
        id=cfg.get("container_id") or None
    ).select_related("catalogue").first()

    if idx == 0:
        raw_rows = cfg.get("product_rows") or default_product_rows()
    else:
        upstream = _selected_input_for_step(steps, idx)
        raw_rows = _transport_rows_from_selected(upstream)
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

    prev = _selected_input_for_step(steps, idx)
    upstream_units = prev.get("total_base_units", 1) if prev else 1

    step["pending_result"] = build_transport_pending_result(
        analysis["container"],
        analysis["result"],
        selected_material=selected_material,
        upstream_units=upstream_units,
    )
