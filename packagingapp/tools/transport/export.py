import os
from html import escape
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

from .modes import (
    DEFAULT_TRANSPORT_PACKING_MODE,
    normalize_transport_packing_mode,
    transport_packing_mode_label,
)


def _clean(value, default="-"):
    if value in (None, "", "None"):
        return default
    return escape(str(value))


def _num(value, decimals=2, default="-"):
    if value in (None, "", "None"):
        return default
    try:
        return f"{float(value):.{decimals}f}"
    except (TypeError, ValueError):
        return default


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
        name="TransportReportTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=17,
        leading=20,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=2,
    ))
    styles.add(ParagraphStyle(
        name="TransportReportSubtitle",
        parent=styles["Normal"],
        fontSize=8.4,
        leading=10,
        textColor=colors.HexColor("#64748b"),
        spaceAfter=5,
    ))
    styles.add(ParagraphStyle(
        name="TransportSectionTitle",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=9.2,
        leading=10.5,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=3,
        spaceAfter=3,
    ))
    styles.add(ParagraphStyle(
        name="TransportBody",
        parent=styles["Normal"],
        fontSize=7.1,
        leading=8.5,
        textColor=colors.HexColor("#334155"),
    ))
    styles.add(ParagraphStyle(
        name="TransportBodySmall",
        parent=styles["Normal"],
        fontSize=6.4,
        leading=7.4,
        textColor=colors.HexColor("#334155"),
    ))
    styles.add(ParagraphStyle(
        name="TransportMetricLabel",
        parent=styles["Normal"],
        fontSize=6.4,
        leading=7.4,
        textColor=colors.HexColor("#64748b"),
        alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        name="TransportMetricValue",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.8,
        leading=10,
        textColor=colors.HexColor("#0f172a"),
        alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        name="TransportNote",
        parent=styles["Normal"],
        fontSize=6.7,
        leading=8,
        textColor=colors.HexColor("#7c2d12"),
        backColor=colors.HexColor("#fff7ed"),
        borderColor=colors.HexColor("#fed7aa"),
        borderWidth=0.4,
        borderPadding=5,
    ))
    styles.add(ParagraphStyle(
        name="TransportCaption",
        parent=styles["Normal"],
        fontSize=6.4,
        leading=7.4,
        textColor=colors.HexColor("#64748b"),
        alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        name="TransportFooter",
        parent=styles["Normal"],
        fontSize=6.3,
        leading=7.5,
        textColor=colors.HexColor("#94a3b8"),
        alignment=TA_CENTER,
    ))

    return styles


_STYLES = _build_styles()


def _p(text, style="TransportBody"):
    return Paragraph(_clean(text), _STYLES[style])


def _raw_p(text, style="TransportBody"):
    return Paragraph(text, _STYLES[style])


def _section_title(text):
    return Paragraph(_clean(text), _STYLES["TransportSectionTitle"])


def _key_value_table(rows, col_widths):
    data = [
        [
            Paragraph(f"<b>{_clean(label)}</b>", _STYLES["TransportBodySmall"]),
            Paragraph(_clean(value), _STYLES["TransportBodySmall"]),
        ]
        for label, value in rows
    ]
    table = Table(data, colWidths=col_widths)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f8fafc")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d9e2ec")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 2.6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.6),
    ]))
    return table


def _metric_cards(metrics):
    cells = []
    for label, value in metrics:
        cells.append([
            Paragraph(f"<b>{_clean(value)}</b>", _STYLES["TransportMetricValue"]),
            Paragraph(_clean(label), _STYLES["TransportMetricLabel"]),
        ])

    table = Table([cells], colWidths=[35 * mm] * len(metrics))
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ("BOX", (0, 0), (-1, -1), 0.35, colors.HexColor("#d9e2ec")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d9e2ec")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def _product_rows_table(rows):
    header = [
        Paragraph("<b>Load unit</b>", _STYLES["TransportBodySmall"]),
        Paragraph("<b>Dims (mm)</b>", _STYLES["TransportBodySmall"]),
        Paragraph("<b>Requested</b>", _STYLES["TransportBodySmall"]),
        Paragraph("<b>Loaded</b>", _STYLES["TransportBodySmall"]),
        Paragraph("<b>Weight</b>", _STYLES["TransportBodySmall"]),
        Paragraph("<b>Stack</b>", _STYLES["TransportBodySmall"]),
        Paragraph("<b>Seq.</b>", _STYLES["TransportBodySmall"]),
    ]

    data = [header]
    for row in (rows or [])[:6]:
        dims = f"{_num(row.get('length'), 0)} x {_num(row.get('width'), 0)} x {_num(row.get('height'), 0)}"
        data.append([
            Paragraph(_clean(row.get("name")), _STYLES["TransportBodySmall"]),
            Paragraph(_clean(dims), _STYLES["TransportBodySmall"]),
            Paragraph(_clean(row.get("qty_requested")), _STYLES["TransportBodySmall"]),
            Paragraph(_clean(row.get("qty_packed")), _STYLES["TransportBodySmall"]),
            Paragraph(f"{_num(row.get('weight_each'), 2)} kg", _STYLES["TransportBodySmall"]),
            Paragraph("Yes" if row.get("stackable", True) else "No", _STYLES["TransportBodySmall"]),
            Paragraph(_clean(row.get("sequence")), _STYLES["TransportBodySmall"]),
        ])

    if len(rows or []) > 6:
        data.append([
            Paragraph(f"+ {len(rows) - 6} more row(s)", _STYLES["TransportBodySmall"]),
            "", "", "", "", "", "",
        ])

    table = Table(data, colWidths=[30 * mm, 32 * mm, 16 * mm, 14 * mm, 18 * mm, 14 * mm, 9 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eaf2ff")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d9e2ec")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("SPAN", (0, -1), (-1, -1)) if len(rows or []) > 6 else ("LINEBELOW", (0, 0), (-1, 0), 0.25, colors.HexColor("#d9e2ec")),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 2.6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.6),
    ]))
    return table


def _product_legend_table(products):
    entries = []
    for product in products or []:
        dimensions = (
            f"{_num(product.get('length'), 0)} x "
            f"{_num(product.get('width'), 0)} x "
            f"{_num(product.get('height'), 0)} mm"
        )
        quantity = f"Loaded: {_clean(product.get('qty_loaded'))}"
        if product.get("qty_requested") is not None:
            quantity += f" / {_clean(product.get('qty_requested'))}"
        copy = Paragraph(
            f"<b>{_clean(product.get('product_id'))}</b> - "
            f"{_clean(product.get('name'))}<br/>"
            f"{_clean(dimensions)}<br/>{quantity}",
            _STYLES["TransportBodySmall"],
        )
        try:
            swatch_color = colors.HexColor(str(product.get("color") or "#94a3b8"))
        except (TypeError, ValueError):
            swatch_color = colors.HexColor("#94a3b8")
        swatch = Table([[""]], colWidths=[4 * mm], rowHeights=[4 * mm])
        swatch.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), swatch_color),
            ("BOX", (0, 0), (-1, -1), 0.35, colors.HexColor("#334155")),
        ]))
        entry = Table([[swatch, copy]], colWidths=[5 * mm, 36.5 * mm])
        entry.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 1.5),
            ("TOPPADDING", (0, 0), (-1, -1), 1.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
        ]))
        entries.append(entry)

    if not entries:
        return _p("No rendered load products.", "TransportBodySmall")

    rows = []
    for offset in range(0, len(entries), 3):
        row = entries[offset:offset + 3]
        row.extend([""] * (3 - len(row)))
        rows.append(row)
    table = Table(rows, colWidths=[42.5 * mm] * 3)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ("BOX", (0, 0), (-1, -1), 0.25, colors.HexColor("#d9e2ec")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d9e2ec")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
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
        rightMargin=12 * mm,
        leftMargin=12 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
        title="Transport Container Report",
    )


def _image_block(image_rel_path, max_w, max_h, caption):
    image_path = _safe_media_path(image_rel_path)
    if not image_path:
        return [_p("Visualization not available.")]

    img = Image(image_path)
    img._restrictSize(max_w, max_h)
    return [img, Paragraph(_clean(caption), _STYLES["TransportCaption"])]


def _validation_note(summary):
    unplaced = int(summary.get("unplaced_units", 0) or 0)
    has_payload_limit = bool(summary.get("has_payload_limit"))
    payload_usage = summary.get("utilization_weight_pct")

    if unplaced > 0:
        return (
            f"Validation note: {unplaced} requested load unit(s) could not be placed. "
            "Review dimensional constraints, loading sequence, rotations and payload limit."
        )
    if has_payload_limit and payload_usage is not None:
        return (
            f"Validation note: all requested load units were placed. Payload usage is {_num(payload_usage, 1)}%, "
            "based on the entered max payload."
        )
    return "Validation note: all requested load units were placed. No max payload was entered, so the result validates dimensional loading only."


def build_transport_container_pdf(export_payload):
    """Build the Transport report from validated browser-rendered snapshots."""
    buffer = BytesIO()
    doc = _build_doc(buffer)
    story = []

    generated_at = export_payload.get("generated_at") or timezone.now().strftime("%Y-%m-%d %H:%M")
    unit = export_payload.get("transport_unit") or {}
    summary = export_payload.get("summary") or {}
    packing_mode = normalize_transport_packing_mode(
        export_payload.get("packing_mode"),
        default=DEFAULT_TRANSPORT_PACKING_MODE,
    )
    packing_mode_label = transport_packing_mode_label(packing_mode)
    snapshot_rel_paths = export_payload.get("threejs_snapshot_rel_paths") or {}

    story.append(Paragraph("Transport Container Analysis Report", _STYLES["TransportReportTitle"]))
    story.append(Paragraph(f"Standalone transport loading analysis - Generated {generated_at}", _STYLES["TransportReportSubtitle"]))

    story.append(_metric_cards([
        ("Placed units", _clean(summary.get("placed_units"))),
        ("Unplaced units", _clean(summary.get("unplaced_units"))),
        ("Volume usage", f"{_num(summary.get('utilization_volume_pct'), 2)}%"),
        ("Payload usage", f"{_num(summary.get('utilization_weight_pct'), 2)}%" if summary.get("utilization_weight_pct") is not None else "Not set"),
        ("Loaded volume", f"{_num(summary.get('packed_volume_m3'), 3)} m3"),
        ("Unit volume", f"{_num(summary.get('container_volume_m3'), 3)} m3"),
    ]))
    story.append(Spacer(1, 3 * mm))

    left_column = [
        _section_title("Transport unit"),
        _key_value_table([
            ("Source", unit.get("source")),
            ("Part number", unit.get("part_number")),
            ("Description", unit.get("description")),
            ("Type", unit.get("type")),
            ("Material", unit.get("material")),
            ("Internal dimensions", unit.get("dimensions")),
            ("Max payload", unit.get("max_payload")),
            ("Tare weight", unit.get("tare_weight")),
        ], [34 * mm, 94 * mm]),
        Spacer(1, 3 * mm),
        _section_title("Loading details"),
        _key_value_table([
            ("Packing mode", packing_mode_label),
            ("Loaded product weight", f"{_num(summary.get('loaded_weight'), 2)} kg"),
            ("Gross loaded weight", f"{_num(summary.get('gross_weight'), 2)} kg"),
            ("Occupied L x W x H", f"{_num(summary.get('occupied_length'), 0)} x {_num(summary.get('occupied_width'), 0)} x {_num(summary.get('occupied_height'), 0)} mm"),
            ("Residual L x W x H", f"{_num(summary.get('residual_length'), 0)} x {_num(summary.get('residual_width'), 0)} x {_num(summary.get('residual_height'), 0)} mm"),
        ], [41 * mm, 87 * mm]),
        Spacer(1, 3 * mm),
        _section_title("Load-unit summary"),
        _product_rows_table(summary.get("product_rows") or []),
        Spacer(1, 3 * mm),
        Paragraph(_clean(_validation_note(summary)), _STYLES["TransportNote"]),
    ]

    right_column = [
        _section_title("Loading View"),
    ]
    right_column.extend(_image_block(snapshot_rel_paths.get("loading"), 123 * mm, 52 * mm, "Loading View - established door-side perspective."))
    right_column.append(Spacer(1, 2 * mm))

    image_cells = []
    top_block = _image_block(snapshot_rel_paths.get("top"), 60 * mm, 38 * mm, "Top View")
    opposite_block = _image_block(snapshot_rel_paths.get("opposite"), 60 * mm, 38 * mm, "Opposite Side")
    image_cells.append([top_block, opposite_block])

    views_table = Table(image_cells, colWidths=[63 * mm, 63 * mm])
    views_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    right_column.extend([
        _section_title("Inspection views"),
        views_table,
        Spacer(1, 2 * mm),
        _section_title("Product legend"),
        _product_legend_table(export_payload.get("product_legend") or []),
        Spacer(1, 2 * mm),
        Paragraph(
            "The Three.js views use the same calculated placement. They only change the camera angle to help inspect hidden placements and floor usage.",
            _STYLES["TransportBodySmall"],
        ),
    ])

    content_table = Table([[left_column, right_column]], colWidths=[132 * mm, 134 * mm])
    content_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(content_table)
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph("Generated by Packaging Engineering - Transport Container Tool", _STYLES["TransportFooter"]))

    doc.build(story, onFirstPage=_draw_report_frame, onLaterPages=_draw_report_frame)
    buffer.seek(0)
    return buffer
