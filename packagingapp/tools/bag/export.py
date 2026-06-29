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

    if not candidate.startswith(media_root):
        return None
    if not os.path.exists(candidate):
        return None

    return candidate


def _build_styles():
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name="BagReportTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=17,
        leading=20,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=2,
    ))
    styles.add(ParagraphStyle(
        name="BagReportSubtitle",
        parent=styles["Normal"],
        fontSize=8.5,
        leading=10,
        textColor=colors.HexColor("#64748b"),
        spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name="BagSectionTitle",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=9.5,
        leading=11,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=4,
        spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name="BagBodySmall",
        parent=styles["Normal"],
        fontSize=6.6,
        leading=7.7,
        textColor=colors.HexColor("#334155"),
    ))
    styles.add(ParagraphStyle(
        name="BagMetricLabel",
        parent=styles["Normal"],
        fontSize=6.7,
        leading=7.7,
        textColor=colors.HexColor("#64748b"),
        alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        name="BagMetricValue",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=10,
        textColor=colors.HexColor("#0f172a"),
        alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        name="BagNote",
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
        name="BagFooter",
        parent=styles["Normal"],
        fontSize=6.5,
        leading=8,
        textColor=colors.HexColor("#94a3b8"),
        alignment=TA_CENTER,
    ))

    return styles


_STYLES = _build_styles()


def _p(text, style="BagBodySmall"):
    return Paragraph(_clean(text), _STYLES[style])


def _section_title(text):
    return Paragraph(text, _STYLES["BagSectionTitle"])


def _key_value_table(rows, col_widths):
    data = [
        [
            Paragraph(f"<b>{_clean(label)}</b>", _STYLES["BagBodySmall"]),
            Paragraph(_clean(value), _STYLES["BagBodySmall"]),
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
            Paragraph(f"<b>{_clean(value)}</b>", _STYLES["BagMetricValue"]),
            Paragraph(_clean(label), _STYLES["BagMetricLabel"]),
        ])

    table = Table([cells], colWidths=[36 * mm] * len(metrics))
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


def _top5_table(rows):
    header = [
        Paragraph("<b>Rank</b>", _STYLES["BagBodySmall"]),
        Paragraph("<b>Part no.</b>", _STYLES["BagBodySmall"]),
        Paragraph("<b>Description</b>", _STYLES["BagBodySmall"]),
        Paragraph("<b>Brand</b>", _STYLES["BagBodySmall"]),
        Paragraph("<b>Bag L</b>", _STYLES["BagBodySmall"]),
        Paragraph("<b>Bag W</b>", _STYLES["BagBodySmall"]),
        Paragraph("<b>Usage</b>", _STYLES["BagBodySmall"]),
        Paragraph("<b>Best required</b>", _STYLES["BagBodySmall"]),
    ]

    data = [header]
    for row in rows[:5]:
        data.append([
            Paragraph(_clean(row.get("rank")), _STYLES["BagBodySmall"]),
            Paragraph(_clean(row.get("part_number")), _STYLES["BagBodySmall"]),
            Paragraph(_clean(row.get("description")), _STYLES["BagBodySmall"]),
            Paragraph(_clean(row.get("brand")), _STYLES["BagBodySmall"]),
            Paragraph(_clean(row.get("bag_length")), _STYLES["BagBodySmall"]),
            Paragraph(_clean(row.get("bag_width")), _STYLES["BagBodySmall"]),
            Paragraph(_clean(row.get("usage_display")), _STYLES["BagBodySmall"]),
            Paragraph(_clean(row.get("best_required")), _STYLES["BagBodySmall"]),
        ])

    table = Table(
        data,
        colWidths=[12 * mm, 28 * mm, 56 * mm, 26 * mm, 22 * mm, 22 * mm, 22 * mm, 34 * mm],
        repeatRows=1,
    )
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eaf2ff")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#f8fafc")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d9e2ec")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return table


def _draw_report_frame(canvas, doc):
    canvas.saveState()
    width, height = doc.pagesize
    canvas.setStrokeColor(colors.HexColor("#d9e2ec"))
    canvas.setLineWidth(0.6)
    canvas.roundRect(9 * mm, 9 * mm, width - 18 * mm, height - 18 * mm, 4 * mm, stroke=1, fill=0)
    canvas.restoreState()


def _build_doc(buffer, title="Bag Selection Report", pagesize=A4):
    return SimpleDocTemplate(
        buffer,
        pagesize=pagesize,
        rightMargin=14 * mm,
        leftMargin=14 * mm,
        topMargin=13 * mm,
        bottomMargin=12 * mm,
        title=title,
    )


def _safe_display(value, fallback="Not available"):
    if value in (None, "", "None"):
        return fallback
    return str(value)


def build_bag_selection_single_pdf(export_payload):
    """
    Build a compact one-page standalone Single bag analysis PDF.
    """
    buffer = BytesIO()
    doc = _build_doc(buffer, title="Bag Selection Single Report")
    story = []

    generated_at = export_payload.get("generated_at") or timezone.now().strftime("%Y-%m-%d %H:%M")
    product = export_payload.get("product") or {}
    bag = export_payload.get("bag") or {}
    analysis = export_payload.get("analysis_report") or {}

    story.append(Paragraph("Bag Selection Report", _STYLES["BagReportTitle"]))
    story.append(Paragraph(f"Single bag analysis - Generated {generated_at}", _STYLES["BagReportSubtitle"]))

    metrics = [
        ("Max qty", f"{analysis.get('max_quantity', '-')} pcs"),
        ("Bag usage", analysis.get("bag_usage_max_display")),
        ("Net weight", analysis.get("net_weight_display")),
        ("Total weight", analysis.get("total_weight_display")),
        ("Payload", analysis.get("payload_usage_display")),
    ]
    story.append(_metric_cards(metrics))
    story.append(Spacer(1, 5))

    product_table = _key_value_table([
        ("Source", product.get("source")),
        ("Product ID", product.get("id")),
        ("Name", product.get("name")),
        ("Dimensions", product.get("dimensions")),
        ("Weight", product.get("weight")),
        ("Orientation", product.get("orientation")),
    ], [28 * mm, 54 * mm])

    bag_table = _key_value_table([
        ("Source", bag.get("source")),
        ("Part no.", bag.get("part_number")),
        ("Description", bag.get("description")),
        ("Brand", bag.get("brand")),
        ("Flat dimensions", bag.get("dimensions")),
        ("Packaging wt / payload", f"{bag.get('weight', '-')} / {bag.get('payload_capacity', '-')}")
    ], [34 * mm, 54 * mm])

    info_grid = Table(
        [[_section_title("Product"), _section_title("Bag / Packaging")], [product_table, bag_table]],
        colWidths=[84 * mm, 90 * mm],
    )
    info_grid.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(info_grid)
    story.append(Spacer(1, 5))

    detail_table = _key_value_table([
        ("Current quantity", f"{analysis.get('current_quantity', '-')} pcs"),
        ("Bag usage - current", analysis.get("bag_usage_current_display")),
        ("Max quantity", f"{analysis.get('max_quantity', '-')} pcs"),
        ("Bag usage - max quantity", analysis.get("bag_usage_max_display")),
        ("Remaining capacity", f"{analysis.get('remaining_capacity', '-')} pcs"),
        ("Calculation note", analysis.get("calculation_note")),
    ], [40 * mm, 132 * mm])
    story.append(_section_title("Result interpretation"))
    story.append(detail_table)
    story.append(Spacer(1, 5))

    image_path = _safe_media_path(export_payload.get("image_rel_path"))
    if image_path:
        story.append(_section_title("Bag visualization"))
        img = Image(image_path)
        max_width = 170 * mm
        max_height = 58 * mm
        scale = min(max_width / img.drawWidth, max_height / img.drawHeight, 1)
        img.drawWidth *= scale
        img.drawHeight *= scale
        story.append(img)
        story.append(Spacer(1, 5))

    story.append(Paragraph(
        "Decision-support representation only. Bag dimensions are interpreted as flat L x W dimensions in millimetres, "
        "with the opening on the width side. Physical validation is recommended for critical packaging decisions. "
        "Final selection may also depend on sealing, protection, handling, branding, transport and quality requirements.",
        _STYLES["BagNote"],
    ))
    story.append(Spacer(1, 4))
    story.append(Paragraph("Generated by Packaging Engineering - Bag Selection Tool", _STYLES["BagFooter"]))

    doc.build(story, onFirstPage=_draw_report_frame, onLaterPages=_draw_report_frame)
    buffer.seek(0)
    return buffer


def build_bag_selection_optimal_pdf(export_payload):
    """
    Build a compact one-page standalone Optimal bag Top 5 PDF.
    """
    buffer = BytesIO()
    doc = _build_doc(buffer, title="Bag Selection Optimal Report", pagesize=landscape(A4))
    story = []

    generated_at = export_payload.get("generated_at") or timezone.now().strftime("%Y-%m-%d %H:%M")
    product = export_payload.get("product") or {}
    top5 = export_payload.get("top5") or []
    recommendation = export_payload.get("selected_candidate") or (top5[0] if top5 else {})
    analysis = export_payload.get("analysis_report") or {}

    story.append(Paragraph("Bag Selection Report", _STYLES["BagReportTitle"]))
    story.append(Paragraph(f"Optimal bag recommendation - Generated {generated_at}", _STYLES["BagReportSubtitle"]))

    metrics = [
        ("Target qty", product.get("desired_qty")),
        ("Candidates", f"{len(top5)} shown"),
        ("Selected", recommendation.get("part_number")),
        ("Current usage", analysis.get("bag_usage_current_display") or recommendation.get("usage_display")),
        ("Max qty", f"{analysis.get('max_quantity', '-')} pcs"),
    ]
    story.append(_metric_cards(metrics))
    story.append(Spacer(1, 5))

    product_table = _key_value_table([
        ("Product source", product.get("source")),
        ("Product ID", product.get("id")),
        ("Name", product.get("name")),
        ("Dimensions", product.get("dimensions")),
        ("Weight", product.get("weight")),
        ("Target quantity", product.get("desired_qty")),
    ], [34 * mm, 72 * mm])

    context_table = _key_value_table([
        ("Mode", "Optimal bag"),
        ("Catalogue", export_payload.get("catalogue_name")),
        ("Ranking logic", "Highest bag usage, then smallest fitting area"),
        ("Selected", recommendation.get("part_number")),
        ("Description", recommendation.get("description")),
        ("Flat dimensions", recommendation.get("dimensions")),
    ], [36 * mm, 66 * mm])

    info_grid = Table(
        [[_section_title("Product"), _section_title("Recommendation context")], [product_table, context_table]],
        colWidths=[106 * mm, 106 * mm],
    )
    info_grid.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(info_grid)
    story.append(Spacer(1, 5))

    story.append(_section_title("Top 5 suitable bag options"))
    story.append(_top5_table(top5))
    story.append(Spacer(1, 5))

    image_path = _safe_media_path(export_payload.get("image_rel_path"))
    if image_path:
        story.append(_section_title("Selected candidate bag visualization"))
        selected_text = recommendation.get("part_number")
        if selected_text:
            story.append(Paragraph(
                f"Selected candidate: <b>{_clean(selected_text)}</b> - {_clean(recommendation.get('description'))}",
                _STYLES["BagBodySmall"],
            ))
            story.append(Spacer(1, 2))

        img = Image(image_path)
        max_width = 125 * mm
        max_height = 44 * mm
        scale = min(max_width / img.drawWidth, max_height / img.drawHeight, 1)
        img.drawWidth *= scale
        img.drawHeight *= scale
        story.append(img)
        story.append(Spacer(1, 5))

    story.append(Paragraph(
        "The Top 5 list includes bag options that can fit the target quantity. "
        "The ranking prioritizes efficient flat bag usage, but final packaging choice may also depend on payload, "
        "sealing, protection, handling, branding, transport and quality requirements.",
        _STYLES["BagNote"],
    ))
    story.append(Spacer(1, 4))
    story.append(Paragraph("Generated by Packaging Engineering - Bag Selection Tool", _STYLES["BagFooter"]))

    doc.build(story, onFirstPage=_draw_report_frame, onLaterPages=_draw_report_frame)
    buffer.seek(0)
    return buffer


def build_bag_selection_pdf(export_payload):
    report_type = (export_payload or {}).get("report_type")
    if report_type == "optimal":
        return build_bag_selection_optimal_pdf(export_payload)
    return build_bag_selection_single_pdf(export_payload)
