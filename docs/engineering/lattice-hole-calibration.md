# Nested Simple Lattice hole-area calibration

## Scope and baseline

The change is confined to `_nested_simple_lattice_entries` in the Palletization
engine. The two lattice families retain their names, geometry constructors,
deduplication, stable count ranking and search limits (30 parameters, 80
materialization candidates, four distinct variants per family). No other
pattern generator or shared Container Selection geometry changes.

Work was performed on `production` at
`4d511fe3fd05ff9a813af6385d19386e424ea0f6`. The checkout already contained
uncommitted Hybrid pinwheel calibration changes. Those changes were retained.
Both sides of the paired comparison use that same working shared core; only
the pre-filter lattice enumeration is loaded from the locked Git commit.
Its equality with the live enumeration was checked before editing.

## Rule and motivating cases

For each existing `(i,j,rotated)` parameter candidate, use normalized carton
sides `L>=S`. The motif contains `i*j` square holes of side `L-S`. Its exact
contour is `(i*L+j*S)` by `(i*S+j*L)`. Reject when:

```text
i*j*(L-S)**2 > 0.20*(i*L+j*S)*(i*S+j*L)
```

The 20% limit is an initial relevance calibration. Equality is eligible.
The comparison uses O(1) arithmetic without division and runs before sorting,
the 80-candidate slice, any placement construction and the four-variant cap.
It measures internal voids independently of exterior pallet slack. It adds no
search, carton-pair checks, graph work, stability simulation or optimization.

| Case | Before 1D shortlisted cartons/layer | Before 2D shortlisted cartons/layer | After | Overall winner before and after |
| --- | --- | --- | --- | --- |
| 2 | 16, 9, 9 | 16 | All retained, identical ordered placements and metrics | Pinwheel, 16/layer, 5 layers, 80 total |
| 7 | 36, 25, 16, 16 | 49, 49, 36, 36 | Both lattice families absent | Block, 96/layer, 10 layers, 960 total |
| 8 | 25, 16, 16, 9 | 36, 25, 16 | Both lattice families absent | Splitrow, 76/layer, 10 layers, 760 total |

Case 2's shortlisted 1D motifs have 0.4682–0.5544% hole area; its 2D motif
has 0.6233%. Case 7's previously shortlisted motifs span 23.8095–36.0000%;
Case 8 spans 33.8624–44.4444%. Every fitting parameter is checked, including
ones that were outside the former four-variant shortlist.

Nested pinwheel remains independent: Case 4's 12-carton and Case 8's
64-carton arrangements retain every ordered placement and analysis metric.
The Case 9 Hybrid winner remains 33/layer, six layers, 198 total.

## Consumer assessment

| Consumer | Verification |
| --- | --- |
| Standalone and `/regressions` | Existing links/calculate/select/recalculate test plus explicit Case 2/7/8 lattice assertions |
| SEO calculator | Case 2 retains selectable 16-carton variants from both families; Cases 7/8 contain neither family |
| Packaging Flow | Same complete result table as SEO for Cases 2/7/8; exact variant selection and serialized selected result parity |
| 3D and JavaScript hydration | Existing variant-key/scene/alternate-preview tests; new SEO selection checks validate scene quantities and bounds |
| PDF/report export | Selected analysis report in session matches the selected row; frozen Stage 2 scene/report-row contract and existing export checks retained |
| Catalogue inputs | Same effective dimensions and shared service; existing catalogue-height, payload and unit tests run |
| Container / Multi-product Container | Shared code and policies untouched; high-hole shared constructors still produce valid geometry; Stage 1 Container baseline retained |
| Multi-product Bag | No dependency on Palletization lattice enumeration |
| Sessions | No new state fields or objects; JSON serialization checked after SEO/Flow selection |

The public preset scan compares every non-lattice analysis row, including
ordered 2D/3D geometry and metrics, for exact equality. The positive lattice
presets compare entire result lists. Existing frozen fixtures and unrelated
assertions are unchanged.

An additional large-scale test observed pre-existing shared-construction
variation for 82×70 cartons on a 1200×800 area when all dimensions are
multiplied by 25.4. Both the locked enumeration and the current enumeration
return the same reduced 1D shortlist and no 2D shortlist at that scale.
Shared construction was left untouched. The new unit-invariance test isolates
eligibility decisions from placement construction; existing real metric/inch
geometry regressions remain active. This is a remaining shared-geometry
limitation outside the requested filter.

## Commands and results

The pre-edit cumulative baseline passed **140 tests** in **99.546 seconds**.
Baseline and final use this same module list; final automatically includes the
new eligibility and consumer regressions:

```powershell
$env:DEBUG='True'
$env:DATABASE_URL='sqlite:///:memory:'
.\.venv\Scripts\python.exe manage.py test packagingapp.tests.test_shared_mosaic_patterns packagingapp.tests.test_shared_mosaic_stage1_baseline packagingapp.tests.test_palletization_stage2_baseline packagingapp.tests.test_nested_simple_lattice_patterns packagingapp.tests.test_pallet_splitrow packagingapp.tests.test_pallet_max_load packagingapp.tests.test_palletization_unit_ui packagingapp.tests.test_regressions.RegressionCompendiumTests packagingapp.tests.test_product_dimensional_allowance packagingapp.tests.test_container_geometry_first packagingapp.tests.test_full_packaging_case --noinput
.\.venv\Scripts\python.exe manage.py check
git diff --check
.\.venv\Scripts\python.exe -m packagingapp.tests.benchmark_lattice_hole_filter --repetitions 7
```

The focused seven-test development run found an overbroad new full-construction
scaling assertion (four scale subtests). The single correction isolated the
filter's unit decisions; no production geometry changed to satisfy that test.
Final cumulative and paired benchmark results are recorded below.

Final cumulative result: **147 tests passed**, zero failures and zero skips,
in **107.875 seconds**. The seven additions are six eligibility methods and
one cross-surface integration method. `manage.py check` reported no issues;
`git diff --check` passed. The pre-existing missing-`staticfiles` warning is
unrelated. No frozen fixture or pre-existing regression assertion was changed.

## Paired runtime and preset impact results

The benchmark warms both paths and alternates execution order for seven
repetitions in one process. Medians are observational. Material regression uses
the existing combined threshold: more than 20% **and** more than 25 ms.
The raw output contains each sample, complete before/after result summaries for
every preset, and the working shared-core SHA-256 for reproducibility.

Only **Calibration Cases 7 and 8** change among the **29 public presets**.
The other 27 presets and the additional small-carton stress case retain their
entire result lists. All 30 comparisons preserve every non-lattice row; all
public preset winners retain their complete ordered geometry and metrics.

| Full analysis | Before median, ms | After median, ms | Change |
| --- | ---: | ---: | ---: |
| Case 2 | 24.835 | 21.552 | -13.22% |
| Case 4 | 25.487 | 20.827 | -18.28% |
| Case 7 | 553.611 | 532.023 | -3.90% |
| Case 8 | 336.017 | 255.390 | -23.99% |
| Case 9 | 161.450 | 168.579 | +4.42% |
| Pinwheel reference | 37.154 | 60.325 | +62.36% |
| Fractional dimensions | 98.071 | 97.504 | -0.58% |
| Small 70×40 carton | 8575.812 | 7713.514 | -10.06% |

| Lattice enumeration and materialization | 1D before → after, ms | 2D before → after, ms |
| --- | ---: | ---: |
| Case 2 | 1.033 → 1.040 | 1.536 → 1.523 |
| Case 7 | 1.533 → 0.044 | 6.104 → 1.032 |
| Case 8 | 0.732 → 0.032 | 2.679 → 0.662 |

All **24 measured paths** remain below the combined material-regression
criterion. The initial Pinwheel reference increase is reported explicitly:
23.171 ms / 62.36%. Both sample sets were variable, while its lattice
generation changed by only 0.021 / 0.066 ms. A justified **21-pair repeat**
of full analysis produced **56.336 → 56.354 ms (+0.03%)**, with identical
outputs, so the initial increase did not persist. Case 9's seven-pair median
increase is 7.129 ms / 4.42%. The raw samples retain these observations;
there is no claim that every individual call is faster.

- [Pre-edit Case 2/7/8 capture](../../artifacts/palletization-lattice-calibration/before.json)
- [Paired benchmark and all-preset scan](../../artifacts/palletization-lattice-calibration/benchmark.json)
- [Pinwheel 21-pair repeat](../../artifacts/palletization-lattice-calibration/pinwheel-repeat.json)

## Changed files

- `packagingapp/utils/palletization/engine.py`: initial threshold and arithmetic eligibility before shortlisting.
- `packagingapp/tests/test_nested_simple_lattice_patterns.py`: boundary, construction/cap ordering, unit/axis/rotation decisions, whole-preset exact comparisons and Container isolation.
- `packagingapp/tests/test_regressions.py`: standalone lattice availability and SEO/Flow/scene/selection/export/session parity.
- `packagingapp/tests/benchmark_lattice_hole_filter.py`: locked-enumeration paired benchmark and all-preset impact scan.
- `docs/domain/palletization-logic.md`, `docs/domain/shared-mosaic-patterns.md`, `docs/engineering/known-issues-and-regressions.md`, and this report: calibration contract, permanent PAL-REG-004 protection and evidence.
- `artifacts/palletization-lattice-calibration/`: pre-edit capture and paired benchmark evidence.

No commit, push, merge, deployment, production migration or production-data
action was taken.
