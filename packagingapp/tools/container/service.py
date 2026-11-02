from django.conf import settings

from ...access import visible_packaging_catalogues, visible_product_catalogues
from ...forms import ContainerSelectionMode1Form
from ...models import (
    CorrugatedBoardConstruction,
    CorrugatedECTReferenceGrade,
    PackagingCatalogue,
    PackagingMaterial,
    ProductCatalogue,
    Product,
)
from ...units import (
    LENGTH_UNITS,
    MASS_UNITS,
    UnsupportedUnitError,
    convert_length,
    convert_mass,
    format_dimensions,
    format_length,
    format_mass,
    kg_to_g,
)
from ...units.input import convert_optional, validate_unit
from ...utils.box_selection.engine import (
    build_container_design_candidates,
    compute_max_quantity_only,
    render_product_base_unit,
    run_mode1_and_render,
)
from ..product_shape import (
    build_product_unit_scene,
    decorate_product_scene,
    normalize_product_shape,
)
from ..product_dimensions import (
    PRODUCT_ALLOWANCE_KEYS,
    apply_product_allowances,
    normalize_product_allowances,
)

from .serializers import sanitize_container_config_for_session
from .dimensions import (
    EXTERNAL_DIMENSION_SOURCE_CATALOGUE_THICKNESS,
    EXTERNAL_DIMENSION_SOURCE_PROVIDED_THICKNESS,
    resolve_external_carton_dimensions,
)
from .carton_tare import calculate_rsc_carton_tare
from .corrugated_material import (
    DEFAULT_MANUAL_RSC_MATERIAL_CODE,
    DEFAULT_MANUAL_RSC_CALIPER_MM,
    build_corrugated_material_options,
    corrugated_material_option,
    resolve_corrugated_caliper,
)


# Packaging types that behave like rectangular/cuboid containers in this module.
# BAG is handled by Bag Selection; PALLET is handled by Palletization.
CONTAINER_SELECTION_ALLOWED_PACKAGING_TYPES = ("BOX", "CRATE", "CONTAINER", "TRAILER")
_UNSCOPED_CATALOGUE_USER = object()


def get_packaging_catalogues(user=None):
    return visible_packaging_catalogues(user).order_by("name")


def get_product_catalogues(user=None):
    return visible_product_catalogues(user).order_by("name")


def get_products_for_catalogue(config, user=_UNSCOPED_CATALOGUE_USER):
    product_catalogue_id = config.get("product_catalogue_id")
    if not product_catalogue_id:
        return Product.objects.none()

    products = Product.objects.filter(
        catalogue_id=product_catalogue_id
    )
    if user is not _UNSCOPED_CATALOGUE_USER:
        products = products.filter(catalogue__in=visible_product_catalogues(user))
    return products.select_related("catalogue").order_by("-created_at")


def get_materials_for_catalogue(config, user=_UNSCOPED_CATALOGUE_USER):
    catalogue_id = config.get("catalogue_id")
    if not catalogue_id:
        return PackagingMaterial.objects.none()

    materials = PackagingMaterial.objects.filter(
        catalogue_id=catalogue_id,
        packaging_type__in=CONTAINER_SELECTION_ALLOWED_PACKAGING_TYPES,
    )
    if user is not _UNSCOPED_CATALOGUE_USER:
        materials = materials.filter(catalogue__in=visible_packaging_catalogues(user))
    return materials.select_related("catalogue").order_by("packaging_type", "part_number")


def get_selected_product(config, user=_UNSCOPED_CATALOGUE_USER):
    selected_product_id = config.get("selected_product_id")
    if not selected_product_id:
        return None

    products = Product.objects.filter(
        id=selected_product_id
    )
    if user is not _UNSCOPED_CATALOGUE_USER:
        products = products.filter(catalogue__in=visible_product_catalogues(user))
    return products.select_related("catalogue").first()


def get_selected_material(config, user=_UNSCOPED_CATALOGUE_USER):
    container_id = config.get("container_id")
    if not container_id:
        return None

    materials = PackagingMaterial.objects.filter(
        id=container_id,
        packaging_type__in=CONTAINER_SELECTION_ALLOWED_PACKAGING_TYPES,
    )
    if user is not _UNSCOPED_CATALOGUE_USER:
        materials = materials.filter(catalogue__in=visible_packaging_catalogues(user))
    return materials.select_related("catalogue").first()


def get_corrugated_materials():
    """Return the active shared corrugated-board construction catalogue."""
    return CorrugatedBoardConstruction.objects.filter(is_active=True).order_by(
        "sort_order", "wall_type", "flute_1", "flute_2", "name"
    )


def get_corrugated_material_options(constructions=None, *, dimension_unit="mm"):
    """Return board options with canonical values and current display units."""
    boards = list(
        constructions if constructions is not None else get_corrugated_materials()
    )
    if not boards:
        return []
    reference_grades = CorrugatedECTReferenceGrade.objects.filter(
        is_active=True
    ).order_by("flute_family", "ect_lb_in", "code")
    return build_corrugated_material_options(
        boards,
        reference_grades,
        dimension_unit=dimension_unit,
    )


def get_selected_corrugated_construction(config=None, form=None):
    """Resolve one active board construction, or ``None`` for custom/none."""
    cleaned = getattr(form, "cleaned_data", {}) or {}
    if "corrugated_material_id" in cleaned:
        # A bound form's explicit empty choice means "no calculation". Do not
        # resurrect a previous session value when the user clears the field.
        raw_id = cleaned.get("corrugated_material_id")
    else:
        raw_id = (config or {}).get("corrugated_material_id")
    raw_id = str(raw_id or "").strip()
    if not raw_id or raw_id == "custom":
        return None
    materials = get_corrugated_materials()
    by_code = materials.filter(code=raw_id).first()
    if by_code is not None:
        return by_code
    try:
        return materials.filter(pk=int(raw_id)).first()
    except (TypeError, ValueError):
        return None


def _corrugated_material_label(construction):
    reference_grades = CorrugatedECTReferenceGrade.objects.filter(
        is_active=True
    ).order_by("flute_family", "ect_lb_in", "code")
    return corrugated_material_option(
        construction,
        resolve_corrugated_caliper(construction, reference_grades),
    )["label"]


def build_hydrated_post_data(raw_post, config, selected_product=None, selected_material=None):
    post_data = raw_post.copy()
    post_data["mode"] = (config or {}).get("mode") or "single"
    post_data["product_shape"] = normalize_product_shape(
        (config or {}).get("product_shape")
    )

    if (config or {}).get("mode") == "design":
        post_data.setdefault("container_source", "manual")

    if config.get("product_source") == "catalogue" and selected_product is not None:
        post_data["product_l"] = "" if selected_product.product_length is None else str(selected_product.product_length)
        post_data["product_w"] = "" if selected_product.product_width is None else str(selected_product.product_width)
        post_data["product_h"] = "" if selected_product.product_height is None else str(selected_product.product_height)

        if (
            post_data.get("product_weight") in (None, "", "None")
            and getattr(selected_product, "weight", None) is not None
        ):
            post_data["product_weight"] = str(kg_to_g(selected_product.weight))

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
            "product_weight": (
                kg_to_g(selected_product.weight)
                if getattr(selected_product, "weight", None) is not None
                else None
            ),
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


def apply_catalogue_choices(
    form,
    packaging_catalogues,
    product_catalogues,
    corrugated_materials=None,
    container_dimension_unit="mm",
):
    form.fields["catalogue_id"].choices = [("", "— Select —")] + [
        (str(c.id), c.name) for c in packaging_catalogues
    ]
    form.fields["product_catalogue_id"].choices = [("", "— Select —")] + [
        (str(c.id), c.name) for c in product_catalogues
    ]
    # Keep this helper side-effect free for pure-service callers and
    # SimpleTestCase fixtures. Views pass the active construction queryset when
    # they render a customer-facing form.
    constructions = list(corrugated_materials) if corrugated_materials is not None else []
    options = get_corrugated_material_options(
        constructions,
        dimension_unit=container_dimension_unit,
    ) if constructions else []
    current_value = ""
    if getattr(form, "is_bound", False):
        current_value = str(form.data.get("corrugated_material_id") or "")
    else:
        current_value = str(form.initial.get("corrugated_material_id") or "")
    choices = [("", "No carton tare calculation")]
    if current_value == "custom":
        # Compatibility only: new configurations never receive this option.
        choices.append(("custom", "Legacy custom material (preserved)"))
    for option in options:
        choices.append((option["code"], option["label"]))
        # Persisted pre-4B sessions used numeric primary keys.  Keep the old
        # value valid while all newly created selections use the stable code.
        if option["id"] and option["id"] != option["code"] and current_value == option["id"]:
            choices.append((option["id"], option["label"]))
    form.fields["corrugated_material_id"].choices = choices


def apply_manual_rsc_design_defaults(config, *, enabled=False):
    """Apply defaults only to a newly created manual Design configuration."""
    if not enabled or not config:
        return config
    if (
        config.get("mode") != "design"
        or config.get("container_source") != "manual"
        or config.get("corrugated_material_id")
        or str(config.get("corrugated_material_user_selected") or "") == "1"
    ):
        return config
    config = dict(config)
    config["corrugated_material_id"] = DEFAULT_MANUAL_RSC_MATERIAL_CODE
    config["box_thickness_user_override"] = "0"
    if not config.get("box_thickness_mm") and not str(
        config.get("box_thickness_user_override") or ""
    ) == "1":
        unit = config.get("container_dimension_unit") or "mm"
        config["box_thickness_mm"] = str(
            convert_length(DEFAULT_MANUAL_RSC_CALIPER_MM, "mm", unit)
        )
    return config


def resolve_product_from_form(form, product_source, selected_product, normalized_product=None):
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

    if normalized_product is not None:
        return normalized_product, r1, r2, r3

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


def resolve_container_from_form(form, container_source, selected_material, normalized_container=None):
    if container_source == "catalogue":
        if not selected_material:
            return None
        return (
            float(selected_material.part_length),
            float(selected_material.part_width),
            float(selected_material.part_height),
        )

    if normalized_container is not None:
        return normalized_container

    bl = form.cleaned_data.get("box_l")
    bw = form.cleaned_data.get("box_w")
    bh = form.cleaned_data.get("box_h")

    if bl is None or bw is None or bh is None:
        return None

    return (float(bl), float(bw), float(bh))


def _resolve_board_caliper(selected_board_construction):
    """Resolve one selected construction's finished-board caliper."""
    if selected_board_construction is None:
        return resolve_corrugated_caliper(None)
    cached = getattr(selected_board_construction, "_resolved_corrugated_caliper", None)
    if cached is not None:
        return cached
    # Lightweight test doubles and legacy callers may only provide grammage;
    # they must not trigger a hidden catalogue query.
    if not hasattr(selected_board_construction, "flute_1") and not hasattr(
        selected_board_construction, "caliper_mm"
    ):
        return resolve_corrugated_caliper(selected_board_construction)
    actual = resolve_corrugated_caliper(selected_board_construction)
    if actual.source == "actual":
        return actual
    reference_grades = CorrugatedECTReferenceGrade.objects.filter(
        is_active=True
    ).order_by("flute_family", "ect_lb_in", "code")
    resolved = resolve_corrugated_caliper(selected_board_construction, reference_grades)
    try:
        selected_board_construction._resolved_corrugated_caliper = resolved
    except (AttributeError, TypeError):
        pass
    return resolved


def resolve_container_dimension_contract(
    form,
    container,
    container_source,
    selected_material=None,
    selected_board_construction=None,
):
    """Return the shared JSON-safe internal/external carton dimension contract."""
    if container is None:
        return None

    if container_source == "catalogue" and selected_material is not None:
        return resolve_external_carton_dimensions(
            *container,
            external_length=getattr(selected_material, "external_length", None),
            external_width=getattr(selected_material, "external_width", None),
            external_height=getattr(selected_material, "external_height", None),
            thickness_mm=getattr(selected_material, "box_thickness_mm", None),
            thickness_source=EXTERNAL_DIMENSION_SOURCE_CATALOGUE_THICKNESS,
        )

    thickness_mm = _resolve_manual_quantity(
        form,
        "box_thickness_mm",
        "container_dimension_unit",
        convert_length,
        "mm",
    )
    if thickness_mm is None:
        thickness_mm = _resolve_board_caliper(
            selected_board_construction
        ).value_mm

    return resolve_external_carton_dimensions(
        *container,
        thickness_mm=thickness_mm,
        thickness_source=EXTERNAL_DIMENSION_SOURCE_PROVIDED_THICKNESS,
    )


def resolve_desired_qty(form, mode, product_source, selected_product):
    desired_qty = int(form.cleaned_data.get("desired_qty") or 1)

    if product_source == "catalogue" and selected_product and mode == "optimal":
        desired_qty = int(getattr(selected_product, "desired_qty", 1) or 1)

    return desired_qty


def inspect_container_readiness(
    form,
    config,
    selected_product=None,
    selected_material=None,
):
    """Inspect calculation prerequisites without running a packing engine.

    Django form validation remains authoritative for types, choices, and
    numeric ranges.  This helper centralizes the source- and mode-dependent
    checks that a consumer needs when deciding whether the current state is
    ready to calculate.  It deliberately returns structured issues rather
    than mutating the form or calculating a result.
    """
    mode = form.cleaned_data.get("mode") or config.get("mode") or "single"
    product_source = (
        form.cleaned_data.get("product_source")
        or config.get("product_source")
        or "manual"
    )
    container_source = (
        form.cleaned_data.get("container_source")
        or config.get("container_source")
        or "manual"
    )

    issues = []

    def add_issue(field, code, message):
        issues.append({"field": field, "code": code, "message": message})

    normalized_inputs = _normalize_manual_container_inputs(
        form, config, product_source, container_source
    )
    for message in normalized_inputs["messages"]:
        add_issue("units", "unsupported_unit", message)

    try:
        product, r1, r2, r3 = resolve_product_from_form(
            form=form,
            product_source=product_source,
            selected_product=selected_product,
            normalized_product=normalized_inputs["product"],
        )
    except (TypeError, ValueError):
        product, r1, r2, r3 = None, 0, 0, 0

    if product_source == "catalogue" and selected_product is None:
        add_issue(
            "product.dimensions",
            "catalogue_selection_required",
            "Select a product from the visible catalogue.",
        )
    elif product is None:
        for field_name, label in (
            ("product_l", "length"),
            ("product_w", "width"),
            ("product_h", "height"),
        ):
            if form.cleaned_data.get(field_name) is None:
                add_issue(
                    f"product.dimensions.{label}",
                    "required",
                    f"Product {label} is required.",
                )

    if not any((r1, r2, r3)):
        add_issue(
            "product.allowed_vertical_axes",
            "required",
            "Enable at least one permitted product orientation.",
        )

    try:
        desired_quantity = resolve_desired_qty(
            form=form,
            mode=mode,
            product_source=product_source,
            selected_product=selected_product,
        )
    except (TypeError, ValueError):
        desired_quantity = None
    if desired_quantity is None or int(desired_quantity) <= 0:
        add_issue(
            "request.desired_quantity",
            "required",
            "Desired quantity must be a positive whole number.",
        )

    container = None
    if mode == "single":
        try:
            container = resolve_container_from_form(
                form=form,
                container_source=container_source,
                selected_material=selected_material,
                normalized_container=normalized_inputs["container"],
            )
        except (TypeError, ValueError):
            container = None
        if container_source == "catalogue" and selected_material is None:
            add_issue(
                "container.internal_dimensions",
                "catalogue_selection_required",
                "Select a packaging item from the visible catalogue.",
            )
        elif container is None:
            for field_name, label in (
                ("box_l", "length"),
                ("box_w", "width"),
                ("box_h", "height"),
            ):
                if form.cleaned_data.get(field_name) is None:
                    add_issue(
                        f"container.internal_dimensions.{label}",
                        "required",
                        f"Container {label} is required.",
                    )
    elif mode == "optimal" and not config.get("catalogue_id"):
        add_issue(
            "container.catalogue_selection",
            "required",
            "Select a visible packaging catalogue.",
        )

    return {
        "mode": mode,
        "product_source": product_source,
        "container_source": container_source,
        "product": product,
        "container": container,
        "r1": r1,
        "r2": r2,
        "r3": r3,
        "desired_quantity": desired_quantity,
        "issues": issues,
    }


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


def _form_or_config_value(form, config, key, default=None):
    cleaned = getattr(form, "cleaned_data", {}) or {}
    value = cleaned.get(key)
    if value in (None, ""):
        data = getattr(form, "data", {}) or {}
        value = data.get(key)
    if value in (None, ""):
        value = (config or {}).get(key, default)
    return default if value in (None, "") else value


def _unit_from_form_or_config(form, config, key, definitions, default, label, messages):
    raw = _form_or_config_value(form, config, key, default)
    try:
        return validate_unit(raw, definitions, default, label)
    except UnsupportedUnitError as exc:
        messages.append(str(exc))
        return None


def _convert_manual(value, unit, converter, label, messages):
    if value in (None, "", "None") or unit is None:
        return None
    try:
        return convert_optional(value, unit, converter, "mm" if converter is convert_length else "g")
    except (TypeError, ValueError, UnsupportedUnitError):
        if not any(label in message for message in messages):
            messages.append(f"Invalid {label} value.")
        return None


def _normalize_manual_container_inputs(form, config, product_source, container_source):
    messages = []
    product_dimension_unit = _unit_from_form_or_config(
        form, config, "product_dimension_unit", LENGTH_UNITS, "mm", "product dimension", messages
    )
    product_mass_unit = _unit_from_form_or_config(
        form, config, "product_mass_unit", MASS_UNITS, "g", "product mass", messages
    )
    container_dimension_unit = _unit_from_form_or_config(
        form, config, "container_dimension_unit", LENGTH_UNITS, "mm", "container dimension", messages
    )
    container_mass_unit = _unit_from_form_or_config(
        form, config, "container_mass_unit", MASS_UNITS, "g", "container mass", messages
    )

    product = None
    if product_source == "manual" and product_dimension_unit is not None:
        product = tuple(
            _convert_manual(
                _form_or_config_value(form, config, key),
                product_dimension_unit,
                convert_length,
                "product dimension",
                messages,
            )
            for key in ("product_l", "product_w", "product_h")
        )
        if any(value is None for value in product):
            product = None

    try:
        product_allowances = normalize_product_allowances(
            tuple(
                _form_or_config_value(form, config, key, "0")
                for key in PRODUCT_ALLOWANCE_KEYS
            ),
            product_dimension_unit or "mm",
        )
    except (TypeError, ValueError, UnsupportedUnitError):
        product_allowances = (0.0, 0.0, 0.0)
        messages.append("Product dimensional allowances must be finite and non-negative.")

    container = None
    if container_source == "manual" and container_dimension_unit is not None:
        container = tuple(
            _convert_manual(
                _form_or_config_value(form, config, key),
                container_dimension_unit,
                convert_length,
                "container dimension",
                messages,
            )
            for key in ("box_l", "box_w", "box_h")
        )
        if any(value is None for value in container):
            container = None

    return {
        "product": product,
        "product_allowances": product_allowances,
        "container": container,
        "product_dimension_unit": product_dimension_unit,
        "product_mass_unit": product_mass_unit,
        "container_dimension_unit": container_dimension_unit,
        "container_mass_unit": container_mass_unit,
        "messages": messages,
    }


def _resolve_manual_quantity(form, key, unit_key, converter, canonical_unit):
    cleaned = getattr(form, "cleaned_data", {}) or {}
    value = cleaned.get(key)
    if value in (None, ""):
        return None
    unit = cleaned.get(unit_key) or ("mm" if canonical_unit == "mm" else "g")
    try:
        return convert_optional(value, unit, converter, canonical_unit)
    except (TypeError, ValueError, UnsupportedUnitError):
        return None


def _resolve_product_weight(form, product_source, selected_product):
    if product_source == "catalogue" and selected_product is not None:
        weight_kg = getattr(selected_product, "weight", None)
        return _safe_float(kg_to_g(weight_kg)) if weight_kg is not None else None

    return _resolve_manual_quantity(
        form,
        "product_weight",
        "product_mass_unit",
        convert_mass,
        "g",
    )


RSC_ELIGIBLE_PACKAGING_TYPES = ("BOX",)


def _corrugated_grammage(form, config, selected_board_construction=None):
    cleaned = getattr(form, "cleaned_data", {}) or {}
    if "corrugated_material_id" in cleaned:
        material_id = cleaned.get("corrugated_material_id")
    else:
        material_id = (config or {}).get("corrugated_material_id")
    material_id = str(material_id or "").strip()

    if material_id == "custom":
        value = cleaned.get("custom_combined_grammage_g_m2")
        if value in (None, ""):
            value = (config or {}).get("custom_combined_grammage_g_m2")
        numeric = _safe_float(value)
        return numeric if numeric is not None and numeric > 0 else None

    if selected_board_construction is None:
        selected_board_construction = get_selected_corrugated_construction(
            config=config,
            form=form,
        )
    combined = getattr(selected_board_construction, "combined_grammage_g_m2", None)
    numeric = _safe_float(combined)
    return numeric if numeric is not None and numeric > 0 else None


def _rsc_estimate_is_eligible(container_source, selected_material):
    if container_source == "manual":
        return True
    return (
        selected_material is not None
        and getattr(selected_material, "packaging_type", None)
        in RSC_ELIGIBLE_PACKAGING_TYPES
    )


def _resolve_container_weight(
    form,
    container_source,
    selected_material,
    container,
    config=None,
    selected_board_construction=None,
):
    """Resolve one carton tare using the shared precedence contract."""
    if container_source == "catalogue":
        weight_kg = getattr(selected_material, "part_weight", None)
        if weight_kg is not None:
            return {
                "tare_g": _safe_float(kg_to_g(weight_kg)),
                "source": "catalogue",
                "source_label": "Known from catalogue",
                "reason": "",
            }

    explicit_tare = _resolve_manual_quantity(
        form,
        "box_weight",
        "container_mass_unit",
        convert_mass,
        "g",
    )
    if explicit_tare is not None:
        return {
            "tare_g": explicit_tare,
            "source": "manual",
            "source_label": "Manually supplied",
            "reason": "",
        }

    grammage = _corrugated_grammage(
        form,
        config,
        selected_board_construction=selected_board_construction,
    )
    if grammage is not None:
        if not _rsc_estimate_is_eligible(container_source, selected_material):
            return {
                "tare_g": None,
                "source": "unavailable",
                "source_label": "Not included",
                "reason": "FEFCO 0201 tare estimates apply only to eligible cartons.",
            }
        try:
            tare = calculate_rsc_carton_tare(
                *(container or (None, None, None)),
                combined_grammage_g_m2=grammage,
            )
        except (TypeError, ValueError):
            return {
                "tare_g": None,
                "source": "unavailable",
                "source_label": "Not included",
                "reason": "Carton dimensions are required for the corrugated tare estimate.",
            }
        if selected_board_construction is None:
            selected_board_construction = get_selected_corrugated_construction(
                config=config,
                form=form,
            )
        selected_id = getattr(selected_board_construction, "code", None)
        if not selected_id:
            selected_id = getattr(selected_board_construction, "pk", None)
        return {
            "tare_g": _safe_float(tare.finished_box_weight_g),
            "source": "estimated_material",
            "source_label": "Estimated from corrugated material",
            "reason": "",
            "corrugated_material_id": str(selected_id) if selected_id is not None else "custom",
            "corrugated_material_name": (
                getattr(selected_board_construction, "name", None)
                or "Custom grammage"
            ),
            "combined_grammage_g_m2": _safe_float(tare.combined_grammage_g_m2),
            "effective_box_area_m2": _safe_float(tare.effective_box_area_m2),
            "fefco_code": "0201",
        }

    return {
        "tare_g": None,
        "source": "unavailable",
        "source_label": "Not included",
        "reason": "Carton tare is not included because no material or authoritative tare was supplied.",
    }


def _resolve_container_tare(form, container_source, selected_material):
    """Backward-compatible tare accessor for existing callers."""
    return _resolve_container_weight(
        form,
        container_source,
        selected_material,
        container=None,
    ).get("tare_g")


def _resolve_payload_capacity(form, container_source, selected_material):
    """
    Manual containers can provide max payload directly in grams.

    PackagingMaterial currently stores tare as part_weight, but no confirmed
    payload field. Keep the catalogue side future-safe: if a payload-like
    field is added later, the report will start using it without changing
    the template contract.
    """
    if container_source == "manual":
        return _resolve_manual_quantity(
            form,
            "box_max_payload",
            "container_mass_unit",
            convert_mass,
            "g",
        )

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
    nominal_product=None,
    product_allowances=None,
    selected_board_construction=None,
):
    """
    Build a compact, JSON-safe report used by both the standalone Container
    Selection Tool and the full packaging workflow.
    """
    if result is None or product is None or container is None:
        return None

    nominal_product = nominal_product if nominal_product is not None else product
    product_allowances = tuple(product_allowances or (0.0, 0.0, 0.0))

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
    dimension_contract = resolve_container_dimension_contract(
        form,
        container,
        container_source,
        selected_material,
        selected_board_construction=selected_board_construction,
    )
    container_weight = _resolve_container_weight(
        form=form,
        container_source=container_source,
        selected_material=selected_material,
        container=container,
        selected_board_construction=selected_board_construction,
    )
    selected_caliper = _resolve_board_caliper(selected_board_construction)
    container_tare = container_weight.get("tare_g")
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
    product_dimension_unit = form.cleaned_data.get("product_dimension_unit") or "mm"
    product_mass_unit = form.cleaned_data.get("product_mass_unit") or "g"
    container_dimension_unit = form.cleaned_data.get("container_dimension_unit") or "mm"
    container_mass_unit = form.cleaned_data.get("container_mass_unit") or "g"

    return {
        **dimension_contract,
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
        "carton_tare_g": _round_or_none(container_tare, 3),
        "carton_tare_source": container_weight.get("source"),
        "carton_tare_source_display": container_weight.get("source_label"),
        "carton_tare_reason": container_weight.get("reason") or "",
        "carton_tare_estimated": container_weight.get("source") == "estimated_material",
        "gross_carton_weight_g": _round_or_none(total_weight_current, 3),
        "weight_source": container_weight.get("source"),
        "weight_source_display": container_weight.get("source_label"),
        "corrugated_material_name": container_weight.get("corrugated_material_name"),
        "corrugated_material_id": container_weight.get("corrugated_material_id"),
        "combined_grammage_g_m2": _round_or_none(
            container_weight.get("combined_grammage_g_m2"), 4
        ),
        "effective_box_area_m2": _round_or_none(
            container_weight.get("effective_box_area_m2"), 9
        ),
        "fefco_code": container_weight.get("fefco_code"),
        "corrugated_caliper_mm": _round_or_none(selected_caliper.value_mm, 3),
        "corrugated_caliper_source": selected_caliper.source,
        "corrugated_caliper_source_display": selected_caliper.source_label,
        "payload_capacity": _round_or_none(payload_capacity, 3),
        "net_weight": _round_or_none(net_weight, 3),
        "total_weight_current": _round_or_none(total_weight_current, 3),
        "payload_usage_pct": _round_int_or_none(payload_usage_pct),
        "volumetric_efficiency_current_display": _format_percent(current_efficiency_pct),
        "volumetric_efficiency_max_display": _format_percent(max_efficiency_pct),
        "unused_volume_current_display": _format_percent(
            100 - current_efficiency_pct if current_efficiency_pct is not None else None
        ),
        "display_units": {
            "product_dimension": product_dimension_unit,
            "product_mass": product_mass_unit,
            "container_dimension": container_dimension_unit,
            "container_mass": container_mass_unit,
        },
        "product_dimensions_display": format_dimensions(
            product[0], product[1], product[2], display_unit=product_dimension_unit
        ),
        "effective_product_dimensions_display": format_dimensions(
            product[0], product[1], product[2], display_unit=product_dimension_unit
        ),
        "nominal_product_dimensions_display": format_dimensions(
            nominal_product[0],
            nominal_product[1],
            nominal_product[2],
            display_unit=product_dimension_unit,
        ),
        "product_allowances_display": format_dimensions(
            product_allowances[0],
            product_allowances[1],
            product_allowances[2],
            display_unit=product_dimension_unit,
        ),
        "internal_dimensions_display": format_dimensions(
            dimension_contract.get("internal_length"),
            dimension_contract.get("internal_width"),
            dimension_contract.get("internal_height"),
            display_unit=container_dimension_unit,
        ),
        "external_dimensions_display": format_dimensions(
            dimension_contract.get("external_length"),
            dimension_contract.get("external_width"),
            dimension_contract.get("external_height"),
            display_unit=container_dimension_unit,
        ),
        "box_thickness_display": format_length(
            dimension_contract.get("box_thickness_mm"),
            display_unit=container_dimension_unit,
        ),
        "product_weight_display": format_mass(
            product_weight, canonical_unit="g", display_unit=product_mass_unit
        ),
        "container_tare_display": format_mass(
            container_tare, canonical_unit="g", display_unit=container_mass_unit
        ),
        "payload_capacity_display": format_mass(
            payload_capacity, canonical_unit="g", display_unit=container_mass_unit
        ),
        "net_weight_display": format_mass(
            net_weight, canonical_unit="g", display_unit=product_mass_unit
        ),
        "total_weight_current_display": format_mass(
            total_weight_current, canonical_unit="g", display_unit=container_mass_unit
        ),
        "carton_tare_display": format_mass(
            container_tare, canonical_unit="g", display_unit=container_mass_unit
        ),
        "gross_carton_weight_display": format_mass(
            total_weight_current, canonical_unit="g", display_unit=container_mass_unit
        ),
        "payload_usage_display": _format_percent(payload_usage_pct),
        "has_product_weight": product_weight is not None,
        "has_container_tare": container_tare is not None,
        "has_payload_capacity": payload_capacity is not None,
        "has_total_weight_current": total_weight_current is not None,
        "has_gross_carton_weight": total_weight_current is not None,
        "has_payload_usage": payload_usage_pct is not None,
    }


def _add_container_design_metrics(
    candidate,
    form,
    product_source,
    selected_product,
    selected_board_construction=None,
):
    row = dict(candidate)
    product_weight = _resolve_product_weight(form, product_source, selected_product)
    quantity = int(row["design_quantity"])
    net_weight = product_weight * quantity if product_weight is not None else None
    dimension_contract = resolve_container_dimension_contract(
        form,
        (
            row["container_length"],
            row["container_width"],
            row["container_height"],
        ),
        "manual",
        selected_board_construction=selected_board_construction,
    )
    container_weight = _resolve_container_weight(
        form=form,
        container_source="manual",
        selected_material=None,
        container=(
            row["container_length"],
            row["container_width"],
            row["container_height"],
        ),
        selected_board_construction=selected_board_construction,
    )
    selected_caliper = _resolve_board_caliper(selected_board_construction)
    container_tare = container_weight.get("tare_g")
    gross_weight = net_weight + container_tare if net_weight is not None and container_tare is not None else None
    row.update({
        **dimension_contract,
        "net_content_weight": _round_or_none(net_weight, 3),
        "net_content_weight_g": _round_or_none(net_weight, 3),
        "container_tare": _round_or_none(container_tare, 3),
        "carton_tare_g": _round_or_none(container_tare, 3),
        "container_tare_display": format_mass(
            container_tare,
            canonical_unit="g",
            display_unit=form.cleaned_data.get("container_mass_unit") or "g",
        ),
        "carton_tare_display": format_mass(
            container_tare,
            canonical_unit="g",
            display_unit=form.cleaned_data.get("container_mass_unit") or "g",
        ),
        "gross_carton_weight": _round_or_none(gross_weight, 3),
        "gross_carton_weight_g": _round_or_none(gross_weight, 3),
        "gross_carton_weight_display": format_mass(
            gross_weight,
            canonical_unit="g",
            display_unit=form.cleaned_data.get("container_mass_unit") or "g",
        ),
        "carton_tare_source": container_weight.get("source"),
        "carton_tare_source_display": container_weight.get("source_label"),
        "carton_tare_reason": container_weight.get("reason") or "",
        "weight_source": container_weight.get("source"),
        "weight_source_display": container_weight.get("source_label"),
        "carton_tare_estimated": container_weight.get("source") == "estimated_material",
        "corrugated_material_name": container_weight.get("corrugated_material_name"),
        "corrugated_material_id": container_weight.get("corrugated_material_id"),
        "combined_grammage_g_m2": _round_or_none(
            container_weight.get("combined_grammage_g_m2"), 4
        ),
        "effective_box_area_m2": _round_or_none(
            container_weight.get("effective_box_area_m2"), 9
        ),
        "fefco_code": container_weight.get("fefco_code"),
        "corrugated_caliper_mm": _round_or_none(selected_caliper.value_mm, 3),
        "corrugated_caliper_source": selected_caliper.source,
        "corrugated_caliper_source_display": selected_caliper.source_label,
        "container_dimensions_display": format_dimensions(
            row["container_length"],
            row["container_width"],
            row["container_height"],
            display_unit=form.cleaned_data.get("container_dimension_unit") or "mm",
        ),
        "external_dimensions_display": format_dimensions(
            dimension_contract.get("external_length"),
            dimension_contract.get("external_width"),
            dimension_contract.get("external_height"),
            display_unit=form.cleaned_data.get("container_dimension_unit") or "mm",
        ),
        "box_thickness_display": format_length(
            dimension_contract.get("box_thickness_mm"),
            display_unit=form.cleaned_data.get("container_dimension_unit") or "mm",
        ),
        "net_content_weight_display": format_mass(
            net_weight,
            canonical_unit="g",
            display_unit=form.cleaned_data.get("product_mass_unit") or "g",
        ),
    })
    return row


def _analyze_container_design(
    form,
    product,
    r1,
    r2,
    r3,
    product_source,
    container_source,
    selected_product,
    selected_material,
    initial_messages=None,
    packing_product=None,
    product_allowances=None,
    selected_board_construction=None,
):
    packing_product = packing_product if packing_product is not None else product
    product_allowances = tuple(product_allowances or (0.0, 0.0, 0.0))
    messages = list(initial_messages or [])
    notices = []
    desired_quantity = form.cleaned_data.get("desired_qty")
    action = form.cleaned_data.get("action") or ""
    if packing_product is None or any(float(value) <= 0 for value in packing_product):
        messages.append("Enter product length, width, and height greater than zero in millimetres.")
    if desired_quantity is None or int(desired_quantity) <= 0:
        messages.append("Enter the desired quantity as a positive whole number.")
    if not any((r1, r2, r3)):
        messages.append("Enable at least one permitted product orientation.")
    base = {
        "messages": messages,
        "notices": notices,
        "result": None,
        "image_url": None,
        "threejs_scene": None,
        "product_unit_scene": build_product_unit_scene(
            product,
            form.cleaned_data.get("product_shape"),
            display_unit=form.cleaned_data.get("product_dimension_unit") or "mm",
        ),
        "analysis_report": None,
        "product_base_image_rel_path": "",
        "product_base_image_url": None,
        "top5": [],
        "design_candidates": [],
        "selected_design_candidate_id": form.cleaned_data.get("selected_design_candidate_id") or "",
    }
    if action not in ("run_design", "select_design_candidate") or messages:
        base["ok"] = not messages
        return base

    design = build_container_design_candidates(
        packing_product, int(desired_quantity), r1, r2, r3
    )
    candidates = [
        _add_container_design_metrics(
            row,
            form,
            product_source,
            selected_product,
            selected_board_construction=selected_board_construction,
        )
        for row in design["candidates"]
    ]
    if not candidates:
        messages.append("No valid container design candidate could be generated for the permitted orientations.")
        base["ok"] = False
        return base

    requested_id = str(form.cleaned_data.get("selected_design_candidate_id") or "")
    selected = next((row for row in candidates if row["candidate_id"] == requested_id), candidates[0])
    decorate_product_scene(
        selected["render_data"],
        product_shape=form.cleaned_data.get("product_shape"),
        product=product,
    )
    if design["additional_capacity"]:
        notices.append(
            f"The requested quantity was {design['desired_quantity']}. The container was designed for "
            f"{design['design_quantity']} units to create a practical arrangement "
            f"({design['additional_capacity']} additional capacity)."
        )
    analysis_report = {
        **selected,
        "shape_score_display": _format_percent(selected["container_cubicity_score"] * 100),
        "volumetric_efficiency_display": _format_percent(selected["volumetric_efficiency"] * 100),
        "has_net_content_weight": selected["net_content_weight"] is not None,
        "design_mode": True,
        "nominal_product_dimensions_display": format_dimensions(
            product[0],
            product[1],
            product[2],
            display_unit=form.cleaned_data.get("product_dimension_unit") or "mm",
        ),
        "effective_product_dimensions_display": format_dimensions(
            packing_product[0],
            packing_product[1],
            packing_product[2],
            display_unit=form.cleaned_data.get("product_dimension_unit") or "mm",
        ),
        "product_allowances_display": format_dimensions(
            product_allowances[0],
            product_allowances[1],
            product_allowances[2],
            display_unit=form.cleaned_data.get("product_dimension_unit") or "mm",
        ),
    }
    base.update({
        "ok": True,
        "result": selected,
        "threejs_scene": selected["render_data"],
        "analysis_report": analysis_report,
        "design_candidates": candidates,
        "selected_design_candidate_id": selected["candidate_id"],
    })
    return base


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
    product_base_image_rel_path = ""
    product_base_image_url = None

    mode = form.cleaned_data.get("mode") or "single"
    action = form.cleaned_data.get("action") or ""
    product_shape = normalize_product_shape(
        form.cleaned_data.get("product_shape")
    )

    product_source = form.cleaned_data.get("product_source") or "manual"
    container_source = form.cleaned_data.get("container_source") or "manual"
    selected_board_construction = get_selected_corrugated_construction(
        config=config,
        form=form,
    )

    normalized_inputs = _normalize_manual_container_inputs(
        form, config, product_source, container_source
    )
    messages.extend(normalized_inputs["messages"])

    nominal_product, r1, r2, r3 = resolve_product_from_form(
        form=form,
        product_source=product_source,
        selected_product=selected_product,
        normalized_product=normalized_inputs["product"],
    )
    packing_product = apply_product_allowances(
        nominal_product,
        normalized_inputs["product_allowances"],
    )
    product_unit_scene = build_product_unit_scene(
        nominal_product,
        product_shape,
        display_unit=form.cleaned_data.get("product_dimension_unit") or "mm",
    )

    if mode == "design":
        return _analyze_container_design(
            form,
            nominal_product,
            r1,
            r2,
            r3,
            product_source,
            container_source,
            selected_product,
            selected_material,
            initial_messages=messages,
            packing_product=packing_product,
            product_allowances=normalized_inputs["product_allowances"],
            selected_board_construction=selected_board_construction,
        )

    if r1 == 0 and r2 == 0 and r3 == 0:
        messages.append("Please enable at least one rotation option.")

    desired_qty = resolve_desired_qty(
        form=form,
        mode=mode,
        product_source=product_source,
        selected_product=selected_product,
    )

    if packing_product is not None and not messages and product_shape == "cuboid":
        try:
            product_base_image_rel_path = render_product_base_unit(
                nominal_product,
                media_root or settings.MEDIA_ROOT,
            )
            if product_base_image_rel_path:
                product_base_image_url = settings.MEDIA_URL + product_base_image_rel_path
        except Exception:
            product_base_image_rel_path = ""
            product_base_image_url = None

    if mode == "single" and not messages:
        should_run_single = action in ("run_single", "select_container")

        if should_run_single:
            container = None

            if product_source == "catalogue" and not selected_product:
                messages.append("Please select a product from the product catalogue.")
            elif product_source == "manual" and packing_product is None:
                messages.append("Please enter product dimensions.")

            if not messages:
                container = resolve_container_from_form(
                    form=form,
                    container_source=container_source,
                    selected_material=selected_material,
                    normalized_container=normalized_inputs["container"],
                )

                if container_source == "manual" and container is None:
                    messages.append("Please enter all manual container dimensions (L/W/H).")
                elif container_source == "catalogue" and selected_material is None:
                    messages.append("Please select a packaging item from the catalogue table.")

            if not messages and container is not None and packing_product is not None:
                render_result = run_mode1_and_render(
                    packing_product,
                    container,
                    r1,
                    r2,
                    r3,
                    media_root or settings.MEDIA_ROOT,
                    render_style="clean",
                )
                decorate_product_scene(
                    render_result.threejs_scene,
                    product_shape=product_shape,
                    product=nominal_product,
                )
                result = render_result
                analysis_report = build_container_analysis_report(
                    form=form,
                    result=render_result,
                    product=packing_product,
                    nominal_product=nominal_product,
                    product_allowances=normalized_inputs["product_allowances"],
                    container=container,
                    desired_qty=desired_qty,
                    product_source=product_source,
                    mode=mode,
                    selected_product=selected_product,
                    selected_material=selected_material,
                    selected_board_construction=selected_board_construction,
                )
                if getattr(render_result, "image_rel_path", None):
                    image_url = settings.MEDIA_URL + render_result.image_rel_path

    if mode == "optimal" and not messages:
        if action in ("find_top5", "select_candidate"):
            if product_source == "catalogue" and not selected_product:
                messages.append("Please select a product from the product catalogue.")
            elif product_source == "manual" and packing_product is None:
                messages.append("Please enter product dimensions.")
            elif not config.get("catalogue_id"):
                messages.append("Please select a packaging catalogue.")

            if not messages:
                if materials is None:
                    materials = get_materials_for_catalogue(config)

                top5 = _score_top5_candidates(
                    product=packing_product,
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
                            packing_product,
                            container,
                            r1,
                            r2,
                            r3,
                            media_root or settings.MEDIA_ROOT,
                            draw_limit=desired_qty,
                            render_style="clean",
                        )
                        decorate_product_scene(
                            render_result.threejs_scene,
                            product_shape=product_shape,
                            product=nominal_product,
                        )
                        result = render_result
                        analysis_report = build_container_analysis_report(
                            form=form,
                            result=render_result,
                            product=packing_product,
                            nominal_product=nominal_product,
                            product_allowances=normalized_inputs["product_allowances"],
                            container=container,
                            desired_qty=desired_qty,
                            product_source=product_source,
                            mode=mode,
                            selected_product=selected_product,
                            selected_material=selected_material,
                            selected_board_construction=selected_board_construction,
                        )
                        if getattr(render_result, "image_rel_path", None):
                            image_url = settings.MEDIA_URL + render_result.image_rel_path

    return {
        "ok": len(messages) == 0,
        "messages": messages,
        "notices": [],
        "result": result,
        "image_url": image_url,
        "threejs_scene": getattr(result, "threejs_scene", None) if result is not None else None,
        "product_unit_scene": product_unit_scene,
        "analysis_report": analysis_report,
        "product_base_image_rel_path": product_base_image_rel_path,
        "product_base_image_url": product_base_image_url,
        "top5": top5,
        "design_candidates": [],
        "selected_design_candidate_id": "",
    }


def analyze_container_capacity(
    form,
    config,
    selected_product=None,
    selected_material=None,
):
    """Calculate the workflow capacity payload inputs without presentation work."""
    mode = form.cleaned_data.get("mode") or "single"
    product_source = form.cleaned_data.get("product_source") or "manual"
    container_source = form.cleaned_data.get("container_source") or "manual"
    selected_board_construction = get_selected_corrugated_construction(
        config=config,
        form=form,
    )
    normalized_inputs = _normalize_manual_container_inputs(
        form, config, product_source, container_source
    )
    nominal_product, r1, r2, r3 = resolve_product_from_form(
        form=form,
        product_source=product_source,
        selected_product=selected_product,
        normalized_product=normalized_inputs["product"],
    )
    product = apply_product_allowances(
        nominal_product,
        normalized_inputs["product_allowances"],
    )
    messages = list(normalized_inputs["messages"])

    if product is None or any(float(value) <= 0 for value in product):
        messages.append("Enter product length, width, and height greater than zero in millimetres.")
    if not any((r1, r2, r3)):
        messages.append("Enable at least one permitted product orientation.")

    desired_quantity = resolve_desired_qty(
        form=form,
        mode=mode,
        product_source=product_source,
        selected_product=selected_product,
    )
    if int(desired_quantity or 0) <= 0:
        messages.append("Enter the desired quantity as a positive whole number.")
    if messages:
        return {"ok": False, "messages": messages, "mode": mode, "result": None}

    if mode == "design":
        design = build_container_design_candidates(
            product,
            int(desired_quantity),
            r1,
            r2,
            r3,
        )
        candidates = [
            _add_container_design_metrics(
                row,
                form,
                product_source,
                selected_product,
                selected_board_construction=selected_board_construction,
            )
            for row in design["candidates"]
        ]
        if not candidates:
            return {
                "ok": False,
                "messages": ["No valid container design candidate could be generated for the permitted orientations."],
                "mode": mode,
                "result": None,
            }
        requested_id = str(form.cleaned_data.get("selected_design_candidate_id") or "")
        selected = next(
            (row for row in candidates if row["candidate_id"] == requested_id),
            candidates[0],
        )
        return {
            "ok": True,
            "messages": [],
            "mode": mode,
            "result": selected,
            "design_candidates": candidates,
            "selected_design_candidate_id": selected["candidate_id"],
        }

    container = resolve_container_from_form(
        form=form,
        container_source=container_source,
        selected_material=selected_material,
        normalized_container=normalized_inputs["container"],
    )
    if container_source == "catalogue" and selected_material is None:
        messages.append("Please select a packaging item from the catalogue table.")
    elif container is None:
        messages.append("Please enter all manual container dimensions (L/W/H).")
    if mode == "optimal" and not config.get("catalogue_id"):
        messages.append("Please select a packaging catalogue.")
    if mode == "optimal" and selected_material is None:
        messages.append("Please select one of the Top 5 containers.")
    if messages:
        return {"ok": False, "messages": messages, "mode": mode, "result": None}

    max_quantity = compute_max_quantity_only(product, container, r1, r2, r3)
    dimension_contract = resolve_container_dimension_contract(
        form,
        container,
        container_source,
        selected_material,
    )
    weight_detail = _resolve_container_weight(
        form=form,
        container_source=container_source,
        selected_material=selected_material,
        container=container,
        config=config,
        selected_board_construction=selected_board_construction,
    )
    requested_for_weight = (
        int(max_quantity or 0) if mode == "single" else int(desired_quantity or 1)
    )
    product_weight = _resolve_product_weight(form, product_source, selected_product)
    net_weight = product_weight * requested_for_weight if product_weight is not None else None
    tare_g = weight_detail.get("tare_g")
    gross_weight = net_weight + tare_g if net_weight is not None and tare_g is not None else None
    return {
        "ok": True,
        "messages": [],
        "mode": mode,
        "result": {
            "container": container,
            "max_quantity": int(max_quantity or 0),
            "desired_quantity": int(desired_quantity or 1),
            "net_content_weight_g": _round_or_none(net_weight, 3),
            "carton_tare_g": _round_or_none(tare_g, 3),
            "gross_carton_weight_g": _round_or_none(gross_weight, 3),
            "carton_tare_source": weight_detail.get("source"),
            "carton_tare_source_display": weight_detail.get("source_label"),
            "weight_source": weight_detail.get("source"),
            "weight_source_display": weight_detail.get("source_label"),
            **dimension_contract,
        },
    }
