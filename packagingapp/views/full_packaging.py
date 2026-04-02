from django.conf import settings
from django.shortcuts import render, redirect

from ..models import PackagingCatalogue, PackagingMaterial, ProductCatalogue, Product
from ..utils.box_selection.engine import run_mode1_and_render, compute_max_quantity_only

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
    cfg["product_source"] = "manual"
    cfg["product_catalogue_id"] = ""
    cfg["selected_product_id"] = ""
    cfg["product_l"] = prev["length"]
    cfg["product_w"] = prev["width"]
    cfg["product_h"] = prev["height"]


def _process_container_step(step, steps, idx, post):
    cfg = step["config"]
    messages = []
    step["top5"] = []
    step["result"] = None
    step["image_url"] = None
    step["pending_result"] = None

    cfg["mode"] = post.get(f"mode_{idx}", cfg.get("mode", "single"))

    # only first step may use product catalogue
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

    # action state updates
    if action == "browse_product" and idx == 0:
        cfg["selected_product_id"] = ""
    elif action == "clear_product" and idx == 0:
        cfg["selected_product_id"] = ""
    elif action == "select_product" and idx == 0:
        cfg["selected_product_id"] = post.get(f"selected_product_id_{idx}", "")
    elif action == "browse_packaging":
        cfg["container_id"] = ""
    elif action == "clear_container":
        cfg["container_id"] = ""
    elif action in ("select_container", "select_candidate"):
        cfg["container_id"] = post.get(f"container_id_{idx}", cfg.get("container_id", ""))

    mode = cfg["mode"]
    product_source = cfg["product_source"]
    container_source = cfg["container_source"]

    selected_product = Product.objects.filter(id=cfg.get("selected_product_id") or None).select_related("catalogue").first()
    selected_material = PackagingMaterial.objects.filter(id=cfg.get("container_id") or None).select_related("catalogue").first()

    # resolve product
    product = None
    if product_source == "catalogue":
        if selected_product:
            product = (float(selected_product.product_length), float(selected_product.product_width), float(selected_product.product_height))
            r1 = 1 if selected_product.rotation_1 else 0
            r2 = 1 if selected_product.rotation_2 else 0
            r3 = 1 if selected_product.rotation_3 else 0
        else:
            r1 = 1 if cfg.get("r1") else 0
            r2 = 1 if cfg.get("r2") else 0
            r3 = 1 if cfg.get("r3") else 0
    else:
        product = (_to_float(cfg.get("product_l")), _to_float(cfg.get("product_w")), _to_float(cfg.get("product_h")))
        r1 = 1 if cfg.get("r1") else 0
        r2 = 1 if cfg.get("r2") else 0
        r3 = 1 if cfg.get("r3") else 0

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
                    container = (float(selected_material.part_length), float(selected_material.part_width), float(selected_material.part_height))

        if not messages and container and product:
            result = run_mode1_and_render(product, container, r1, r2, r3, settings.MEDIA_ROOT)
            step["image_url"] = settings.MEDIA_URL + result.image_rel_path
            step["result"] = {"max_quantity": result.max_quantity}
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

            if action == "select_candidate" and selected_material:
                container = (float(selected_material.part_length), float(selected_material.part_width), float(selected_material.part_height))
                result = run_mode1_and_render(product, container, r1, r2, r3, settings.MEDIA_ROOT, draw_limit=desired_qty)
                step["image_url"] = settings.MEDIA_URL + result.image_rel_path
                step["result"] = {"max_quantity": result.max_quantity}
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
            new_step = _new_container_step()
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
                _process_container_step(steps[idx], steps, idx, request.POST)
                workflow["show_add_bar_after"] = None
                _save_workflow(request, workflow)
            return redirect("full_packaging_mode")

        if action == "use_step_result":
            idx = _to_int(request.POST.get("index"))
            if idx is not None and 0 <= idx < len(steps):
                pending = steps[idx].get("pending_result")
                if pending:
                    steps[idx]["selected"] = pending
                    steps[idx]["summary"] = _build_summary(pending)

                    _invalidate_downstream(steps, idx)

                    # preserve current step after invalidation
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

        # only first step gets product catalogue features
        if idx == 0:
            step["products"] = Product.objects.filter(
                catalogue_id=cfg.get("product_catalogue_id") or None
            ).select_related("catalogue").order_by("-created_at") if cfg.get("product_catalogue_id") else Product.objects.none()
            step["selected_product"] = Product.objects.filter(
                id=cfg.get("selected_product_id") or None
            ).select_related("catalogue").first()
        else:
            step["products"] = Product.objects.none()
            step["selected_product"] = None
            cfg["product_source"] = "manual"
            cfg["product_catalogue_id"] = ""
            cfg["selected_product_id"] = ""

        step["materials"] = PackagingMaterial.objects.filter(
            catalogue_id=cfg.get("catalogue_id") or None
        ).select_related("catalogue").order_by("part_number") if cfg.get("catalogue_id") else PackagingMaterial.objects.none()

        step["selected_material"] = PackagingMaterial.objects.filter(
            id=cfg.get("container_id") or None
        ).select_related("catalogue").first()

    return render(request, 'full_packaging/full_packaging_mode.html', {
        'steps': steps,
        'show_add_bar_after': workflow.get('show_add_bar_after'),
        'product_catalogues': product_catalogues,
        'packaging_catalogues': packaging_catalogues,
    })