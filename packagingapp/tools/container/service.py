from django.conf import settings

from ...access import visible_packaging_catalogues, visible_product_catalogues
from ...forms import ContainerSelectionMode1Form
from ...models import PackagingCatalogue, PackagingMaterial, ProductCatalogue, Product
from ...utils.box_selection.engine import run_mode1_and_render, compute_max_quantity_only

from .serializers import sanitize_container_config_for_session


# Packaging types that behave like rectangular/cuboid containers in this module.
# BAG is handled by Bag Selection; PALLET is handled by Palletization.
CONTAINER_SELECTION_ALLOWED_PACKAGING_TYPES = ("BOX", "CRATE", "CONTAINER", "TRAILER")


def get_packaging_catalogues(user=None):
    return visible_packaging_catalogues(user).order_by("name")


def get_product_catalogues(user=None):
    return visible_product_catalogues(user).order_by("name")


def get_products_for_catalogue(config):
    product_catalogue_id = config.get("product_catalogue_id")
    if not product_catalogue_id:
        return Product.objects.none()

    return Product.objects.filter(
        catalogue_id=product_catalogue_id
    ).select_related("catalogue").order_by("-created_at")


def get_materials_for_catalogue(config):
    catalogue_id = config.get("catalogue_id")
    if not catalogue_id:
        return PackagingMaterial.objects.none()

    return PackagingMaterial.objects.filter(
        catalogue_id=catalogue_id,
        packaging_type__in=CONTAINER_SELECTION_ALLOWED_PACKAGING_TYPES,
    ).select_related("catalogue").order_by("packaging_type", "part_number")


def get_selected_product(config):
    selected_product_id = config.get("selected_product_id")
    if not selected_product_id:
        return None

    return Product.objects.filter(
        id=selected_product_id
    ).select_related("catalogue").first()


def get_selected_material(config):
    container_id = config.get("container_id")
    if not container_id:
        return None

    return PackagingMaterial.objects.filter(
        id=container_id,
        packaging_type__in=CONTAINER_SELECTION_ALLOWED_PACKAGING_TYPES,
    ).select_related("catalogue").first()


def build_hydrated_post_data(raw_post, config, selected_product=None, selected_material=None):
    post_data = raw_post.copy()

    if config.get("product_source") == "catalogue" and selected_product is not None:
        post_data["product_l"] = "" if selected_product.product_length is None else str(selected_product.product_length)
        post_data["product_w"] = "" if selected_product.product_width is None else str(selected_product.product_width)
        post_data["product_h"] = "" if selected_product.product_height is None else str(selected_product.product_height)

        if (
            post_data.get("product_weight") in (None, "", "None")
            and getattr(selected_product, "weight", None) is not None
        ):
            post_data["product_weight"] = str(selected_product.weight)

        post_data["r1"] = "on" if bool(getattr(selected_product, "rotation_1", False)) else ""
        post_data["r2"] = "on" if bool(getattr(selected_product, "rotation_2", False)) else ""
        post_data["r3"] = "on" if bool(getattr(selected_product, "rotation_3", False)) else ""

        if (
            config.get("mode") == "optimal"
            and getattr(selected_product, "desired_qty", None) not in (None, "", "None")
        ):
            post_data["desired_qty"] = str(selected_product.desired_qty)

    if config.get("container_source") == "catalogue" and selected_material is not None:
        post_data["box_l"] = "" if selected_material.part_length is None else str(selected_material.part_length)
        post_data["box_w"] = "" if selected_material.part_width is None else str(selected_material.part_width)
        post_data["box_h"] = "" if selected_material.part_height is None else str(selected_material.part_height)

    return post_data


def build_initial_data(config, selected_product=None, selected_material=None):
    initial_data = dict(config)

    if config.get("product_source") == "catalogue" and selected_product is not None:
        initial_data.update({
            "product_l": selected_product.product_length,
            "product_w": selected_product.product_width,
            "product_h": selected_product.product_height,
            "product_weight": getattr(selected_product, "weight", None),
            "r1": bool(getattr(selected_product, "rotation_1", False)),
            "r2": bool(getattr(selected_product, "rotation_2", False)),
            "r3": bool(getattr(selected_product, "rotation_3", False)),
        })
        if config.get("mode") == "optimal":
            initial_data["desired_qty"] = getattr(selected_product, "desired_qty", 1) or 1

    if config.get("container_source") == "catalogue" and selected_material is not None:
        initial_data.update({
            "box_l": selected_material.part_length,
            "box_w": selected_material.part_width,
            "box_h": selected_material.part_height,
        })

    return initial_data


def build_container_form(request, config, selected_product=None, selected_material=None):
    if request.method == "POST":
        hydrated_post = build_hydrated_post_data(
            raw_post=request.POST,
            config=config,
            selected_product=selected_product,
            selected_material=selected_material,
        )
        return ContainerSelectionMode1Form(hydrated_post)

    initial_data = build_initial_data(
        config=config,
        selected_product=selected_product,
        selected_material=selected_material,
    )
    return ContainerSelectionMode1Form(initial=initial_data)


def apply_catalogue_choices(form, packaging_catalogues, product_catalogues):
    form.fields["catalogue_id"].choices = [("", "— Select —")] + [
        (str(c.id), c.name) for c in packaging_catalogues
    ]
    form.fields["product_catalogue_id"].choices = [("", "— Select —")] + [
        (str(c.id), c.name) for c in product_catalogues
    ]


def resolve_product_from_form(form, product_source, selected_product):
    if product_source == "catalogue":
        if not selected_product:
            return None, 0, 0, 0

        product = (
            float(selected_product.product_length),
            float(selected_product.product_width),
            float(selected_product.product_height),
        )
        r1 = 1 if bool(getattr(selected_product, "rotation_1", False)) else 0
        r2 = 1 if bool(getattr(selected_product, "rotation_2", False)) else 0
        r3 = 1 if bool(getattr(selected_product, "rotation_3", False)) else 0
        return product, r1, r2, r3

    r1 = 1 if form.cleaned_data.get("r1") else 0
    r2 = 1 if form.cleaned_data.get("r2") else 0
    r3 = 1 if form.cleaned_data.get("r3") else 0

    product = None
    if (
        form.cleaned_data.get("product_l") is not None
        and form.cleaned_data.get("product_w") is not None
        and form.cleaned_data.get("product_h") is not None
    ):
        product = (
            float(form.cleaned_data["product_l"]),
            float(form.cleaned_data["product_w"]),
            float(form.cleaned_data["product_h"]),
        )

    return product, r1, r2, r3


def resolve_container_from_form(form, container_source, selected_material):
    if container_source == "catalogue":
        if not selected_material:
            return None
        return (
            float(selected_material.part_length),
            float(selected_material.part_width),
            float(selected_material.part_height),
        )

    bl = form.cleaned_data.get("box_l")
    bw = form.cleaned_data.get("box_w")
    bh = form.cleaned_data.get("box_h")

    if bl is None or bw is None or bh is None:
        return None

    return (float(bl), float(bw), float(bh))


def resolve_desired_qty(form, mode, product_source, selected_product):
    desired_qty = int(form.cleaned_data.get("desired_qty") or 1)

    if product_source == "catalogue" and selected_product and mode == "optimal":
        desired_qty = int(getattr(selected_product, "desired_qty", 1) or 1)

    return desired_qty


def _score_top5_candidates(product, materials, desired_qty, r1, r2, r3):
    product_vol = product[0] * product[1] * product[2]
    scored = []

    for m in materials:
        container = (
            float(m.part_length),
            float(m.part_width),
            float(m.part_height),
        )
        max_qty = compute_max_quantity_only(product, container, r1, r2, r3)

        if max_qty >= desired_qty:
            container_vol = (
                float(m.part_volume)
                if m.part_volume is not None
                else (container[0] * container[1] * container[2])
            )
            usage = (
                (desired_qty * product_vol) / container_vol
                if container_vol > 0
                else 0.0
            )

            scored.append({
                "material": m,
                "max_qty": max_qty,
                "usage": usage,
                "container_vol": container_vol,
            })

    scored.sort(key=lambda x: (-x["usage"], x["container_vol"]))
    return scored[:5]



def _safe_float(value):
    if value in (None, "", "None"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _round_or_none(value, digits=2):
    if value is None:
        return None
    return round(float(value), digits)


def _round_int_or_none(value):
    if value is None:
        return None
    return int(round(float(value)))


def _format_percent(value):
    if value is None:
        return "Not available"
    return f"{_round_int_or_none(value)}%"


def _format_weight(value):
    """
    Weight inputs in this tool are stored in grams. Keep the report compact:
    show grams for smaller values and whole kilograms for larger values.
    """
    numeric_value = _safe_float(value)
    if numeric_value is None:
        return "Not available"

    if abs(numeric_value) >= 1000:
        return f"{int(round(numeric_value / 1000))} kg"

    return f"{int(round(numeric_value))} g"


def _first_available_numeric_attr(obj, attr_names):
    if obj is None:
        return None

    for attr_name in attr_names:
        value = getattr(obj, attr_name, None)
        numeric_value = _safe_float(value)
        if numeric_value is not None:
            return numeric_value

    return None


def _resolve_product_weight(form, product_source, selected_product):
    if product_source == "catalogue" and selected_product is not None:
        return _safe_float(getattr(selected_product, "weight", None))

    return _safe_float(form.cleaned_data.get("product_weight"))


def _resolve_container_tare(form, container_source, selected_material):
    if container_source == "manual":
        return _safe_float(form.cleaned_data.get("box_weight"))

    return _safe_float(getattr(selected_material, "part_weight", None))


def _resolve_payload_capacity(form, container_source, selected_material):
    """
    Manual containers can provide max payload directly in grams.

    PackagingMaterial currently stores tare as part_weight, but no confirmed
    payload field. Keep the catalogue side future-safe: if a payload-like
    field is added later, the report will start using it without changing
    the template contract.
    """
    if container_source == "manual":
        return _safe_float(form.cleaned_data.get("box_max_payload"))

    return _first_available_numeric_attr(
        selected_material,
        [
            "max_payload",
            "payload_capacity",
            "max_payload_kg",
            "max_load",
            "max_load_kg",
            "max_weight",
            "max_weight_kg",
        ],
    )


def build_container_analysis_report(
    *,
    form,
    result,
    product,
    container,
    desired_qty,
    product_source,
    mode="single",
    selected_product=None,
    selected_material=None,
):
    """
    Build a compact, JSON-safe report used by both the standalone Container
    Selection Tool and the full packaging workflow.
    """
    if result is None or product is None or container is None:
        return None

    max_quantity = int(getattr(result, "max_quantity", 0) or 0)
    requested_qty = max_quantity if mode == "single" else int(desired_qty or 1)

    product_volume = float(product[0]) * float(product[1]) * float(product[2])
    container_volume = float(container[0]) * float(container[1]) * float(container[2])
    current_product_volume = product_volume * requested_qty
    max_product_volume = product_volume * max_quantity

    current_efficiency_pct = None
    max_efficiency_pct = None
    if container_volume > 0:
        current_efficiency_pct = (current_product_volume / container_volume) * 100
        max_efficiency_pct = (max_product_volume / container_volume) * 100

    product_weight = _resolve_product_weight(form, product_source, selected_product)
    container_source = form.cleaned_data.get("container_source") or "manual"
    container_tare = _resolve_container_tare(form, container_source, selected_material)
    payload_capacity = _resolve_payload_capacity(form, container_source, selected_material)

    net_weight = None
    total_weight_current = None
    payload_usage_pct = None

    if product_weight is not None:
        net_weight = product_weight * requested_qty
        if container_tare is not None:
            total_weight_current = net_weight + container_tare
        if payload_capacity and payload_capacity > 0:
            payload_usage_pct = (net_weight / payload_capacity) * 100

    remaining_capacity = max(max_quantity - requested_qty, 0)

    return {
        "requested_qty": requested_qty,
        "max_quantity": max_quantity,
        "remaining_capacity": remaining_capacity,
        "volumetric_efficiency_current_pct": _round_int_or_none(current_efficiency_pct),
        "volumetric_efficiency_max_pct": _round_int_or_none(max_efficiency_pct),
        "unused_volume_current_pct": _round_int_or_none(
            100 - current_efficiency_pct if current_efficiency_pct is not None else None
        ),
        "product_volume": _round_or_none(product_volume, 2),
        "container_volume": _round_or_none(container_volume, 2),
        "current_product_volume": _round_or_none(current_product_volume, 2),
        "max_product_volume": _round_or_none(max_product_volume, 2),
        "product_weight": _round_or_none(product_weight, 3),
        "container_tare": _round_or_none(container_tare, 3),
        "payload_capacity": _round_or_none(payload_capacity, 3),
        "net_weight": _round_or_none(net_weight, 3),
        "total_weight_current": _round_or_none(total_weight_current, 3),
        "payload_usage_pct": _round_int_or_none(payload_usage_pct),
        "volumetric_efficiency_current_display": _format_percent(current_efficiency_pct),
        "volumetric_efficiency_max_display": _format_percent(max_efficiency_pct),
        "unused_volume_current_display": _format_percent(
            100 - current_efficiency_pct if current_efficiency_pct is not None else None
        ),
        "product_weight_display": _format_weight(product_weight),
        "container_tare_display": _format_weight(container_tare),
        "payload_capacity_display": _format_weight(payload_capacity),
        "net_weight_display": _format_weight(net_weight),
        "total_weight_current_display": _format_weight(total_weight_current),
        "payload_usage_display": _format_percent(payload_usage_pct),
        "has_product_weight": product_weight is not None,
        "has_container_tare": container_tare is not None,
        "has_payload_capacity": payload_capacity is not None,
        "has_total_weight_current": total_weight_current is not None,
        "has_payload_usage": payload_usage_pct is not None,
    }

def analyze_container_form(
    form,
    config,
    selected_product=None,
    selected_material=None,
    materials=None,
    media_root=None,
):
    result = None
    image_url = None
    top5 = []
    messages = []
    analysis_report = None

    mode = form.cleaned_data.get("mode") or "single"
    action = form.cleaned_data.get("action") or ""

    product_source = form.cleaned_data.get("product_source") or "manual"
    container_source = form.cleaned_data.get("container_source") or "manual"

    product, r1, r2, r3 = resolve_product_from_form(
        form=form,
        product_source=product_source,
        selected_product=selected_product,
    )

    if r1 == 0 and r2 == 0 and r3 == 0:
        messages.append("Please enable at least one rotation option.")

    desired_qty = resolve_desired_qty(
        form=form,
        mode=mode,
        product_source=product_source,
        selected_product=selected_product,
    )

    if mode == "single" and not messages:
        should_run_single = action in ("run_single", "select_container")

        if should_run_single:
            container = None

            if product_source == "catalogue" and not selected_product:
                messages.append("Please select a product from the product catalogue.")
            elif product_source == "manual" and product is None:
                messages.append("Please enter product dimensions.")

            if not messages:
                container = resolve_container_from_form(
                    form=form,
                    container_source=container_source,
                    selected_material=selected_material,
                )

                if container_source == "manual" and container is None:
                    messages.append("Please enter all manual container dimensions (L/W/H).")
                elif container_source == "catalogue" and selected_material is None:
                    messages.append("Please select a packaging item from the catalogue table.")

            if not messages and container is not None and product is not None:
                render_result = run_mode1_and_render(
                    product,
                    container,
                    r1,
                    r2,
                    r3,
                    media_root or settings.MEDIA_ROOT,
                    render_style="clean",
                )
                result = render_result
                analysis_report = build_container_analysis_report(
                    form=form,
                    result=render_result,
                    product=product,
                    container=container,
                    desired_qty=desired_qty,
                    product_source=product_source,
                    mode=mode,
                    selected_product=selected_product,
                    selected_material=selected_material,
                )
                if getattr(render_result, "image_rel_path", None):
                    image_url = settings.MEDIA_URL + render_result.image_rel_path

    if mode == "optimal" and not messages:
        if action in ("find_top5", "select_candidate"):
            if product_source == "catalogue" and not selected_product:
                messages.append("Please select a product from the product catalogue.")
            elif product_source == "manual" and product is None:
                messages.append("Please enter product dimensions.")
            elif not config.get("catalogue_id"):
                messages.append("Please select a packaging catalogue.")

            if not messages:
                if materials is None:
                    materials = get_materials_for_catalogue(config)

                top5 = _score_top5_candidates(
                    product=product,
                    materials=materials,
                    desired_qty=desired_qty,
                    r1=r1,
                    r2=r2,
                    r3=r3,
                )

                if action == "select_candidate":
                    if not selected_material:
                        messages.append("Please select one of the Top 5 containers.")
                    else:
                        container = (
                            float(selected_material.part_length),
                            float(selected_material.part_width),
                            float(selected_material.part_height),
                        )
                        render_result = run_mode1_and_render(
                            product,
                            container,
                            r1,
                            r2,
                            r3,
                            media_root or settings.MEDIA_ROOT,
                            draw_limit=desired_qty,
                            render_style="clean",
                        )
                        result = render_result
                        analysis_report = build_container_analysis_report(
                            form=form,
                            result=render_result,
                            product=product,
                            container=container,
                            desired_qty=desired_qty,
                            product_source=product_source,
                            mode=mode,
                            selected_product=selected_product,
                            selected_material=selected_material,
                        )
                        if getattr(render_result, "image_rel_path", None):
                            image_url = settings.MEDIA_URL + render_result.image_rel_path

    return {
        "ok": len(messages) == 0,
        "messages": messages,
        "result": result,
        "image_url": image_url,
        "threejs_scene": getattr(result, "threejs_scene", None) if result is not None else None,
        "analysis_report": analysis_report,
        "top5": top5,
    }
