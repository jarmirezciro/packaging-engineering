from django.conf import settings
from django.shortcuts import render, redirect

from ..models import PackagingCatalogue, PackagingMaterial
from ..utils.box_selection.engine import run_mode1_and_render, compute_max_quantity_only
from ..utils.bag_selection.engine import (
    build_required_bag_options,
    best_usage_for_bag,
    run_bag_mode1_and_render,
)
from ..utils.palletization.engine import (
    run_palletization_analysis,
    render_selected_result,
)
from ..utils.container_tool.engine import run_container_tool


SESSION_KEY = "full_packaging_mode_session"


# =========================================================
# Session helpers
# =========================================================

def _init_workflow_session(request):
    if SESSION_KEY not in request.session:
        request.session[SESSION_KEY] = {
            "steps": [],
            "show_add_bar_after": None,   # None | "start" | step index
        }
        request.session.modified = True


def _get_workflow(request):
    _init_workflow_session(request)
    return request.session[SESSION_KEY]


def _save_workflow(request, workflow):
    request.session[SESSION_KEY] = workflow
    request.session.modified = True


def _new_step(step_type):
    return {
        "type": step_type,              # container | bag | pallet | transport
        "expanded": True,
        "selected": None,
        "summary": "",
        "candidates": [],
        "result_image_url": None,
        "config": {},
        "messages": [],
    }


def _invalidate_downstream(steps, start_idx):
    for i in range(start_idx + 1, len(steps)):
        steps[i]["selected"] = None
        steps[i]["summary"] = ""
        steps[i]["candidates"] = []
        steps[i]["result_image_url"] = None
        steps[i]["messages"] = ["This step was cleared because an upstream step changed."]


# =========================================================
# Common helpers
# =========================================================

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


def _checked(post, key):
    return 1 if post.get(key) in ("1", "true", "True", "on", "yes") else 0


def _get_selected_input_for_step(steps, idx):
    if idx <= 0:
        return None
    prev = steps[idx - 1].get("selected")
    return prev if prev else None


def _build_selected_summary(selected):
    if not selected:
        return ""
    return (
        f'{selected.get("label", "").strip()} | '
        f'{selected.get("length")} × {selected.get("width")} × {selected.get("height")} mm | '
        f'contains {selected.get("units_per_parent", 1)} inner units | '
        f'total base units: {selected.get("total_base_units", 1)}'
    )


def _refresh_selected_preview(step, steps, idx):
    """
    Rebuild preview image for the selected candidate.
    Important in Optimal mode, where selection happens after the analysis.
    """
    selected = step.get("selected")
    if not selected:
        return

    prev = _get_selected_input_for_step(steps, idx)
    cfg = step.get("config", {})

    try:
        # -------------------------------------------------
        # CONTAINER / BOX
        # -------------------------------------------------
        if step["type"] == "container":
            if prev:
                product = (
                    float(prev["length"]),
                    float(prev["width"]),
                    float(prev["height"]),
                )
            else:
                product = (
                    float(cfg.get("product_l")),
                    float(cfg.get("product_w")),
                    float(cfg.get("product_h")),
                )

            desired_qty = int(cfg.get("desired_qty") or 1)
            r1 = 1 if cfg.get("r1") else 0
            r2 = 1 if cfg.get("r2") else 0
            r3 = 1 if cfg.get("r3") else 0

            container = (
                float(selected["length"]),
                float(selected["width"]),
                float(selected["height"]),
            )

            render_res = run_mode1_and_render(
                product,
                container,
                r1,
                r2,
                r3,
                settings.MEDIA_ROOT,
                draw_limit=desired_qty,
            )
            step["result_image_url"] = settings.MEDIA_URL + render_res.image_rel_path
            return

        # -------------------------------------------------
        # BAG
        # -------------------------------------------------
        if step["type"] == "bag":
            if prev:
                product = (
                    float(prev["length"]),
                    float(prev["width"]),
                    float(prev["height"]),
                )
            else:
                product = (
                    float(cfg.get("product_l")),
                    float(cfg.get("product_w")),
                    float(cfg.get("product_h")),
                )

            desired_qty = int(cfg.get("desired_qty") or 1)

            req = build_required_bag_options(product[0], product[1], product[2], desired_qty)

            render_res = run_bag_mode1_and_render(
                product=product,
                selected_bag=(float(selected["length"]), float(selected["width"])),
                desired_qty=desired_qty,
                solutions=req["solutions"],
                media_root=settings.MEDIA_ROOT,
                draw_limit=desired_qty,
            )
            step["result_image_url"] = settings.MEDIA_URL + render_res.image_rel_path
            return

        # -------------------------------------------------
        # PALLET
        # -------------------------------------------------
        if step["type"] == "pallet":
            cfg = step.get("config", {})

            prev = _get_selected_input_for_step(steps, idx)
            if prev:
                box_l = float(prev["length"])
                box_w = float(prev["width"])
                box_h = float(prev["height"])
            else:
                box_l = float(cfg.get("box_l"))
                box_w = float(cfg.get("box_w"))
                box_h = float(cfg.get("box_h"))

            source = cfg.get("pallet_source", "manual")
            max_stack_height = float(cfg.get("max_stack_height") or 1600)
            max_width_stickout = float(cfg.get("max_width_stickout") or 0)
            max_length_stickout = float(cfg.get("max_length_stickout") or 0)

            if source == "manual":
                pallet_l = float(cfg.get("pallet_l"))
                pallet_w = float(cfg.get("pallet_w"))
            else:
                material_id = cfg.get("material_id")
                if not material_id:
                    return
                m = PackagingMaterial.objects.get(id=material_id, packaging_type="PALLET")
                pallet_l = float(m.part_length)
                pallet_w = float(m.part_width)

            # Rebuild the full pallet analysis rows
            results_table = run_palletization_analysis(
                box_l=box_l,
                box_w=box_w,
                box_h=box_h,
                pallet_l=pallet_l,
                pallet_w=pallet_w,
                max_stack_height=max_stack_height,
                max_width_stickout=max_width_stickout,
                max_length_stickout=max_length_stickout,
                box_weight=None,
                max_weight_on_bottom_box=None,
            )

            # Match the selected candidate back to the full engine row
            full_row = None
            for row in results_table:
                row_label = f'{row["pattern"]} / {row["stacking"]}'
                row_loaded_height = 100 + (float(row["layers"]) * box_h)

                if (
                    row_label == selected.get("label") and
                    int(row["total_boxes"]) == int(selected.get("units_per_parent")) and
                    round(row_loaded_height, 2) == round(float(selected.get("height")), 2)
                ):
                    full_row = row
                    break

            if not full_row:
                return

            render_res = render_selected_result(
                selected_result=full_row,
                pallet_l=pallet_l,
                pallet_w=pallet_w,
                max_stack_height=max_stack_height,
                media_root=settings.MEDIA_ROOT,
            )
            step["result_image_url"] = settings.MEDIA_URL + render_res.image_rel_path
            return

    except Exception as exc:
        step["messages"] = step.get("messages", [])
        step["messages"].append(f"Preview render failed after selection: {exc}")


def _catalogues():
    return PackagingCatalogue.objects.all().order_by("name")


def _materials_for_catalogue(catalogue_id, packaging_type=None):
    qs = PackagingMaterial.objects.none()
    if catalogue_id:
        qs = PackagingMaterial.objects.filter(catalogue_id=catalogue_id)
        if packaging_type:
            qs = qs.filter(packaging_type=packaging_type)
        qs = qs.order_by("part_number")
    return qs


def _apply_chained_display_defaults(steps):
    """
    Populate the original module input fields with the previous selected step values,
    so the user sees real values in the normal inputs instead of placeholder text.
    """
    for idx, step in enumerate(steps):
        prev = _get_selected_input_for_step(steps, idx)
        cfg = step.setdefault("config", {})

        if not prev:
            continue

        if step["type"] in ["container", "bag"]:
            cfg["product_l"] = prev["length"]
            cfg["product_w"] = prev["width"]
            cfg["product_h"] = prev["height"]

        elif step["type"] == "pallet":
            cfg["box_l"] = prev["length"]
            cfg["box_w"] = prev["width"]
            cfg["box_h"] = prev["height"]

        elif step["type"] == "transport":
            cfg["input_l"] = prev["length"]
            cfg["input_w"] = prev["width"]
            cfg["input_h"] = prev["height"]
            cfg["input_total_base_units"] = prev.get("total_base_units", 1)
            cfg["input_units_per_parent"] = prev.get("units_per_parent", 1)


# =========================================================
# Container / Box step
# =========================================================

def _run_container_step(step, steps, idx, post):
    messages = []
    candidates = []
    result_image_url = None

    prev = _get_selected_input_for_step(steps, idx)

    if prev:
        product_l = float(prev["length"])
        product_w = float(prev["width"])
        product_h = float(prev["height"])
        base_units_in_child = int(prev.get("total_base_units", 1))
    else:
        product_l = _to_float(post.get(f"product_l_{idx}"))
        product_w = _to_float(post.get(f"product_w_{idx}"))
        product_h = _to_float(post.get(f"product_h_{idx}"))
        base_units_in_child = 1

    desired_qty = _to_int(post.get(f"desired_qty_{idx}"), 1)

    if not all(v is not None and v > 0 for v in [product_l, product_w, product_h, desired_qty]):
        step["messages"] = ["Please provide valid product/package dimensions and desired quantity."]
        step["candidates"] = []
        step["result_image_url"] = None
        return

    r1 = _checked(post, f"r1_{idx}")
    r2 = _checked(post, f"r2_{idx}")
    r3 = _checked(post, f"r3_{idx}")
    if r1 == 0 and r2 == 0 and r3 == 0:
        step["messages"] = ["Please enable at least one rotation option."]
        step["candidates"] = []
        step["result_image_url"] = None
        return

    mode = post.get(f"container_mode_{idx}", "optimal")
    source = post.get(f"container_source_{idx}", "catalogue")
    catalogue_id = post.get(f"catalogue_id_{idx}", "") or ""
    material_id = post.get(f"material_id_{idx}", "") or ""

    step["config"] = {
        "product_l": product_l,
        "product_w": product_w,
        "product_h": product_h,
        "desired_qty": desired_qty,
        "r1": bool(r1),
        "r2": bool(r2),
        "r3": bool(r3),
        "container_mode": mode,
        "container_source": source,
        "catalogue_id": catalogue_id,
        "material_id": material_id,
        "box_l": post.get(f"box_l_{idx}", ""),
        "box_w": post.get(f"box_w_{idx}", ""),
        "box_h": post.get(f"box_h_{idx}", ""),
    }

    product = (product_l, product_w, product_h)
    product_vol = product_l * product_w * product_h

    if mode == "single":
        container = None
        label = "Manual Box"

        if source == "manual":
            box_l = _to_float(post.get(f"box_l_{idx}"))
            box_w = _to_float(post.get(f"box_w_{idx}"))
            box_h = _to_float(post.get(f"box_h_{idx}"))
            if not all(v is not None and v > 0 for v in [box_l, box_w, box_h]):
                step["messages"] = ["Please enter valid manual box dimensions."]
                step["candidates"] = []
                step["result_image_url"] = None
                return
            container = (box_l, box_w, box_h)
        else:
            if not material_id:
                step["messages"] = ["Please select a box from the catalogue table."]
                step["candidates"] = []
                step["result_image_url"] = None
                return
            m = PackagingMaterial.objects.get(id=material_id)
            container = (float(m.part_length), float(m.part_width), float(m.part_height))
            label = f"{m.part_number}"

        max_qty = compute_max_quantity_only(product, container, r1, r2, r3)
        if max_qty < desired_qty:
            messages.append(f"The selected box fits max {max_qty} inner units, below desired quantity {desired_qty}.")

        usage = 0.0
        container_vol = container[0] * container[1] * container[2]
        if container_vol > 0:
            usage = (min(desired_qty, max_qty) * product_vol) / container_vol

        try:
            render_res = run_mode1_and_render(
                product=product,
                container=container,
                r1=r1,
                r2=r2,
                r3=r3,
                media_root=settings.MEDIA_ROOT,
                draw_limit=desired_qty,
            )
            result_image_url = settings.MEDIA_URL + render_res.image_rel_path
        except Exception as exc:
            messages.append(f"Preview render failed: {exc}")

        candidates = [{
            "label": label,
            "length": round(container[0], 2),
            "width": round(container[1], 2),
            "height": round(container[2], 2),
            "units_per_parent": desired_qty,
            "total_base_units": desired_qty * base_units_in_child,
            "usage_pct": round(usage * 100, 2),
            "meta": f"max fit {max_qty}",
        }]

    else:
        if not catalogue_id:
            step["messages"] = ["Please select a packaging catalogue for optimal box search."]
            step["candidates"] = []
            step["result_image_url"] = None
            return

        materials = _materials_for_catalogue(catalogue_id, packaging_type="BOX")
        scored = []

        for m in materials:
            container = (float(m.part_length), float(m.part_width), float(m.part_height))
            max_qty = compute_max_quantity_only(product, container, r1, r2, r3)
            if max_qty >= desired_qty:
                container_vol = float(m.part_volume) if m.part_volume is not None else (container[0] * container[1] * container[2])
                usage = (desired_qty * product_vol) / container_vol if container_vol > 0 else 0.0
                scored.append({
                    "material": m,
                    "max_qty": max_qty,
                    "usage": usage,
                    "container_vol": container_vol,
                })

        scored.sort(key=lambda x: (-x["usage"], x["container_vol"]))
        top5 = scored[:5]

        for row in top5:
            m = row["material"]
            candidates.append({
                "label": f"{m.part_number}",
                "length": round(float(m.part_length), 2),
                "width": round(float(m.part_width), 2),
                "height": round(float(m.part_height), 2),
                "units_per_parent": desired_qty,
                "total_base_units": desired_qty * base_units_in_child,
                "usage_pct": round(row["usage"] * 100, 2),
                "meta": f"max fit {row['max_qty']}",
                "material_id": m.id,
            })

        if not candidates:
            messages.append("No box in the selected catalogue can fit the requested quantity.")

    step["messages"] = messages
    step["candidates"] = candidates
    step["result_image_url"] = result_image_url


# =========================================================
# Bag step
# =========================================================

def _run_bag_step(step, steps, idx, post):
    messages = []
    candidates = []
    result_image_url = None

    prev = _get_selected_input_for_step(steps, idx)

    if prev:
        product_l = float(prev["length"])
        product_w = float(prev["width"])
        product_h = float(prev["height"])
        base_units_in_child = int(prev.get("total_base_units", 1))
    else:
        product_l = _to_float(post.get(f"product_l_{idx}"))
        product_w = _to_float(post.get(f"product_w_{idx}"))
        product_h = _to_float(post.get(f"product_h_{idx}"))
        base_units_in_child = 1

    desired_qty = _to_int(post.get(f"desired_qty_{idx}"), 1)
    mode = post.get(f"bag_mode_{idx}", "optimal")
    source = post.get(f"bag_source_{idx}", "catalogue")
    catalogue_id = post.get(f"catalogue_id_{idx}", "") or ""
    material_id = post.get(f"material_id_{idx}", "") or ""

    step["config"] = {
        "product_l": product_l,
        "product_w": product_w,
        "product_h": product_h,
        "desired_qty": desired_qty,
        "bag_mode": mode,
        "bag_source": source,
        "catalogue_id": catalogue_id,
        "material_id": material_id,
        "bag_length": post.get(f"bag_length_{idx}", ""),
        "bag_width": post.get(f"bag_width_{idx}", ""),
    }

    if not all(v is not None and v > 0 for v in [product_l, product_w, product_h, desired_qty]):
        step["messages"] = ["Please provide valid inner package dimensions and desired quantity."]
        step["candidates"] = []
        step["result_image_url"] = None
        return

    product = (product_l, product_w, product_h)
    req = build_required_bag_options(product_l, product_w, product_h, desired_qty)
    required_bags = req["required"]

    if mode == "single":
        bag = None
        label = "Manual Bag"

        if source == "manual":
            bag_l = _to_float(post.get(f"bag_length_{idx}"))
            bag_w = _to_float(post.get(f"bag_width_{idx}"))
            if not all(v is not None and v > 0 for v in [bag_l, bag_w]):
                step["messages"] = ["Please enter valid manual bag dimensions."]
                step["candidates"] = []
                step["result_image_url"] = None
                return
            bag = (bag_l, bag_w)
        else:
            if not material_id:
                step["messages"] = ["Please select a bag from the catalogue table."]
                step["candidates"] = []
                step["result_image_url"] = None
                return
            m = PackagingMaterial.objects.get(id=material_id)
            bag = (float(m.part_length), float(m.part_width))
            label = f"{m.part_number}"

        best = best_usage_for_bag(bag[0], bag[1], required_bags)
        if best is None:
            messages.append("The selected bag does not fit the requested grouped inner packages.")
        else:
            try:
                render_res = run_bag_mode1_and_render(
                    product=product,
                    selected_bag=(bag[0], bag[1]),
                    desired_qty=desired_qty,
                    solutions=req["solutions"],
                    media_root=settings.MEDIA_ROOT,
                    draw_limit=desired_qty,
                )
                result_image_url = settings.MEDIA_URL + render_res.image_rel_path
            except Exception as exc:
                messages.append(f"Preview render failed: {exc}")

        candidates = [{
            "label": label,
            "length": round(bag[0], 2),
            "width": round(bag[1], 2),
            "height": round(product_h, 2),
            "units_per_parent": desired_qty,
            "total_base_units": desired_qty * base_units_in_child,
            "usage_pct": round((best["usage"] * 100) if best else 0.0, 2),
            "meta": f"required {best['req_len']} × {best['req_w']}" if best else "does not fit",
        }]

    else:
        if not catalogue_id:
            step["messages"] = ["Please select a packaging catalogue for optimal bag search."]
            step["candidates"] = []
            step["result_image_url"] = None
            return

        materials = _materials_for_catalogue(catalogue_id, packaging_type="BAG")
        scored = []

        for m in materials:
            bag_l = float(m.part_length or 0)
            bag_w = float(m.part_width or 0)
            if bag_l <= 0 or bag_w <= 0:
                continue

            best = best_usage_for_bag(bag_l, bag_w, required_bags)
            if best is not None:
                scored.append({
                    "material": m,
                    "bag_l": bag_l,
                    "bag_w": bag_w,
                    "usage": best["usage"],
                    "best_required": (best["req_len"], best["req_w"]),
                    "bag_area": best["bag_area"],
                })

        scored.sort(key=lambda x: (-x["usage"], x["bag_area"]))
        top5 = scored[:5]

        for row in top5:
            m = row["material"]
            candidates.append({
                "label": f"{m.part_number}",
                "length": round(row["bag_l"], 2),
                "width": round(row["bag_w"], 2),
                "height": round(product_h, 2),
                "units_per_parent": desired_qty,
                "total_base_units": desired_qty * base_units_in_child,
                "usage_pct": round(row["usage"] * 100, 2),
                "meta": f"required {row['best_required'][0]} × {row['best_required'][1]}",
                "material_id": m.id,
            })

        if not candidates:
            messages.append("No bag in the selected catalogue can fit the requested grouped inner packages.")

    step["messages"] = messages
    step["candidates"] = candidates
    step["result_image_url"] = result_image_url


# =========================================================
# Pallet step
# =========================================================

def _run_pallet_step(step, steps, idx, post):
    messages = []
    candidates = []
    result_image_url = None

    prev = _get_selected_input_for_step(steps, idx)

    if prev:
        box_l = float(prev["length"])
        box_w = float(prev["width"])
        box_h = float(prev["height"])
        base_units_in_child = int(prev.get("total_base_units", 1))
    else:
        box_l = _to_float(post.get(f"box_l_{idx}"))
        box_w = _to_float(post.get(f"box_w_{idx}"))
        box_h = _to_float(post.get(f"box_h_{idx}"))
        base_units_in_child = 1

    source = post.get(f"pallet_source_{idx}", "manual")
    catalogue_id = post.get(f"catalogue_id_{idx}", "") or ""
    material_id = post.get(f"material_id_{idx}", "") or ""

    max_stack_height = _to_float(post.get(f"max_stack_height_{idx}"), 1600)
    max_width_stickout = _to_float(post.get(f"max_width_stickout_{idx}"), 0)
    max_length_stickout = _to_float(post.get(f"max_length_stickout_{idx}"), 0)

    step["config"] = {
        "box_l": box_l,
        "box_w": box_w,
        "box_h": box_h,
        "pallet_source": source,
        "catalogue_id": catalogue_id,
        "material_id": material_id,
        "pallet_l": post.get(f"pallet_l_{idx}", ""),
        "pallet_w": post.get(f"pallet_w_{idx}", ""),
        "max_stack_height": max_stack_height,
        "max_width_stickout": max_width_stickout,
        "max_length_stickout": max_length_stickout,
    }

    if not all(v is not None and v > 0 for v in [box_l, box_w, box_h, max_stack_height]):
        step["messages"] = ["Please provide valid package dimensions and pallet constraints."]
        step["candidates"] = []
        step["result_image_url"] = None
        return

    if source == "manual":
        pallet_l = _to_float(post.get(f"pallet_l_{idx}"))
        pallet_w = _to_float(post.get(f"pallet_w_{idx}"))
        if not all(v is not None and v > 0 for v in [pallet_l, pallet_w]):
            step["messages"] = ["Please enter valid manual pallet dimensions."]
            step["candidates"] = []
            step["result_image_url"] = None
            return
    else:
        if not material_id:
            step["messages"] = ["Please select a pallet from the catalogue table."]
            step["candidates"] = []
            step["result_image_url"] = None
            return
        m = PackagingMaterial.objects.get(id=material_id, packaging_type="PALLET")
        pallet_l = float(m.part_length)
        pallet_w = float(m.part_width)

    try:
        results_table = run_palletization_analysis(
            box_l=box_l,
            box_w=box_w,
            box_h=box_h,
            pallet_l=pallet_l,
            pallet_w=pallet_w,
            max_stack_height=max_stack_height,
            max_width_stickout=max_width_stickout,
            max_length_stickout=max_length_stickout,
            box_weight=None,
            max_weight_on_bottom_box=None,
        )
    except Exception as exc:
        step["messages"] = [f"Palletization analysis failed: {exc}"]
        step["candidates"] = []
        step["result_image_url"] = None
        return

    if not results_table:
        step["messages"] = ["No palletization solutions found."]
        step["candidates"] = []
        step["result_image_url"] = None
        return

    top_rows = results_table[:5]

    for row in top_rows:
        loaded_height = 100 + (float(row["layers"]) * box_h)
        candidates.append({
            "label": f'{row["pattern"]} / {row["stacking"]}',
            "length": round(pallet_l, 2),
            "width": round(pallet_w, 2),
            "height": round(loaded_height, 2),
            "units_per_parent": int(row["total_boxes"]),
            "total_base_units": int(row["total_boxes"]) * base_units_in_child,
            "usage_pct": round(float(row["volumetric_util_pct"]), 2),
            "meta": f'layers {row["layers"]} | total boxes {row["total_boxes"]}',
            "pattern": row["pattern"],
            "stacking": row["stacking"],
            "layers": int(row["layers"]),
            "total_boxes": int(row["total_boxes"]),
            "pallet_l": round(pallet_l, 2),
            "pallet_w": round(pallet_w, 2),
            "max_stack_height": round(max_stack_height, 2),
        })

    try:
        render_res = render_selected_result(
            selected_result=top_rows[0],
            pallet_l=pallet_l,
            pallet_w=pallet_w,
            max_stack_height=max_stack_height,
            media_root=settings.MEDIA_ROOT,
        )
        result_image_url = settings.MEDIA_URL + render_res.image_rel_path
    except Exception as exc:
        messages.append(f"Preview render failed: {exc}")

    step["messages"] = messages
    step["candidates"] = candidates
    step["result_image_url"] = result_image_url


# =========================================================
# Transport Container step
# =========================================================

def _run_transport_step(step, steps, idx, post):
    messages = []
    candidates = []
    result_image_url = None

    prev = _get_selected_input_for_step(steps, idx)
    if not prev:
        step["messages"] = ["Transport Container needs a previous selected step, usually a pallet."]
        step["candidates"] = []
        step["result_image_url"] = None
        return

    item_qty = _to_int(post.get(f"item_qty_{idx}"), 1)
    item_weight = _to_float(post.get(f"item_weight_{idx}"), 0.0)

    container_l = _to_float(post.get(f"container_l_{idx}"), 12032)
    container_w = _to_float(post.get(f"container_w_{idx}"), 2352)
    container_h = _to_float(post.get(f"container_h_{idx}"), 2698)
    max_weight = _to_float(post.get(f"max_weight_{idx}"), 26000)

    step["config"] = {
        "item_qty": item_qty,
        "item_weight": item_weight,
        "container_l": container_l,
        "container_w": container_w,
        "container_h": container_h,
        "max_weight": max_weight,
        "input_l": prev["length"],
        "input_w": prev["width"],
        "input_h": prev["height"],
        "input_total_base_units": prev.get("total_base_units", 1),
        "input_units_per_parent": prev.get("units_per_parent", 1),
    }

    if not all(v is not None and v > 0 for v in [container_l, container_w, container_h, max_weight, item_qty]):
        step["messages"] = ["Please provide valid transport container inputs."]
        step["candidates"] = []
        step["result_image_url"] = None
        return

    container = {
        "L": container_l,
        "W": container_w,
        "H": container_h,
        "max_weight": max_weight,
    }

    products = [{
        "name": prev.get("label", "Loaded package"),
        "length": float(prev["length"]),
        "width": float(prev["width"]),
        "height": float(prev["height"]),
        "qty": item_qty,
        "weight": item_weight,
        "sequence": 1,
        "r1": True,
        "r2": False,
        "r3": False,
    }]

    try:
        result = run_container_tool(
            container=container,
            products=products,
            media_root=settings.MEDIA_ROOT,
        )
        result_image_url = settings.MEDIA_URL + result["image_rel_path"]

        placed_units = int(result["summary"]["placed_units"])
        util_pct = float(result["summary"]["utilization_volume_pct"])
        loaded_weight_pct = float(result["summary"]["utilization_weight_pct"])

        total_base_units = placed_units * int(prev.get("total_base_units", 1))

        candidates = [{
            "label": "Transport Container Load",
            "length": round(container_l, 2),
            "width": round(container_w, 2),
            "height": round(container_h, 2),
            "units_per_parent": placed_units,
            "total_base_units": total_base_units,
            "usage_pct": round(util_pct, 2),
            "meta": f"placed {placed_units} | weight util {loaded_weight_pct:.2f}%",
        }]
    except Exception as exc:
        messages.append(f"Transport container analysis failed: {exc}")

    step["messages"] = messages
    step["candidates"] = candidates
    step["result_image_url"] = result_image_url


# =========================================================
# Controller
# =========================================================

def full_packaging_mode(request):
    workflow = _get_workflow(request)
    steps = workflow["steps"]

    if request.method == "POST":
        action = request.POST.get("action", "")

        if action == "show_add_bar":
            anchor = request.POST.get("after_index", "start")
            workflow["show_add_bar_after"] = anchor

            # collapse previous/current step when clicking +
            if anchor != "start":
                idx = _to_int(anchor)
                if idx is not None and 0 <= idx < len(steps):
                    steps[idx]["expanded"] = False

            _save_workflow(request, workflow)
            return redirect("full_packaging_mode")

        if action == "hide_add_bar":
            workflow["show_add_bar_after"] = None
            _save_workflow(request, workflow)
            return redirect("full_packaging_mode")

        if action == "add_step":
            step_type = request.POST.get("step_type", "")
            after_index = request.POST.get("after_index", "")

            if step_type in ["container", "bag", "pallet", "transport"]:
                new_step = _new_step(step_type)

                if after_index in ("", "start"):
                    steps.append(new_step)
                else:
                    idx = _to_int(after_index)
                    if idx is not None and 0 <= idx < len(steps):
                        steps[idx]["expanded"] = False
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
                steps[idx]["messages"] = []
                steps[idx]["candidates"] = []
                steps[idx]["result_image_url"] = None

                step_type = steps[idx]["type"]

                if step_type == "container":
                    _run_container_step(steps[idx], steps, idx, request.POST)
                elif step_type == "bag":
                    _run_bag_step(steps[idx], steps, idx, request.POST)
                elif step_type == "pallet":
                    _run_pallet_step(steps[idx], steps, idx, request.POST)
                elif step_type == "transport":
                    _run_transport_step(steps[idx], steps, idx, request.POST)

                workflow["show_add_bar_after"] = None
                _save_workflow(request, workflow)
            return redirect("full_packaging_mode")

        if action == "select_candidate":
            idx = _to_int(request.POST.get("index"))
            candidate_idx = _to_int(request.POST.get("candidate_index"))

            if (
                idx is not None and candidate_idx is not None and
                0 <= idx < len(steps) and
                0 <= candidate_idx < len(steps[idx].get("candidates", []))
            ):
                selected = dict(steps[idx]["candidates"][candidate_idx])

                steps[idx]["selected"] = selected
                steps[idx]["summary"] = _build_selected_summary(selected)
                steps[idx]["expanded"] = True

                _refresh_selected_preview(steps[idx], steps, idx)
                _invalidate_downstream(steps, idx)

                # restore current step after invalidating downstream
                steps[idx]["selected"] = selected
                steps[idx]["summary"] = _build_selected_summary(selected)
                steps[idx]["expanded"] = True
                _refresh_selected_preview(steps[idx], steps, idx)

                workflow["show_add_bar_after"] = None
                _save_workflow(request, workflow)

            return redirect("full_packaging_mode")

    catalogue_list = _catalogues()

    for step in steps:
        cfg = step.get("config", {})
        catalogue_id = cfg.get("catalogue_id") or ""
        if step["type"] == "container":
            step["materials"] = list(
                _materials_for_catalogue(catalogue_id, "BOX").values(
                    "id", "part_number", "part_description", "branding",
                    "part_length", "part_width", "part_height"
                )
            )
        elif step["type"] == "bag":
            step["materials"] = list(
                _materials_for_catalogue(catalogue_id, "BAG").values(
                    "id", "part_number", "part_description", "branding",
                    "part_length", "part_width", "part_height"
                )
            )
        elif step["type"] == "pallet":
            step["materials"] = list(
                _materials_for_catalogue(catalogue_id, "PALLET").values(
                    "id", "part_number", "part_description", "branding",
                    "packaging_type", "part_length", "part_width", "part_height"
                )
            )
        else:
            step["materials"] = []

    _apply_chained_display_defaults(steps)

    final_summary = None
    if steps and steps[-1].get("selected"):
        final_summary = steps[-1]["selected"]

    return render(
        request,
        "full_packaging/full_packaging_mode.html",
        {
            "steps": steps,
            "catalogues": catalogue_list,
            "final_summary": final_summary,
            "show_add_bar_after": workflow.get("show_add_bar_after"),
        }
    )