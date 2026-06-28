import os
from io import BytesIO

from django.conf import settings
from django.utils import timezone

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
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


def _clean(value, default="—"):
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


def _section_title(text, styles):
    return Paragraph(text, styles["SectionTitle"])


def _key_value_table(rows):
    data = [[Paragraph(f"<b>{_clean(label)}</b>", _STYLES["Body"]), Paragraph(_clean(value), _STYLES["Body"])] for label, value in rows]
    table = Table(data, colWidths=[48 * mm, 112 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f8fafc")),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#0f172a")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d9e2ec")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def _metric_table(metrics):
    data = [
        [
            Paragraph(f"<b>{_clean(label)}</b>", _STYLES["MetricLabel"]),
            Paragraph(_clean(value), _STYLES["MetricValue"]),
        ]
        for label, value in metrics
    ]
    table = Table(data, colWidths=[80 * mm, 80 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#d9e2ec")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return table


def _build_styles():
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name="ReportTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name="ReportSubtitle",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#64748b"),
        spaceAfter=12,
    ))
    styles.add(ParagraphStyle(
        name="SectionTitle",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=8,
        spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name="Body",
        parent=styles["Normal"],
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#334155"),
    ))
    styles.add(ParagraphStyle(
        name="MetricLabel",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#64748b"),
    ))
    styles.add(ParagraphStyle(
        name="MetricValue",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=11,
        textColor=colors.HexColor("#0f172a"),
    ))
    styles.add(ParagraphStyle(
        name="Note",
        parent=styles["Normal"],
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#7c2d12"),
        backColor=colors.HexColor("#fff7ed"),
        borderColor=colors.HexColor("#fed7aa"),
        borderWidth=0.5,
        borderPadding=6,
    ))
    styles.add(ParagraphStyle(
        name="Footer",
        parent=styles["Normal"],
        fontSize=7,
        leading=9,
        textColor=colors.HexColor("#94a3b8"),
        alignment=TA_CENTER,
    ))

    return styles


_STYLES = _build_styles()


def build_container_selection_pdf(export_payload):
    """
    Build a standalone Container Selection PDF report.

    export_payload is a JSON-safe dict stored in the session after a successful
    Single container analysis.
    """
    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title="Container Selection Report",
    )

    story = []

    generated_at = export_payload.get("generated_at") or timezone.now().strftime("%Y-%m-%d %H:%M")
    story.append(Paragraph("Container Selection Report", _STYLES["ReportTitle"]))
    story.append(Paragraph(f"Single container analysis · Generated {generated_at}", _STYLES["ReportSubtitle"]))

    product = export_payload.get("product") or {}
    container = export_payload.get("container") or {}
    analysis = export_payload.get("analysis_report") or {}

    story.append(_section_title("Product information", _STYLES))
    story.append(_key_value_table([
        ("Source", product.get("source")),
        ("Product ID", product.get("id")),
        ("Name", product.get("name")),
        ("Dimensions", product.get("dimensions")),
        ("Weight", product.get("weight")),
        ("Desired quantity", product.get("desired_qty")),
        ("Allowed rotations", product.get("rotations")),
    ]))

    story.append(Spacer(1, 6))
    story.append(_section_title("Packaging information", _STYLES))
    story.append(_key_value_table([
        ("Source", container.get("source")),
        ("Part number", container.get("part_number")),
        ("Description", container.get("description")),
        ("Type", container.get("type")),
        ("Material", container.get("material")),
        ("Internal dimensions", container.get("dimensions")),
        ("Packaging weight", container.get("tare")),
        ("Max payload", container.get("payload_capacity")),
    ]))

    story.append(Spacer(1, 6))
    story.append(_section_title("Result summary", _STYLES))
    story.append(_metric_table([
        ("Maximum quantity", f"{analysis.get('max_quantity', '—')} pcs"),
        ("Current quantity", f"{analysis.get('requested_qty', '—')} pcs"),
        ("Volumetric efficiency", analysis.get("volumetric_efficiency_current_display")),
        ("Volumetric efficiency at max qty", analysis.get("volumetric_efficiency_max_display")),
        ("Net weight", analysis.get("net_weight_display")),
        ("Total weight", analysis.get("total_weight_current_display")),
        ("Payload usage", analysis.get("payload_usage_display")),
        ("Remaining capacity", f"{analysis.get('remaining_capacity', '—')} pcs"),
    ]))

    image_path = _safe_media_path(export_payload.get("image_rel_path"))
    if image_path:
        story.append(Spacer(1, 8))
        story.append(_section_title("Packing visualization", _STYLES))
        img = Image(image_path)
        max_width = 160 * mm
        max_height = 90 * mm
        scale = min(max_width / img.drawWidth, max_height / img.drawHeight, 1)
        img.drawWidth *= scale
        img.drawHeight *= scale
        story.append(img)

    story.append(Spacer(1, 10))
    story.append(Paragraph(
        "The 3D visualization is a decision-support representation of the packing logic. "
        "Physical validation is recommended for critical packaging decisions. Final packaging "
        "selection may also depend on protection, handling, branding, transport, and quality requirements.",
        _STYLES["Note"],
    ))

    story.append(Spacer(1, 10))
    story.append(Paragraph("Generated by Packaging Engineering · Container Selection Tool", _STYLES["Footer"]))

    doc.build(story)
    buffer.seek(0)
    return buffer
