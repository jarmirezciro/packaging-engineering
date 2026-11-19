# Perimeter-Core Mosaic relevance calibration

## Scope and criteria

Work is based on the clean `production` checkout at
`b3915cf14bf1e30da3fb33346000ff75df21bf62`. The sole runtime change is in
`packagingapp/utils/packing_patterns/core.py`: an opt-in search-policy field
enabled by `PALLETIZATION_SEARCH_POLICY`, plus two area comparisons before
`_perimeter_core_mosaic_motif` is called.

For normalized carton sides `L>=S`, occupied area is `10*L*S`. Both conditions
must hold:

- occupied area is at least 90% of `(2*L+S)*(2*L)`, the motif contour;
- occupied area is at least 60% of the existing effective footprint, including
  permitted overhang.

Equality is eligible. These independent customer-relevance checks use constant
arithmetic and introduce no enumeration, placement-pair analysis, optimization,
dependency or search-limit changes. The geometric `L>=2*S` tolerance, motif
coordinates/orientation sequence, rotation/mirroring, collision checks,
interlock generation, ranking, deduplication and unit conversion are unchanged.
Container Selection leaves the new policy disabled. This is not a mechanical
stability claim or an exact-2:1 restriction.

## Before and after

All dimensions below are the existing `/regressions` presets. Percentages use
canonical converted dimensions and the engine's effective area.

| Case | Motif density | Floor coverage | Before Perimeter-Core | After |
| --- | ---: | ---: | --- | --- |
| Calibration 3 | 95.4064% | 82.4400% | 10/layer, 2 layers, 20 total | Identical |
| Calibration 4 | 100% | 66.6667% | 10/layer, 2 layers, 20 total | Identical |
| CapePack perimeter-core-10 | 95.4064% | 82.4400% | 10/layer, 2 layers, 20 total | Identical |
| Calibration 6 | 100% | 37.5000% | 10/layer, 2 layers, 20 total | Excluded |
| Calibration 7 | 55.5556% | 10.4167% | 10/layer, 10 layers, 100 total | Excluded |
| Calibration 8 | 45.4545% | 13.0208% | 10/layer, 10 layers, 100 total | Excluded |

The all-preset scan found three additional, intended exclusions:

| Preset | Motif density | Floor coverage | Removed Perimeter-Core alternative |
| --- | ---: | ---: | --- |
| tops-case-pack-8 | 95.3608% | 37.5227% | 10/layer, 6 layers, 60 total |
| north-american-splitrow | 96.3303% | 36.5570% | 10/layer, 6 layers, 60 total |
| brick-centre-filled | 100% | 55.5556% | 10/layer, 5 layers, 50 total |

Only these six presets change among all 29. Every non-Perimeter-Core row,
including ordered 2D/3D placements, interlock metadata, engineering metrics
and result order, compares equal. Every overall winner compares equal. The
other 23 complete result lists are identical. No replacement is constructed.
The original Case 3/4/CapePack layer and complete stack hashes match the
pre-edit capture, including the alternate layers and orientation order.

## Consumer assessment

| Consumer | Verification |
| --- | --- |
| Standalone and `/regressions` | All existing load/calculate/select/recalculate tests; explicit six-case family availability and table checks |
| Public calculator | Same tables as standalone; retained ten-carton results and alternate previews remain selectable |
| Packaging Flow | Same tables and selected serialized values; prefix-safe selection; reset preview state between independent test cases |
| Three.js / JS hydration | Both normal and alternate scene payloads for Cases 3/4/CapePack equal those driven by the locked original constructor, including ordered coordinates and orientations; existing bounds/count/unit assertions pass |
| PDF/report | Export-session analysis equals the exact selected row; existing Stage 2 report/scene and payload/PDF tests remain active |
| Catalogue | Existing shared normalization, catalogue-height and weight tests; no catalogue/form/selector changes |
| Container / Multi-product Container | New policy disabled; negative cases retain their original valid shared geometry, Stage 1 and Container regressions run |
| Multi-product Bag | No dependency on this family or Palletization policy |
| Sessions | No new state/schema fields; cross-surface sessions serialize with `allow_nan=False` |

No Three.js renderer, browser interaction, UI template or unit-conversion code
changed. Verification is automated scene/contract verification; no manual
browser visual inspection is claimed.

## Tests and commands

The pre-edit cumulative baseline passed **147 tests**, zero failures/skips,
in **113.101 seconds**. The final cumulative command uses the same modules
and includes seven new test methods:

```powershell
$env:DEBUG='True'
$env:DATABASE_URL='sqlite:///:memory:'
.\.venv\Scripts\python.exe manage.py test packagingapp.tests.test_shared_mosaic_patterns packagingapp.tests.test_shared_mosaic_stage1_baseline packagingapp.tests.test_palletization_stage2_baseline packagingapp.tests.test_nested_simple_lattice_patterns packagingapp.tests.test_pallet_splitrow packagingapp.tests.test_pallet_max_load packagingapp.tests.test_palletization_unit_ui packagingapp.tests.test_regressions.RegressionCompendiumTests packagingapp.tests.test_product_dimensional_allowance packagingapp.tests.test_container_geometry_first packagingapp.tests.test_full_packaging_case --noinput
.\.venv\Scripts\python.exe manage.py check
git diff --check
.\.venv\Scripts\python.exe -m packagingapp.tests.benchmark_perimeter_core_filter --repetitions 7
```

The focused seven-test development run passed all six new domain methods.
Its integration method initially found four subtest mismatches caused by a
previous case's alternate-preview selection persisting in the same Flow step.
The test now clears the selected key on a fresh analysis. The existing
delegation test uses a 1200x800 area for Perimeter-Core, replacing its 55.6%
square-area fixture with an eligible 83.3% fixture; other families keep their
original fixture. The shared-constructor parity test now passes the same
Palletization policy on both sides for this family, as it already did for
Hybrid. An intermediate cumulative run had precisely those two old
policy/fixture assumptions failing (154 tests, two failures, 108.904 seconds).
No production behavior was rewritten during correction.
No frozen historical artifact, fixture builder or historical assertion was
silently refreshed.

Supplementary checks ran **34 tests** against the reconstructed pre-filter
constructor and the current constructor: both passed with zero failures/skips,
in **0.333 / 0.295 seconds**. They cover catalogue/manual units, pallet height,
canonical presentation, capacity/full-service parity, occupied Flow footprint,
and selection preserving optimizer ranking. Their exact labels were:

```python
labels = (
    "packagingapp.test_pallet_height",
    "packagingapp.tests.test_unit_contracts.PalletizationResultCompatibilityTests",
    "packagingapp.tests.test_unit_contracts.PalletizationManualUnitBoundaryTests",
    "packagingapp.tests.test_unit_contracts.CatalogueBoundaryContractTests.test_packaging_catalogue_kg_becomes_grams_for_palletization",
    "packagingapp.tests.test_unit_contracts.CatalogueBoundaryContractTests.test_manual_and_catalogue_carton_weights_are_physically_equivalent",
    "packagingapp.tests.test_catalogue_unit_integration.CatalogueUnitViewTests.test_pallet_picker_uses_box_and_pallet_dimensions_with_shared_mass_state",
    "packagingapp.tests.test_full_packaging_chain_optimizer.CapacityOnlyEvaluationTests.test_pallet_capacity_and_full_service_select_the_same_numeric_row",
    "packagingapp.tests.test_full_packaging_chain_optimizer.CapacityOnlyEvaluationTests.test_pallet_capacity_uses_the_same_actual_footprint_as_normal_flow",
    "packagingapp.tests.test_full_packaging_chain_optimizer.ChainOptimizerViewTests.test_pallet_layout_selection_preserves_ranking",
    "packagingapp.tests.test_task6_unit_presentation.MajorToolResultPresentationTests.test_pallet_and_transport_presenters_do_not_change_canonical_geometry",
)
```

After `django.setup()`, these labels ran through
`call_command("test", *labels, interactive=False, verbosity=1)` inside
`patch.object(core, "pattern_perimeter_core_mosaic", pattern)`, first with
`benchmark_perimeter_core_filter.load_baseline_pattern()`, then with the
current constructor. The captured pre-edit hashes confirm that all 29 locked
baseline results equal the actual pre-edit engine results. The benchmark's
working-source hash matches the final shared core.

The final cumulative suite passed **154 tests**, zero failures/skips, in
**133.461 seconds**. Together with the 34 supplementary checks, **188 final
tests pass**. `manage.py check` reports no issues and `git diff --check` passes.
The existing missing-`staticfiles` directory warning is unrelated. Both frozen
consumer baselines and all earlier active Palletization calibrations pass;
historical baseline JSON files are unchanged.

## Paired runtime

The benchmark loads only the original family entry point from the locked Git
commit. Both paths use the same remaining shared core, engine and policies.
It warms both paths, then alternates execution order for seven repetitions in
one process. Retained family rows, unrelated rows and overall winners are
checked for exact equality before timing is reported.
The repository's material-regression criterion requires both a median increase
over 20% and an absolute increase over 25 ms.

| Full analysis | Before median, ms | After median, ms | Change |
| --- | ---: | ---: | ---: |
| Case 3 | 10.966 | 11.150 | +1.68% |
| Case 4 | 19.872 | 19.639 | -1.17% |
| Case 6 | 47.633 | 44.525 | -6.52% |
| Case 7 | 583.318 | 614.579 | +5.36% |
| Case 8 | 230.072 | 234.683 | +2.00% |
| CapePack reference | 11.391 | 10.888 | -4.41% |
| Pinwheel reference | 39.943 | 48.615 | +21.71% |
| Fractional dimensions | 56.572 | 58.405 | +3.24% |

All 16 timed paths pass that combined criterion. Positive-case family calls
measure 0.205–0.361 ms before and 0.207–0.362 ms after (CapePack
0.205→0.213 ms). Excluded Case 6/7/8 calls fall from
0.393/0.202/0.202 ms to 0.003/0.002/0.002 ms. No additional placements or
candidates are generated. Some full-analysis medians increased: Case 7's
31.261 ms increase is 5.36%, and the Pinwheel reference's 21.71% increase is
8.672 ms. These observations are retained; this is not a claim that every
request became faster or that timing variance is eliminated.

- [Pre-edit capture](../../artifacts/palletization-perimeter-core-calibration/before.json)
- [Paired benchmark and all-preset scan](../../artifacts/palletization-perimeter-core-calibration/benchmark.json)

The JSON includes every sample, complete result summaries, full-result and
Perimeter-Core hashes, the baseline commit and working-core source hash.

## Changed files and remaining limits

- `packagingapp/utils/packing_patterns/core.py`: policy flag and early relevance checks.
- `packagingapp/tests/test_shared_mosaic_patterns.py`: six domain regressions and eligible delegation fixture.
- `packagingapp/tests/test_regressions.py`: cross-surface availability, scenes, alternate preview, export and session protection.
- `packagingapp/tests/benchmark_perimeter_core_filter.py`: locked-constructor comparison and runtime scan.
- Domain/shared-pattern documentation, PAL-REG-005, this report and two evidence JSON files.

The thresholds are the requested relevance calibration. They do not establish
mechanical stability. No merge, deployment, production migration or
production-data operation was performed. Commit and push were authorized
separately after implementation and validation.
