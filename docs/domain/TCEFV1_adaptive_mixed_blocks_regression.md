# TCEFV1 Adaptive Mixed-Lane Blocks regression report

## Result

TCEFV1 now supports quantity-aware Adaptive Mixed-Lane Blocks (AMLB) without
replacing exact synchronized Product Blocks or either mode orchestrator.

- Three non-stackable 1200 × 800 × 144 mm pallets now use one 1200 mm tail and
  one two-unit 1600 mm tail, so all three occupy 1600 mm X in every active
  mode. The previous result used 2400 mm in Progressive Fill and 2000 mm in
  Balanced Spread.
- A non-stackable 1200 × 801 × 144 mm request loads 25/30 in the exact
  12032 × 2352 × 2698 mm test container. One 801 mm-wide lane contains ten
  1200 mm-long units and ends at 12000 mm; the adjacent 1200 mm-wide lane
  contains fifteen 801 mm-long units and ends at 12015 mm. The previous engine
  loaded 20/30.
- The exact 1200 × 800 synchronized five-unit module remains selected for the
  25-pallet case. Its complete placement signature is unchanged in all four
  modes.
- The approved stacked multi-SKU orchestration, P4/P2 Native/DGFE decisions,
  Balanced Spread residual cases, and TOPS benchmark signatures are unchanged.

No pallet dimension, 3:2 ratio, count, container model, or physical
near-equality threshold is hardcoded.

## Implementation

AMLB extends `ProductBlockCandidate` with an exact per-lane stack plan,
`planned_quantity`, a non-repeatable marker, and actual-envelope efficiency.
The generator:

1. pairs any two enabled orientations with equal item height;
2. builds bounded lane compositions inside the current free width;
3. uses rational integer bisection over critical X depths;
4. commits actual stack heights at each populated lane position;
5. ranks by actual phase quantity, occupied depth, actual envelope efficiency,
   effective prism utilization, and stable geometry ties.

The existing repeatable winner is retained on a true outcome tie. Exact
synchronized modules therefore keep their approved priority. An AMLB is
committed once; it is never repeated as if unequal tails formed a full module.
Metadata keeps the existing compatibility aliases and adds lane `start_y`,
`orientation_index`, `unit_count`, `stack_heights`, and `actual_x_end` plus
block `planned_quantity`, `actual_depth`, and `repeatable`.

Candidate work is capped at 128 physical lanes and 4096 materialized floor
columns per AMLB. Counts above 128 are sampled at stable proportional points.
The ordinary pallet fixtures expand completely. Stacked AMLB geometry is
generated and materializable, including partial vertical layers, but active
stacked phases keep the repeatable/residual contract so an adaptive block
cannot erase P4/P2 DGFE, Balanced Spread residual, or existing single-SKU
presentation semantics. Non-stackable AMLB remains eligible in single- and
multi-SKU phases.

## Core old-versus-new evidence

All dimensions in this section are millimetres. `PF` is Progressive Fill,
`PFI` is Progressive Fill + Infill, `BS` is Balanced Spread, and `BSI` is
Balanced Spread + Infill.

| Fixture | Mode | Old packed | New packed | Old X | New X | Selected family |
|---|---:|---:|---:|---:|---:|---|
| EUR qty 3 | PF | 3 | 3 | 2400 | 1600 | adaptive_mixed_lane |
| EUR qty 3 | PFI | 3 | 3 | 2400 | 1600 | adaptive_mixed_lane |
| EUR qty 3 | BS | 3 | 3 | 2000 | 1600 | adaptive_mixed_lane |
| EUR qty 3 | BSI | 3 | 3 | 2000 | 1600 | adaptive_mixed_lane |
| EUR qty 25 | all four | 25 | 25 | 12000 | 12000 | synchronized_mixed_orientation |
| 1200 × 801 qty 30 | all four | 20 | 25 | 12000 | 12015 | adaptive_mixed_lane |

The 25-pallet signature remains
`af13b18cdfeef653ddac85fd36c5c66c7a12acc4f0efa5112ba1f2a3e94553a7`
in every mode. The 1200 × 801 improvement raises packed envelope volume from
2.768256 m³ to 3.460320 m³ and test-container utilization from 3.626% to
4.532%.

The quantity sweep `[1, 2, 3, 4, 5, 6, 7, 17, 24, 25, 26, 30]` is
deterministic in all four modes and loads `min(requested, 25)` for this
non-stackable Euro-pallet/container fixture. The suite separately covers a
stacked partial AMLB candidate and unchanged stacked end-to-end behavior,
exact/short/narrow boundaries, payload exhaustion,
fractional dimensions, R2-only and R3-only compatible-height pairs, disabled
orientation groups, 1200 × 790, 1200 × 825, other rectangles, and a two-SKU
case.

## Max quantity non-monotonic regression and solver

The Max-quantity service previously binary-searched the predicate “the engine
fully packed the requested quantity.” That predicate is not monotonic. For a
12000 × 2000 × 2698 mm container and stackable 1200 × 800 × 1200 mm Euro-pallet
load, every active mode produced this request sequence:

| Requested | Packed | Fully packed | Product Block outcome |
|---:|---:|---:|---|
| 48 | 48 | yes | 40 regular + 8 residual |
| 49 | 48 | no | 40 regular + 8 residual; 1 unplaced |
| 50 | 50 | yes | five complete ten-unit synchronized blocks |

The old binary-search path accepted 48, rejected 49, and never evaluated 50,
so the UI reported 48 even though entering 50 manually loaded all 50. The new
service solver searches downward from a safe physical/capped upper bound and
selects the first fully packed result. It now returns 50 in Progressive Fill,
Progressive Fill + Infill, Balanced Spread, and Balanced Spread + Infill.

The change is generalized rather than a regression exception. The upper bound
uses enabled-orientation fit, volume, payload, fixed-row reservations, and a
safe floor-area limit for a lone non-stackable row. Candidate requests are
evaluated by the selected real engine without assuming monotonicity. The same
solver also finds
450 rather than the previous 432 for a stackable 1200 × 800 × 144 mm load in a
12032 × 2352 × 2698 mm container. Tests additionally protect payload/fixed-row
reservation and row-ordered multiple-Max behavior. No dimensions or quantities
from either fixture occur in production solver logic, and no packing-mode
orchestration changed.

## Protected TCEFV1 evidence

The pre-change targeted suites ran 77 tests successfully. After AMLB, the same
suites retain their captured placement signatures and all 77 pass.

- Original primary-case Balanced Spread golden digest:
  `0fe3904ce174d598cd4d7462ed4610328b16198bf5de82bf8b22c2a216a66041`.
- Original primary-case Progressive Fill golden digest:
  `8416bd1c04162d9a052d8c53560c30290ae72ffc4a3a4ba12f8cb8b80db5c679`.
- P4 residual 20 → P2 quantity 10 remains the compact Native construction.
- P2 residual 3 → P1 quantity 114 remains the selected DGFE transition.
- Balanced Spread Phase 1 and its accepted 48-unit residual continuation keep
  their frozen signatures and phase counts.
- `engine_legacy.py` is not imported.

## TOPS MaxLoad / KolliPack benchmark

### Provenance and parity boundary

The first four rows, flags, weights, and sequences come from
`packagingapp/tools/transport/case_presets.py`. Tests use the task's exact
inch-derived container geometry, 12039.6 × 2362.2 × 2692.4 mm, rather than the
public preset's rounded 12039 × 2362 × 2692 mm.

The checked-in public preset contains only the original four-row manifest. A
retained KolliPack optimized-result image identifies P5 as 558.8 × 406.4 ×
317.5 mm, stackable, 4.54 kg, sequence 1, but does not expose its rotation
checkboxes. The five-row tests explicitly assume R1-only for P5, matching all
four preset rows. Consequently, the optimized/probe rows are traceable
KolliPack reconstruction tests, but they are not claimed as fully source-parity
fixtures for every hidden P5 setting. The external TOPS figures remain
attributed references, not KolliPack expected results.

Requested envelope volumes are 2271.02 ft³ (original), 2388.31 ft³
(optimized), 2437.01 ft³ (probe A), and 2408.68 ft³ (probe B). Probe A and B
are run independently.

| Fixture | Mode | Demand | Old → new packed | Packed ft³ | Util. | Occupied X | Phase outcome | Signature |
|---|---|---:|---:|---:|---:|---:|---|---|
| Original | PF | 1228 | 1228 → 1228 | 2271.02 | 83.984% | 11303.00 | 1060 regular + 168 frontier; 3 frontiers | unchanged |
| Original | PFI | 1228 | 1228 → 1228 | 2271.02 | 83.984% | 11303.00 | same parent geometry | unchanged |
| Original | BS | 1228 | 1228 → 1228 | 2271.02 | 83.984% | 11342.37 | 1180 regular + 48 residual; 2 frontiers | unchanged |
| Original | BSI | 1228 | 1228 → 1228 | 2271.02 | 83.984% | 11342.37 | same parent geometry | unchanged |
| Optimized | PF | 1285 | 1285 → 1285 | 2388.31 | 88.322% | 11988.80 | 1132 regular + 153 frontier; 3 frontiers | unchanged |
| Optimized | PFI | 1285 | 1285 → 1285 | 2388.31 | 88.322% | 11988.80 | same parent geometry | unchanged |
| Optimized | BS | 1285 | 1285 → 1285 | 2388.31 | 88.322% | 12028.17 | 1252 regular + 33 residual; 2 frontiers | unchanged |
| Optimized | BSI | 1285 | 1285 → 1285 | 2388.31 | 88.322% | 12028.17 | same parent geometry | unchanged |
| Probe A | PF | 1319 | 1319 → 1319 | 2437.01 | 90.122% | 11988.80 | 1172 regular + 147 frontier; 2 frontiers | unchanged |
| Probe A | PFI | 1319 | 1319 → 1319 | 2437.01 | 90.122% | 11988.80 | same parent geometry | unchanged |
| Probe A | BS | 1319 | 1315 → 1315 | 2431.28 | 89.911% | 12028.17 | 1252 regular + 63 residual; 4 P1 unplaced | unchanged |
| Probe A | BSI | 1319 | 1315 → 1315 | 2431.28 | 89.911% | 12028.17 | same parent geometry | unchanged |
| Probe B | PF | 1293 | 1293 → 1293 | 2408.68 | 89.075% | 11934.44 | 1108 regular + 185 frontier; 5 frontiers | unchanged |
| Probe B | PFI | 1293 | 1293 → 1293 | 2408.68 | 89.075% | 11934.44 | same parent geometry | unchanged |
| Probe B | BS | 1293 | 1280 → 1280 | 2388.62 | 88.333% | 11760.20 | 1252 regular + 28 residual; 13 P2 unplaced | unchanged |
| Probe B | BSI | 1293 | 1280 → 1280 | 2388.62 | 88.333% | 11760.20 | same parent geometry | unchanged |

These results do not combine the probes and do not relabel KolliPack output as
a TOPS result.

## Physical and serialization validation

The reusable test helper uses an active-X sweep rather than an all-pairs
overlap scan. It checks positive dimensions, XYZ bounds, permitted
orientations, positive-volume overlap, full union support, non-stackable
support rejection, payload, per-row unique indices, requested/packed/unplaced
reconciliation, sequence normalization/preservation, and placement-volume
reconciliation. Every pallet, perturbation, multi-SKU, and 16-run benchmark
result passed. AMLB metadata is JSON serializable and contains primitives only.

### Shared-consumer assessment

| Surface | Check | Result |
|---|---|---|
| Standalone Transport | direct engine, service/sequence, public view and Three.js tests | PASS |
| Packaging Flow | `test_full_packaging_case` session/scene/orientation tests | PASS (3/3) |
| Public SEO/demo | canonical public preset provenance plus visualization route tests | PASS |
| PDF/report | shared placement/summary serialization and export endpoint contract in visualization suite | PASS |
| Catalogue source | no catalogue normalization code changed; exact manual/preset dimensions pass | assessed, unchanged |
| Multi-product Container | separate Container Design engine; not a Transport Container consumer | not applicable |

No template or JavaScript calculation was added. Standalone, public, report,
and Flow surfaces continue to consume the shared engine placement and JSON-safe
metadata contracts.

## Performance observations

One paired wall-time pass loaded the checked-in `HEAD` engine in memory beside
the changed engine. Timings are observations, not CI thresholds.

- Qty 3 and 1200 × 801 pallet cases remained around 0.001–0.003 seconds per
  mode.
- Original TOPS PF: 4.004 s old, 4.297 s new; original BS: 1.812 s old,
  2.069 s new.
- Optimized TOPS PF: 4.237 s old, 4.348 s new; optimized BS: 0.200 s old,
  0.223 s new.
- Probe A PF: 4.203 s old, 4.189 s new; probe A BS: 0.484 s old, 0.488 s new.
- Probe B PF: 7.287 s old, 7.064 s new; probe B BS: 0.379 s old, 0.469 s new.
- A 5000-unit 50 × 40 × 30 mm small-carton fixture loaded all 5000 with an
  unchanged signature: 0.070 s old and 0.178 s new. Candidate tests confirm
  deterministic work below 10000 evaluations and the 4096-column AMLB cap.

The small-carton case shows the largest relative overhead but no uncontrolled
growth; candidate work stays geometry/cap bounded rather than enumerating
quantity partitions.

## Commands and results

```powershell
.\.venv\Scripts\python.exe manage.py test packagingapp.tests.test_transport_front_to_back packagingapp.tests.test_transport_mixed_cargo_infill packagingapp.tests.test_space_evenly_stabilization
.\.venv\Scripts\python.exe manage.py test packagingapp.tests.test_transport_adaptive_mixed_lane
.\.venv\Scripts\python.exe manage.py test packagingapp.tests.test_transport_adaptive_mixed_lane_benchmarks
.\.venv\Scripts\python.exe manage.py test packagingapp.tests.test_transport_max_quantity_solver
.\.venv\Scripts\python.exe manage.py test packagingapp.tests.test_transport_adaptive_mixed_lane packagingapp.tests.test_transport_adaptive_mixed_lane_benchmarks packagingapp.tests.test_transport_front_to_back packagingapp.tests.test_transport_mixed_cargo_infill packagingapp.tests.test_space_evenly_stabilization packagingapp.tests.test_transport_sequence_semantics packagingapp.tests.test_transport_visualization
.\.venv\Scripts\python.exe manage.py test packagingapp.tests.test_transport_adaptive_mixed_lane packagingapp.tests.test_transport_adaptive_mixed_lane_benchmarks packagingapp.tests.test_transport_front_to_back packagingapp.tests.test_transport_mixed_cargo_infill packagingapp.tests.test_space_evenly_stabilization packagingapp.tests.test_transport_sequence_semantics packagingapp.tests.test_transport_visualization packagingapp.tests.test_transport_max_quantity_solver
.\.venv\Scripts\python.exe manage.py test packagingapp.tests.test_full_packaging_case
.\.venv\Scripts\python.exe manage.py check
```

The pre-change protected run passed 77/77. The two defect-first tests then
failed against the old selector as expected. Post-change focused results are
9/9 AMLB tests and 2/2 benchmark tests. The final combined engine, sequence,
service/view, and visualization run passed 109/109 in 153.524 seconds. Django
`manage.py check` also reported no issues.

An attempted direct label for the legacy monolithic
`packagingapp/tests.py::TransportThreeJsAndPdfTests` was not importable because
the `packagingapp.tests` package shadows that legacy module path; Django
reported a test-label `ModuleNotFoundError`, not an application assertion
failure. The discoverable transport visualization/export contract suite and
the Packaging Flow suite both pass.

For the Max-quantity follow-up, the four real-engine service tests failed first
with the old 48 and 432 results. The final module, including a synthetic
non-monotonic predicate test, passes 5/5 in 1.244 seconds. The combined
transport engine, sequence, service/view, visualization, AMLB, benchmark, and
initial four Max-quantity tests passed 113/113 in 331.460 seconds. Packaging
Flow remains 3/3 and the Django system check remains clean.
