# Known issues and regression traps

## 1. Partial shared refactors

Symptom: backend creates a shared UI contract but workflow template still renders an old inline block.

Prevention: remove or migrate the legacy template and scripts in the same coherent task; do not report full parity before that.

## 2. Duplicate hidden inputs and hard-coded IDs

Symptom: catalogue selection or result hydration works standalone but fails in Flow, especially with repeated steps.

Prevention: all IDs/names/selectors derive from `prefix`; wrapper includes scripts once; workflow owns no duplicate tool hidden fields.

## 3. Non-JSON session objects

Observed example:

```text
TypeError: Object of type PackagingMaterial is not JSON serializable
```

Prevention: shared serializer converts models, QuerySets, `Decimal`, numpy, dataclasses, and placement objects to primitives before session write.

## 4. Rotation restrictions applied only to the main region

Symptom: Container Selection produces forbidden orientations in recursive leftover subboxes.

Prevention: pass and enforce R1/R2/R3 in every `MainBox`, leftover, recursive, ranking, and render path.

## 5. Bag sealing margin drawn on the wrong dimension

Symptom: image adds sealing allowance to width or lets product occupy sealing area.

Prevention: reserve sealing space in bag length only; keep tolerance separate; test displayed geometry and calculation.

## 6. Pallet pinwheel/mosaic looks plausible but is wrong

Symptom: odd pattern for 230×170×130 on 1200×800, duplicate cartons, bad filler symmetry, or invalid interlock.

Prevention: coordinate/bounds/overlap assertions plus visual fixture; conservative interlock filtering; dedupe symmetric results.

## 7. Transport door end or view inconsistency

Symptom: doors are on the wrong end or Main/Opposite/Top/Side show inconsistent placements.

Prevention: one coordinate system and one placement list for every camera; explicit door-end fixture.

## 8. PDF exports the wrong candidate

Symptom: Top-5 selected result differs from the image/data in PDF.

Prevention: report receives selected normalized result ID/data; no independent “first candidate” lookup.

## 9. Tool actions scroll to page top

Symptom: every select/calculate action loses the working position.

Prevention: identify form/link/focus/DOM cause; use anchors/focus/partial update;
avoid timeout hacks. Full-page KolliPack tool forms now use the shared contract
in `docs/frontend/tool-scroll-preservation.md`; new programmatic submissions must
use `window.KolliPackToolScroll.submit(form)` and stable opt-in instance keys.

## 10. Global CSS replacement for local issue

Symptom: one tool looks better but other pages regress or lose the approved theme.

Prevention: inspect actual loaded CSS, reuse shared classes, add scoped rules, test app shell/sidebar/responsive widths.

## 11. Debug visuals leak into final UI

Symptom: matplotlib axes, mesh, subbox wireframes, titles, or development colors appear in customer result/PDF.

Prevention: explicit clean/debug render modes with tests/defaults.

## 12. SEO demo changes application defaults

Symptom: standalone or Flow unexpectedly opens with public demo values.

Prevention: inject demo state only in SEO-page view/context; shared engine remains stateless.

## 13. “Done” before consumer parity

Symptom: agent repeatedly asks for the next file after each partial change.

Prevention: map the vertical slice first and finish all required layers before final reporting.
## 14. Multi-product consumers left on legacy graphics

Symptom: standalone Bag or Container Selection receives improved graphics/result components, while Multi-product Bag Selection or Multi-product Container Selection still renders the former image style or copied template.

Prevention: include both multi-product tools in the initial consumer map; reuse the shared renderer/presenter/component; verify an equivalent one-row fixture and a genuine multi-row fixture before completion.

## 15. Transport packing-mode semantics leak into another mode

The specific Maximum, Accessible Sequence, and Strict Sequence examples below
are historical compatibility traps. The current active engine dispatches
Balanced Spread, Progressive Fill, and both Mixed Cargo Infill variants;
retain these notes for archived mode work, not as a claim that the retired
solvers currently produce placements.

Symptom: fixing a residual/compaction issue in one mode changes geometry in Maximum, Accessible Sequence, or Strict Sequence.

Prevention: treat `docs/domain/transport-container-engine.md` as the algorithm contract; trace dispatch before editing; prefer mode-specific helpers for mode semantics; run direct engine geometry signatures for all unaffected modes after any shared-helper change.

## 16. Strict Sequence reuses a side residual

Symptom: a later product is placed beside an earlier product behind its strict frontier.

Prevention: Strict Sequence creates one full-width forward space after every product row. Do not pass side/top/deep residuals from the completed row to the next row. This is a space-generation rule, not a compaction problem.

## 17. Maximum residual partitions become invisible physical walls

Symptom: later products show repeating gaps aligned with earlier-product split boundaries even though the physical corridor is continuous.

Prevention: Maximum Utilization must evaluate physical free geometry without treating guillotine/residual split planes as obstacles. Regression fixtures and accepted semantics are maintained in `docs/domain/transport-container-engine.md`.

## Central cumulative calculation-engine regression register

This is the single central register. Existing general traps above remain in
force. Every newly resolved engine defect must be added here with an executable
test; future work must run all active applicable cases before and after its
change. **Protected** means an active executable contract; **pending test**
means unresolved protection, not an accepted fix; **historical/retired** keeps
an obsolete contract discoverable with its replacement. Do not delete or
silently relabel a historical expectation to approve a new outcome.

### Active Container Selection input and result regressions

| ID | Defect and root cause | Protected behavior and test reference | Status |
| --- | --- | --- | --- |
| CS-REG-001 | Container Selection rejected valid negative allowances through form minima and the shared allowance sign check. | Signed allowances are applied once to nominal dimensions. Invalid effective axes stop packing across entry points. Catalogue dimensions, rendering geometry, units and rotation permissions are preserved. `packagingapp.tests.test_product_dimensional_allowance` | Protected |
| CS-REG-002 | Legacy inference treated tare values without an override flag as manual, including a default zero. | Design requires an explicit override. Each candidate has its own estimated or unavailable tare, the selected value appears in Advanced, and Flow inherits gross weight and its source. Deliberate zero and restoring the automatic source are protected by `packagingapp.tests.test_container_geometry_first`. | Protected |

### Active Transport index

Test paths below are relative to `packagingapp.tests.`. A module entry protects
every test in that module, including tests added later. Run the complete active
command in [testing-and-verification.md](testing-and-verification.md), not just
one listed witness. Engine/component is Transport Container unless specified.

| ID | Engine/component | Original defect | Root cause | Protected behavior | Automated test | Reference | Status |
|---|---|---|---|---|---|---|---|
| TC-REG-001 | Progressive Fill DGFE finalization | Freezer clean row retained an avoidable X gap | Trial-envelope position survived closure despite a clear preceding strip | `dgfe_extended`; trial 9305, clean row 8785, frontier 9085, reclaimed 220, total X 11145 mm; all quantities and physics | `test_transport_easycargo_preset.EasyCargoEngineTests.test_r3_only_closes_gap_before_freezer_clean_row`; entire `test_transport_easycargo_preset` module | Current EasyCargo 40HC preset; engine contract, DGFE finalization | Protected |
| TC-REG-002 | Mono lane compaction | Right lanes were anchored at the far wall | Materialization discarded each lane's actual Y-overlap blocker | Independent starts 10465/10845 mm in witness; supported 48-unit outcome at X 11660 mm; determinism/capacity | `test_transport_mono_lane_transition.MonoLaneTransitionEngineTests.test_per_lane_blockers_compact_the_four_lane_coordinate_witness`; `.test_supported_two_layer_transition_reaches_forty_eight` | `../domain/TCEFV1_mono_lane_compaction_regression.md` | Protected |
| TC-REG-003 | Progressive Fill Native frontier | Weak DGFE extension could displace compact P4/P2 Native | Envelope efficiency did not express the marginal cost of extra X | P4 residual 20 → P2 qty 10 stays Native; actual Pi footprint, regular-block benchmark, Native value ties | `test_transport_front_to_back.LoadFrontToBackV1Tests.test_p4_p2_preserves_native_candidate_and_rejects_weak_extension`; entire `test_transport_front_to_back` module | `../domain/transport-container-engine.md`, Progressive Fill DGFE | Protected |
| TC-REG-004 | Progressive Fill extended/deferred frontier | Valid P2/P1 extended outcome could be lost with invalid Native settlement | Candidate families/settlement need independent physical evaluation | P2 residual 3 → P1 qty 114 remains DGFE; all orientations/four strategies, vertical-only settlement, quantity carry-forward | `test_transport_front_to_back.LoadFrontToBackV1Tests.test_primary_p2_p1_top_down_row_first_candidate_matches_dgfe_geometry`; `.test_p2_p1_native_invalid_dgfe_extended_remains_eligible`; entire module | `../domain/transport-container-engine.md` | Protected |
| TC-REG-005 | Adaptive mixed-lane Product Blocks | Synchronized blocks missed compact partial/unequal tails | Fixed synchronized depth could not express independent lane lengths | Three Euro pallets at 1600 mm; 1200×801 qty 25; exact synchronized tie; stacked candidate generation; rotations/fractions/payload; baseline golden geometry | Entire `test_transport_adaptive_mixed_lane` module; `test_transport_mixed_cargo_infill.MixedCargoInfillTests.test_approved_modes_keep_captured_golden_geometry` | `../domain/TCEFV1_adaptive_mixed_blocks_regression.md` | Protected |
| TC-REG-006 | Mono rectangular transition | Fixed lane composition missed feasible stepped arrangements | One Product Block composition could not exchange lanes along X | Independent 24/23-unit oracle, unrelated rectangles, 0/1 transitions, stacked preservation, mixed-row exclusion, bounded fallback | Entire `test_transport_mono_lane_transition` module | `../domain/TCEFV1_generalized_mono_rectangular_packing_regression.md`; compaction report supersedes old X coordinates | Protected |
| TC-REG-007 | Balanced Spread regular/support continuation | Upper-row choices or terminal support changes disturbed approved phases | Orientation continuation and support heuristics require scoped precedence | Frozen Phase 1 signature, accepted supported 48-unit residual continuation, payload/upper-row orientation behavior | Entire `test_space_evenly_stabilization` module | `../domain/transport-container-engine.md`, Phase 1 and historical support helpers | Protected |
| TC-REG-008 | Balanced Spread residual closure | Per-support partitions hid valid union-supported packing | Computational residual boundaries treated as physical walls | Ordered compact Pi, local X closure, quantities 1/2/3/17, union support, gaps, deferred gravity, Native ties, JSON safety | Entire `test_space_evenly_residual_frontier_closure` module | `../domain/transport-container-engine.md`, Residual Frontier Closure V2 | Protected |
| TC-REG-009 | Mixed Cargo Infill side/top closure | Isolated strips or inconsistent state missed usable bounded residuals | Residual merging, roof planes, and quantity/item-index state must follow committed geometry | Parent anchors unchanged; side X tails; Balanced local closure; top union/elevations/blockers; re-derivation; no historical gap reopening; payload/carry-forward | Entire `test_transport_mixed_cargo_infill` module | Engine contract, Mixed Cargo Infill variants | Protected |
| TC-REG-010 | TOPS manifest regressions | Algorithm changes can disturb established mixed manifests | Whole-load results cannot be inferred from local candidates | All four original/optimized/probe manifests in all four modes; independent probes; explicit P5 flag provenance caveat | Entire `test_transport_adaptive_mixed_lane_benchmarks` module | `../domain/TCEFV1_adaptive_mixed_blocks_regression.md`, TOPS evidence | Protected |
| TC-REG-011 | Transport Max quantity service | Binary search missed feasible larger synchronized quantities | Engine feasibility is non-monotonic in requested quantity | 48/49/50 gap, larger gap, descending solver, fixed-row/payload reservation, ordered multiple Max rows, tall mono transition | Entire `test_transport_max_quantity_solver` module | Adaptive and mono compaction reports | Protected |
| TC-REG-012 | Transport loading sequence | Mode switching or infill could lose/violate sequence groups | Parent normalization and bounded filler eligibility differ by mode | Balanced forces 1; Progressive preserves groups; no cross-group side/top leapfrog; standalone/Flow UI state | Entire `test_transport_sequence_semantics` and `test_transport_sequence_ui` modules; `node packagingapp/tests/js/test_transport_sequence.js` | `../domain/transport-selection-logic.md` | Protected |
| TC-REG-013 | Supported-top adaptive eligibility | Stackable cargo loaded only 12 despite a valid 15-unit roof plan | `_fill_candidate_plan` rejected every stackable non-repeatable candidate | Top-only opt-in; 11+4 physical lanes; single commitment; partial Z stacks; unrelated geometry, quantities, rotations, payload/sequence, real gaps/shortages and bounded search | `test_transport_mixed_cargo_infill.SupportedTopAdaptiveMixedLaneTests` (all methods) | `../domain/transport-container-engine.md`, supported-top adaptive evidence; synthetic 275.5×94.2×45.01 roof | Protected |
| TC-REG-014 | Existing larger-roof capability | Eligibility improvement could disturb the already feasible 17-unit result | Guard against a lower-volume adaptive choice displacing the 16+1 construction | Preserve exact 4×4 grid plus rotated tail on 275.8×94.5×45.01; synchronized true ties; controlled A–G dimension/sequence comparisons | `test_transport_mixed_cargo_infill.SupportedTopAdaptiveMixedLaneTests.test_larger_roof_preserves_the_existing_seventeen_unit_geometry`; `.test_exact_supported_outcome_tie_preserves_synchronized_block`; `.test_complete_reconstructed_semitrailer_experiments_keep_physics_and_sequence` | Current executable fixtures; not a newly solved 17-unit optimization | Protected |
| TC-REG-015 | Transport unit/service boundary | Rounded display values or mixed units can alter physical fits | Canonical mm/kg scalars must bypass display rounding | Equivalent inch/mm inputs yield identical normalized geometry; catalogue/inherited scalars and payload authoritative; small real shortages still fail | Entire `test_transport_unit_integration` module; supported-top dimensional-shortage test in TC-REG-013 | `../domain/transport-selection-logic.md`, Manual input units | Protected |
| TC-REG-016 | Transport shared consumers | Scene/report/Flow can diverge from engine identity or session state | Separate presentation copies and non-primitive state are regression risks | Shared placements, row/color identity, camera/door contract, public presets, PDF views, prefixed Flow state, JSON serialization | Entire `test_transport_visualization` and `test_full_packaging_case` modules | Shared consumer matrix in testing guide; transport service/serializer | Protected |
| TC-REG-017 | Mixed infill support-bed construction | ExpV2-2 placed E on the floor before D and left 30 D unplaced | Homogeneous blocks maximized their own height; supported-top closure could consume an existing bed but did not construct one before upper floor commitment | Geometry-only task reconstruction 103→133 Progressive / 105→133 Balanced; D48; full support, rotations, quantity, sequence, no row loss, true-tie fallback, bounded candidates, compound-window closure, service/scene/JSON and units | `test_transport_mixed_cargo_infill.SupportBedConstructionTests` (all methods); `test_transport_unit_integration.TransportManualUnitBoundaryTests.test_support_beds_reach_scene_report_and_json_with_equivalent_units` | `../domain/transport-container-engine.md`, bounded support-bed construction; 2026-11-07 approved implementation after investigation | Protected |
| TC-REG-H01 | Retired Transport modes/metadata | Historical Maximum/Sequence/Floor-First fixtures target obsolete contracts | Active dispatcher replaced or retired those paths | Preserve the historical record; active-mode replacement coverage is TC-REG-001–016 | `test_transport_container_engine` (excluded from active suite) | Mono rectangular report, broader diagnostic record: 21 failures/5 errors in the historical combined run | Historical/retired |

IDs are stable and cumulative; a new fixture should extend an existing defect
entry or receive the next unused ID. The latest supported-top change does not
activate stackable adaptive candidates in regular Product Blocks or side infill,
and does not modify either baseline, Native/DGFE selection, or residual detection.

TC-REG-017 adds a bounded compound choice before upper floor commitment in an
additional run of the existing infill orchestration. This is the explicit narrow
exception to TC-REG-009's ordinary parent-anchor preservation: selection requires
strictly more units with no row losing quantity. Existing protected fixtures and
both baseline signatures remain required; none is retired or re-goldened.
