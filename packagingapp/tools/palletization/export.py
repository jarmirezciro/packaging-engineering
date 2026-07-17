import os
from io import BytesIO

from django.conf import settings
from django.utils import timezone

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def _clean(value, default="-"):
    if value in (None, "", "None"):
        return default
    return str(value)


def _safe_media_path(image_rel_path):
    if not image_rel_path:
        return None

    media_root = os.path.abspath(settings.MEDIA_ROOT)
    candidate = os.path.abspath(os.path.join(media_root, image_rel_path))

    try:
        if os.path.commonpath([media_root, candidate]) != media_root:
            return None
    except ValueError:
        return None
    if not os.path.exists(candidate):
        return None

    return candidate


def _build_styles():
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name="PalletReportTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=17,
        leading=20,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=2,
    ))
    styles.add(ParagraphStyle(
        name="PalletReportSubtitle",
        parent=styles["Normal"],
        fontSize=8.5,
        leading=10,
        textColor=colors.HexColor("#64748b"),
        spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name="PalletSectionTitle",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=9.5,
        leading=11,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=4,
        spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name="PalletBodySmall",
        parent=styles["Normal"],
        fontSize=6.8,
        leading=8,
        textColor=colors.HexColor("#334155"),
    ))
    styles.add(ParagraphStyle(
        name="PalletMetricLabel",
        parent=styles["Normal"],
        fontSize=6.7,
        leading=7.7,
        textColor=colors.HexColor("#64748b"),
        alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        name="PalletMetricValue",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=10,
        textColor=colors.HexColor("#0f172a"),
        alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        name="PalletNote",
        parent=styles["Normal"],
        fontSize=6.8,
        leading=8,
        textColor=colors.HexColor("#7c2d12"),
        backColor=colors.HexColor("#fff7ed"),
        borderColor=colors.HexColor("#fed7aa"),
        borderWidth=0.4,
        borderPadding=5,
    ))
    styles.add(ParagraphStyle(
        name="PalletFooter",
        parent=styles["Normal"],
        fontSize=6.5,
        leading=8,
        textColor=colors.HexColor("#94a3b8"),
        alignment=TA_CENTER,
    ))

    return styles


_STYLES = _build_styles()


def _p(text, style="PalletBodySmall"):
    return Paragraph(_clean(text), _STYLES[style])


def _section_title(text):
    return Paragraph(text, _STYLES["PalletSectionTitle"])


def _key_value_table(rows, col_widths):
    data = [
        [
            Paragraph(f"<b>{_clean(label)}</b>", _STYLES["PalletBodySmall"]),
            Paragraph(_clean(value), _STYLES["PalletBodySmall"]),
        ]
        for label, value in rows
    ]
    table = Table(data, colWidths=col_widths)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f8fafc")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d9e2ec")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return table


def _metric_cards(metrics):
    cells = []
    for label, value in metrics:
        cells.append([
            Paragraph(f"<b>{_clean(value)}</b>", _STYLES["PalletMetricValue"]),
            Paragraph(_clean(label), _STYLES["PalletMetricLabel"]),
        ])

    table = Table([cells], colWidths=[32 * mm] * len(metrics))
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ("BOX", (0, 0), (-1, -1), 0.35, colors.HexColor("#d9e2ec")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d9e2ec")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def _draw_report_frame(canvas, doc):
    canvas.saveState()
    width, height = doc.pagesize
    canvas.setStrokeColor(colors.HexColor("#d9e2ec"))
    canvas.setLineWidth(0.6)
    canvas.roundRect(9 * mm, 9 * mm, width - 18 * mm, height - 18 * mm, 4 * mm, stroke=1, fill=0)
    canvas.restoreState()


def _build_doc(buffer):
    return SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=14 * mm,
        leftMargin=14 * mm,
        topMargin=13 * mm,
        bottomMargin=12 * mm,
        title="Palletization Report",
    )


def _load_check_label(analysis):
    if analysis.get("weight_limit_kg") in (None, "", "None"):
        return "Not checked"
    return "OK" if analysis.get("feasible_weight") else "Review required"


def _cartons_per_layer(analysis):
    main_layer = _clean(analysis.get("boxes_layer_A"))
    alternate_layer = analysis.get("boxes_layer_B")
    if alternate_layer not in (None, "", "None") and str(alternate_layer) != str(analysis.get("boxes_layer_A")):
        return f"{main_layer} / {alternate_layer}"
    return main_layer


def _analysis_rows(analysis):
    weight_limit = analysis.get("weight_limit_kg")
    return [
        ("Main layer cartons", f"{_clean(analysis.get('boxes_layer_A'))} pcs"),
        ("Alternate layer cartons", f"{_clean(analysis.get('boxes_layer_B'))} pcs" if analysis.get("boxes_layer_B") not in (None, "", "None") else "Not available"),
        ("Used stack height", f"{_clean(analysis.get('used_height_mm'))} mm"),
        ("Pallet floor usage", f"{_clean(analysis.get('layer_footprint_util_pct'))}%"),
        ("Stack volume usage", f"{_clean(analysis.get('volumetric_util_pct'))}%"),
        ("Alternate layer possible", "Yes" if analysis.get("interlock_possible") else "No"),
        ("Bottom-carton load check", _load_check_label(analysis)),
        ("Max bottom-carton load", f"{_clean(analysis.get('max_bottom_load_kg'))} g" if weight_limit not in (None, "", "None") else "Not available"),
        ("Bottom-carton load limit", f"{_clean(weight_limit)} g" if weight_limit not in (None, "", "None") else "Not provided"),
    ]


def _ranking_table(rows, selected_result_key):
    data = [[
        _p("Rank"),
        _p("Pattern"),
        _p("Stacking"),
        _p("Cartons"),
        _p("Floor use"),
    ]]
    for index, row in enumerate((rows or [])[:5], start=1):
        selected_marker = " (selected)" if row.get("result_key") == selected_result_key else ""
        data.append([
            _p(f"{index}{selected_marker}"),
            _p(row.get("pattern")),
            _p(row.get("stacking")),
            _p(row.get("total_boxes")),
            _p(f"{_clean(row.get('layer_footprint_util_pct'))}%"),
        ])

    table = Table(data, colWidths=[22 * mm, 27 * mm, 23 * mm, 18 * mm, 21 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    return table


def build_palletization_pdf(export_payload):
    """
    Build a compact palletization report from the current browser 3D view.
    """
    buffer = BytesIO()
    doc = _build_doc(buffer)
    story = []

    generated_at = export_payload.get("generated_at") or timezone.now().strftime("%Y-%m-%d %H:%M")
    box = export_payload.get("box") or {}
    pallet = export_payload.get("pallet") or {}
    analysis = export_payload.get("analysis_report") or {}

    story.append(Paragraph("Palletization Report", _STYLES["PalletReportTitle"]))
    story.append(Paragraph(f"Generated {generated_at}", _STYLES["PalletReportSubtitle"]))

    story.append(_metric_cards([
        ("Total cartons", f"{_clean(analysis.get('total_boxes'))} pcs"),
        ("Layers", _clean(analysis.get("layers"))),
        ("Cartons/layer", _cartons_per_layer(analysis)),
        ("Stack height", f"{_clean(analysis.get('used_height_mm'))} mm"),
        ("Floor usage", f"{_clean(analysis.get('layer_footprint_util_pct'))}%"),
        ("Volume usage", f"{_clean(analysis.get('volumetric_util_pct'))}%"),
    ]))
    story.append(Spacer(1, 4 * mm))

    left_column = [
        _section_title("Carton / box"),
        _key_value_table([
            ("Source", box.get("source")),
            ("Part number", box.get("part_number")),
            ("Description", box.get("description")),
            ("Material", box.get("material")),
            ("Dimensions", box.get("dimensions")),
            ("Carton weight", box.get("weight")),
            ("Bottom load limit", box.get("bottom_load_limit")),
        ], [34 * mm, 75 * mm]),
        Spacer(1, 3 * mm),
        _section_title("Pallet"),
        _key_value_table([
            ("Source", pallet.get("source")),
            ("Part number", pallet.get("part_number")),
            ("Description", pallet.get("description")),
            ("Material", pallet.get("material")),
            ("Dimensions", pallet.get("dimensions")),
            ("Max stack height", pallet.get("max_stack_height")),
            ("Allowed overhang", pallet.get("overhang")),
        ], [34 * mm, 75 * mm]),
    ]
    ranking = export_payload.get("ranking") or []
    if ranking:
        left_column.extend([
            Spacer(1, 3 * mm),
            _section_title("Ranked pallet patterns"),
            _ranking_table(ranking, analysis.get("result_key")),
        ])

    right_column = [
        _section_title("Current Three.js pallet view"),
        _p(export_payload.get("threejs_view_label") or "Current interactive 3D view"),
        Spacer(1, 1.5 * mm),
    ]

    image_path = _safe_media_path(export_payload.get("threejs_snapshot_rel_path"))
    if image_path:
        image = Image(image_path)
        image._restrictSize(126 * mm, 74 * mm)
        right_column.append(image)
    else:
        right_column.append(_p("No Three.js snapshot was captured for this report."))

    right_column.extend([
        Spacer(1, 3 * mm),
        _section_title("Detailed analysis"),
        _key_value_table(_analysis_rows(analysis), [45 * mm, 58 * mm]),
    ])

    content_table = Table([[left_column, right_column]], colWidths=[114 * mm, 134 * mm])
    content_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(content_table)
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph(
        "Validation note: this result is an engineering estimate. Final approval should consider pallet stability, "
        "carton compression strength, handling, wrapping, transport conditions, and customer-specific restrictions.",
        _STYLES["PalletNote"],
    ))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(
        "Generated by KolliPack - Palletization Tool",
        _STYLES["PalletFooter"],
    ))

    doc.build(story, onFirstPage=_draw_report_frame, onLaterPages=_draw_report_frame)
    buffer.seek(0)
    return buffer
