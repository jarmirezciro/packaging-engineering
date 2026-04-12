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
    if selected_product:
        title = selected_product.product_id or "Selected product"
        if selected_product.product_name:
            title = f"{title} — {selected_product.product_name}"

        meta_parts = []
        weight = getattr(selected_product, "weight", None)
        if weight not in (None, "", "None"):
            meta_parts.append(f"Wt: {weight}")

        if mode == "optimal":
            qty = getattr(selected_product, "desired_qty", None)
            if qty not in (None, "", "None"):
                meta_parts.append(f"Desired Qty: {qty}")

        return {
            "title": title,
            "dims": f"{selected_product.product_length} × {selected_product.product_width} × {selected_product.product_height}",
            "meta": " | ".join(meta_parts),
        }

    qty = _read_value(data, "desired_qty", "")
    meta = []
    if mode == "optimal" and qty not in (None, "", "None"):
        meta.append(f"Desired Qty: {qty}")

    return {
        "title": "Manual product",
        "dims": f'{_read_value(data, "product_l", "")} × {_read_value(data, "product_w", "")} × {_read_value(data, "product_h", "")}',
        "meta": " | ".join(meta),
    }


def selected_bag_summary(selected_material, data):
    if selected_material:
        meta_parts = []
        weight = getattr(selected_material, "part_weight", None)
        if weight not in (None, "", "None"):
            meta_parts.append(f"Wt: {weight}")
        if getattr(selected_material, "packaging_type", None):
            meta_parts.append(str(selected_material.packaging_type))
        if getattr(selected_material, "branding", None):
            meta_parts.append(str(selected_material.branding))

        return {
            "title": f"{selected_material.part_number} — {selected_material.part_description}",
            "dims": f"{selected_material.part_length} × {selected_material.part_width}",
            "meta": " | ".join(meta_parts),
        }

    return {
        "title": "Manual bag",
        "dims": f'{_read_value(data, "bag_length", "")} × {_read_value(data, "bag_width", "")}',
        "meta": "Manual dimensions",
    }
