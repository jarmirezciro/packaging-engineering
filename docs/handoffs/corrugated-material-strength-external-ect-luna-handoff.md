# Corrugated Material & Strength refinement - Luna handoff

## Scope delivered

The standalone corrugated tool now separates internal dimensions from an
estimated external-dimension result and uses the external result only for
corrugated-tool palletization. A separate Admin-managed reference ECT table is
available without changing the meaning or seed data of
`CorrugatedBoardConstruction`.

## Files created

- `packagingapp/migrations/0012_corrugated_ect_reference_grade.py`
- `packagingapp/tools/corrugated_material_strength/dimensions.py`
- `packagingapp/templates/corrugated_material_strength/partials/_dimensions_results.html`
- `docs/handoffs/corrugated-material-strength-external-ect-luna-handoff.md`

## Files modified

- `packagingapp/models.py` - `CorrugatedECTReferenceGrade` model.
- `packagingapp/admin.py` - reference-grade Admin registration and fieldsets.
- `packagingapp/forms.py` - reference-grade field and server-side compatibility validation.
- `packagingapp/views/corrugated_material_strength.py` - active grade loading, metadata and service resolution.
- `packagingapp/tools/corrugated_material_strength/contracts.py` and `serializers.py` - shared field/input contracts.
- `packagingapp/tools/corrugated_material_strength/service.py` - caliper resolution, external dimensions and partial results.
- `packagingapp/tools/corrugated_material_strength/pallet.py` and `carbon.py` - external-dimension basis and unavailable-pallet handling.
- `packagingapp/tools/corrugated_material_strength/strength.py` - reference priority and source metadata.
- `packagingapp/tools/corrugated_material_strength/export.py` - PDF dimensions, ECT and source sections.
- corrugated templates and `static/js/corrugated_material_strength.js` - reference-grade selection and result presentation.
- `packagingapp/tests/test_corrugated_material_strength.py` - updated and new benchmarks.
- `docs/domain/corrugated-material-strength.md` - domain and architecture rules.

## Reference-grade matrix

Migration `0012_corrugated_ect_reference_grade` seeds 28 records, all with
source type `INDUSTRY_REFERENCE` and source label
`FBA-hosted corrugated board strength reference table`.

| Flute family | Wall | ECT categories (lb/in) | Metric conversion (kN/m, stored to 9 decimals) |
| --- | --- | --- | --- |
| A | Single | 32, 40, 44, 55 | 5.604058720, 7.005073400, 7.705580740, 9.631975925 |
| B | Single | 32, 40, 44, 55 | 5.604058720, 7.005073400, 7.705580740, 9.631975925 |
| C | Single | 32, 40, 44, 55 | 5.604058720, 7.005073400, 7.705580740, 9.631975925 |
| E | Single | 32, 40, 44, 55 | 5.604058720, 7.005073400, 7.705580740, 9.631975925 |
| EB | Double | 42, 48, 51, 61, 71, 82 | 7.355327070, 8.406088080, 8.931468585, 10.682736935, 12.434005285, 14.360400470 |
| BC | Double | 42, 48, 51, 61, 71, 82 | 7.355327070, 8.406088080, 8.931468585, 10.682736935, 12.434005285, 14.360400470 |

The display rounds metric values to three decimals. The model recalculates
`ect_kn_m` from `ect_lb_in` on save using `0.175126835`.

## Reference-caliper matrix

| Flute family | 32 ECT | 40 ECT | 44 ECT | 55 ECT |
| --- | ---: | ---: | ---: | ---: |
| A | 5.15 mm | 5.31 mm | 5.46 mm | 5.72 mm |
| B | 3.10 mm | 3.26 mm | 3.41 mm | 3.67 mm |
| C | 4.08 mm | 4.23 mm | 4.38 mm | 4.64 mm |
| E | null | null | null | null |

| Double-wall family | 42 ECT | 48 ECT | 51 ECT | 61 ECT | 71 ECT | 82 ECT |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| EB | null | null | null | null | null | null |
| BC | 6.62 mm | 6.77 mm | 7.03 mm | null | 7.54 mm | 7.90 mm |

Records intentionally left without reference caliper are every E grade, every
EB grade, and `REF_BC_61`. No caliper is inferred from nominal flute height or
from adjacent grades.

## Calculation priorities

External dimensions use the first available caliper in this order:

1. One-time actual caliper override.
2. Construction caliper and its source metadata.
3. Reference-grade target caliper.

When available, the preliminary method is:

```text
L_external = L_internal + 2 x t
W_external = W_internal + 2 x t
H_external = H_internal + 2 x t
```

The method code is `CALIPER_TWO_SIDES_ESTIMATE`. If no caliper exists,
external dimensions, palletization, required BCT and strength margin are
unavailable; geometry, material, scrap and CO2 still render.

Strength priority remains measured BCT override, stored measured BCT, a
complete one-time ECT/caliper pair, a complete construction ECT/caliper pair,
then reference ECT with an effective caliper. Reference-driven McKee results
carry an explicit illustrative-screening warning. McKee continues to use the
internal-dimension perimeter convention.

## Updated benchmarks

The existing override benchmark (400 x 300 x 200 mm internal, ECT 4.0 kN/m,
caliper 3.6 mm, 1200 x 800 x 144 mm pallet, 1200 mm maximum) now produces:

- external box: 407.2 x 307.2 x 207.2 mm;
- 4 boxes/layer, 5 layers, 20 boxes/pallet;
- palletized height: 1180 mm;
- material mass, gross box mass, static load, required BCT, McKee BCT and strength margin unchanged from the prior 40-box benchmark;
- per-pallet material/CO2 totals scaled to 20 boxes.

The new `REF_C_44` benchmark produces external dimensions 408.76 x 308.76 x
208.76 mm, 4 boxes/layer, 5 layers, 20 boxes/pallet and 1187.80 mm palletized
height. ECT, caliper and BCT are marked reference-based.

## Verification

- `manage.py check` - passed.
- `manage.py test packagingapp.tests.test_corrugated_material_strength --noinput` - 16 tests passed.
- Node syntax check for `static/js/corrugated_material_strength.js` - passed.
- Python compilation checks for modified Python modules - passed.
- `git diff --check` - passed; only repository line-ending warnings were reported.

The nine existing board-construction seeds remain unchanged: all still have
null ECT, null actual caliper and null measured BCT. No SCT calculation was
implemented. Packaging Flow was not modified. The standalone Palletization
engine was not modified. No customer-facing grade-management UI was added;
Django Admin is the only reference-grade management surface.

## Sol review areas

- Confirm supplier directional outside gains and converter-specific allowances.
- Revisit whether McKee should eventually use an external perimeter.
- Research defensible E- and EB-flute target calipers and supplier metadata.
- Review reference-grade UX and future Packaging Flow integration.
- Consider additional FEFCO styles and supplier documentation fields.
