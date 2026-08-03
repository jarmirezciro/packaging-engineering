# Corrugated Material & Strength — Luna handoff

## Implementation summary

The standalone `/corrugated-material-strength/` tool is implemented on `pre-production`. It provides an Admin-managed corrugated board catalogue, nine seeded constructions, FEFCO 0201 geometry, material and geometric scrap calculations, existing-pallet/manual pallet loading, static bottom-box load, preliminary BCT, McKee strength screening, CO₂ screening, a backend-generated SVG blank preview, JSON-safe contracts, and a ReportLab PDF report.

## Files created

- `packagingapp/migrations/0011_corrugated_board_construction.py`
- `packagingapp/tools/corrugated_material_strength/__init__.py`
- `packagingapp/tools/corrugated_material_strength/constants.py`
- `packagingapp/tools/corrugated_material_strength/flute_profiles.py`
- `packagingapp/tools/corrugated_material_strength/geometry.py`
- `packagingapp/tools/corrugated_material_strength/material.py`
- `packagingapp/tools/corrugated_material_strength/pallet.py`
- `packagingapp/tools/corrugated_material_strength/strength.py`
- `packagingapp/tools/corrugated_material_strength/carbon.py`
- `packagingapp/tools/corrugated_material_strength/serializers.py`
- `packagingapp/tools/corrugated_material_strength/contracts.py`
- `packagingapp/tools/corrugated_material_strength/service.py`
- `packagingapp/tools/corrugated_material_strength/export.py`
- `packagingapp/views/corrugated_material_strength.py`
- `packagingapp/templates/corrugated_material_strength/corrugated_material_strength_tool.html`
- `packagingapp/templates/corrugated_material_strength/partials/_box_product_inputs.html`
- `packagingapp/templates/corrugated_material_strength/partials/_pallet_inputs.html`
- `packagingapp/templates/corrugated_material_strength/partials/_board_inputs.html`
- `packagingapp/templates/corrugated_material_strength/partials/_distribution_inputs.html`
- `packagingapp/templates/corrugated_material_strength/partials/_carbon_inputs.html`
- `packagingapp/templates/corrugated_material_strength/partials/_corrugated_results.html`
- `packagingapp/templates/corrugated_material_strength/partials/_result_card.html`
- `packagingapp/templates/corrugated_material_strength/partials/_fefco_0201_preview.html`
- `packagingapp/templates/corrugated_material_strength/partials/_material_results.html`
- `packagingapp/templates/corrugated_material_strength/partials/_pallet_results.html`
- `packagingapp/templates/corrugated_material_strength/partials/_strength_results.html`
- `packagingapp/templates/corrugated_material_strength/partials/_carbon_results.html`
- `packagingapp/templates/corrugated_material_strength/partials/_calculation_explanation.html`
- `static/js/corrugated_material_strength.js`
- `packagingapp/tests/test_corrugated_material_strength.py`
- `docs/domain/corrugated-material-strength.md`
- `docs/handoffs/corrugated-material-strength-luna-handoff.md`

## Files modified

- `packagingapp/models.py` — `CorrugatedBoardConstruction` model and validation.
- `packagingapp/admin.py` — Admin registration, fieldsets, filters, search and readonly calculated fields.
- `packagingapp/forms.py` — standalone calculation form.
- `packagingapp/urls.py` — standalone and PDF routes.
- `packagingapp/templates/base.html` — Advanced Tools navigation link.

## Architecture and formulas

- Geometry: `tools/corrugated_material_strength/geometry.py`.
- Material mass: `material.py`.
- Pallet adapter: `pallet.py`; existing Palletization engine was not changed.
- Required BCT and McKee: `strength.py`.
- CO₂: `carbon.py`.
- Orchestration: `service.py`.
- Prefix-safe UI: `contracts.py`.
- JSON-safe session/result serialization: `serializers.py`.
- PDF report: `export.py`.

## Migration and seeds

Migration: `0011_corrugated_board_construction`.

Seed codes: `GEN_E_125_90_125`, `GEN_E_150_100_150`, `GEN_B_125_100_125`, `GEN_B_150_120_150`, `GEN_C_150_120_150`, `FEFCO_C_175_140_175`, `GEN_A_175_140_175`, `GEN_EB_150_100_125_120_150`, and `GEN_BC_175_120_150_140_175`.

Every seed has null ECT, null actual caliper and null measured BCT. The FEFCO C reference stores exact calculated grammage 560.20 g/m²; display may round it to 560 g/m².

## Verification

Baseline before edits:

- `manage.py check` — passed.
- Explicit existing suite of 43 tests — passed. The app-wide `manage.py test packagingapp` label remains affected by the pre-existing `packagingapp.py` versus `packagingapp/tests/` module-name collision.

After implementation:

- `manage.py check` — passed.
- `manage.py makemigrations packagingapp --check --dry-run` — no changes detected.
- `manage.py test packagingapp.tests.test_corrugated_material_strength --noinput` — 11 tests passed.

The focused benchmark uses the exact seeded 560.20 g/m² value. Its geometry is blank 1440 × 500 mm, sheet 1480 × 540 mm, effective area 0.7080 m², utilization 88.5886%, 8 boxes/layer, 5 layers and 40 boxes/pallet. McKee with ECT 4.0 kN/m and 3.6 mm caliper is approximately 1586.695 N.

## Deliberate deviations and limitations

- Packaging Flow was not changed, as required. The standalone shared contract and partials are prefix-ready but have no workflow consumer yet.
- The current repository has no migrations for its local pallet catalogue sample rows; the view reuses existing `PackagingMaterial` pallet rows when present and falls back to the specified manual Euro-pallet dimensions.
- PDF export uses a compact ReportLab vector equivalent of the backend SVG preview because the repository’s existing PDF stack does not include an SVG embedding dependency.
- No additional ECT, caliper, commercial supplier grade or CO₂ factor was searched for or invented.
- No customer material-management UI, cost, price, supplier proposal or certification workflow was added.

## Questions and suggested Sol refinement areas

- Review exact FEFCO 0201 slot geometry and converter dimensional allowances.
- Review actual production-sheet-size constraints and future nesting providers.
- Consider additional strength models and supplier-specific measured data policy.
- Refine SVG linework, accessibility and result-card responsive layout.
- Review supplier-specific CO₂ factor governance and report presentation.
- Add a Packaging Flow adapter only after the standalone contract is accepted.

No undocumented shortcut should be treated as a supplier approval or certification path.
