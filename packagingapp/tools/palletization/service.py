from django.conf import settings

from ...models import PackagingMaterial
from ...utils.palletization.engine import run_palletization_analysis, render_selected_result
from .serializers import (
    sanitize_palletization_config_for_session,
    serialize_pallet_analysis_result,
)
from .state import default_palletization_config


INTERLOCK_RENDER_SUFFIX = "__interlock_preview"


def split_pallet_result_key(selected_result_key):
    key = str(selected_result_key or "")
    if key.endswith(INTERLOCK_RENDER_SUFFIX):
        return key[:-len(INTERLOCK_RENDER_SUFFIX)], True
    return key, False


def _to_float(value, default=None):
    try:
        if value in (None, "", "None"):
            return default
        return float(value)
    except Exception:
        return default


def _dimension_from_material(material, *attrs):
    """Return the first positive catalogue dimension from the requested fields.

    Some catalogue rows have external_* stored as 0 while the usable value is in
    part_*. Treat 0 as an empty catalogue dimension for fallback purposes, but
    still return 0 if no positive fallback exists so validation can show a clear
    message instead of crashing later.
    """
    first_numeric = None
    for attr in attrs:
        value = _to_float(getattr(material, attr, None), None)
        if value is None:
            continue
        if first_numeric is None:
            first_numeric = value
        if value > 0:
            return value
    return first_numeric if first_numeric is not None else 0.0


def dims_from_material(material, prefer_external=False):
    if not material:
        return None

    if prefer_external:
        length_attrs = ("external_length", "part_length")
        width_attrs = ("external_width", "part_width")
        height_attrs = ("external_height", "part_height")
    else:
        length_attrs = ("part_length", "external_length")
        width_attrs = ("part_width", "external_width")
        height_attrs = ("part_height", "external_height")

    return (
        _dimension_from_material(material, *length_attrs),
        _dimension_from_material(material, *width_attrs),
        _dimension_from_material(material, *height_attrs),
    )


def get_selected_box_material(config):
    selected_box_id = (config or {}).get("selected_box_id")
    if not selected_box_id:
        return None
    return PackagingMaterial.objects.filter(
        id=selected_box_id,
        packaging_type__in=["BOX", "CRATE"],
    ).select_related("catalogue").first()


def get_selected_pallet_material(config):
    pallet_id = (config or {}).get("pallet_id")
    if not pallet_id:
        return None
    return PackagingMaterial.objects.filter(
        id=pallet_id,
        packaging_type="PALLET",
    ).select_related("catalogue").first()


def get_box_materials(config):
    catalogue_id = (config or {}).get("box_catalogue_id")
    if not catalogue_id:
        return PackagingMaterial.objects.none()
    return PackagingMaterial.objects.filter(
        catalogue_id=catalogue_id,
        packaging_type__in=["BOX", "CRATE"],
    ).select_related("catalogue").order_by("part_number")


def get_pallet_materials(config):
    catalogue_id = (config or {}).get("pallet_catalogue_id")
    if not catalogue_id:
        return PackagingMaterial.objects.none()
    return PackagingMaterial.objects.filter(
        catalogue_id=catalogue_id,
        packaging_type="PALLET",
    ).select_related("catalogue").order_by("part_number")


def build_effective_palletization_config(config, selected_box_material=None, selected_pallet_material=None):
    cfg = default_palletization_config()
    cfg.update(sanitize_palletization_config_for_session(config or {}))

    messages = []

    box_source = cfg.get("box_source") or "manual"
    pallet_source = cfg.get("pallet_source") or "manual"

    if box_source == "catalogue":
        if not selected_box_material:
            messages.append("Please select a box/container from the catalogue table.")
            box_l = box_w = box_h = None
            box_weight = None
        else:
            box_dims = dims_from_material(selected_box_material, prefer_external=True)
            box_l, box_w, box_h = box_dims
            inferred_box_weight = _to_float(getattr(selected_box_material, "part_weight", None))
            manual_box_weight = _to_float(cfg.get("box_weight"))
            box_weight = manual_box_weight if manual_box_weight is not None else inferred_box_weight
    else:
        box_l = _to_float(cfg.get("box_l"))
        box_w = _to_float(cfg.get("box_w"))
        box_h = _to_float(cfg.get("box_h"))
        box_weight = _to_float(cfg.get("box_weight"))
        if None in (box_l, box_w, box_h):
            messages.append("Please enter all manual box dimensions.")

    if pallet_source == "catalogue":
        if not selected_pallet_material:
            messages.append("Please select a pallet from the catalogue table.")
            pallet_l = pallet_w = None
        else:
            pallet_dims = dims_from_material(selected_pallet_material, prefer_external=True)
            pallet_l, pallet_w, _ = pallet_dims
    else:
        pallet_l = _to_float(cfg.get("pallet_l"))
        pallet_w = _to_float(cfg.get("pallet_w"))
        if pallet_l is None or pallet_w is None:
            messages.append("Please enter pallet length and pallet width.")

    max_stack_height = _to_float(cfg.get("max_stack_height"))
    if max_stack_height is None:
        messages.append("Please enter max stack height.")

    max_weight_on_bottom_box = _to_float(cfg.get("max_weight_on_bottom_box"))
    max_width_stickout = _to_float(cfg.get("max_width_stickout"), 0) or 0
    max_length_stickout = _to_float(cfg.get("max_length_stickout"), 0) or 0

    for label, value in [
        ("box length", box_l),
        ("box width", box_w),
        ("box height", box_h),
        ("pallet length", pallet_l),
        ("pallet width", pallet_w),
        ("max stack height", max_stack_height),
    ]:
        if value is not None and value <= 0:
            messages.append(f"{label.capitalize()} must be greater than 0.")

    for label, value in [
        ("box weight", box_weight),
        ("max weight on bottom box", max_weight_on_bottom_box),
        ("max width overhang", max_width_stickout),
        ("max length overhang", max_length_stickout),
    ]:
        if value is not None and value < 0:
            messages.append(f"{label.capitalize()} cannot be negative.")

    effective_config = {
        "box_source": box_source,
        "pallet_source": pallet_source,
        "box_l": box_l,
        "box_w": box_w,
        "box_h": box_h,
        "box_weight": box_weight,
        "max_weight_on_bottom_box": max_weight_on_bottom_box,
        "pallet_l": pallet_l,
        "pallet_w": pallet_w,
        "max_stack_height": max_stack_height,
        "max_width_stickout": max_width_stickout,
        "max_length_stickout": max_length_stickout,
    }

    return {
        "ok": len(messages) == 0,
        "messages": messages,
        "effective_config": effective_config,
    }


def analyze_palletization_config(config, selected_result_key="", selected_box_material=None, selected_pallet_material=None, media_root=None):
    selected_base_result_key, render_interlock_preview = split_pallet_result_key(selected_result_key)

    built = build_effective_palletization_config(
        config=config,
        selected_box_material=selected_box_material,
        selected_pallet_material=selected_pallet_material,
    )

    if not built["ok"]:
        return {
            "ok": False,
            "messages": built["messages"],
            "effective_config": built["effective_config"],
            "serialized_result": None,
            "result": None,
        }

    eff = built["effective_config"]

    raw_results = run_palletization_analysis(
        box_l=float(eff["box_l"]),
        box_w=float(eff["box_w"]),
        box_h=float(eff["box_h"]),
        pallet_l=float(eff["pallet_l"]),
        pallet_w=float(eff["pallet_w"]),
        max_stack_height=float(eff["max_stack_height"]),
        max_width_stickout=float(eff["max_width_stickout"]),
        max_length_stickout=float(eff["max_length_stickout"]),
        box_weight=eff["box_weight"],
        max_weight_on_bottom_box=eff["max_weight_on_bottom_box"],
    )

    selected_row = None
    if selected_base_result_key:
        for row in raw_results:
            row_key = f'{row["pattern"]}__{row["stacking"]}'
            if row_key == selected_base_result_key:
                selected_row = row
                break

    if selected_row is None and raw_results:
        selected_row = raw_results[0]

    render_result = None
    image_rel_path = None
    active_selected_result_key = ""
    if selected_row is not None:
        can_render_interlock = bool(selected_row.get("interlock_possible") and selected_row.get("interlock_possible_layer"))
        render_interlock_preview = bool(render_interlock_preview and can_render_interlock)
        selected_row["interlock_render_active"] = render_interlock_preview

        base_row_key = f'{selected_row["pattern"]}__{selected_row["stacking"]}'
        active_selected_result_key = (
            f"{base_row_key}{INTERLOCK_RENDER_SUFFIX}" if render_interlock_preview else base_row_key
        )

        render_result = render_selected_result(
            selected_result=selected_row,
            pallet_l=float(eff["pallet_l"]),
            pallet_w=float(eff["pallet_w"]),
            max_stack_height=float(eff["max_stack_height"]),
            media_root=media_root or settings.MEDIA_ROOT,
            render_interlock=render_interlock_preview,
        )
        image_rel_path = render_result.image_rel_path

    serialized_result = serialize_pallet_analysis_result(
        raw_results=raw_results,
        selected_row=selected_row,
        image_rel_path=image_rel_path,
        selected_result_key=active_selected_result_key,
    )

    return {
        "ok": True,
        "messages": [],
        "effective_config": eff,
        "serialized_result": serialized_result,
        "result": {
            "raw_results": raw_results,
            "selected_row": selected_row,
            "render_result": render_result,
        },
    }