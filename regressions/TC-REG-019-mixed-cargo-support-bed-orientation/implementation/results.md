# TC-REG-019 — Approved bounded implementation, remaining target open

The owner approved the Phase 1 plan. The two fixed-policy extension is now
implemented locally on `production`. **Engine output is 119 units in the R3
Progressive Infill reference case; the 123-unit target remains unresolved.**
No further packing policy, intermediate support tier or frontier behavior was
added beyond the approved plan.

**Subsequent screenshot follow-up:** the owner's all-stackable configuration
reproduces 83 units and bypasses both constructed-bed paths. The 119-unit result
above applies to the earlier B/E=false fixture. See
[the separate diagnosis](../stackable-screenshot.md); this additional eligibility
gap remains unresolved and no packing behavior was changed during that check.

## Implemented behavior

`engine.py` preserves the original public constructor body in
`_pack_container_approved()`, including its TC-REG-017 full-request support-bed
outcome. The public entry point keeps that complete result as incumbent.
Incomplete eligible infill requests can evaluate two additional complete runs
through the same mode orchestration: **projected** and **compact**.

The new chooser uses existing bounded count sampling to derive homogeneous
foundation shapes, and the existing Product Block generator/fill planner to
populate the actual roof with a partial or complete non-stackable cap, including
adaptive mixed-lane caps. It attempts at most 256 bed/roof configurations per
window and materializes at most 512 bed+cap units. The projection ranks candidates
without rejecting a feasible cap merely because its estimate is worse.

The original modes, sorting, orientation families, physical tolerances, regular
blocks, Native/DGFE evaluation, Pi priority, extension efficiency, deferred
settlement, side/top infill, Balanced residual closure and mono transitions are
unchanged. Only an uncommitted compound in an additional construction can differ.
There are no permutations, historical gap scans, backwards moves or search trees.

Both new complete outcomes are validated for identity, rotations, sequence,
indices/quantities, mass/payload and shared physical geometry. A trial must load
strictly more total units and reduce no row against the approved incumbent.
Equal totals, invalid geometry or row loss retain the exact incumbent placements.
`*_infill_partial_support_beds` records primitive policy/outcome diagnostics.
Existing service/serializer/scene/report/Flow consumers use the same placements.

## Reference results

The original input fixture and all Phase 1 evidence remain unchanged. A is
15.70×55.10×63.00 inches, not TC-REG-017's 15.75×55.15 variant. B/E remain
non-stackable and the service performs canonical mm/kg conversion.

Progressive Infill counts are A–G:

| R permissions | Approved before | Implementation | Total before → after | B fully on A after |
|---|---|---|---:|---:|
| R1 | 30,17,16,0,8,0,0 | 30,17,16,14,10,0,0 | 71→87 | 0 |
| R2 | 9,17,0,0,0,0,0 | 30,17,0,0,2,2,0 | 26→51 | 10 |
| R3 | 26,17,10,0,0,0,0 | **30,17,16,48,8,0,0** | **53→119** | **15** |
| R1+R2 | 30,17,16,6,8,0,0 | 30,17,16,27,12,0,0 | 77→102 | 0 |
| R1+R3 | 30,17,16,42,14,4,4 | Same | 127→127 | 15 |
| R2+R3 | 30,17,16,30,14,4,0 | 30,17,16,36,14,4,4 | 111→121 | 15 |
| R1+R2+R3 | 30,17,16,42,14,4,4 | Same | 127→127 | 15 |

Balanced Infill retains its R3 outcome `[0,13,4,42,14,0,0]`, 73 units. Its
R1+R2 case improves 110→118; the other rotation configurations keep their
incumbents. Both baseline modes retain all seven exact placement signatures.
Every mixed-mode row is preserved or improved in the 28 saved mode/rotation
comparisons. Physical validation and deterministic repetitions pass.

All eight independent/control cases with previously dominating manual witnesses
now meet or exceed those witnesses. The equivalent physical R1/R2/R3 control
improves `[0,3]` to `[6,3]`; the unrelated aspect-ratio case reaches `[2,3]`.
At payload 5 the former reaches `[2,3]`. Height, payload, sequence, insufficient
support, completed requests and zero-budget fallbacks retain their constraints.

## Why the optimization target remains open

The R3 projected construction selects A30 supporting B15, then continues through
ordinary blocks and infill. Later it selects a D48/E8 compound. That bed consumes
189 inches of X and ends around X=529.4 inches; the remaining length cannot fit
a 47.2-inch F/G unit. The compact construction loses C quantity and is rejected.

The separate `reproduce.py --assert-target` still exits **1**, explicitly showing
**119 < 123**. The threshold and the original evidence were not weakened or
rewritten. The original 123-unit witness proves headroom against the original
53-unit baseline; its E4 count does not dominate the new E8 result.

A further **independent 127-unit certificate** retains every quantity of the
119-unit result: `[30,17,16,48,8,4,4]`. It keeps D's roof at 62.8 inches, inserts
one F/G layer of 21.7 inches at the eight E bases, and places E above it:

```text
D 62.8 + F/G 21.7 + E 21.7 = 106.2 inches <= 108 inches
```

It fits the existing X/XY footprints and passes both the independent physical
validator and the complete-outcome geometry gate. Its complete coordinates,
quantity/mass checks and signature are in `127-unit-certificate.json.gz`.
**This is an explicit feasibility certificate, not an engine-generated result.**

The approved compound has one homogeneous foundation row and immediately
commits its non-stackable cap. Existing infill cannot subsequently insert F/G
under that cap. Evaluating the certificate requires a new bounded construction
decision, such as reserving cap height while admitting one supported intermediate
layer before cap commitment. That changes compound synthesis/infill ordering
and is outside the two-policy approval. It has not been implemented or claimed
proven. The approved plan explicitly requires reporting this remaining gap and
seeking a scoped decision rather than rewriting the same heuristics indefinitely.

### Proposed next scope — not implemented

One additional bounded construction could keep the current two-policy result
as incumbent and evaluate **one intermediate supported tier before cap
commitment**:

```text
construct the homogeneous foundation at the active uncommitted frontier
reserve the selected cap's actual height within this fixed window
admit eligible same-sequence, later, stackable intermediate rows
    use existing block generation/materialization and support validation
    allow at most one physical layer at each intermediate position
re-derive real coplanar support planes
populate the original non-stackable cap using existing top-fill plans
continue through the parent mode without reopening the window
accept only a valid complete outcome that improves total and loses no current row
```

This introduces a bounded multi-row compound, not a global reorder or an
insertion beneath already committed cargo. The current 119-unit R3 result,
including E8, remains incumbent. At most one extra complete parent run raises
the maximum from four to five. Keep a 256-configuration window budget and count
foundation, intermediate and cap units together within 512 materialized units.
A shortage, unequal support heights, no fit, payload/sequence conflict or
exhausted budget must keep the incumbent, with deterministic diagnostics.

Coding would be restricted to an opt-in staging helper/commit path and internal
policy plumbing in `engine.py`. Ordinary infill, both current policies,
Native/DGFE/settlement and baseline modes retain their behavior. Tests would
cover the 127-unit physical reference, independent three-tier geometries,
incomplete middle layers, support gaps/heights, all rotation families,
quantity/index/mass continuation, payload/sequence, no-row-loss selection and
hard budget fallback. The complete cumulative suite, all archived signatures
and controlled serial timing comparison would run again.

Acceptance requires at least 123 units in the R3 reference **without reducing
any row of the current 119-unit result**. The 127-unit certificate is not a
promised algorithm outcome; whether this policy finds it remains unproven.
This is the concrete additional scope requiring a new decision.

## Validation

- Fresh pre-edit cumulative suite: **210 passed**, no failures/errors/skips,
  **284.139 s** (`baseline-suite.log`).
- Initial focused support-bed/unit suite: **28 passed**, **33.034 s**
  (`focused-tests.log`).
- Final complete active Transport command: **220 passed**, no failures/errors/
  skips, **453.033 s** (`final-suite.log`). Ten added test methods protect the
  new behavior. Existing golden assertions and quantities are unchanged; only
  the existing constructor mocks were extended for two additional calls.
- Django system check: passed, no issues.
- Node sequence checks: **2/2**; editable-unit checks: **8/8**.
- All 28 reference mode/rotation results: physical checks and per-row incumbent
  preservation passed; baseline-mode signatures match the pre-edit capture.
- Stronger 123-unit target: **unresolved**, expected failing assertion at 119.

- Archived cohort: **700 cases × four modes = 2,800 physically valid outcomes**,
  **zero quantity regressions, zero signature differences, zero invalid results**.
  `br700-comparison.json` records 923.649 s with four worker processes. The exact
  CSV hash remains `8ed970b177b832a4f89a1fb0201ccf5fef48a1b939cbd1975ce9e984fd4f6536`.
  These manifests have no eligible partial-bed requests; they protect unchanged
  parent behavior rather than measuring the new planner.
- Source audit: the approved constructor body is unchanged after its rename;
  **116 existing engine functions, all dataclasses and the public signature are
  unchanged**. Only the three internal plumbing/commit functions and the public
  wrapper differ, plus four new helpers. All previous assertion expressions in
  both modified test modules are preserved (`source-audit.json`).
- Immutable Phase 1 writer guard, Python syntax/artifact checks and final
  `git diff --check`: passed.

Engine SHA-256 after implementation:
`75baac144a2d9c9203e185d9e94ab3c2726c582cb8c1a1ae474935e4d3e17d3c`.
The source, outcome and cohort records all identify the same engine bytes.

### Controlled runtime and explained cost

After the cohort workers finished, each case was warmed up and measured through
five alternating serial calls to the checksum-verified approved engine and the
implementation. The old Git blob's LF line endings were restored to the recorded
Windows CRLF representation and verified against the original SHA before loading
it in memory solely for measurement. No alternate engine is used by the app.

Median engine-call times, milliseconds (`serial-timing.json`):

| R permissions | Approved | Implementation | Added time |
|---|---:|---:|---:|
| R1 | 15.134 | 81.463 | 66.329 |
| R2 | 16.514 | 109.969 | 93.455 |
| R3 | 47.807 | 229.366 | 181.559 |
| R1+R2 | 109.024 | 452.941 | 343.917 |
| R1+R3 | 170.989 | 601.408 | 430.419 |
| R2+R3 | 84.714 | 667.878 | 583.164 |
| R1+R2+R3 | 271.342 | 1035.462 | 764.120 |

This exceeds the plan's investigation threshold and is a material tradeoff,
including on trials that retain the incumbent. Profiling identifies the added
bed/upper-block generation as the main cost (`profile-cost.json`): R3 attempts
292 + 147 configurations across the two policies' windows; all rotations attempt
474 + 474. Each individual window still respects 256. The profiled complete calls
make 546 and 1,135 Product Block-generator calls respectively, including their
parent work; both include only two complete-outcome validation calls. The work
is bounded but not free. The implementation does not claim unchanged runtime.

Parallel suite/cohort wall times are not isolated performance comparisons.
The serial medians above are local observations, not CI latency guarantees or
evidence that every possible eligible request has the same overhead. Further
staging must be evaluated against both this cost and the still-open target.

The cohort helper was restarted once to normalize integer row keys against JSON
string keys in its comparison code. No expected quantities, coordinates or
signatures were changed. Comparisons use the original SHA-verified CSV conversion
and immutable Phase 1 outputs.

## Shared-consumer assessment

| Surface | Evidence |
|---|---|
| Standalone/public/Flow | Existing active view, sequence, visualization and full-case modules pass; all call the shared transport service |
| New partial construction | Imperial/mm service calls yield matching canonical geometry, primitive session data and selected partial-bed diagnostics |
| Three.js/PDF/report | Shared scene items and report summary contain the selected placement count; active report/visualization contracts pass |
| Catalogue/inherited units | Existing canonical input and boundary tests pass; no normalizer or catalogue code changed |
| JavaScript/hydration | Existing 10 sequence/unit checks pass; no UI controls or session inputs added |
| Multi-product Container/Bag | Not Transport consumers; their separate engines are unchanged |

## Reproduction and file scope

From `C:\PackagingEngineering`:

```powershell
$casePath = 'regressions/TC-REG-019-mixed-cargo-support-bed-orientation'
.\.venv\Scripts\python.exe "$casePath/reproduce.py" --output "$casePath/implementation/results.json.gz" --assert-target
# Expected exit 1: 123-unit target remains unresolved.
.\.venv\Scripts\python.exe "$casePath/validate_implementation.py" cohort --workers 4
.\.venv\Scripts\python.exe "$casePath/validate_implementation.py" timing
.\.venv\Scripts\python.exe "$casePath/validate_implementation.py" certificate
```

The full active command is unchanged in the testing guide and appears in the
historical `../verification.md`. The current implementation adds tests to its
existing modules rather than excluding the unresolved target by changing that
command. Phase 1 writers now refuse to overwrite approved evidence with a
different engine. The reproduction keeps the original defect certificate check
against the original baseline, so improvements in an individual row do not
invalidate that historical proof; the 123-unit assertion remains unchanged.

Production code changed only in `engine.py`. Tests changed in
`test_transport_mixed_cargo_infill.py` and `test_transport_unit_integration.py`.
The domain/consumer/testing contracts and central register describe the new
bounded behavior and the still-open target. This reference directory holds
the comparison, physical evidence and timing data. Pre-existing retired-LTHR
history and unrelated artifacts remain preserved.

No commit, push, merge, deployment, Railway action, production migration or
production-data write occurred.
