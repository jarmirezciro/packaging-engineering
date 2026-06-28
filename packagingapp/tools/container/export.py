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
        name="ReportTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=17,
        leading=20,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=2,
    ))
    styles.add(ParagraphStyle(
        name="ReportSubtitle",
        parent=styles["Normal"],
        fontSize=8.5,
        leading=10,
        textColor=colors.HexColor("#64748b"),
        spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name="SectionTitle",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=9.5,
        leading=11,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=4,
        spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name="Body",
        parent=styles["Normal"],
        fontSize=7.4,
        leading=8.8,
        textColor=colors.HexColor("#334155"),
    ))
    styles.add(ParagraphStyle(
        name="BodySmall",
        parent=styles["Normal"],
        fontSize=6.6,
        leading=7.7,
        textColor=colors.HexColor("#334155"),
    ))
    styles.add(ParagraphStyle(
        name="MetricLabel",
        parent=styles["Normal"],
        fontSize=6.7,
        leading=7.7,
        textColor=colors.HexColor("#64748b"),
        alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        name="MetricValue",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=10,
        textColor=colors.HexColor("#0f172a"),
        alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        name="Note",
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
        name="Footer",
        parent=styles["Normal"],
        fontSize=6.5,
        leading=8,
        textColor=colors.HexColor("#94a3b8"),
        alignment=TA_CENTER,
    ))

    return styles


_STYLES = _build_styles()


def _p(text, style="Body"):
    return Paragraph(_clean(text), _STYLES[style])



def _section_title(text):
    return Paragraph(text, _STYLES["SectionTitle"])


def _key_value_table(rows, col_widths):
    data = [
        [
            Paragraph(f"<b>{_clean(label)}</b>", _STYLES["BodySmall"]),
            Paragraph(_clean(value), _STYLES["BodySmall"]),
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
            Paragraph(f"<b>{_clean(value)}</b>", _STYLES["MetricValue"]),
            Paragraph(_clean(label), _STYLES["MetricLabel"]),
        ])

    data = [cells]
    table = Table(data, colWidths=[36 * mm] * len(metrics))
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
        Paragraph("<b>Rank</b>", _STYLES["BodySmall"]),
        Paragraph("<b>Part no.</b>", _STYLES["BodySmall"]),
        Paragraph("<b>Description</b>", _STYLES["BodySmall"]),
        Paragraph("<b>Type</b>", _STYLES["BodySmall"]),
        Paragraph("<b>Internal dims</b>", _STYLES["BodySmall"]),
        Paragraph("<b>Weight</b>", _STYLES["BodySmall"]),
        Paragraph("<b>Max qty</b>", _STYLES["BodySmall"]),
        Paragraph("<b>Usage</b>", _STYLES["BodySmall"]),
    ]

    data = [header]
    for row in rows[:5]:
        data.append([
            Paragraph(_clean(row.get("rank")), _STYLES["BodySmall"]),
            Paragraph(_clean(row.get("part_number")), _STYLES["BodySmall"]),
            Paragraph(_clean(row.get("description")), _STYLES["BodySmall"]),
            Paragraph(_clean(row.get("type")), _STYLES["BodySmall"]),
            Paragraph(_clean(row.get("dimensions")), _STYLES["BodySmall"]),
            Paragraph(_clean(row.get("weight")), _STYLES["BodySmall"]),
            Paragraph(_clean(row.get("max_qty")), _STYLES["BodySmall"]),
            Paragraph(_clean(row.get("usage_display")), _STYLES["BodySmall"]),
        ])

    table = Table(
        data,
        colWidths=[12 * mm, 28 * mm, 54 * mm, 22 * mm, 38 * mm, 24 * mm, 20 * mm, 20 * mm],
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


def _build_doc(buffer, title="Container Selection Report", pagesize=A4):
    return SimpleDocTemplate(
        buffer,
        pagesize=pagesize,
        rightMargin=14 * mm,
        leftMargin=14 * mm,
        topMargin=13 * mm,
        bottomMargin=12 * mm,
        title=title,
    )


def build_container_selection_single_pdf(export_payload):
    """
    Build a compact one-page standalone Single container analysis PDF.
    """
    buffer = BytesIO()
    doc = _build_doc(buffer, title="Container Selection Single Report")
    story = []

    generated_at = export_payload.get("generated_at") or timezone.now().strftime("%Y-%m-%d %H:%M")
    product = export_payload.get("product") or {}
    container = export_payload.get("container") or {}
    analysis = export_payload.get("analysis_report") or {}

    story.append(Paragraph("Container Selection Report", _STYLES["ReportTitle"]))
    story.append(Paragraph(f"Single container analysis - Generated {generated_at}", _STYLES["ReportSubtitle"]))

    metrics = [
        ("Max qty", f"{analysis.get('max_quantity', '-')} pcs"),
        ("Current qty", f"{analysis.get('requested_qty', '-')} pcs"),
        ("Efficiency", analysis.get("volumetric_efficiency_current_display")),
        ("Total weight", analysis.get("total_weight_current_display")),
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
        ("Rotations", product.get("rotations")),
    ], [28 * mm, 54 * mm])

    container_table = _key_value_table([
        ("Source", container.get("source")),
        ("Part no.", container.get("part_number")),
        ("Description", container.get("description")),
        ("Type", container.get("type")),
        ("Internal dims", container.get("dimensions")),
        ("Tare / payload", f"{container.get('tare', '-')} / {container.get('payload_capacity', '-')}"),
    ], [30 * mm, 58 * mm])

    info_grid = Table(
        [[_section_title("Product"), _section_title("Packaging")], [product_table, container_table]],
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

    image_path = _safe_media_path(export_payload.get("image_rel_path"))
    if image_path:
        story.append(_section_title("Packing visualization"))
        img = Image(image_path)
        max_width = 170 * mm
        max_height = 70 * mm
        scale = min(max_width / img.drawWidth, max_height / img.drawHeight, 1)
        img.drawWidth *= scale
        img.drawHeight *= scale
        story.append(img)
        story.append(Spacer(1, 5))

    story.append(Paragraph(
        "Decision-support representation only. Physical validation is recommended for critical packaging decisions. "
        "Final selection may also depend on protection, handling, branding, transport and quality requirements.",
        _STYLES["Note"],
    ))
    story.append(Spacer(1, 4))
    story.append(Paragraph("Generated by Packaging Engineering - Container Selection Tool", _STYLES["Footer"]))

    doc.build(story, onFirstPage=_draw_report_frame, onLaterPages=_draw_report_frame)
    buffer.seek(0)
    return buffer


def build_container_selection_optimal_pdf(export_payload):
    """
    Build a compact one-page standalone Optimal container Top 5 PDF.
    """
    buffer = BytesIO()
    doc = _build_doc(buffer, title="Container Selection Optimal Report", pagesize=landscape(A4))
    story = []

    generated_at = export_payload.get("generated_at") or timezone.now().strftime("%Y-%m-%d %H:%M")
    product = export_payload.get("product") or {}
    top5 = export_payload.get("top5") or []
    recommendation = top5[0] if top5 else {}

    story.append(Paragraph("Container Selection Report", _STYLES["ReportTitle"]))
    story.append(Paragraph(f"Optimal container recommendation - Generated {generated_at}", _STYLES["ReportSubtitle"]))

    metrics = [
        ("Required qty", product.get("desired_qty")),
        ("Candidates", f"{len(top5)} shown"),
        ("Recommended", recommendation.get("part_number")),
        ("Best usage", recommendation.get("usage_display")),
        ("Best max qty", f"{recommendation.get('max_qty', '-')} pcs"),
    ]
    story.append(_metric_cards(metrics))
    story.append(Spacer(1, 5))

    product_table = _key_value_table([
        ("Product source", product.get("source")),
        ("Product ID", product.get("id")),
        ("Name", product.get("name")),
        ("Dimensions", product.get("dimensions")),
        ("Weight", product.get("weight")),
        ("Rotations", product.get("rotations")),
    ], [34 * mm, 72 * mm])

    context_table = _key_value_table([
        ("Mode", "Optimal container"),
        ("Catalogue", export_payload.get("catalogue_name")),
        ("Ranking logic", "Highest volume usage, then smaller container volume"),
        ("Recommendation", recommendation.get("part_number")),
        ("Description", recommendation.get("description")),
        ("Internal dims", recommendation.get("dimensions")),
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

    story.append(_section_title("Top 5 suitable packaging options"))
    story.append(_top5_table(top5))
    story.append(Spacer(1, 5))

    image_path = _safe_media_path(export_payload.get("image_rel_path"))
    if image_path:
        selected_candidate = export_payload.get("selected_candidate") or {}
        story.append(_section_title("Selected candidate packing visualization"))
        selected_text = selected_candidate.get("part_number")
        if selected_text:
            story.append(Paragraph(
                f"Selected candidate: <b>{_clean(selected_text)}</b> - {_clean(selected_candidate.get('description'))}",
                _STYLES["BodySmall"],
            ))
            story.append(Spacer(1, 2))

        img = Image(image_path)
        max_width = 125 * mm
        max_height = 48 * mm
        scale = min(max_width / img.drawWidth, max_height / img.drawHeight, 1)
        img.drawWidth *= scale
        img.drawHeight *= scale
        story.append(img)
        story.append(Spacer(1, 5))

    story.append(Paragraph(
        "The Top 5 list includes packaging options that can fit the required quantity. "
        "The ranking prioritizes efficient internal volume usage, but final packaging choice may also depend on payload, protection, handling, branding, transport and quality requirements.",
        _STYLES["Note"],
    ))
    story.append(Spacer(1, 4))
    story.append(Paragraph("Generated by Packaging Engineering - Container Selection Tool", _STYLES["Footer"]))

    doc.build(story, onFirstPage=_draw_report_frame, onLaterPages=_draw_report_frame)
    buffer.seek(0)
    return buffer


# Backward-compatible name used by earlier code.
def build_container_selection_pdf(export_payload):
    report_type = (export_payload or {}).get("report_type")
    if report_type == "optimal":
        return build_container_selection_optimal_pdf(export_payload)
    return build_container_selection_single_pdf(export_payload)
