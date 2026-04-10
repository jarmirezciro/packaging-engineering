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
                meta_parts.append(f"Qty: {qty}")

        return {
            "title": title,
            "dims": f"{selected_product.product_length} × {selected_product.product_width} × {selected_product.product_height}",
            "meta": " | ".join(meta_parts),
        }

    meta_parts = []
    weight = _read_value(data, "product_weight", "")
    if weight not in (None, "", "None"):
        meta_parts.append(f"Wt: {weight}")

    qty = _read_value(data, "desired_qty", "")
    if mode == "optimal" and qty not in (None, "", "None"):
        meta_parts.append(f"Qty: {qty}")

    return {
        "title": "Manual product",
        "dims": f'{_read_value(data, "product_l", "")} × {_read_value(data, "product_w", "")} × {_read_value(data, "product_h", "")}',
        "meta": " | ".join(meta_parts),
    }


def selected_container_summary(selected_material, data):
    if selected_material:
        meta_parts = [
            str(selected_material.packaging_type or ""),
            str(selected_material.branding or ""),
        ]
        weight = getattr(selected_material, "part_weight", None)
        if weight not in (None, "", "None"):
            meta_parts.insert(0, f"Wt: {weight}")

        meta = " | ".join([p for p in meta_parts if p])

        return {
            "title": f"{selected_material.part_number} — {selected_material.part_description}",
            "dims": f"{selected_material.part_length} × {selected_material.part_width} × {selected_material.part_height}",
            "meta": meta,
        }

    return {
        "title": "Manual container",
        "dims": f'{_read_value(data, "box_l", "")} × {_read_value(data, "box_w", "")} × {_read_value(data, "box_h", "")}',
        "meta": "Manual dimensions",
    }