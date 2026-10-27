# TCEFV1 generalized mono-product rectangular packing regression

> **Compaction follow-up:** The later per-lane blocker compaction refinement
> supersedes the occupied-X and exact-coordinate measurements in this report
> while preserving its capacity and mixed-cargo conclusions. See
> [TCEFV1_mono_lane_compaction_regression.md](TCEFV1_mono_lane_compaction_regression.md)
> for the current geometry and verification record.

## Outcome

TCEFV1 now has a bounded, geometry-driven `mono_lane_transition` floor-plan
competitor for a complete request containing exactly one positive-quantity
input row. It supports any axis-aligned rectangular cargo accepted by the
shared R1/R2/R3 orientation contract. Product name, packaging family, pallet
dimensions, target quantity, and container preset are not used for eligibility
or search generation.

The existing active mode runs to completion first. The new exact-placement
plan is selected only by the complete-outcome order: more units, shorter actual
X extent, less unused area in the XY bounding envelope, then baseline on a true
tie. Mixed cargo is ineligible, so Product Blocks, residual closure, DGFE,
infill, sequence handling, and TOPS benchmark behavior remain isolated.

This is a bounded constructive optimizer over enumerated lane configurations.
It is not a complete general 2D or 3D bin-packing solver and does not establish
a universal geometric maximum unless a separate proof is recorded below.

## Version and fixture provenance

- Branch observed before and after implementation: `production`.
- Checked-out `HEAD`: `b635c34cb76609f9511611b9f1894d464881f443`.
- “Before” is the active uncommitted TCEFV1 state with the approved AMLB and
  Max-quantity changes but without `mono_lane_transition`; it is not a separate
  committed release.
- “After” is the current uncommitted implementation in
  `packagingapp/utils/container_tool/engine.py`.
- Canonical overhang container: 12032 × 2352 × 2698 mm, no payload limit.
- Canonical row: quantity 30, 1 kg, nonstackable, R1 only, R2/R3 disabled,
  144 mm high, footprint `(1200+d) × (800+d)` mm.

All four active modes produced the same canonical floor geometry and signature
for each `d`: Progressive Fill (`front_to_back`), Progressive Fill + Infill,
Balanced Spread (`space_evenly`), and Balanced Spread + Infill.

## Root cause and implementation boundary

AMLB improved unequal lane tails, but one Product Block still retains one fixed
Y-lane composition for its full X depth. Slightly enlarged rectangles therefore
stopped at 23 even though a 24-unit stepped arrangement exists. Raising AMLB
priority globally was rejected because a locally larger block can reduce the
complete mixed-cargo result.

The new plan type stores exact `Placement` cuboids rather than pretending the
irregular result is a repeatable Product Block. It enumerates enabled floor
orientations, bounded lane compositions, left/right alignment, and
dimension-derived critical X cuts. For every right lane, its start is computed
from the furthest overlapping left-lane endpoint. Lane boundaries can therefore
be asynchronous rather than sharing one false full-width transition plane.
Every materialized candidate passes the shared exact bounds/collision validator.

A stackable row remains eligible when only one physical Z layer fits. If any
fitting orientation permits multiple supported layers, the floor-only search
is skipped so it cannot displace the established 3D result. The 600 × 400 ×
300 mm stacked fixture in 2400 × 1200 × 1000 mm therefore remains 36 units and
keeps its baseline signature.

## Canonical before/after matrix

`d` is the increase in each **total outside footprint dimension**, not the
overhang on one side. Thus `d=40/50/60` corresponds to 20/25/30 mm per side.
Timing ranges are one local measured pass across the four modes and are not CI
thresholds.

| d (mm) | Before packed / X (mm) | After packed / unplaced / X (mm) | Selected outcome | Realized transitions | Candidates | Elapsed per mode | Status |
|---:|---:|---:|---|---:|---:|---:|---|
| 0 | 25 / 12000 | 25 / 5 / 12000 | baseline | 0 | 1168 | 0.344–0.370 s | preserved feasible result |
| 5 | 23 / 11270 | 24 / 6 / 12032 | mono lane transition | 1 | 1232 | 0.426–0.722 s | proven optimum 24 |
| 10 | 23 / 11340 | 24 / 6 / 12032 | mono lane transition | 1 | 1232 | 0.631–0.695 s | proven optimum 24 |
| 15 | 23 / 11410 | 24 / 6 / 12032 | mono lane transition | 1 | 1232 | 0.681–0.874 s | proven optimum 24 |
| 20 | 23 / 11480 | 24 / 6 / 12032 | mono lane transition | 1 | 1232 | 0.565–0.663 s | proven optimum 24 |
| 25 | 23 / 11550 | 24 / 6 / 12032 | mono lane transition | 1 | 1232 | 0.634–0.761 s | proven optimum 24 |
| 30 | 23 / 11620 | 24 / 6 / 12032 | mono lane transition | 1 | 1232 | 0.631–0.708 s | proven optimum 24 |
| 40 | 23 / 11760 | 23 / 7 / 11760 | baseline | 0 | 1232 | 0.725–0.824 s | proven optimum 23 |
| 50 | 23 / 11900 | 23 / 7 / 11900 | baseline | 0 | 1232 | 0.884–0.988 s | proven optimum 23 |
| 60 | 22 / 11340 | 23 / 7 / 12032 | mono lane transition | 1 | 1184 | 0.642–0.687 s | proven optimum 23 |

The test-only feasibility oracle constructs 24 separate rectangles for every
`d` from 5 through 30 and checks all bounds and all pairs independently. For
these dimensions the floor never permits three items at an X cross-section,
there are at most `floor(L/b)` short-X items, and 25 items would require more
than `2L` total longitudinal occupancy. This proves the fixture-specific upper
bound of 24. The same independent occupancy inequality excludes 24 for
`d=40/50/60`; the validated engine constructions supply the matching feasible
lower bound of 23. These proofs do not generalize to arbitrary rectangles.

The prior 1200 × 801 and 1200 × 802 AMLB cases remain 25. The quantity sweep
`[1,2,3,4,5,6,7,17,23,24,25,26,30]` loads `min(requested, capacity)` for both
the nominal and perturbed fixture in all modes. The three-unit nominal result
remains at or below 1600 mm X.

## Exact selected geometry example

For `d=10`, every active mode returns signature
`a6c3d68f8140134625c027fd3ec7108a6ff1a8c73f8c75adc27da402b16700d0`.
The selected left composition contains 13 units of orientation
810 × 1210 × 144 ending at X=10530 and nine units of orientation
1210 × 810 × 144 ending at X=10890. The right composition swaps the Y
assignment: one 1210 × 810 unit occupies X=10822..12032 and one
810 × 1210 unit occupies X=11222..12032. These staggered starts overlap in X
only where their Y intervals are disjoint. The additive diagnostics report the
two orientation indices, each lane's Y, quantity, X start/end, transition limit
and realized count, search count/caps, actual depth, compactness waste, and a
bounded coordinate sample.

## Non-pallet generalization matrix

All rows are nonstackable, R1-only, request 100, and use a one-layer container.
Every result passed the independent physical validator in all four modes.

| Test family | Floor / item (mm) | Before | After | X (mm) | Transition / candidates | Conclusion |
|---|---|---:|---:|---:|---:|---|
| Small cartons | 2400×1200 / 600×400 | 12 | 12 | 2400 | baseline / 288 | proven optimum by constructive tiling plus area bound |
| Reusable crates | 3500×1500 / 700×500 | 15 | 15 | 3500 | baseline / 490 | proven optimum by constructive tiling plus area bound |
| Asymmetric cases | 4100×1730 / 730×470 | 18 | 19 | 4100 | 1 / 1848 | best found; improved feasible lower bound |
| Machinery bases | 6000×1250 / 1450×260 | 16 | 16 | 5800 | baseline / 0 | best found; unchanged |
| Nearly square cartons | 3010×2010 / 505×495 | 23 | 24 | 3010 | 1 / 4096 | best found; improved at candidate cap |
| Fractional trays | 3100.5×1610.25 / 617.5×383.25 | 20 | 20 | 3087.5 | baseline / 1848 | best found; unchanged |

The same production entry point also passes quantities
`[1,2,3,4,5,7,11,17,50]` on the exact carton and asymmetric-case families.
Scale factors 0.5, 1, and 2 preserve count and normalized placement signature.
Swapped product axes preserve quantity when R1 permits both floor rotations;
the corresponding rotated-container case also preserves quantity.

R1-only, R2-only, R3-only, all-rotation, and no-orientation cases were checked;
the independent validator rejects any orientation not explicitly enabled.
One positive row plus a zero row activates the mono plan, while two positive
rows with identical geometry remain mixed and retain their baseline signature.
Payload, narrow/short floors, fractional dimensions, repeated deterministic
signatures, and unsupported transition limit `2` are also covered.

## Bounds and fallback behavior

- `max_lane_transitions`: `0` or `1`; default `1`; another value fails
  explicitly rather than silently running a different search.
- physical lanes: 128;
- distinct lane configurations: 128;
- critical cuts per configuration: 256;
- candidate materializations: 4096;
- requested placements for this exact-placement pass: 512.

A 5000-unit 10 × 5 × 100 mm pathological case in a 10000 × 1000 × 100 mm
container reaches the placement cap and cleanly retains the baseline 5000-unit
signature. Diagnostics report 128 configurations and zero transition
materializations. The nearly square case reaches exactly 4096 candidates and
remains deterministic. These observations demonstrate bounded work, not a
runtime or optimality guarantee for every geometry. Peak process memory was
not separately profiled; the hard object/count caps are the reviewed resource
indication.

## Regression isolation

- The single-row 1800 × 2352 mm / 260 × 1200 mm / qty 26 case improves from
  10 to 11 or better under the mono outcome comparison.
- A fully specified two-row 4800 × 1800 × 2698 mm counterexample keeps the
  exact transition-disabled signature in every mode. The original exploratory
  randomized quantities/flags were not recoverable, so the historical
  25→22/29→22/29→26 observations are not claimed as an exact replay.
- The approved P4/P2 Native/DGFE, Pi compactness, orientation evaluation,
  deferred-gravity, residual closure, infill, sequence, and carry-forward
  fixtures remain protected by their dedicated suites.
- All 16 TOPS/KolliPack manifest-mode runs retain the pre-planner counts because
  they contain multiple positive rows and never invoke the mono pass:
  original 1228 in all modes; optimized 1285 in all modes; probe A 1319 in
  Progressive Fill and 1315 in Balanced Spread; probe B 1293 in Progressive
  Fill and 1280 in Balanced Spread. External TOPS demand and KolliPack engine
  outcomes remain separately labeled. The reconstructed P5 flags retain the
  provenance caveat documented in the AMLB regression report.

## Verification record

Focused generalized tests:

```powershell
.\.venv\Scripts\python.exe manage.py test packagingapp.tests.test_transport_mono_lane_transition --verbosity 2
```

Result: 16/16 passed in 139.057 seconds before the additional independent
`d=40/50/60` upper-bound assertion was added; that assertion contains no engine
execution and is included in the final combined run.

The active Transport regression command is:

```powershell
.\.venv\Scripts\python.exe manage.py test packagingapp.tests.test_transport_adaptive_mixed_lane packagingapp.tests.test_transport_adaptive_mixed_lane_benchmarks packagingapp.tests.test_transport_front_to_back packagingapp.tests.test_transport_mixed_cargo_infill packagingapp.tests.test_space_evenly_stabilization packagingapp.tests.test_transport_sequence_semantics packagingapp.tests.test_transport_visualization packagingapp.tests.test_transport_max_quantity_solver packagingapp.tests.test_transport_mono_lane_transition
```

Result: 131/131 passed in 391.072 seconds. This includes all 17 final mono
tests, the Max-quantity solver, AMLB, TOPS, DGFE/infill, sequence, and
visualization/export contracts. Packaging Flow passed 3/3 in 1.783 seconds,
and `manage.py check` reported no issues.

A broader diagnostic run including the historical
`test_transport_container_engine` module completed 134 tests in 414.545 seconds
with 21 failures and five errors. Those assertions target retired Maximum,
Floor First, Accessible Sequence, and Strict Sequence contracts or old
monolithic metadata shapes; the repository testing guide explicitly classifies
those legacy-only expectations as stale unless reactivated. No attempt was made
to revive those modes as part of this mono-planner change.

No commit, push, deployment, migration, production-data operation, or
`engine_legacy.py` change was performed.
