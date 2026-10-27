# TCEFV1 mono-product lane-transition compaction regression

## Root cause

The existing `_mono_transition_candidate()` calculated each right lane's
actual Y-overlap blocker, `blocking_end`, and used it to calculate the number
of valid repetitions. It then discarded that value and placed the lane at
`container["L"] - count * lane_length`. This preserved the count but anchored
every right lane at the far wall, leaving an avoidable internal X void.

The correction retains the per-lane count formula and materializes each right
lane at its own `blocking_end`. Different Y-overlap sets therefore produce
different X starts. Vertical layers are displaced together with their floor
cell. The existing shared 3D validator still guards the candidate before it
can become the incumbent.

## Screenshot fixture: before and after

Inputs: container 12032 × 2352 × 2698 mm; one R1-only product 1205 × 805 ×
1341 mm; quantity 48/60; stackable; zero weight; all four active modes.

| Metric | Before compaction | After compaction |
|---|---:|---:|
| Packed units | 48 | 48 |
| Floor units | 24 | 24 |
| Supported top units | 24 | 24 |
| Occupied X | 12032 mm | 11660 mm |
| Internal right-lane void | 362/382 mm relative to the witness blockers | eliminated by per-lane starts |
| Candidate count | 1232 | 1232 |
| Geometry | valid | valid |
| Support | valid | valid |
| Selection | mono transition | mono transition |

The selected implementation layout is even shorter than the required witness.
Its four lane tails are:

| Side | Y start | Orientation L×W | Quantity | Floor quantity | X start | X end |
|---|---:|---|---:|---:|---:|---:|
| Left | 0 | 805×1205 | 14 | 7 | 0 | 5635 |
| Left | 1205 | 1205×805 | 10 | 5 | 0 | 6025 |
| Right | 0 | 1205×805 | 10 | 5 | 5635 | 11660 |
| Right | 805 | 805×1205 | 14 | 7 | 6025 | 11660 |

The focused four-lane coordinate witness separately fixes the left endpoints at
10465 and 10845 mm and verifies the right starts are exactly those two values.
That test is a geometry assertion only; neither coordinate is present in
production logic.

All four modes return the same 48-unit compact geometry and repeated runs have
identical placement signatures. The Max qty service now returns 48 for the
same Auto max input. Its mono lower-bound probe avoids re-running the expensive
transition search for every rejected quantity above the validated bound; the
existing descending baseline search remains in place for non-monotonic mode
behavior.

## Generalization and stack boundaries

The compaction rule uses only actual lane Y intervals, orientations, counts,
and container length. It does not identify pallets, names, 1205/805 dimensions,
48 units, or a particular container. It applies to the existing non-pallet
rectangular families and to right lanes overlapping one or multiple left lanes.
Empty Y-overlap sets use blocker X=0 and remain subject to the shared geometry
validator.

The transition extension supports one floor layer or two identical-footprint
supported layers. A product whose enabled orientation permits more than two
layers remains on the established supported Product Block path; this protects
the existing deep-stack behavior and avoids turning the bounded mono compactor
into a second 3D engine. `max_lane_transitions` remains limited to 0 or 1, all
candidate/configuration/placement caps remain unchanged, and mixed cargo never
invokes the mono pass.

Representative post-compaction measurements for the nonstackable canonical
footprint matrix (all four modes) were:

| Total dimension increase d | Packed | Occupied X |
|---:|---:|---:|
| 0 | 25 | 12000 |
| 5 | 24 | 11660 |
| 10 | 24 | 11720 |
| 15 | 24 | 11780 |
| 20 | 24 | 11840 |
| 25 | 24 | 11900 |
| 30 | 24 | 11960 |
| 40 | 23 | 11680 |
| 50 | 23 | 11800 |
| 60 | 23 | 11920 |

Counts and physical validity are unchanged; the compaction can select a
shorter equal-count mono outcome, including the d=40/50/60 cases. The standard
25-unit and 24-unit capacity proofs remain the same.

## Verification

Focused commands and results:

```powershell
.\.venv\Scripts\python.exe manage.py test packagingapp.tests.test_transport_mono_lane_transition.MonoLaneTransitionEngineTests.test_per_lane_blockers_compact_the_four_lane_coordinate_witness packagingapp.tests.test_transport_mono_lane_transition.MonoLaneTransitionEngineTests.test_supported_two_layer_transition_reaches_forty_eight packagingapp.tests.test_transport_max_quantity_solver
```

The coordinate witness and two-layer engine tests passed. The Max solver suite
passed 6/6 after preserving the existing mocked non-monotonic call contract.
The screenshot Auto max path was measured at 48 loaded units in approximately
1.7 seconds per mode in the local service probe after the lower-bound shortcut.

The active mixed/TOPS/DGFE/infill/sequence/visualization Transport suites passed
115/115 in 416.994 seconds after this patch. Packaging Flow passed 3/3 in
13.694 seconds, and `manage.py check` reported no issues. The full mono module
passed 19/19 in 176.695 seconds. The retired historical
`test_transport_container_engine` expectations are still outside this scope
and are documented as stale compatibility tests.

No mixed-cargo algorithm, DGFE Native/Extended logic, residual support-surface
logic, renderer, session contract, or `engine_legacy.py` was changed.
