from decimal import Decimal

from django.http import HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from ..access import visible_packaging_catalogues
from ..forms import CorrugatedMaterialStrengthForm
from ..models import CorrugatedBoardConstruction, PackagingMaterial
from ..tools.corrugated_material_strength.contracts import build_shared_corrugated_material_ui_contract
from ..tools.corrugated_material_strength.serializers import json_safe, serialize_corrugated_inputs
from ..tools.corrugated_material_strength.service import calculate_corrugated_material_strength
from ..tools.corrugated_material_strength.export import build_corrugated_material_strength_pdf


def _dimension(material, *names):
    for name in names:
        value = getattr(material, name, None)
        if value is not None and Decimal(str(value)) > 0:
            return value
    return Decimal("0")


def _catalogue_pallets(request):
    catalogues = visible_packaging_catalogues(request.user)
    return PackagingMaterial.objects.filter(
        catalogue__in=catalogues, packaging_type="PALLET"
    ).select_related("catalogue").order_by("part_description", "part_number")


def _board_option(construction):
    text = f"{construction.name} · {construction.combined_grammage_g_m2:g} g/m²"
    if construction.ect_kn_m is not None and construction.caliper_mm is not None:
        text += f" · ECT {construction.ect_kn_m:g} kN/m · {construction.caliper_mm:g} mm"
    else:
        text += " · strength data not included"
    return str(construction.pk), text


def _pallet_option(material):
    length = _dimension(material, "external_length", "part_length")
    width = _dimension(material, "external_width", "part_width")
    height = _dimension(material, "external_height", "part_height")
    return str(material.pk), f"{material.part_description or material.part_number} · {length:g} × {width:g} × {height:g} mm"


def _board_metadata(construction):
    return {
        "id": construction.pk, "code": construction.code, "name": construction.name,
        "wall_type": construction.get_wall_type_display(), "flute": construction.flute_display,
        "combined_grammage_g_m2": construction.combined_grammage_g_m2,
        "nominal_flute_height_mm": construction.nominal_flute_height_mm,
        "caliper_mm": construction.caliper_mm, "ect_kn_m": construction.ect_kn_m,
        "measured_bct_n": construction.measured_bct_n,
        "source_type": construction.get_source_type_display(),
        "source_label": construction.source_label,
        "source_notes": construction.source_notes,
        "co2_factor_kg_co2e_per_kg": construction.co2_factor_kg_co2e_per_kg,
    }


def _pallet_metadata(material):
    if material is None:
        return None
    return {
        "id": material.pk, "code": material.part_number,
        "name": material.part_description, "catalogue": material.catalogue.name,
        "length_mm": _dimension(material, "external_length", "part_length"),
        "width_mm": _dimension(material, "external_width", "part_width"),
        "height_mm": _dimension(material, "external_height", "part_height"),
        "weight_kg": material.part_weight or Decimal("0"),
    }


def _apply_choices(form, boards, pallets):
    form.fields["board_construction_id"].choices = [
        ("", "— Select construction —"), *[_board_option(board) for board in boards]
    ]
    form.fields["pallet_code"].choices = [
        ("", "— Select existing pallet —"), *[_pallet_option(pallet) for pallet in pallets]
    ]


def _shared_fields(form, ui):
    return {
        key: form[name]
        for key, name in ui["field_names"].items()
        if name in form.fields
    }


def corrugated_material_strength(request):
    boards = list(CorrugatedBoardConstruction.objects.filter(is_active=True).order_by("sort_order", "wall_type", "flute_1", "flute_2", "name"))
    pallets = list(_catalogue_pallets(request))

    initial = {}
    if request.method == "GET":
        if boards:
            initial["board_construction_id"] = str(boards[0].pk)
        euro = next((item for item in pallets if item.part_number.upper() == "EUROPALLET"), None)
        if euro is not None:
            initial.update({
                "pallet_source": "catalogue", "pallet_code": str(euro.pk),
                "pallet_length_mm": _dimension(euro, "external_length", "part_length"),
                "pallet_width_mm": _dimension(euro, "external_width", "part_width"),
                "pallet_height_mm": _dimension(euro, "external_height", "part_height"),
                "pallet_weight_kg": euro.part_weight or Decimal("0"),
            })

    if request.method == "POST":
        form = CorrugatedMaterialStrengthForm(request.POST)
    else:
        form = CorrugatedMaterialStrengthForm(initial=initial)
    _apply_choices(form, boards, pallets)

    result = None
    selected_board = None
    selected_pallet = None
    if request.method == "GET":
        selected_board = boards[0] if boards else None
        selected_pallet = next((item for item in pallets if item.part_number.upper() == "EUROPALLET"), None)
    if request.method == "POST" and form.is_valid():
        if form.cleaned_data.get("board_mode") == "catalogue":
            selected_board = next((item for item in boards if str(item.pk) == str(form.cleaned_data.get("board_construction_id"))), None)
        if form.cleaned_data.get("pallet_source") == "catalogue":
            selected_pallet = next((item for item in pallets if str(item.pk) == str(form.cleaned_data.get("pallet_code"))), None)
        try:
            inputs = serialize_corrugated_inputs(form.cleaned_data)
            if selected_pallet is not None:
                inputs.update({
                    "pallet_length_mm": json_safe(_dimension(selected_pallet, "external_length", "part_length")),
                    "pallet_width_mm": json_safe(_dimension(selected_pallet, "external_width", "part_width")),
                    "pallet_height_mm": json_safe(_dimension(selected_pallet, "external_height", "part_height")),
                    "pallet_weight_kg": json_safe(selected_pallet.part_weight or Decimal("0")),
                })
            result = calculate_corrugated_material_strength(
                inputs, construction=selected_board, pallet_material=selected_pallet
            )
            request.session["corrugated_material_strength_last_analysis"] = {
                "inputs": inputs, "result": result,
            }
            request.session.modified = True
        except (ValueError, ArithmeticError) as exc:
            form.add_error(None, str(exc))

    if selected_board is None and form.data.get("board_construction_id"):
        selected_board = next((item for item in boards if str(item.pk) == str(form.data.get("board_construction_id"))), None)
    if selected_pallet is None and form.data.get("pallet_code"):
        selected_pallet = next((item for item in pallets if str(item.pk) == str(form.data.get("pallet_code"))), None)

    catalogue = {
        "boards": [json_safe(_board_metadata(board)) for board in boards],
        "pallets": [json_safe(_pallet_metadata(pallet)) for pallet in pallets],
    }
    ui = build_shared_corrugated_material_ui_contract(
        mode="standalone", prefix="", catalogue=catalogue
    )
    ui["form_action"] = reverse("corrugated_material_strength")
    return render(request, "corrugated_material_strength/corrugated_material_strength_tool.html", {
        "form": form,
        "fields": _shared_fields(form, ui),
        "ui": ui,
        "result": result,
        "selected_board": json_safe(_board_metadata(selected_board)) if selected_board else None,
        "selected_pallet": json_safe(_pallet_metadata(selected_pallet)) if selected_pallet else None,
        "board_metadata_json": catalogue["boards"],
        "pallet_metadata_json": catalogue["pallets"],
        "has_board_catalogue": bool(boards),
        "has_pallet_catalogue": bool(pallets),
    })


def corrugated_material_strength_export_pdf(request):
    payload = request.session.get("corrugated_material_strength_last_analysis")
    if not payload or not payload.get("result"):
        return HttpResponse("Please run a Corrugated Material & Strength analysis before exporting a PDF report.", status=400, content_type="text/plain")
    pdf_buffer = build_corrugated_material_strength_pdf(payload)
    timestamp = timezone.now().strftime("%Y%m%d_%H%M")
    response = HttpResponse(pdf_buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="corrugated_material_strength_report_{timestamp}.pdf"'
    return response
