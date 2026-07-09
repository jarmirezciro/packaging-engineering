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
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


TOOL_LABELS = {
    "container": "Container Selection",
    "bag": "Bag Selection",
    "pallet": "Palletization",
    "transport": "Transport Container",
}

PACKAGE_LABELS = {
    "container": "Carton / container",
    "bag": "Bag",
    "pallet": "Loaded pallet",
    "transport_unit": "Transport unit",
}


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


def _int(value, default="-"):
    if value in (None, "", "None"):
        return default
    try:
        return str(int(float(value)))
    except (TypeError, ValueError):
        return default


def _first_present(*values, default=None):
    for value in values:
        if value not in (None, "", "None"):
            return value
    return default


def _url_to_media_rel_path(value):
    """Accept a media-relative path or a MEDIA_URL-based URL and return a safe relative path."""
    if not value:
        return None

    text = str(value).strip()
    media_url = getattr(settings, "MEDIA_URL", "/media/") or "/media/"

    if text.startswith(media_url):
        text = text[len(media_url):]
    elif text.startswith("/media/"):
        text = text[len("/media/"):]
    elif "/media/" in text:
        text = text.split("/media/", 1)[1]

    text = text.lstrip("/")
    return text or None


def _safe_media_path(value):
    image_rel_path = _url_to_media_rel_path(value)
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
        name="WorkflowReportTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=17,
        leading=20,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=2,
    ))
    styles.add(ParagraphStyle(
        name="WorkflowReportSubtitle",
        parent=styles["Normal"],
        fontSize=8.4,
        leading=10,
        textColor=colors.HexColor("#64748b"),
        spaceAfter=5,
    ))
    styles.add(ParagraphStyle(
        name="WorkflowSectionTitle",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=9.3,
        leading=10.7,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=3,
        spaceAfter=3,
    ))
    styles.add(ParagraphStyle(
        name="WorkflowBody",
        parent=styles["Normal"],
        fontSize=7.1,
        leading=8.5,
        textColor=colors.HexColor("#334155"),
    ))
    styles.add(ParagraphStyle(
        name="WorkflowBodySmall",
        parent=styles["Normal"],
        fontSize=6.4,
        leading=7.5,
        textColor=colors.HexColor("#334155"),
    ))
    styles.add(ParagraphStyle(
        name="WorkflowMetricLabel",
        parent=styles["Normal"],
        fontSize=6.4,
        leading=7.4,
        textColor=colors.HexColor("#64748b"),
        alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        name="WorkflowMetricValue",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.7,
        leading=9.8,
        textColor=colors.HexColor("#0f172a"),
        alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        name="WorkflowChip",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.1,
        leading=8.2,
        textColor=colors.HexColor("#0f172a"),
        alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        name="WorkflowCaption",
        parent=styles["Normal"],
        fontSize=6.3,
        leading=7.2,
        textColor=colors.HexColor("#64748b"),
        alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        name="WorkflowNote",
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
        name="WorkflowOkNote",
        parent=styles["Normal"],
        fontSize=6.7,
        leading=8,
        textColor=colors.HexColor("#065f46"),
        backColor=colors.HexColor("#ecfdf5"),
        borderColor=colors.HexColor("#bbf7d0"),
        borderWidth=0.4,
        borderPadding=5,
    ))
    styles.add(ParagraphStyle(
        name="WorkflowFooter",
        parent=styles["Normal"],
        fontSize=6.3,
        leading=7.5,
        textColor=colors.HexColor("#94a3b8"),
        alignment=TA_CENTER,
    ))

    return styles


_STYLES = _build_styles()


def _p(text, style="WorkflowBody"):
    return Paragraph(_clean(text), _STYLES[style])


def _raw_p(text, style="WorkflowBody"):
    return Paragraph(text, _STYLES[style])


def _section_title(text):
    return Paragraph(_clean(text), _STYLES["WorkflowSectionTitle"])


def _format_dims(payload):
    if not payload:
        return "-"
    length = _first_present(payload.get("length"), payload.get("l"))
    width = _first_present(payload.get("width"), payload.get("w"))
    height = _first_present(payload.get("height"), payload.get("h"))
    if length in (None, "") or width in (None, "") or height in (None, ""):
        return "-"
    return f"{_num(length, 0)} x {_num(width, 0)} x {_num(height, 0)} mm"


def _format_weight(payload):
    if not payload:
        return "-"
    weight_kg = payload.get("weight_kg")
    if weight_kg not in (None, "", "None"):
        return f"{_num(weight_kg, 2)} kg"
    weight_g = payload.get("weight_g")
    if weight_g not in (None, "", "None"):
        try:
            return f"{float(weight_g) / 1000.0:.2f} kg"
        except Exception:
            return f"{_clean(weight_g)} g"
    return "-"


def _effective_output(step):
    return (step or {}).get("pending_result") or (step or {}).get("selected")


def _input_for_step(steps, index):
    if index <= 0:
        return None
    return _effective_output(steps[index - 1])


def _image_for_step(step):
    image_urls = (step or {}).get("image_urls") or {}
    return _first_present(
        image_urls.get("main"),
        (step or {}).get("image_url"),
        default=None,
    )


def _status_for_step(step):
    if (step or {}).get("messages"):
        return "Needs attention"
    if _effective_output(step):
        return "Result available"
    if (step or {}).get("result"):
        return "Analysis complete"
    return "Not calculated"


def _step_title(step, index):
    step_type = (step or {}).get("type") or "container"
    return f"Step {index + 1} - {TOOL_LABELS.get(step_type, step_type.title())}"


def _chain_item(step, index):
    step_type = (step or {}).get("type") or "container"
    output = _effective_output(step) or {}
    package_type = output.get("package_type") or step_type
    label = output.get("label") or TOOL_LABELS.get(step_type, step_type.title())
    return {
        "title": PACKAGE_LABELS.get(package_type, TOOL_LABELS.get(step_type, step_type.title())),
        "label": label,
        "dims": _format_dims(output),
        "step": index + 1,
        "status": _status_for_step(step),
    }


def _summary_metrics(final_step):
    if not final_step:
        return []

    step_type = final_step.get("type")
    output = _effective_output(final_step) or {}
    result = final_step.get("result") or {}
    analysis = final_step.get("analysis_report") or (result.get("analysis_report") if isinstance(result, dict) else {}) or {}

    if step_type == "transport":
        summary = (result.get("summary") or {}) if isinstance(result, dict) else {}
        return [
            ("Placed units", _int(summary.get("placed_units"))),
            ("Unplaced units", _int(summary.get("unplaced_units"))),
            ("Volume usage", f"{_num(summary.get('utilization_volume_pct'), 2)}%"),
            ("Payload usage", f"{_num(summary.get('utilization_weight_pct'), 2)}%" if summary.get("utilization_weight_pct") is not None else "Not set"),
            ("Gross weight", f"{_num(summary.get('gross_weight'), 2)} kg"),
            ("Final base units", _int(output.get("total_base_units"))),
        ]

    if step_type == "pallet":
        selected = final_step.get("selected_result") or {}
        return [
            ("Cartons per pallet", _int(selected.get("total_boxes") or output.get("units_per_parent"))),
            ("Layers", _int(selected.get("layers"))),
            ("Pallet floor usage", f"{_num(selected.get('layer_footprint_util_pct'), 2)}%"),
            ("Stack volume usage", f"{_num(selected.get('volumetric_util_pct'), 2)}%"),
            ("Gross weight", _format_weight(output)),
            ("Final base units", _int(output.get("total_base_units"))),
        ]

    if step_type == "bag":
        return [
            ("Units per bag", _int(output.get("units_per_parent") or analysis.get("current_quantity"))),
            ("Max quantity", _int(analysis.get("max_quantity"))),
            ("Bag usage", analysis.get("bag_usage_current_display") or f"{_num(analysis.get('bag_usage_current_pct'), 0)}%"),
            ("Payload usage", analysis.get("payload_usage_display") or "Not set"),
            ("Gross weight", _format_weight(output)),
            ("Final base units", _int(output.get("total_base_units"))),
        ]

    return [
        ("Units per carton", _int(output.get("units_per_parent") or analysis.get("requested_qty"))),
        ("Max quantity", _int(analysis.get("max_quantity") or (result.get("max_quantity") if isinstance(result, dict) else None))),
        ("Volume usage", analysis.get("volumetric_efficiency_current_display") or f"{_num(analysis.get('volumetric_efficiency_current_pct'), 0)}%"),
        ("Payload usage", analysis.get("payload_usage_display") or "Not set"),
        ("Gross weight", _format_weight(output)),
        ("Final base units", _int(output.get("total_base_units"))),
    ]


def _step_metrics(step):
    step_type = (step or {}).get("type")
    result = (step or {}).get("result") or {}
    analysis = (step or {}).get("analysis_report") or (result.get("analysis_report") if isinstance(result, dict) else {}) or {}
    output = _effective_output(step) or {}

    if step_type == "transport":
        summary = (result.get("summary") or {}) if isinstance(result, dict) else {}
        rows = [
            ("Placed units", _int(summary.get("placed_units"))),
            ("Unplaced units", _int(summary.get("unplaced_units"))),
            ("Volume usage", f"{_num(summary.get('utilization_volume_pct'), 2)}%"),
            ("Payload usage", f"{_num(summary.get('utilization_weight_pct'), 2)}%" if summary.get("utilization_weight_pct") is not None else "Not set"),
            ("Loaded volume", f"{_num(summary.get('packed_volume_m3'), 3)} m3"),
            ("Gross loaded weight", f"{_num(summary.get('gross_weight'), 2)} kg"),
            ("Occupied L x W x H", f"{_num(summary.get('occupied_length'), 0)} x {_num(summary.get('occupied_width'), 0)} x {_num(summary.get('occupied_height'), 0)} mm"),
            ("Residual L x W x H", f"{_num(summary.get('residual_length'), 0)} x {_num(summary.get('residual_width'), 0)} x {_num(summary.get('residual_height'), 0)} mm"),
        ]
        return rows

    if step_type == "pallet":
        selected = (step or {}).get("selected_result") or {}
        return [
            ("Main layer cartons", _int(selected.get("boxes_layer_A"))),
            ("Alternate layer cartons", _int(selected.get("boxes_layer_B"))),
            ("Layers", _int(selected.get("layers"))),
            ("Total cartons", _int(selected.get("total_boxes") or output.get("units_per_parent"))),
            ("Used stack height", f"{_num(selected.get('used_height_mm'), 0)} mm"),
            ("Pallet floor usage", f"{_num(selected.get('layer_footprint_util_pct'), 2)}%"),
            ("Stack volume usage", f"{_num(selected.get('volumetric_util_pct'), 2)}%"),
            ("Bottom-carton load check", "OK" if selected.get("feasible_weight") else ("Review required" if selected else "Not checked")),
        ]

    if step_type == "bag":
        return [
            ("Requested quantity", _int(analysis.get("current_quantity") or analysis.get("requested_qty"))),
            ("Max quantity", _int(analysis.get("max_quantity"))),
            ("Remaining capacity", _int(analysis.get("remaining_capacity"))),
            ("Bag usage", analysis.get("bag_usage_current_display") or f"{_num(analysis.get('bag_usage_current_pct'), 0)}%"),
            ("Max bag usage", analysis.get("bag_usage_max_display") or f"{_num(analysis.get('bag_usage_max_pct'), 0)}%"),
            ("Total weight", analysis.get("total_weight_display") or _format_weight(output)),
            ("Payload usage", analysis.get("payload_usage_display") or "Not set"),
        ]

    return [
        ("Requested quantity", _int(analysis.get("requested_qty"))),
        ("Max quantity", _int(analysis.get("max_quantity") or (result.get("max_quantity") if isinstance(result, dict) else None))),
        ("Remaining capacity", _int(analysis.get("remaining_capacity"))),
        ("Volume usage", analysis.get("volumetric_efficiency_current_display") or f"{_num(analysis.get('volumetric_efficiency_current_pct'), 0)}%"),
        ("Max volume usage", analysis.get("volumetric_efficiency_max_display") or f"{_num(analysis.get('volumetric_efficiency_max_pct'), 0)}%"),
        ("Total weight", analysis.get("total_weight_current_display") or _format_weight(output)),
        ("Payload usage", analysis.get("payload_usage_display") or "Not set"),
    ]


def build_workflow_report_payload(workflow):
    steps = (workflow or {}).get("steps") or []
    report_steps = []

    for index, step in enumerate(steps):
        input_payload = _input_for_step(steps, index)
        output_payload = _effective_output(step)
        image_urls = (step or {}).get("image_urls") or {}

        report_steps.append({
            "number": index + 1,
            "type": (step or {}).get("type") or "container",
            "title": _step_title(step, index),
            "status": _status_for_step(step),
            "input": input_payload,
            "output": output_payload,
            "metrics": _step_metrics(step),
            "messages": list((step or {}).get("messages") or []),
            "image_rel_path": _url_to_media_rel_path(_image_for_step(step)),
            "image_rel_paths": {
                key: _url_to_media_rel_path(value)
                for key, value in image_urls.items()
                if value
            },
            "transport_rows": (((step or {}).get("result") or {}).get("summary") or {}).get("product_rows") or [],
        })

    final_step = None
    for step in reversed(steps):
        if _effective_output(step) or step.get("result"):
            final_step = step
            break

    return {
        "title": "Packaging Flow Report",
        "generated_at": timezone.now().strftime("%Y-%m-%d %H:%M"),
        "chain": [_chain_item(step, idx) for idx, step in enumerate(steps)],
        "summary_metrics": _summary_metrics(final_step),
        "final_image_rel_path": _url_to_media_rel_path(_image_for_step(final_step)) if final_step else None,
        "steps": report_steps,
    }


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
        title="Packaging Flow Report",
    )


def _metric_cards(metrics):
    metrics = list(metrics or [])[:6]
    if not metrics:
        metrics = [("Workflow status", "No result yet")]

    cells = []
    width = max(1, len(metrics))
    for label, value in metrics:
        cells.append([
            Paragraph(f"<b>{_clean(value)}</b>", _STYLES["WorkflowMetricValue"]),
            Paragraph(_clean(label), _STYLES["WorkflowMetricLabel"]),
        ])

    table = Table([cells], colWidths=[(266 * mm) / width] * width)
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


def _key_value_table(rows, col_widths=None):
    data = [
        [
            Paragraph(f"<b>{_clean(label)}</b>", _STYLES["WorkflowBodySmall"]),
            Paragraph(_clean(value), _STYLES["WorkflowBodySmall"]),
        ]
        for label, value in rows
    ]
    table = Table(data, colWidths=col_widths or [34 * mm, 94 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f8fafc")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d9e2ec")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
    ]))
    return table


def _chain_table(chain):
    if not chain:
        return _p("No workflow steps yet.")

    cells = []
    for item in chain[:6]:
        title = _clean(item.get("title"))
        label = _clean(item.get("label"))
        dims = _clean(item.get("dims"))
        status = _clean(item.get("status"))
        cells.append([
            Paragraph(f"Step {item.get('step')}<br/><b>{title}</b>", _STYLES["WorkflowChip"]),
            Paragraph(f"{label}<br/>{dims}<br/>{status}", _STYLES["WorkflowCaption"]),
        ])

    table = Table([cells], colWidths=[(266 * mm) / len(cells)] * len(cells))
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#eef6ff")),
        ("BOX", (0, 0), (-1, -1), 0.35, colors.HexColor("#bfdbfe")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#bfdbfe")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def _image_block(image_rel_path, max_w, max_h, caption="Visualization"):
    image_path = _safe_media_path(image_rel_path)
    if not image_path:
        return [_p("Visualization not available.", "WorkflowBodySmall")]

    img = Image(image_path)
    img._restrictSize(max_w, max_h)
    return [img, Paragraph(_clean(caption), _STYLES["WorkflowCaption"])]


def _payload_rows(title, payload):
    if not payload:
        return [
            (title, "Not available"),
            ("Dimensions", "-"),
            ("Units per parent", "-"),
            ("Total base units", "-"),
            ("Gross weight", "-"),
        ]

    return [
        (title, payload.get("label") or "Workflow load unit"),
        ("Dimensions", _format_dims(payload)),
        ("Units per parent", _int(payload.get("units_per_parent"))),
        ("Total base units", _int(payload.get("total_base_units"))),
        ("Gross weight", _format_weight(payload)),
    ]


def _transport_rows_table(rows):
    rows = rows or []
    header = [
        Paragraph("<b>Load unit</b>", _STYLES["WorkflowBodySmall"]),
        Paragraph("<b>Dims (mm)</b>", _STYLES["WorkflowBodySmall"]),
        Paragraph("<b>Requested</b>", _STYLES["WorkflowBodySmall"]),
        Paragraph("<b>Loaded</b>", _STYLES["WorkflowBodySmall"]),
        Paragraph("<b>Weight</b>", _STYLES["WorkflowBodySmall"]),
    ]
    data = [header]
    for row in rows[:5]:
        dims = f"{_num(row.get('length'), 0)} x {_num(row.get('width'), 0)} x {_num(row.get('height'), 0)}"
        requested = _int(row.get("qty_requested"))
        if row.get("max_qty"):
            requested = f"Max ({requested})"
        data.append([
            Paragraph(_clean(row.get("name")), _STYLES["WorkflowBodySmall"]),
            Paragraph(_clean(dims), _STYLES["WorkflowBodySmall"]),
            Paragraph(_clean(requested), _STYLES["WorkflowBodySmall"]),
            Paragraph(_int(row.get("qty_packed")), _STYLES["WorkflowBodySmall"]),
            Paragraph(f"{_num(row.get('weight_each'), 2)} kg", _STYLES["WorkflowBodySmall"]),
        ])

    if len(rows) > 5:
        data.append([Paragraph(f"+ {len(rows) - 5} more row(s)", _STYLES["WorkflowBodySmall"]), "", "", "", ""])

    table = Table(data, colWidths=[36 * mm, 34 * mm, 22 * mm, 18 * mm, 24 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eaf2ff")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d9e2ec")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("SPAN", (0, -1), (-1, -1)) if len(rows) > 5 else ("LINEBELOW", (0, 0), (-1, 0), 0.25, colors.HexColor("#d9e2ec")),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
    ]))
    return table


def _step_detail_block(step):
    left_column = [
        _section_title(step.get("title")),
        _key_value_table([
            ("Status", step.get("status")),
            ("Input", (step.get("input") or {}).get("label") or "Manual input / catalogue"),
            ("Input dimensions", _format_dims(step.get("input"))),
            ("Output", (step.get("output") or {}).get("label") or "Not available"),
            ("Output dimensions", _format_dims(step.get("output"))),
        ], [34 * mm, 94 * mm]),
        Spacer(1, 2 * mm),
        _section_title("Key metrics"),
        _key_value_table(step.get("metrics") or [], [44 * mm, 84 * mm]),
    ]

    if step.get("type") == "transport" and step.get("transport_rows"):
        left_column.extend([
            Spacer(1, 2 * mm),
            _section_title("Load-unit rows"),
            _transport_rows_table(step.get("transport_rows")),
        ])

    messages = step.get("messages") or []
    if messages:
        left_column.extend([
            Spacer(1, 2 * mm),
            Paragraph(_clean("; ".join(messages)), _STYLES["WorkflowNote"]),
        ])
    else:
        left_column.extend([
            Spacer(1, 2 * mm),
            Paragraph("No validation warnings for this calculated step.", _STYLES["WorkflowOkNote"]),
        ])

    right_column = [_section_title("Visualization")]
    right_column.extend(_image_block(step.get("image_rel_path"), 128 * mm, 64 * mm, "Calculated result view"))

    if step.get("type") == "transport":
        image_paths = step.get("image_rel_paths") or {}
        top_or_side = image_paths.get("top") or image_paths.get("side")
        opposite = image_paths.get("opposite")
        if top_or_side or opposite:
            views_table = Table([[
                _image_block(top_or_side, 61 * mm, 34 * mm, "Top / side view"),
                _image_block(opposite, 61 * mm, 34 * mm, "Opposite view"),
            ]], colWidths=[64 * mm, 64 * mm])
            views_table.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]))
            right_column.extend([Spacer(1, 2 * mm), _section_title("Inspection views"), views_table])

    table = Table([[left_column, right_column]], colWidths=[132 * mm, 134 * mm])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return table


def build_full_packaging_pdf(report_payload):
    """Build a compact PDF report for the Packaging Flow workflow."""
    buffer = BytesIO()
    doc = _build_doc(buffer)
    story = []

    generated_at = report_payload.get("generated_at") or timezone.now().strftime("%Y-%m-%d %H:%M")
    steps = report_payload.get("steps") or []

    story.append(Paragraph("Packaging Flow Report", _STYLES["WorkflowReportTitle"]))
    story.append(Paragraph(f"Full packaging workflow analysis - Generated {generated_at}", _STYLES["WorkflowReportSubtitle"]))

    story.append(_metric_cards(report_payload.get("summary_metrics") or []))
    story.append(Spacer(1, 3 * mm))

    story.append(_section_title("Packaging chain"))
    story.append(_chain_table(report_payload.get("chain") or []))
    story.append(Spacer(1, 3 * mm))

    final_image = report_payload.get("final_image_rel_path")
    if final_image:
        story.append(_section_title("Final visualization"))
        final_img_block = _image_block(final_image, 256 * mm, 82 * mm, "Final calculated workflow result")
        story.extend(final_img_block)
        story.append(Spacer(1, 2 * mm))

    if steps:
        story.append(_section_title("Step summary"))
        rows = [[
            Paragraph("<b>Step</b>", _STYLES["WorkflowBodySmall"]),
            Paragraph("<b>Status</b>", _STYLES["WorkflowBodySmall"]),
            Paragraph("<b>Input</b>", _STYLES["WorkflowBodySmall"]),
            Paragraph("<b>Output</b>", _STYLES["WorkflowBodySmall"]),
            Paragraph("<b>Output dimensions</b>", _STYLES["WorkflowBodySmall"]),
        ]]
        for step in steps:
            rows.append([
                Paragraph(_clean(step.get("title")), _STYLES["WorkflowBodySmall"]),
                Paragraph(_clean(step.get("status")), _STYLES["WorkflowBodySmall"]),
                Paragraph(_clean((step.get("input") or {}).get("label") or "Manual input / catalogue"), _STYLES["WorkflowBodySmall"]),
                Paragraph(_clean((step.get("output") or {}).get("label") or "Not available"), _STYLES["WorkflowBodySmall"]),
                Paragraph(_clean(_format_dims(step.get("output"))), _STYLES["WorkflowBodySmall"]),
            ])
        summary_table = Table(rows, colWidths=[48 * mm, 30 * mm, 58 * mm, 58 * mm, 72 * mm], repeatRows=1)
        summary_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eaf2ff")),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d9e2ec")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ]))
        story.append(summary_table)

    for step in steps:
        story.append(PageBreak())
        story.append(_step_detail_block(step))
        story.append(Spacer(1, 2 * mm))
        story.append(Paragraph("Generated by Packaging Engineering - Packaging Flow", _STYLES["WorkflowFooter"]))

    if not steps:
        story.append(_p("No workflow steps are available. Add and run at least one step before exporting a useful report."))

    doc.build(story, onFirstPage=_draw_report_frame, onLaterPages=_draw_report_frame)
    buffer.seek(0)
    return buffer
