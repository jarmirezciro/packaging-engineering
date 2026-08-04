# Corrugated Material & Strength

## Purpose

The standalone Corrugated Material & Strength tool provides preliminary engineering estimates for FEFCO 0201 regular slotted cases. It combines blank geometry, effective material area, geometric cutting scrap, board mass, pallet loading, a static bottom-box load, preliminary BCT, the metric McKee estimate when suitable strength data exist, and material-based CO₂ screening indicators.

The tool is intended to support early packaging-engineering comparisons and supplier discussions. It is not a certification, supplier approval, laboratory result, formal product carbon footprint, or distribution-test replacement.

## Scope and boundaries

Included in this version:

- FEFCO 0201 only;
- single-wall A, B, C and E and seeded EB/BC double-wall constructions;
- active constructions managed through Django Admin;
- one-time manual board properties and strength overrides;
- existing `PackagingMaterial` pallet catalogue records plus manual pallet dimensions;
- orthogonal column-aligned/interlocked preview with the same simplified load model;
- Light, Normal, Demanding and Custom distribution factors;
- backend-generated responsive SVG blank preview;
- JSON-safe calculation results and a prefix-safe UI contract for future workflow use;
- a report using the existing ReportLab convention.

Packaging Flow, customer-owned materials, supplier proposal comparison, price/cost, automatic nesting, production-sheet optimization, additional FEFCO styles, creep/humidity/vibration models and finite-element analysis are intentionally out of scope.

## Architecture

```text
Standalone view
      │
Shared UI contract (contracts.py)
      │
Shared form/result partials
      │
Calculation service (service.py)
      ├── Geometry provider (geometry.py)
      ├── Material engine (material.py)
      ├── Pallet adapter (pallet.py)
      ├── Strength engine (strength.py)
      └── Carbon engine (carbon.py)
      │
Admin-managed board catalogue (CorrugatedBoardConstruction)
```

The future consumer is deliberately not implemented:

```text
Packaging Flow step
      │
Same shared UI contract
      │
Same partials
      │
Same calculation service
```

`contracts.py` exposes `build_shared_corrugated_material_ui_contract()` and prefix helpers. Standalone names are unprefixed; a future workflow step using prefix `3` receives names and IDs such as `3_box_length_mm`. The current standalone view stores only the serialized result and inputs in the session.

## Board model and Admin workflow

`CorrugatedBoardConstruction` is the only board catalogue table. It is registered in Django Admin and has no customer-facing CRUD surface. `code` is unique and stable. `source_type` must classify every record as one of `OFFICIAL_REFERENCE`, `ILLUSTRATIVE_DERIVED`, `ADMIN_ENTERED`, `SUPPLIER_DOCUMENTED` or `COMPANY_MEASURED`.

For double wall, `flute_1` is the first/inner medium in the selected design order and `flute_2` is the second medium. Their concatenation is displayed as `EB` or `BC`.

Administrators enter layer grammages, take-up factors and glue consumption. `combined_grammage_g_m2` is readonly in Admin and is recalculated from the component values on save. The model validates single-wall and double-wall layer requirements, positive engineering values, and CO₂ metadata whenever a factor exists. `nominal_flute_height_mm` is also readonly and derived from the version-controlled flute profiles.

### Combined grammage

Single wall:

```text
G = outer liner + medium 1 × TUF 1 + inner liner + 2 × glue 1
```

Double wall:

```text
G = outer liner + medium 1 × TUF 1 + middle liner
    + medium 2 × TUF 2 + inner liner
    + 2 × glue 1 + 2 × glue 2
```

The model preserves decimal values internally and only formats them for display. The nine migration seeds are keyed with `update_or_create()` and remain Admin-editable.

## Seed-data provenance and strength policy

The version-controlled profiles encode the supplied indicative A/B/C/E flute heights, flute counts, take-up ranges and glue ranges. A, B and E defaults use the supplied range midpoints; C uses the supplied worked-example values. These are calculation aids, not commercial specifications.

The seeded records are:

- `GEN_E_125_90_125` — 377.25 g/m²;
- `GEN_E_150_100_150` — 440.00 g/m²;
- `GEN_B_125_100_125` — 394.00 g/m²;
- `GEN_B_150_120_150` — 470.50 g/m²;
- `GEN_C_150_120_150` — 481.60 g/m²;
- `FEFCO_C_175_140_175` — 560.20 g/m², the supplied FEFCO C-flute reference;
- `GEN_A_175_140_175` — 573.00 g/m²;
- `GEN_EB_150_100_125_120_150` — 735.50 g/m²;
- `GEN_BC_175_120_150_140_175` — 880.70 g/m².

All research-derived seeds intentionally have null ECT, null actual caliper and null measured BCT. The tool does not infer ECT from grammage or caliper from nominal flute height. If a generic record lacks strength data, geometry, material and CO₂ results remain available while the strength panel states that ECT and actual finished-board caliper must be entered or a material containing strength data selected.

## External dimensions and pallet basis

The entered length, width and height are internal dimensions. They remain the
product-fit definition and the basis for the existing preliminary FEFCO 0201
blank/effective-area formulas. A separate resolver calculates estimated
external dimensions only when an effective finished-board caliper is available:

```text
L_external = L_internal + 2 x caliper
W_external = W_internal + 2 x caliper
H_external = H_internal + 2 x caliper
```

The method code is `CALIPER_TWO_SIDES_ESTIMATE`. The caliper priority is
one-time actual override, construction caliper with its source metadata, then
reference-grade target caliper. Nominal flute height is never used as finished
board caliper. Without caliper, the tool returns material, geometry and CO2
results but marks external dimensions and palletization unavailable; it never
silently falls back to internal dimensions.

The architecture boundary is:

```text
Internal dimensions
        |
        +-- FEFCO geometry and material
        |
Effective caliper resolver
        |
        +-- External dimensions
                    |
                    +-- Pallet calculation
```

Pallet footprint, boxes per layer, layer count, palletized height and boxes per
pallet use the resolved external dimensions. The existing standalone
Palletization engine is not modified.

## Reference ECT grades

`CorrugatedECTReferenceGrade` is a separate Admin-managed table. It contains
28 seeded screening categories across A, B, C, E, EB and BC flute families.
The metric value is calculated from the stored imperial category using:

```text
ECT_kN/m = ECT_lb/in x 0.175126835
```

Reference ECT is not a measured result for a selected paper construction. The
calculator filters active grades by flute family in the browser and validates
the family and wall type again on the server. Supplier/measured and one-time
values remain higher priority than a reference grade. Reference caliper is
only populated where the task provides a defensible target; E-flute, EB and
BC 61 ECT records intentionally remain without target caliper.

Strength data priority is:

```text
Measured BCT override
      |
      +-- Highest priority
Construction ECT + caliper
      |
Reference ECT grade + effective caliper
      |
      +-- Screening fallback
```

When reference ECT or caliper contributes to McKee, the result is labelled as
an illustrative screening estimate. The current McKee perimeter intentionally
preserves the existing internal-dimension convention:

```text
perimeter_cm = 2 x (L_internal + W_internal) / 10
```

A future methodology review may revisit that convention.

## FEFCO 0201 geometry

Version 1 uses entered internal dimensions directly and does not apply converter-specific dimensional allowances or board-thickness allowances.

```text
Blank length       = 2 × (L + W) + joint
Blank width        = H + W
Effective area     = 2 × (L + W) × H + 2 × W × (L + W) + joint × H
Sheet length       = blank length + 2 × margin
Sheet width        = blank width + 2 × margin
Blank void area    = blank area − effective area
Sheet-margin area  = sheet area − blank area
Total scrap area   = sheet area − effective area
Utilization        = effective area / sheet area × 100
```

The corrected effective-area formula includes both complete flap sets. Slot-cut width is treated as negligible. The SVG is generated on the server from these geometry results and shows the sheet boundary, blank boundary, four body panels, eight flaps, joint, fold lines, cut lines and margin/scrap areas. Browser JavaScript only toggles visibility and hydrates metadata; it does not recalculate dimensions.

## Pallet calculation

The corrugated adapter supplies external length, width and height to the
calculation and records `dimension_basis = EXTERNAL` in the result. It does
not modify the existing standalone Palletization engine.

The dedicated adapter reuses existing pallet catalogue records and does not modify the existing Palletization engine. It evaluates both orthogonal footprint orientations, selects the larger count, and uses `L along pallet length` as the deterministic tie result. Layers are based on `maximum palletized height − pallet height`; reported palletized height includes the pallet.

For one pallet:

```text
Supported mass = (layers − 1) × gross packed-box mass
Static load    = supported mass in kg × 9.80665 m/s²
```

Vertically stacked pallets use the supplied evenly distributed upper-load approximation. Interlocked stacking keeps the same simplified supported-mass calculation and exposes a warning that real compression performance may be reduced.

## Strength calculation

Required BCT is:

```text
Required BCT = static bottom-box load × distribution factor
```

The factors are KolliPack screening assumptions: Light 2.0, Normal 3.0, Demanding 5.0, or a positive custom value. They are not universal ASTM, FEFCO or ISO values.

The metric McKee calculation is implemented only for FEFCO 0201 regular slotted cases:

```text
BCT_kgf = 1.82 × ECT × 1.0194 × caliper^0.508 × perimeter^0.492
perimeter_cm = 2 × (L + W) / 10
BCT_N = BCT_kgf × 9.80665
```

Inputs are ECT in kN/m, actual or reference finished-board caliper in mm, and
the existing internal-dimension perimeter in cm. The priority is measured BCT
override, construction measured BCT, a complete one-time ECT/caliper pair, a
complete construction ECT/caliper pair, then a selected reference ECT grade
with an effective caliper. A single override is never combined with a
catalogue value. Reference-based McKee results carry a warning and are not
called measured, supplier documented, verified, certified or guaranteed.

## CO₂ screening

Seed records use the supplied generic 0.491 kg CO₂e/kg screening factor with the supplied cradle-to-grave screening, Europe and required-sheet-mass metadata. The service applies the selected factor to finished-box mass, geometric scrap mass and required production-sheet mass, then scales the sheet indicator by boxes per pallet and requested production quantity. The box plus scrap indicators are checked against the sheet indicator within the calculation path.

Results are labelled `Material-based CO₂ screening estimate`. No process waste, startup loss, printing rejects, supplier price or cost is included.

The shared result contract exposes JSON-safe internal/external dimensions and
reference-grade metadata for a future Packaging Flow adapter. Packaging Flow is
not implemented in this refinement.

## Known limitations and future extensions

- FEFCO 0201 geometry is preliminary and does not model slots, converter allowances, board thickness or production-sheet nesting.
- The SVG is a clean orthogonal preview, not a die-line approval drawing.
- The nine generic board-construction seeds retain null ECT, null actual caliper and null measured BCT; reference ECT grades remain separate.
- Reference-caliper gaps are intentional for E-flute, EB and BC 61 ECT; supplier or measured caliper is required for those cases.
- McKee is a screening estimate and does not model humidity, creep, vibration, edge damage or distribution-test effects.
- Pallet loading is orthogonal and does not reduce compression capacity for interlock.
- PDF export uses a small ReportLab vector equivalent of the browser preview rather than embedding the browser SVG directly.
- A future extension can add complex FEFCO geometry providers, supplier-specific strength/CO₂ records, and a Packaging Flow adapter without moving formulas into a view or browser script.
