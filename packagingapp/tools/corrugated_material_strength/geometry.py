from dataclasses import dataclass
from decimal import Decimal
from html import escape
from typing import Protocol


MM2_PER_M2 = Decimal("1000000")


@dataclass(frozen=True)
class BoxGeometryInput:
    length_mm: Decimal
    width_mm: Decimal
    height_mm: Decimal
    joint_width_mm: Decimal
    sheet_margin_per_edge_mm: Decimal


@dataclass(frozen=True)
class BoxGeometryResult:
    blank_length_mm: Decimal
    blank_width_mm: Decimal
    blank_bounding_area_m2: Decimal
    production_sheet_length_mm: Decimal
    production_sheet_width_mm: Decimal
    production_sheet_area_m2: Decimal
    effective_box_area_m2: Decimal
    blank_void_area_m2: Decimal
    sheet_margin_area_m2: Decimal
    total_scrap_area_m2: Decimal
    material_utilization_percent: Decimal
    scrap_percent: Decimal
    body_panel_area_m2: Decimal
    flap_area_m2: Decimal
    joint_body_area_m2: Decimal
    preview_svg: str


class BoxStyleGeometryProvider(Protocol):
    def calculate(self, inputs: BoxGeometryInput) -> BoxGeometryResult:
        ...


def _m2(mm2):
    return mm2 / MM2_PER_M2


def _fmt(value, places=3):
    return f"{float(value):.{places}f}".rstrip("0").rstrip(".")


def render_fefco_0201_svg(result: BoxGeometryResult, inputs: BoxGeometryInput) -> str:
    """Render a backend-driven, responsive SVG for the simplified blank."""
    sheet_w = float(result.production_sheet_length_mm)
    sheet_h = float(result.production_sheet_width_mm)
    margin = float(inputs.sheet_margin_per_edge_mm)
    blank_x = margin
    blank_y = margin
    blank_w = float(result.blank_length_mm)
    blank_h = float(result.blank_width_mm)
    l = float(inputs.length_mm)
    w = float(inputs.width_mm)
    h = float(inputs.height_mm)
    joint = float(inputs.joint_width_mm)
    flap_depth = w / 2
    body_y = blank_y + flap_depth
    panel_widths = [l, w, l, w, joint]
    x_positions = []
    x = blank_x
    for panel_width in panel_widths:
        x_positions.append(x)
        x += panel_width

    def rect(x, y, width, height, cls, extra=""):
        return f'<rect x="{x:.3f}" y="{y:.3f}" width="{width:.3f}" height="{height:.3f}" class="{cls}" {extra}/>'

    parts = [
        f'<svg class="corrugated-blank-svg" viewBox="0 0 {sheet_w:.3f} {sheet_h:.3f}" role="img" aria-label="FEFCO 0201 blank preview" xmlns="http://www.w3.org/2000/svg">',
        "<style>.sheet{fill:#f8fafc;stroke:#94a3b8;stroke-width:1}.blank{fill:#dcfce7;stroke:#15803d;stroke-width:1}.joint{fill:#bbf7d0;stroke:#15803d;stroke-width:1}.flap{fill:#dcfce7;stroke:#15803d;stroke-width:1}.fold{stroke:#64748b;stroke-width:1;stroke-dasharray:6 4}.cut{stroke:#15803d;stroke-width:1.3;fill:none}.margin{fill:#fff7ed;fill-opacity:.7}.label{font:12px sans-serif;fill:#334155}.scrap-label{font:11px sans-serif;fill:#9a3412}</style>",
        rect(0, 0, sheet_w, sheet_h, "sheet"),
        rect(blank_x, blank_y, blank_w, blank_h, "margin"),
    ]

    # Four body panels plus the manufacturer's joint.  The joint has body
    # material only; no flap rectangles are drawn over it.
    body_x = blank_x
    for index, panel_width in enumerate(panel_widths):
        cls = "joint" if index == 4 else "blank"
        parts.append(rect(body_x, body_y, panel_width, h, cls))
        if index < 4:
            parts.append(rect(body_x, blank_y, panel_width, flap_depth, "flap"))
            parts.append(rect(body_x, body_y + h, panel_width, flap_depth, "flap"))
        body_x += panel_width

    for fold_x in x_positions[1:]:
        parts.append(f'<line x1="{fold_x:.3f}" y1="{body_y:.3f}" x2="{fold_x:.3f}" y2="{body_y + h:.3f}" class="fold"/>')
    parts.append(f'<line x1="{blank_x:.3f}" y1="{body_y:.3f}" x2="{blank_x + blank_w:.3f}" y2="{body_y:.3f}" class="fold"/>')
    parts.append(f'<line x1="{blank_x:.3f}" y1="{body_y + h:.3f}" x2="{blank_x + blank_w:.3f}" y2="{body_y + h:.3f}" class="fold"/>')
    parts.append(f'<path d="M {blank_x} {blank_y} H {blank_x + blank_w} V {blank_y + blank_h} H {blank_x} Z" class="cut"/>')
    parts.append(f'<text x="{blank_x + 8:.3f}" y="{blank_y + 16:.3f}" class="label">FEFCO 0201 blank</text>')
    parts.append(f'<text x="{blank_x + blank_w - 100:.3f}" y="{blank_y + 16:.3f}" class="scrap-label">margin</text>')
    parts.append(f'<text x="{x_positions[4] + 4:.3f}" y="{body_y + h / 2:.3f}" class="label">joint</text>')
    parts.append("</svg>")
    return "".join(parts)


class Fefco0201GeometryProvider:
    """Preliminary orthogonal geometry for FEFCO 0201 regular slotted cases."""

    def calculate(self, inputs: BoxGeometryInput) -> BoxGeometryResult:
        values = (
            inputs.length_mm,
            inputs.width_mm,
            inputs.height_mm,
            inputs.joint_width_mm,
            inputs.sheet_margin_per_edge_mm,
        )
        if any(value is None for value in values):
            raise ValueError("All FEFCO 0201 geometry inputs are required.")
        if any(value <= 0 for value in values[:3]):
            raise ValueError("Box dimensions must be greater than zero.")
        if inputs.joint_width_mm < 0 or inputs.sheet_margin_per_edge_mm < 0:
            raise ValueError("Joint and sheet margin cannot be negative.")

        blank_length = 2 * (inputs.length_mm + inputs.width_mm) + inputs.joint_width_mm
        blank_width = inputs.height_mm + inputs.width_mm
        blank_area = _m2(blank_length * blank_width)
        body_panel_area = _m2(2 * (inputs.length_mm + inputs.width_mm) * inputs.height_mm)
        flap_area = _m2(2 * inputs.width_mm * (inputs.length_mm + inputs.width_mm))
        joint_body_area = _m2(inputs.joint_width_mm * inputs.height_mm)
        effective_area = body_panel_area + flap_area + joint_body_area

        sheet_length = blank_length + 2 * inputs.sheet_margin_per_edge_mm
        sheet_width = blank_width + 2 * inputs.sheet_margin_per_edge_mm
        sheet_area = _m2(sheet_length * sheet_width)
        void_area = blank_area - effective_area
        margin_area = sheet_area - blank_area
        scrap_area = sheet_area - effective_area
        if effective_area > sheet_area:
            raise ValueError("Effective area cannot exceed production-sheet area.")
        if void_area < 0 or margin_area < 0 or scrap_area < 0:
            raise ValueError("Calculated geometric scrap cannot be negative.")

        utilization = (effective_area / sheet_area * Decimal("100")) if sheet_area else Decimal("0")
        scrap_percent = (scrap_area / sheet_area * Decimal("100")) if sheet_area else Decimal("0")
        provisional = BoxGeometryResult(
            blank_length_mm=blank_length,
            blank_width_mm=blank_width,
            blank_bounding_area_m2=blank_area,
            production_sheet_length_mm=sheet_length,
            production_sheet_width_mm=sheet_width,
            production_sheet_area_m2=sheet_area,
            effective_box_area_m2=effective_area,
            blank_void_area_m2=void_area,
            sheet_margin_area_m2=margin_area,
            total_scrap_area_m2=scrap_area,
            material_utilization_percent=utilization,
            scrap_percent=scrap_percent,
            body_panel_area_m2=body_panel_area,
            flap_area_m2=flap_area,
            joint_body_area_m2=joint_body_area,
            preview_svg="",
        )
        return BoxGeometryResult(
            **{
                **provisional.__dict__,
                "preview_svg": render_fefco_0201_svg(provisional, inputs),
            }
        )
