from io import BytesIO

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Flowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _value(value, suffix=""):
    if value in (None, "", "None"):
        return "Unavailable"
    if isinstance(value, float):
        value = f"{value:.4f}".rstrip("0").rstrip(".")
    return f"{value}{suffix}"


class BlankPreviewFlowable(Flowable):
    """Small reportlab equivalent of the browser's backend-driven blank SVG."""

    def __init__(self, geometry):
        super().__init__()
        self.geometry = geometry or {}
        self.width = 160 * mm
        self.height = 62 * mm

    def draw(self):
        canvas = self.canv
        g = self.geometry
        sheet_l = float(g.get("production_sheet_length_mm") or 1)
        sheet_w = float(g.get("production_sheet_width_mm") or 1)
        scale = min((self.width - 8 * mm) / sheet_l, (self.height - 8 * mm) / sheet_w)
        ox, oy = 4 * mm, 4 * mm
        def xy(x, y):
            return ox + x * scale, oy + y * scale
        canvas.setFillColor(colors.HexColor("#fff7ed"))
        canvas.setStrokeColor(colors.HexColor("#94a3b8"))
        canvas.rect(ox, oy, sheet_l * scale, sheet_w * scale, fill=1, stroke=1)
        margin = 20.0
        blank_l = float(g.get("blank_length_mm") or sheet_l - 2 * margin)
        blank_w = float(g.get("blank_width_mm") or sheet_w - 2 * margin)
        bx, by = xy(margin, margin)
        canvas.setFillColor(colors.HexColor("#dcfce7"))
        canvas.setStrokeColor(colors.HexColor("#15803d"))
        canvas.rect(bx, by, blank_l * scale, blank_w * scale, fill=1, stroke=1)
        canvas.setStrokeColor(colors.HexColor("#64748b"))
        canvas.setDash(3, 2)
        canvas.line(bx, by + blank_w * scale / 2, bx + blank_l * scale, by + blank_w * scale / 2)
        canvas.setDash()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#334155"))
        canvas.drawString(bx + 3, by + blank_w * scale - 9, "FEFCO 0201 blank / sheet boundary")


def _styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="CMS_Title", parent=styles["Title"], fontSize=17, leading=20, textColor=colors.HexColor("#0f172a"), spaceAfter=3))
    styles.add(ParagraphStyle(name="CMS_Section", parent=styles["Heading2"], fontSize=11, leading=13, textColor=colors.HexColor("#0f766e"), spaceBefore=7, spaceAfter=4))
    styles.add(ParagraphStyle(name="CMS_Body", parent=styles["Normal"], fontSize=8, leading=10, textColor=colors.HexColor("#334155")))
    return styles


def _table(rows, styles):
    table = Table([[Paragraph(f"<b>{label}</b>", styles["CMS_Body"]), Paragraph(_value(value), styles["CMS_Body"])] for label, value in rows], colWidths=[52 * mm, 122 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f8fafc")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d9e2ec")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return table


def build_corrugated_material_strength_pdf(payload):
    styles = _styles()
    result = payload.get("result") or {}
    geometry = result.get("box_geometry") or {}
    material = result.get("material") or {}
    pallet = result.get("pallet") or {}
    strength = result.get("strength") or {}
    carbon = result.get("carbon") or {}
    source = result.get("source_metadata") or {}
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=16 * mm, leftMargin=16 * mm, topMargin=14 * mm, bottomMargin=14 * mm, title="Corrugated Material & Strength Report")
    story = [
        Paragraph("Corrugated Material & Strength", styles["CMS_Title"]),
        Paragraph(f"Preliminary engineering estimate · generated {timezone.now():%Y-%m-%d %H:%M}", styles["CMS_Body"]),
        Spacer(1, 3 * mm),
        Paragraph("Inputs and construction", styles["CMS_Section"]),
        _table([
            ("Selected construction", source.get("name")), ("Source type", source.get("source_type")),
            ("Source label", source.get("source_label")), ("Board grammage", (result.get("board") or {}).get("combined_grammage_g_m2")),
            ("Preliminary box style", "FEFCO 0201"),
        ], styles),
        Paragraph("FEFCO 0201 preview", styles["CMS_Section"]),
        BlankPreviewFlowable(geometry),
        Paragraph("Geometry", styles["CMS_Section"]),
        _table([
            ("Blank", f"{_value(geometry.get('blank_length_mm'))} × {_value(geometry.get('blank_width_mm'))} mm"),
            ("Blank bounding area", _value(geometry.get("blank_bounding_area_m2"), " m²")),
            ("Required sheet", f"{_value(geometry.get('production_sheet_length_mm'))} × {_value(geometry.get('production_sheet_width_mm'))} mm"),
            ("Required sheet area", _value(geometry.get("production_sheet_area_m2"), " m²")),
            ("Effective box area", _value(geometry.get("effective_box_area_m2"), " m²")),
            ("Geometric scrap", _value(geometry.get("total_scrap_area_m2"), " m²")),
            ("Utilization", _value(geometry.get("material_utilization_percent"), "%")),
        ], styles),
        Paragraph("Material", styles["CMS_Section"]),
        _table([
            ("Combined grammage", _value(material.get("combined_grammage_g_m2"), " g/m²")),
            ("Finished-box weight", _value(material.get("finished_box_weight_g"), " g")),
            ("Required-sheet weight", _value(material.get("production_sheet_weight_g"), " g")),
            ("Geometric scrap weight", _value(material.get("cutting_scrap_weight_g"), " g")),
            ("Gross packed-box weight", _value(material.get("gross_packed_box_weight_g"), " g")),
        ], styles),
        Paragraph("Pallet and strength", styles["CMS_Section"]),
        _table([
            ("Orientation", pallet.get("selected_orientation")), ("Boxes per layer", pallet.get("boxes_per_layer")),
            ("Layers", pallet.get("layers")), ("Boxes per pallet", pallet.get("boxes_per_pallet")),
            ("Palletized height", _value(pallet.get("palletized_height_mm"), " mm")),
            ("Static load", _value(pallet.get("static_load_n"), " N")),
            ("Required BCT", _value(strength.get("required_bct_n"), " N")),
            ("Available BCT", _value(strength.get("available_bct_n"), " N")),
            ("Strength margin", _value(strength.get("strength_margin"))),
            ("Interpretation", strength.get("strength_status")),
        ], styles),
        Paragraph("CO₂ screening", styles["CMS_Section"]),
        _table([
            ("Factor", _value(carbon.get("factor_kg_co2e_per_kg"), " kg CO₂e/kg")),
            ("Source", carbon.get("source_label")), ("Boundary", carbon.get("boundary")),
            ("Finished-box indicator", _value(carbon.get("finished_box_co2_kg"), " kg CO₂e")),
            ("Required-sheet indicator", _value(carbon.get("required_sheet_co2_kg"), " kg CO₂e")),
            ("Per pallet", _value(carbon.get("pallet_co2_kg"), " kg CO₂e")),
            ("Production quantity", _value(carbon.get("quantity_co2_kg"), " kg CO₂e")),
        ], styles),
        Paragraph("Assumptions and limitations", styles["CMS_Section"]),
    ]
    for item in result.get("assumptions") or []:
        story.append(Paragraph(f"• {item}", styles["CMS_Body"]))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph("This is a preliminary engineering estimate. Confirm final specifications with the corrugated supplier and representative testing. It is not a formal product carbon footprint, supplier approval, certification, or distribution-test replacement.", styles["CMS_Body"]))
    doc.build(story)
    buffer.seek(0)
    return buffer
