# Container material properties — verification record

Verified on 4 November 2026 against the checked-out `production` branch
(`5754ef9`). The checkout already contained unrelated Palletization/Mosaic work;
those files were preserved. No packing engine, orientation rule or Top 5 sort
was changed by this task.

## Implemented contract

- Manual Single/Design: independent Caliper and Grammage override/reset flags;
  reference values resolve from the selected construction. New manual Design
  selects `FEFCO_C_175_140_175` (KL175/RF140/TL175), 4.08 mm and 560.2 g/m².
- Catalogue: explicit SKU caliper/grammage precede the SKU's own construction.
  Complete explicit external dimensions remain authoritative. Manual inputs and
  the global board selector cannot fill missing SKU properties.
- Tare: actual catalogue kg weight converted once to grams, otherwise an estimate
  only with confirmed BOX/FEFCO 0201 geometry and valid grammage/dimensions,
  otherwise `None`. Manual authoritative tare precedes the same shared estimate.
  All estimates reuse `calculate_rsc_carton_tare()` and its established geometry.
- Only complete gross mass populates Flow `weight_kg`/`weight_g`. Net mass and tare
  remain separate, with `gross_known`, `gross_estimated`, `net_only` or `unknown`
  status. Incomplete downstream mass leaves geometric calculations available
  and explicitly marks weight/payload checks unavailable.
- Caliper uses the existing length selector; grammage uses g/m² or lb/MSF.
  Rounded automatic inputs never replace canonical material properties.
- Primary Result has no separate Carton weight card. Detailed analysis and PDFs
  carry the weight breakdown, Caliper, Grammage and provenance. Contents-only
  results say Contents weight and keep gross weight unavailable.

## Automated checks

201 relevant tests passed: the 178-test focused suite below plus 23 legacy
catalogue, multi-product rendering and scroll tests. Subsequent focused checks
also passed after the final precision and JavaScript guards: 29 catalogue/material
tests, 15 material/precision tests, and the browser smoke test.

All Django test commands used `.venv\Scripts\python.exe`, `DEBUG=True`, and an
explicit isolated SQLite `DATABASE_URL` under `tmp/`. Django created/destroyed its
own test database; the existing development/production data was not migrated.

Focused command:

```powershell
.venv\Scripts\python.exe manage.py test packagingapp.tests.test_container_material_properties packagingapp.tests.test_container_carton_tare packagingapp.tests.test_corrugated_material_selection packagingapp.tests.test_container_external_dimensions packagingapp.tests.test_corrugated_material_strength packagingapp.tests.test_unit_contracts packagingapp.tests.test_task6_unit_presentation packagingapp.tests.test_full_packaging_chain_optimizer packagingapp.tests.test_full_packaging_case packagingapp.tests.test_container_assistant_context packagingapp.tests.test_container_bag_unit_rollout packagingapp.tests.test_catalogue_unit_integration --noinput --verbosity 1
```

The 23 legacy tests were loaded explicitly from `packagingapp/tests.py` using
Django `DiscoverRunner` because the repository also has a `packagingapp/tests/`
package. Classes: `CatalogueAdministrationRightsTests`,
`PackagingMaterialPictureTests`, `CatalogueRowDeletionTests`,
`CatalogueRowEditingTests`, `MultiProductContainerThreeJsTests`, and
`ToolScrollPreservationTests`. All passed.

Additional commands:

```powershell
.venv\Scripts\python.exe manage.py check
.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.venv\Scripts\python.exe manage.py sqlmigrate packagingapp 0018
```

Results: no Django issues, no missing migrations, and additive nullable SQL for
all three new fields. Fresh isolated test databases applied the full migration
chain successfully. Existing rows need no backfill. Catalogue CRUD and metric
Excel export/import round trips pass, including old spreadsheets without new
columns and confirmed non-BOX exclusion from RSC tare estimates.

## Browser and PDF checks

A temporary local Django server and Playwright/Edge checked desktop (1500 px)
and mobile (390 px): construction changes, independent overrides, independent
resets, metric/imperial conversion, Design POST/GET, Design-to-Single switching,
contents-only Single results, repeated Flow prefixes and mobile overflow.
The final smoke run passed with zero JavaScript errors. An empty Flow page also
loads safely before any Container step exists.

Rendered and visually inspected metric Single, imperial Design, and imperial
Top 5 PDFs (including five ranking rows). All fit one page in the tested
fixtures. Fixed the Top 5 context-table width so it does not overlap the
visualization column. Report tests check engineering values, provenance and
contents-only labels. QA fixtures without a browser snapshot intentionally use
the existing missing-snapshot message; the normal Three.js snapshot pipeline
was preserved. Browser results retained the clean Three.js scene.

Consumer assessment: standalone and Flow use the same form/service/partials;
public Container calculator consumes them as well; Multi-product Container's
catalogue-driven internal-dimension capacity/ranking surface and actual-weight
metadata remain unchanged. Existing assistant tests pass, and accepted Caliper
proposals set the manual override flag. Sessions and candidate payloads pass
JSON serialization checks.

## Pre-push verification

After the explicit commit/push request, the 178-test focused suite was rerun
successfully against an isolated export of the staged production snapshot.
This excluded all pre-existing uncommitted Palletization/Mosaic edits. The
remote production branch matched the local base before committing.

## Files changed by this task

- `docs/UNIT_SYSTEM_AUDIT.md`
- `docs/domain/container-selection-logic.md`
- `docs/engineering/container-material-properties-verification.md`
- `packagingapp/forms.py`
- `packagingapp/migrations/0018_packagingmaterial_corrugated_properties.py`
- `packagingapp/models.py`
- `packagingapp/services/excel_import.py`
- `packagingapp/templates/container_selection_tool/container_selection_wrapper.html`
- `packagingapp/templates/container_selection_tool/partials/_container_selection_container_section.html`
- `packagingapp/templates/container_selection_tool/partials/_container_selection_design_result.html`
- `packagingapp/templates/container_selection_tool/partials/_container_selection_result_section.html`
- `packagingapp/templates/container_selection_tool/partials/_container_selection_scripts.html`
- `packagingapp/templates/packaging_catalogue/_material_form_fields.html`
- `packagingapp/templates/packaging_catalogue/catalogue_detail.html`
- `packagingapp/templates/packaging_catalogue/upload_excel.html`
- `packagingapp/tests/test_catalogue_unit_integration.py`
- `packagingapp/tests/test_container_external_dimensions.py`
- `packagingapp/tests/test_container_material_properties.py`
- `packagingapp/tools/container/assistant.py`
- `packagingapp/tools/container/assistant_actions.py`
- `packagingapp/tools/container/carton_tare.py`
- `packagingapp/tools/container/corrugated_material.py`
- `packagingapp/tools/container/dimensions.py`
- `packagingapp/tools/container/export.py`
- `packagingapp/tools/container/presenter.py`
- `packagingapp/tools/container/serializers.py`
- `packagingapp/tools/container/service.py`
- `packagingapp/tools/container/state.py`
- `packagingapp/tools/full_packaging/chain_optimizer.py`
- `packagingapp/tools/full_packaging/export.py`
- `packagingapp/tools/full_packaging/presentation.py`
- `packagingapp/views/container_selection.py`
- `packagingapp/views/full_packaging.py`
- `packagingapp/views/packaging_catalogue.py`

## Remaining operational step

Migration `0018_packagingmaterial_corrugated_properties` must be applied through
the normal authorized release process before the updated app is used against
an existing database. At implementation verification, no real database migration,
commit, push, merge, Railway change or deployment had been performed. The later
explicit user request authorizes committing and pushing these changes to
`origin/production`; manual migrations and Railway operations remain outside
that request. Cartons without actual tare or sufficient
confirmed geometry/material data intentionally retain unavailable gross mass
and weight feasibility. Temporary test services were stopped after verification.
