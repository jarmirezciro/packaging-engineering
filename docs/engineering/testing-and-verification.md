# Testing and verification

## Test layers

### Domain unit tests

Test formulas, placements, bounds, overlap, orientation restrictions, ranking, and governing constraints without Django templates.

### Service/serializer tests

Test:

- manual and catalogue inputs normalize identically;
- engine results serialize to primitives;
- selected candidate remains stable;
- report/presenter values match service values;
- numpy/Decimal/model objects do not leak into session contracts.

### Django view tests

Test:

- GET defaults;
- valid and invalid POST;
- permissions;
- correct template/context;
- PDF/image endpoints;
- public SEO demo versus normal defaults.

### Template/interaction tests

Where practical, test or manually verify:

- unique prefixed IDs;
- catalogue row selection;
- hidden-field hydration;
- repeated same-type workflow steps;
- result selection and downstream invalidation;
- no unexpected page-to-top scroll;
- collapsible instructions and 3D view controls.

## Shared consumer matrix

Every relevant change should record:

| Surface | Automated | Manual | Result |
|---|---|---|---|
| Standalone |  |  |  |
| Packaging Flow |  |  |  |
| Multi-product Container |  |  |  |
| Multi-product Bag |  |  |  |
| SEO/public |  |  |  |
| PDF/report |  |  |  |
| Catalogue source |  |  |  |

## Geometry assertions

For placement engines, tests should assert data, not only snapshots:

- `x >= min_x`, `y >= min_y`, `z >= min_z`;
- placement max coordinates stay within usable bounds/overhang;
- pairwise boxes/rectangles do not overlap;
- count equals placement list length;
- orientation is allowed;
- total weight and height are recomputed from primitives;
- deterministic ordering.

## Visual regression fixtures

Use stable fixtures for known sensitive layouts:

- container leftover packing;
- pallet 230×170×130 on 1200×800 pinwheel/mosaic;
- bag sealing margin displayed on length;
- transport door end and Main/Opposite/Top/Side views;
- base product L/W/H labels;
- equivalent one-row fixtures render identically in standalone and the related multi-product tool;
- genuine multi-row Bag/Container fixtures use the current shared graphics rather than legacy renderers.

Images may be compared with coordinate fixtures or approved snapshots, but never use image appearance as the only correctness test.

## Django checks and commands

Use commands actually configured in the repository. Typical examples:

```powershell
python manage.py check
python manage.py test <relevant_app_or_test_module>
```

Do not run a broad destructive migration or production command as a substitute for focused verification.

## Transport Container engine regression contract

### Permanent cumulative policy (all calculation engines)

Before every engine edit, read the applicable engine contract and the central
register in [known-issues-and-regressions.md](known-issues-and-regressions.md).
Identify every active applicable case, execute its tests, and record a baseline
(including counts/signatures for affected packing fixtures). After the edit,
execute the cumulative applicable suite again, investigate every changed
historical result, and report exact commands and pass/fail/skip totals. Do not
run unrelated engines unless a shared dependency affects them.

Every confirmed, resolved engine defect requires an executable test and a
stable central register entry with the defect, root cause where established,
protected behavior, exact test path/module, reference, and status. The register
is cumulative: retain historical entries, and explain any explicitly approved
retirement plus replacement test. Never silently rewrite expected geometry or
counts to make a regression pass. Passing a new test while breaking an active
older case does not complete a task.

### Complete active Transport suite

This is the required baseline and final command for **every Transport engine
change**, including changes to one infill context. It includes all modules in
the active Transport register, service/unit boundaries, standalone/public/Flow,
scene serialization, and PDF contracts. Add new Transport regression tests to
these modules or extend this command when a new module becomes necessary.

```powershell
.\.venv\Scripts\python.exe manage.py test packagingapp.tests.test_transport_mixed_cargo_infill packagingapp.tests.test_transport_adaptive_mixed_lane packagingapp.tests.test_transport_adaptive_mixed_lane_benchmarks packagingapp.tests.test_transport_front_to_back packagingapp.tests.test_transport_mono_lane_transition packagingapp.tests.test_transport_easycargo_preset packagingapp.tests.test_transport_sequence_semantics packagingapp.tests.test_space_evenly_stabilization packagingapp.tests.test_space_evenly_residual_frontier_closure packagingapp.tests.test_transport_max_quantity_solver packagingapp.tests.test_transport_unit_integration packagingapp.tests.test_transport_visualization packagingapp.tests.test_transport_sequence_ui packagingapp.tests.test_full_packaging_case --noinput
.\.venv\Scripts\python.exe manage.py check
node packagingapp/tests/js/test_transport_sequence.js
```

`test_transport_container_engine` contains retired-mode and old metadata
expectations and is **historical/retired**, not part of this active command.
Its active behavior is covered by the newer registered mode-specific modules;
do not conflate historical failures with active regressions or reactivate those
algorithms as a side effect. See the mono rectangular regression report for
the previous diagnostic failure record.

Supported-top adaptive tests live in
`test_transport_mixed_cargo_infill.SupportedTopAdaptiveMixedLaneTests`. Protect
the generated 15-unit unequal-tail construction, real supported-top selection,
existing 17-unit coordinates, repeatable tie preference, single commitment,
partial Z stacks, physical shortages, payload, rotations, sequence, union/gap
support, scaling, quantity/candidate bounds, and controlled seven-row outcomes.
An inch/mm service-normalization equivalence test is a different experiment
from retaining the same numeric geometry at a different physical scale.

TC-REG-017 support-bed tests are included in the same active command:
`test_transport_mixed_cargo_infill.SupportBedConstructionTests` and the
support-bed service/scene/JSON/unit-equivalence method in
`test_transport_unit_integration.TransportManualUnitBoundaryTests`. Keep the
ExpV2-2 task reconstruction separate from the public preset and EasyCargo's
different sequence groups. The principal benchmark omits payload and requires
133/133 in both mixed modes, including D48. Protect no-row-loss outcome selection,
true ties, full support and shortages, sequence isolation, bounded search,
quantity/index carry-forward and side/top closure of the compound window.
Test changed stackability on older residual fixtures without rewriting their
original expectations. Configured-payload checks remain part of the suite.

The current active `engine.py` dispatch implements the unchanged Balanced Spread
and Progressive Fill baselines plus their opt-in Mixed Cargo Infill variants.
Progressive Fill is canonicalized to `front_to_back`; the historical
`maximum_utilization` values remain compatibility aliases. Older fixture material may refer to the
former Maximum, Accessible, or Strict Sequence implementations; those legacy
paths are not imported by the current engine. Run focused checks for both
approved baselines and the affected infill variants; treat failures isolated
to legacy-only modes as stale
compatibility expectations unless a task explicitly reactivates one.

Before changing Transport Container packing behavior, run or establish a direct engine regression module (preferably `packagingapp/tests/test_transport_container_engine.py`). These tests are independent of Three.js/HTML and complement visualization tests.

For each protected mode fixture, record a deterministic geometry signature containing at least `row_index`, `x`, `y`, `z`, `l`, `w`, and `h`, plus loaded counts by row. Assert the shared physical invariants (bounds, no positive-volume overlap, allowed orientations, support/stackability, and payload).

Max-quantity service regressions must test the service separately from direct
engine geometry. Include at least one non-monotonic request sequence where a
smaller quantity is not fully packed but a larger synchronized-block quantity
is fully packed. Assert that all active modes return the largest fully packed
quantity within the physical/capped bound, fixed rows and payload remain
authoritative, multiple automatic rows retain row-order semantics, and the
implementation contains no fixture-specific dimensions or quantities.

Mono-product lane-transition regressions must exercise the same production
entry point in all four active modes with transition limits zero and one. Use
an independent rectangle oracle for any certified stepped arrangement, and run
the shared physical validator over every engine result. Coverage must include
multiple unrelated rectangle families, total-dimension perturbations, quantity
sweeps, uniform scaling, swapped input axes, rotated containers, R1/R2/R3 and
disabled rotations, payload, fractional dimensions, one-layer stackable parity,
true multi-layer preservation, deterministic repeated signatures, zero-quantity
rows, identical-but-distinct positive rows, narrow/short containers, and a
thousands-of-units cap fallback. Assert candidate/configuration counts remain
within the documented bounds and label non-certified results as best found.
Mixed-cargo signatures, TOPS fixtures, DGFE, residual closure, and infill must
remain unchanged because the mono whole-outcome pass is ineligible there.

For a change scoped to one mode:

- the changed mode receives explicit acceptance assertions;
- unaffected established modes must keep their accepted count/signature fixtures unless the task explicitly approves a semantic change;
- a shared-helper change is incomplete until every unaffected established mode has been checked;
- visual appearance alone is never sufficient evidence of a packing-engine fix.

Mixed Cargo Infill regression must additionally assert that the parent anchor
signature is unchanged, filler quantity carries forward, side residuals are
derived from committed XY geometry, complete-face-compatible X/Y residuals
merge without overlap, partial fillers preserve their unused X tails, and
Progressive Fill sees residuals produced by the committed local frontier/DGFE
geometry. Balanced Spread Infill must close every committed residual frontier in
its own X window, synchronize the same remaining/item-index/weight state, and
then run the separate supported-top closure only above local, coplanar,
stackable, roof-clear support unions. Top closure must re-derive after each
block, preserve side/top accounting, validate union support and overlap, and
report explicit no-fit reasons for supported residuals left unused. Sequence
groups cannot leapfrog, payload remains authoritative, and diagnostics keep
historical gap searches, backtracking, and beam states at zero. High-quantity
fixtures must show candidate counts bounded by geometry rather than requested
units.

Balanced Spread residual regression must preserve the exact Phase 1 Product Block
signature and cover ordered anchor selection, quantities 1/2/3 and a larger
arbitrary residual, whole-frontier population, contiguous union support,
unsupported gaps, non-stackable lower and upper placements, payload limits,
restricted rotations, no-residual and X-exhausted cases, both Bottom-Up and
deferred candidates, Native preference on an extension-efficiency tie,
deterministic placements, and JSON-safe diagnostics.

Progressive Fill regression must additionally cover four residual strategies
per enabled current orientation and both Native/DGFE family outcomes, arbitrary
residual quantities, placement-derived Pi X footprints, first-clean-row
envelope closure, all-orientation incoming-product evaluation, vertical-only
deferred settlement, collision-free paths, coplanar union support,
non-stackable rejection, quantity carry-forward, and JSON-safe candidate
diagnostics. Preserve the compact Native fixture for P4 residual 20 → P2
quantity 10 and the DGFE fixture for P2 residual 3 → P1 quantity 114. Assert
that Pi compactness precedes local efficiency, DGFE marginal extra-X value is
compared with the shared Pi+1 Product Block utilization, equal value prefers
Native, no-regular-block fallback is deterministic, and a valid DGFE outcome
may survive an invalid Native settlement.

Use the canonical fixture definitions and mode semantics in `docs/domain/transport-container-engine.md`; do not duplicate the complete fixture specification here.
