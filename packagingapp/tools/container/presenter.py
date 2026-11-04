from types import SimpleNamespace
from ...units import format_dimensions, format_mass


def _read_value(data, key, default=""):
    if isinstance(data, dict):
        return data.get(key, default)

    if hasattr(data, "cleaned_data") and isinstance(getattr(data, "cleaned_data", None), dict):
        cleaned = data.cleaned_data
        if key in cleaned:
            return cleaned.get(key, default)

    try:
        bound = data[key]
        if hasattr(bound, "value"):
            return bound.value()
    except Exception:
        pass

    return getattr(data, key, default)


def selected_product_summary(selected_product, data, mode="single"):
    dimension_unit = _read_value(data, "product_dimension_unit", "mm") or "mm"
    mass_unit = _read_value(data, "product_mass_unit", "g") or "g"
    if selected_product:
        title = selected_product.product_id or "Selected product"
        if selected_product.product_name:
            title = f"{title} — {selected_product.product_name}"

        meta_parts = []
        weight = getattr(selected_product, "weight", None)
        if weight not in (None, "", "None"):
            meta_parts.append(
                "Wt: " + format_mass(weight, canonical_unit="kg", display_unit=mass_unit)
            )

        if mode == "optimal":
            qty = getattr(selected_product, "desired_qty", None)
            if qty not in (None, "", "None"):
                meta_parts.append(f"Qty: {qty}")

        return {
            "title": title,
            "dims": format_dimensions(
                selected_product.product_length,
                selected_product.product_width,
                selected_product.product_height,
                display_unit=dimension_unit,
            ),
            "meta": " | ".join(meta_parts),
        }

    meta_parts = []
    weight = _read_value(data, "product_weight", "")
    if weight not in (None, "", "None"):
        meta_parts.append(f"Wt: {weight} {mass_unit}")

    qty = _read_value(data, "desired_qty", "")
    if mode == "optimal" and qty not in (None, "", "None"):
        meta_parts.append(f"Qty: {qty}")

    return {
        "title": "Manual product",
        "dims": f'{_read_value(data, "product_l", "")} × {_read_value(data, "product_w", "")} × {_read_value(data, "product_h", "")} {dimension_unit}',
        "meta": " | ".join(meta_parts),
    }


def selected_container_summary(selected_material, data):
    dimension_unit = _read_value(data, "container_dimension_unit", "mm") or "mm"
    mass_unit = _read_value(data, "container_mass_unit", "g") or "g"
    if selected_material:
        meta_parts = [
            str(selected_material.packaging_type or ""),
            str(selected_material.branding or ""),
        ]
        weight = getattr(selected_material, "part_weight", None)
        if weight not in (None, "", "None"):
            meta_parts.insert(
                0,
                "Wt: " + format_mass(weight, canonical_unit="kg", display_unit=mass_unit),
            )

        meta = " | ".join([p for p in meta_parts if p])
        from .service import resolve_container_material_properties
        properties = resolve_container_material_properties(
            SimpleNamespace(cleaned_data={"container_dimension_unit": dimension_unit}), "catalogue", selected_material,
        )

        return {
            "title": f"{selected_material.part_number} — {selected_material.part_description}",
            "dims": format_dimensions(
                selected_material.part_length,
                selected_material.part_width,
                selected_material.part_height,
                display_unit=dimension_unit,
            ),
            "meta": meta,
            "properties": properties,
        }

    return {
        "title": "Manual container",
        "dims": f'{_read_value(data, "box_l", "")} × {_read_value(data, "box_w", "")} × {_read_value(data, "box_h", "")} {dimension_unit}',
        "meta": "Manual dimensions",
    }


def build_container_advanced_context(config, form, selected_product=None, selected_material=None,
                                     analysis_report=None, *, inherited_product=False):
    """One Advanced input/source contract for standalone and prefixed Flow."""
    from ...forms import ContainerSelectionMode1Form
    from ...units import convert_length, convert_mass, kg_to_g
    from .corrugated_material import gsm_to_lb_msf
    from .service import (build_hydrated_post_data, resolve_container_material_properties,
                          _resolve_container_weight, _resolve_product_weight, _resolve_payload_capacity)

    if form.is_bound:
        probe = form
    else:
        probe = ContainerSelectionMode1Form(build_hydrated_post_data(config, config, selected_product, selected_material))
        for key in ("catalogue_id", "product_catalogue_id", "corrugated_material_id"):
            probe.fields[key].choices = list(form.fields[key].choices)
    probe.is_valid()
    cleaned = probe.cleaned_data
    source = "catalogue" if config.get("mode") == "optimal" else "manual" if config.get("mode") == "design" else config.get("container_source") or "manual"
    properties = resolve_container_material_properties(probe, source, selected_material)
    dimensions = None
    if analysis_report and analysis_report.get("internal_length") is not None:
        dimensions = tuple(analysis_report.get("internal_" + axis) for axis in ("length", "width", "height"))
    elif source == "catalogue" and selected_material is not None:
        dimensions = tuple(float(getattr(selected_material, "part_" + axis)) for axis in ("length", "width", "height"))
    elif config.get("mode") != "design" and all(cleaned.get(key) is not None for key in ("box_l", "box_w", "box_h")):
        dimensions = tuple(float(convert_length(cleaned[key], cleaned.get("container_dimension_unit") or "mm", "mm")) for key in ("box_l", "box_w", "box_h"))
    tare = _resolve_container_weight(probe, source, selected_material, dimensions)
    baseline_form = SimpleNamespace(data={**dict(probe.data), "box_weight_user_override": "", "box_max_payload_user_override": ""},
                                    cleaned_data={**cleaned, "box_weight_user_override": "", "box_max_payload_user_override": ""})
    baseline_tare = _resolve_container_weight(baseline_form, source, selected_material, dimensions)
    product_source = config.get("product_source") or "manual"
    product_weight = _resolve_product_weight(probe, product_source, selected_product)
    product_baseline = float(kg_to_g(selected_product.weight)) if product_source == "catalogue" and selected_product is not None and selected_product.weight is not None else None
    product_override = str(cleaned.get("product_weight_user_override") or "") == "1" and not inherited_product
    if product_source == "manual" and not product_override:
        product_baseline = product_weight
    payload = _resolve_payload_capacity(probe, source, selected_material)
    baseline_payload = _resolve_payload_capacity(baseline_form, "catalogue", selected_material) if source == "catalogue" else None
    dimension_unit = cleaned.get("container_dimension_unit") or config.get("container_dimension_unit") or "mm"
    mass_unit = cleaned.get("container_mass_unit") or config.get("container_mass_unit") or "g"
    product_mass_unit = cleaned.get("product_mass_unit") or config.get("product_mass_unit") or "g"
    imperial = dimension_unit in {"in", "ft"}
    def number(value):
        return "" if value is None else format(float(value), ".12g")
    def length(value):
        return number(convert_length(value, "mm", dimension_unit)) if value is not None else ""
    def mass(value, unit):
        return number(convert_mass(value, "g", unit)) if value is not None else ""
    flags = {"caliper": properties["caliper_user_override"], "grammage": properties["grammage_user_override"],
             "tare": str(cleaned.get("box_weight_user_override") or "") == "1",
             "payload": str(cleaned.get("box_max_payload_user_override") or "") == "1", "product_weight": product_override}
    baselines = {
        "caliper": {"value": properties["caliper_baseline_mm"], "label": properties["caliper_baseline_source_display"], "source": properties["caliper_baseline_source"]},
        "grammage": {"value": properties["grammage_baseline_g_m2"], "label": properties["grammage_baseline_source_display"], "source": properties["grammage_baseline_source"]},
        "tare": {"value": baseline_tare.get("tare_g"), "label": baseline_tare.get("source_label"), "source": baseline_tare.get("source")},
        "payload": {"value": baseline_payload, "label": "Catalogue" if baseline_payload is not None else "Not available", "source": "catalogue" if baseline_payload is not None else "unavailable"},
        "product_weight": {"value": product_baseline, "label": ("Catalogue" if product_source == "catalogue" else "Manual input") if product_baseline is not None else "Not available", "source": product_source if product_baseline is not None else "unavailable"},
    }
    inputs = {
        "box_thickness_mm": length(properties["caliper_mm"]),
        "combined_grammage_g_m2": number(gsm_to_lb_msf(properties["combined_grammage_g_m2"]) if imperial else properties["combined_grammage_g_m2"]),
        "box_weight": mass(tare.get("tare_g"), mass_unit), "box_max_payload": mass(payload, mass_unit),
        "product_weight": mass(product_weight, product_mass_unit),
    }
    for key in inputs:
        if key in probe.errors:
            inputs[key] = str(probe.data.get(key) or "")
    product_errors = any(key in probe.errors for key in ("product_weight", "product_shape", "product_allowance_l", "product_allowance_w", "product_allowance_h"))
    container_errors = any(key in probe.errors for key in ("box_thickness_mm", "combined_grammage_g_m2", "box_weight", "box_max_payload", "corrugated_material_id", "container_dimension_unit", "container_mass_unit"))
    return {
        "inputs": inputs, "properties": properties, "baselines": baselines, "flags": flags, "errors": list(probe.errors),
        "labels": {"caliper": properties["caliper_source_display"], "grammage": properties["grammage_source_display"],
                   "tare": tare.get("source_label"), "payload": "Manual override" if flags["payload"] else baselines["payload"]["label"],
                   "product_weight": "Previous workflow step" if inherited_product else "Manual override" if product_override or product_source == "manual" and product_weight is not None else baselines["product_weight"]["label"]},
        "effective": {"caliper": properties["caliper_mm"], "grammage": properties["combined_grammage_g_m2"], "tare": tare.get("tare_g"), "payload": payload, "product_weight": product_weight},
        "sku": {"caliper": float(selected_material.box_thickness_mm) if source == "catalogue" and selected_material is not None and getattr(selected_material, "box_thickness_mm", None) is not None else None,
                "grammage": float(selected_material.combined_grammage_g_m2) if source == "catalogue" and selected_material is not None and getattr(selected_material, "combined_grammage_g_m2", None) is not None else None},
        "board_code": properties["corrugated_material_id"], "catalogue": source == "catalogue",
        "product_open": str(config.get("product_advanced_open") or "") == "1" or product_errors,
        "container_open": str(config.get("container_advanced_open") or "") == "1" or container_errors,
        "inherited_product": inherited_product,
    }
