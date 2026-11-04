# Geometry-first Container Advanced parameters

Verified on 2026-11-04 against `production` at `4e667d4`, with the implementation
in the working tree. The supplied HTML was used as a visual reference; its
demonstration calculations were not copied. This task supersedes the previous
rule that catalogue properties could not be overridden for an analysis.

## Effective-property contract

| Value | Resolution, in order |
|---|---|
| Caliper / grammage, independently | Explicit scoped analysis override; SKU property; linked construction; eligible C-reference assumption; unavailable |
| Carton tare | Explicit scoped analysis override; actual SKU `part_weight` converted kg to g; existing eligible FEFCO 0201 estimate using effective grammage; unavailable |
| Product weight | Explicit scoped analysis override; catalogue weight converted kg to g; unavailable |
| Payload | Explicit scoped analysis override; existing supported catalogue payload attribute, if present; unavailable |

The agreed reference is the existing active `FEFCO_C_175_140_175` construction:
4.08 mm and 560.2 g/m² (approximately 0.161 in and 114.7 lb/MSF). Automatic
Design defaults and missing eligible catalogue properties are labelled
**Reference assumption**. Resulting tare estimates say **Estimated from assumed
material data**. Explicit board selection identifies the construction instead.
An analysis board selection can fill the construction baseline; measured SKU
properties still take priority over that baseline.

Catalogue assumptions require a confirmed corrugated `BOX` / `0201` carton;
obvious plastic, wood and metal descriptions are excluded. Actual external
dimensions remain authoritative. Caliper affects derived external dimensions,
but does not determine grammage or tare. Changing grammage preserves actual SKU
tare unless tare itself is overridden. Existing geometry, material-area,
packing and ranking services remain authoritative.

## UI and state

| Surface | Primary controls | Advanced controls |
|---|---|---|
| Design | Product geometry/source, desired quantity, existing viewer/rotations; Generate Designs | Product mass, shape and allowances; container material and weights |
| Optimal / Top 5 | Existing product and catalogue selection; Find Top 5 and candidate rows | Same shared controls, scoped to the selected candidate |
| Single manual | Product and container geometry; Run Analysis | Same optional controls |
| Single catalogue | Catalogue, selected item identification/dimensions; Run Analysis | Editable effective SKU properties and independent source restoration |
| Packaging Flow | The same prefixed partials and mode controls | Independent state and units for each step; inherited product mass remains read-only |

Product uses the existing dimensional-allowance Advanced component. Container
uses the same header/toggle pattern after the primary action, with compact
caliper/grammage, board, and tare/payload rows. Both start collapsed, retain
enabled inputs while collapsed, preserve their open state after calculation,
and expand for relevant validation errors. Single retains its capacity-based
quantity semantics; Optimal catalogue quantity retains its existing catalogue
contract. Design quantity is accessible for catalogue products as well.

Override flags, display-unit tokens, and `manual` / `catalogue:<id>` targets are
stored as JSON-safe form/session scalars. Same-item reruns retain overrides;
switching packaging or product clears the old item's scope. Each Top 5 row
resolves independently. **Restore source** appears only for an overridden
property and resets that field alone. Canonical metadata and the existing unit
selector preserve physical values through metric/imperial switches.

Editing calculated inputs shows a stale-result notice and disables result
acceptance and PDF actions, including Flow's report link. Recalculation
restores those actions. The Flow accept action also recalculates submitted
Container fields, protecting acceptance when client-side disabling is bypassed.

## Accepted workflow and reports

The versioned `effective_specification` stores original product, packaging and
construction IDs; effective internal/external dimensions; caliper/grammage and
baseline/override provenance; product, net, tare and gross mass; payload; weight
status; and packed quantity. No catalogue model instances enter session data.
Palletization receives effective external dimensions and complete carton mass.
Pallet and transport outputs preserve the snapshot as
`upstream_packaging_specification` and retain the original container ID without
reconstructing the carton from catalogue defaults. Changes to an accepted
specification clear acceptance and invalidate downstream results.

Only complete gross mass populates authoritative `weight_kg`. The accepted
snapshot retains the adapter's upstream estimation/completeness status.
`gross_known`,
`gross_estimated`, `net_only` and `unknown` remain distinct. A net-only value is
never passed as verified gross mass. The compact Result still shows quantity,
efficiency and total/contents weight; no separate Carton weight card was added.
Detailed analysis and standalone/Flow PDFs use effective values and sources.
Single/Design PDFs use three columns so all provenance rows fit with the
existing visualization and product image.

## Changed files

- `packagingapp/forms.py` — hidden analysis scope/override/open-state fields.
- `packagingapp/tools/container/state.py`, `serializers.py` — defaults, scoped
  overrides, legacy compatibility and JSON-safe storage.
- `packagingapp/tools/container/service.py` — authoritative effective-property
  resolution, mass precedence, provenance and accepted snapshot.
- `packagingapp/tools/container/presenter.py` — shared Advanced input/source
  contract for standalone and Flow.
- `packagingapp/tools/container/carton_tare.py` — propagate effective metadata
  through the existing mass adapter; FEFCO calculation unchanged.
- `packagingapp/tools/container/assistant.py`, `assistant_actions.py` — effective
  product weight and override-aware assistant state/fingerprints.
- `packagingapp/views/container_selection.py`, `full_packaging.py` — shared
  hydration, validation, export inputs, acceptance and downstream propagation.
- `packagingapp/templates/shared/_product_dimensional_allowance.html` — extend
  the existing Advanced component while retaining Bag compatibility.
- `packagingapp/templates/container_selection_tool/container_selection_wrapper.html`.
- Container partials under
  `packagingapp/templates/container_selection_tool/partials/`:
  `_container_selection_product_section.html`,
  `_container_selection_product_advanced_fields.html` (new),
  `_container_selection_container_section.html`,
  `_container_selection_advanced_section.html` (new),
  `_container_selection_property_source.html` (new),
  `_container_selection_result_section.html`,
  `_container_selection_design_result.html`, `_container_selection_scripts.html`.
- `packagingapp/templates/full_packaging/full_packaging_mode.html` — shared
  Advanced context and stale-export hook.
- `packagingapp/tools/container/export.py`,
  `packagingapp/tools/full_packaging/export.py` — effective report provenance
  and Single/Design PDF layout.
- `packagingapp/tests/test_container_geometry_first.py` (new) — 18 focused
  tests covering defaults, read-only overrides, scope, units, weights, views,
  validation, accepted snapshots/invalidation, acceptance and PDF values.
- `docs/domain/container-selection-logic.md`,
  `docs/architecture/packaging-flow.md`, this report — updated contracts.

Pre-existing mosaic/palletization work is outside this change and was preserved.
No models or migrations changed.

## Verification

- **240 tests passed** in the final focused Django run: geometry-first,
  material properties, corrugated selection/strength, carton tare, external
  dimensions, Container/Bag units, assistant context, Flow chain optimizer and
  case, product allowances/shapes, catalogue units, unit contracts, and unit
  presentation modules. Reproducible PowerShell command below. Isolated SQLite test database;
  system checks found no issues.
- **21 tests passed** in the final run from the legacy `packagingapp/tests.py` catalogue rights,
  row editing/deletion, Multi-product Container Three.js and scroll-preservation
  classes, loaded with `importlib` and Django's `DiscoverRunner` because the
  repository also contains a `packagingapp/tests/` package.
- **20 browser checks passed**, with zero JavaScript errors: reference/mockup
  comparison, collapsed/enabled inputs, independent overrides, repeated unit
  switches, preserved state, source restoration, stale results/actions,
  390 px mobile overflow, editable catalogue values, actual/manual tare,
  Top 5 isolation, imperial reference precision, net-only results, repeated
  Flow prefixes/unique IDs, Flow export/accept invalidation and recovery, and
  catalogue-product Design quantity.
- Generated Single and Design PDFs (one page each) and a Flow PDF (two pages)
  using the real shared builders and isolated fixtures. Poppler rendering and
  visual inspection confirmed readable tables and effective provenance. An
  oversized nested-table export failure found during verification was fixed
  by the three-column Single/Design layout.
- Catalogue/product `save()` was forbidden during analysis in regression
  tests; original caliper, grammage, product mass and actual tare were checked
  unchanged. Accepted/pending snapshots were verified with `json.dumps`.
- Shared consumers assessed: standalone, Flow, public SEO calculator (same
  wrapper/service), Multi-product Container (existing capacity/ranking and
  actual-SKU metadata contract), shared Bag allowances, reports, units,
  catalogue selection, Three.js and serialization.
- `git diff --check` passed. Implementation verification changed no packing
  engine, global theme, database schema or production data. Commit/push was
  subsequently authorized explicitly by the user as a release follow-up.
- Release verification also passed all 240 focused tests against an isolated
  copy of the staged tree, excluding the unrelated mosaic/palletization work.

```powershell
$env:DEBUG = 'True'
$env:DATABASE_URL = 'sqlite:///C:/PackagingEngineering/tmp/geometry-first-tests.sqlite3'
$tests = @(
  'container_geometry_first', 'container_material_properties',
  'corrugated_material_selection', 'container_carton_tare',
  'corrugated_material_strength', 'container_external_dimensions',
  'container_bag_unit_rollout', 'container_assistant_context',
  'full_packaging_chain_optimizer', 'full_packaging_case',
  'product_dimensional_allowance', 'product_shape_visualization',
  'catalogue_unit_integration', 'unit_contracts', 'task6_unit_presentation'
)
.venv\Scripts\python.exe manage.py test ($tests | ForEach-Object { "packagingapp.tests.test_$_" })
```

## Limits

No known unresolved acceptance failures remain. The C-reference fallback
requires its existing active construction record; absent source data stays
unavailable. Unknown carton styles do not gain an RSC estimate. The catalogue
currently has no dedicated payload field, so payload source fallback only uses
supported attributes when available. Multi-product Container retains its
existing capacity-oriented UI and does not gain a separate Advanced form.
Verification used local isolated fixtures and did not exercise production data
or a hosted deployment.
