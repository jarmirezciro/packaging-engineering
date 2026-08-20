# Codex Task — Floor First Near-Aligned Composite Blocks (Regression-Protected)

## Recommended model

- Luna
- Extra High reasoning

## Objective

Experiment with a new packing operation **only in Maximum Utilization — Floor First**:

> **Near-Aligned Mixed-Orientation Composite Block**

The operation combines **two complete homogeneous sub-blocks of the same product**, using two distinct allowed orientations, side-by-side across the container width.

The two sub-blocks do not need to finish at exactly the same `x`. Their longitudinal ends may differ by up to **2%**, while all physical placement dimensions remain exact.

This must be implemented as an **additional bounded continuation candidate**, not as a rewrite or replacement of existing Floor First logic.

The existing Floor First behavior is the incumbent and must remain available.

---

## 1. Mandatory baseline before editing

Before modifying code:

1. Read root `AGENTS.md`.
2. Read:
   - `docs/domain/transport-container-engine.md`
   - `docs/domain/transport-selection-logic.md` when consumer behavior is relevant
   - `docs/engineering/testing-and-verification.md`
3. Inspect the current:
   - `packagingapp/utils/container_tool/engine.py`
   - `packagingapp/tests/test_transport_container_engine.py`
   - `packagingapp/tests/test_transport_visualization.py`
4. Record:
   - current branch;
   - complete `git status --short` output;
   - existing modified/untracked files;
   - test commands and results;
   - current Floor First geometry and loaded quantities.
5. Verify the exact current implementations of:
   - `_floor_first_block_candidates`
   - `_floor_first_main_block_choice`
   - `_floor_first_orientation_choices`
   - `_floor_first_continuation_candidates`
   - `_floor_first_choose_continuation`
   - `_floor_first_compare_frontier_reflow`
   - `_floor_first_fill_group`
   - `_floor_first_materialize_block`
   - `_pack_container_floor_first_blocks`
   - `_pack_container_maximum_utilization_floor_first`
6. Capture deterministic geometry signatures for the protected modes before editing.

Use the repository’s configured Python environment. In the current local setup, the focused command is equivalent to:

```powershell
$env:DEBUG = 'true'
$env:SECRET_KEY = 'test'
$env:ALLOWED_HOSTS = 'localhost'
.\.venv\Scripts\python.exe manage.py test `
  packagingapp.tests.test_transport_container_engine `
  packagingapp.tests.test_transport_visualization
```

**STOP if the baseline Transport tests fail before this feature.** Do not compensate by modifying expected tests.

### Worktree safety

The repository may contain unrelated user edits and generated files. Preserve them.

Do not run:

- `git reset --hard`;
- `git checkout -- ...`;
- `git clean`;
- broad formatting over the repository;
- package installation or build commands that rewrite unrelated generated files.

Use path-scoped diffs and preserve all unrelated modifications.

---

## 2. Scope and mode isolation

Change behavior only for:

```text
maximum_utilization_floor_first
```

Do not modify behavior of:

```text
maximum_utilization
space_evenly
accessible_sequence_loading
sequence_loading / strict_sequence_loading
```

Do not change:

- UI;
- forms;
- Three.js;
- reports or PDF export;
- Packaging Flow;
- service/session serialization contracts;
- shared Sequence helpers;
- shared collision/support/payload semantics.

Preferred implementation files:

```text
packagingapp/utils/container_tool/engine.py
packagingapp/tests/test_transport_container_engine.py
docs/domain/transport-container-engine.md
docs/engineering/decision-log.md
```

Do not modify unrelated files unless a test proves a required consumer contract must be updated.

---

## 3. Existing Floor First behavior is protected

Preserve all existing Floor First behavior, including:

- homogeneous main-block candidates;
- Space Evenly-derived `ny × nz` transverse candidate mathematics;
- current main-block selection;
- current alternate-orientation consideration;
- current residual fill;
- current frontier/reflow behavior;
- current selected-frontier traversal handoff behavior;
- exact physical free-space subtraction;
- support and gravity rules;
- current Maximum Best-Fit capacity guard.

The new operation is:

```text
existing Floor First
        +
additional bounded composite continuation candidate
```

It is not:

```text
replace Floor First with composite packing
```

Do not add composite main blocks at `x = 0` in V1.

---

## 4. Protected canonical regression case

Use this exact case as a regression fixture:

Container:

```text
L = 12039 mm
W = 2362 mm
H = 2692 mm
```

Products, all stackable, R1 enabled and R2/R3 disabled:

```text
P1 / row 0: SKU302473
L = 457.2, W = 279.4, H = 317.5
qty = 375, sequence = 4

P2 / row 1: SKU503739
L = 431.8, W = 318.77, H = 317.5
qty = 405, sequence = 3

P3 / row 2: Case Pack 12
L = 558.8, W = 377.444, H = 317.5
qty = 288, sequence = 1

P4 / row 3: Case Pack
L = 558.8, W = 355.6, H = 381.0
qty = 160, sequence = 2
```

The current protected behavior loads:

```text
P1 = 375
P2 = 405
P3 = 288
P4 = 160
total = 1228
unplaced = 0
```

The current P4/P2 and P2/P1 frontier behavior is a protected reference. In particular, the existing P2/P1 frontier search is bounded at 24 traversal candidates and currently selects the established row-first frontier solution.

Capture and compare the full deterministic signature:

```text
(
    row_index,
    item_index,
    x,
    y,
    z,
    l,
    w,
    h,
)
```

Do not silently update this fixture merely because a composite candidate exists. Any intentional geometry change must be demonstrated as an improvement against the stated Floor First objectives and reviewed separately.

---

## 5. Definition: homogeneous sub-block

Each constituent block is a complete integer grid:

```text
Q = nx × ny × nz
```

with exact dimensions:

```text
L = nx × l
W = ny × w
H = nz × h
```

There are:

- no missing cells;
- no partial rows;
- no partial layers;
- no L-shapes;
- no irregular internal filling.

For every selected composite:

```text
materialized_A_count = nx_A × ny_A × nz_A
materialized_B_count = nx_B × ny_B × nz_B
```

---

## 6. Definition: near-aligned composite

A composite contains exactly two sub-blocks:

```text
Sub-block A + Sub-block B
```

Requirements:

- same product row;
- same `row_index`;
- same product identity;
- two distinct allowed orientations from that row;
- same starting `x`;
- same starting `z`;
- adjacent across `y`;
- complete homogeneous grids;
- same final height exactly within `_EPS`;
- longitudinal ends equal or near-aligned;
- relative longitudinal mismatch no greater than 2%.

Coordinate convention:

```text
x = back wall → doors
y = container width
z = floor → ceiling
```

The outer envelope may be approximately cuboidal, but the actual sub-block placements remain exact.

---

## 7. Parent-space geometry contract

The composite must be generated inside **one existing real `Space`**.

For a parent space:

```text
Space(x, y, z, L, W, H)
```

the canonical V1 placement is:

```text
A starts at (x, y, z)
B starts at (x, y + composite_width_A, z)
```

Both blocks must satisfy:

```text
x + length_A <= space.x + space.L
x + length_B <= space.x + space.L
y + width_A + width_B <= space.y + space.W
z + common_height <= space.z + space.H
```

Additional rules:

- Do not span multiple free spaces.
- Do not merge free spaces merely to create a composite.
- Do not cross an artificial partition in V1.
- Do not place one sub-block in a different `x` or `z` layer.
- Do not use a bounding-envelope subtraction.
- The exact individual placements must be subtracted from the existing free-space geometry.

Use one deterministic A/B lateral order. Do not add mirrored left/right composite search in V1.

The candidate must be anchored using the same continuation/frontier rules as existing Floor First continuation candidates. It must not appear at an arbitrary distant space merely because that space has better width utilization.

---

## 8. Same product and two orientations only

The helper API should guarantee same-product composition structurally.

Never create:

```text
Product A sub-block + Product B sub-block
```

The candidate must use exactly two distinct allowed orientation tuples from one product group.

Do not implement:

- three-orientation composites;
- recursive composites;
- composites across product rows;
- mirrored A/B search;
- global orientation backtracking.

If more than two allowed orientations exist, evaluate only a deterministic bounded set of orientation pairs. Define an explicit cap in code and expose the evaluated count diagnostically.

---

## 9. Explicit integer width-composition search

For orientation A:

```text
w_A = item width
ny_A = number of A lanes
```

For orientation B:

```text
w_B = item width
ny_B = number of B lanes
```

For parent-space width `W`:

```text
ny_A × w_A + ny_B × w_B <= W
```

For a true mixed-orientation composite:

```text
ny_A >= 1
ny_B >= 1
```

Examples that must be understood by the implementation:

```text
W = 11, w_A = 7, w_B = 2
7 × 1 + 2 × 2 = 11

W = 11, w_A = 7, w_B = 3
7 × 1 + 3 × 1 = 10
```

Exact width filling is preferred but not required.

Define:

```text
width_utilization = composite_width / parent_width
```

The candidate must never exceed parent width.

Prefer higher width utilization when other relevant metrics are equal.

Use a Floor-First-local helper such as:

```python
_floor_first_composite_width_compositions(...)
```

Do not modify the Sequence `_lane_compositions()` helper.

---

## 10. Bounded width search

Do not perform a broad Cartesian search.

For a given orientation pair, the mathematical range is:

```text
1 <= ny_A <= floor(W / w_A)
```

For each useful `ny_A`, derive:

```text
ny_B_max = floor((W - ny_A × w_A) / w_B)
```

Evaluate only:

- `ny_B_max`;
- optionally `ny_B_max - 1` when useful for quantity or alignment diversity.

For very small products where `ny_A` could become large, use a deterministic sampled set consistent with existing bounded candidate generation. Define an explicit maximum number of width compositions per orientation pair.

Expose:

```text
floor_first_composite_width_compositions_evaluated
```

---

## 11. Bounded longitudinal alignment search

For each width composition, derive useful longitudinal counts:

```text
L_A = nx_A × l_A
L_B = nx_B × l_B
```

Define:

```text
alignment_error_absolute = abs(L_A - L_B)
alignment_error_relative = abs(L_A - L_B) / max(L_A, L_B)
```

Accept only:

```text
alignment_error_relative <= 0.02 + _EPS
```

Examples:

```text
3 × 800 = 2400
2 × 1200 = 2400
error = 0%

4 × 2500 = 10000
3 × 3300 = 9900
error = 1%

10000 vs 9600
error = 4%
reject
```

For a candidate `nx_A`, derive:

```text
nx_B_ideal = L_A / l_B
```

Evaluate only meaningful nearby integers, normally floor and ceiling, subject to:

- parent-space length;
- remaining quantity;
- payload;
- width composition;
- vertical count;
- stackability.

Reuse existing bounded/interesting Floor First counts where appropriate. Do not enumerate hundreds of longitudinal combinations.

Define an alignment quality for ranking:

```text
alignment_quality = clamp(1 - alignment_error_relative / 0.02, 0, 1)
```

Exact alignment must beat near alignment on an otherwise equal deterministic tie.

Expose:

```text
floor_first_composite_length_combinations_evaluated
```

---

## 12. Exact vertical construction

Require:

```text
H_A = nz_A × h_A
H_B = nz_B × h_B
abs(H_A - H_B) <= _EPS
```

The 2% tolerance applies only to X-length alignment. Never apply it to Z.

For non-stackable products:

```text
nz_A = 1
nz_B = 1
```

unless the current authoritative Floor First implementation has a stricter applicable rule.

Vertical-count search must be bounded. Do not perform an unbounded common-multiple scan.

Add tests for:

- exact equal heights;
- unequal unit heights with an exact common final height;
- near-but-not-exact final heights, which must be rejected;
- non-stackable products, which must not gain vertical stacking.

---

## 13. Quantity, payload, and identity

For A:

```text
Q_A = nx_A × ny_A × nz_A
```

For B:

```text
Q_B = nx_B × ny_B × nz_B
```

Total:

```text
Q_total = Q_A + Q_B
```

Require:

```text
Q_total <= remaining_qty
```

Also require payload feasibility:

```text
loaded_weight + Q_total × group_weight <= payload_limit
```

when a payload limit exists.

Placement identity must remain continuous:

```text
A item indices use the current item offset
B item indices begin after Q_A
later residuals begin after Q_A + Q_B
```

No duplicate or skipped item indices are permitted.

---

## 14. Physical exactness and notch preservation

If:

```text
A length = 10000
B length = 9900
```

then materialized placements must end at:

```text
max_x(A) = 10000
max_x(B) = 9900
```

Do not:

- stretch B;
- round B to 10000;
- create fake cargo;
- occupy the composite bounding envelope;
- subtract a rectangular envelope instead of exact placements.

The 100-unit longitudinal notch on B’s side remains real free space. Subtract the actual A and B placements using existing exact free-space machinery.

Do not immediately fill the notch as part of composite generation. It may be used later only if ordinary Floor First residual logic finds a physically valid placement.

The notch test must verify physical availability without depending on one particular internal `Space` partition shape. Prefer a valid probe-placement witness or an equivalent exact free-space-union assertion.

---

## 15. Pure candidate generation and materialization separation

Candidate generation must be pure arithmetic and must not mutate spaces.

It may calculate:

- orientation pair;
- `nx`, `ny`, `nz` values;
- quantity;
- exact sub-block dimensions;
- width usage;
- common height;
- alignment error;
- candidate score.

It must not perform:

- placement-vs-placement collision searches over hypothetical candidates;
- free-space mutation;
- compaction;
- session serialization.

Materialization occurs only after a candidate wins:

```text
materialize A placements
materialize B placements
subtract exact individual placements
continue with ordinary Floor First residual logic
```

Use a private immutable structure such as:

```python
FloorFirstCompositeCandidate
```

but never expose that object in engine results or session data.

Keep `SpaceEvenlyBlockCandidate` and `_floor_first_materialize_block()` semantics unchanged. Add a separate composite materializer rather than overloading the homogeneous-block materializer with ambiguous fields.

---

## 16. First integration point: continuation stage only

Do not replace the initial Floor First main block.

The existing continuation choices are approximately:

```text
homogeneous continuation A
homogeneous continuation B
residual fill
```

Add:

```text
composite continuation A+B
```

The existing homogeneous candidates must remain available and unchanged.

Prefer a separate helper:

```python
_floor_first_composite_candidates(...)
```

Do not make `_floor_first_continuation_candidates()` return mixed object types without an explicit plan/type contract.

---

## 17. Composite/frontier interaction and calculation bound

The current Floor First frontier/reflow algorithm is protected.

Do not create a Cartesian product such as:

```text
composites × tail windows × orientations × traversals
```

For V1, use this bounded strategy:

1. Generate the existing homogeneous continuation plans exactly as today.
2. Run the existing frontier/reflow evaluation exactly as today.
3. Generate a bounded set of composite continuation plans.
4. Select at most one best composite local plan per continuation boundary.
5. Compare the best composite plan against the existing reflow-selected legacy plan.
6. Preserve the legacy plan on an exact tie unless the composite has a clearly better existing Floor First structural metric.

Do not change the existing 24-candidate frontier count for legacy plans.

If composite metadata cannot safely satisfy the existing reflow helper contract, do not rewrite that helper. Compare the composite plan outside the legacy reflow search instead.

The selected frontier traversal handoff already present in Floor First must remain unchanged.

---

## 18. Candidate and plan ranking

For composite candidate generation, prefer this deterministic hierarchy:

1. Valid complete quantity.
2. Strong transverse `width × height` coverage.
3. Strong width utilization.
4. Compact occupied X length.
5. Smaller longitudinal alignment error.
6. Stable deterministic tie-break.

Useful fields:

```text
composite_width
composite_height
transverse_area
width_utilization
max_subblock_length
alignment_error_relative
alignment_quality
qty_total
```

When comparing the final composite plan with the existing Floor First incumbent:

- never replace an incumbent with lower current-product quantity;
- never replace a plan that causes lower final capacity;
- preserve the legacy incumbent on exact plan-level ties;
- do not cause geometry churn merely because a composite is available.

The composite is a layout heuristic, not a global utilization proof.

---

## 19. Floor First A/B capacity protection

Add a private development switch, not a user-facing UI control:

```python
_FLOOR_FIRST_COMPOSITE_ENABLED = True
```

The switch must allow comparison of:

```text
False → existing Floor First
True  → existing Floor First + composite candidate
```

For representative fixtures, compare enabled and disabled results.

If composite-enabled Floor First loads fewer total units or fewer units in a protected row than disabled Floor First, the enabled result must not replace the disabled result.

This guard is Floor First-only. Do not alter Maximum Utilization or the existing Best-Fit global guard.

The existing final comparison remains:

```text
Floor First result
        vs
unchanged Best-Fit result
```

Best Fit replaces Floor First only when it packs strictly greater capacity. Floor First owns capacity ties.

---

## 20. Required pure tests

### Test A — exact longitudinal alignment

Use floor rotations:

```text
A = (800, 1200, H)
B = (1200, 800, H)
nx_A = 3
nx_B = 2
```

Verify:

```text
3 × 800 = 2 × 1200 = 2400
alignment_error_relative = 0
```

Accepted.

### Test B — 1% alignment

```text
4 × 2500 = 10000
3 × 3300 = 9900
```

Verify:

```text
alignment_error_relative = 0.01
```

Accepted.

### Test C — 4% alignment

```text
10000 vs 9600
```

Verify:

```text
alignment_error_relative = 0.04
```

Rejected.

---

## 21. Required width-composition tests

For:

```text
W = 11
w_A = 7
w_B = 2
```

verify the search includes:

```text
7 × 1 + 2 × 2 = 11
```

For:

```text
W = 11
w_A = 7
w_B = 3
```

verify the search includes:

```text
7 × 1 + 3 × 1 = 10
```

and does not reject it merely because one width unit remains unused.

For every generated candidate, verify:

```text
used_width <= parent_width
ny_A >= 1
ny_B >= 1
```

---

## 22. Required physical and grid tests

Add tests for:

- complete A and B grid counts;
- exact common height;
- rejection of unequal final heights;
- width bounds;
- parent-space length bounds;
- same `x` and `z` origins;
- adjacent non-overlapping Y bands;
- allowed orientations only;
- same product row only;
- item-index continuity;
- payload feasibility;
- non-stackable `nz = 1`;
- exact physical notch preservation;
- no positive-volume overlap;
- bounds and full-base support.

---

## 23. Determinism

Identical inputs must produce:

- identical orientation-pair ordering;
- identical width-composition ordering;
- identical length and height candidate ordering;
- identical selected composite;
- identical placement coordinates;
- identical item indices;
- identical diagnostics.

Do not rely on unordered sets or dictionaries for final tie-breaking.

---

## 24. Regression protection across all modes

Run the existing regression fixtures for:

- Maximum Utilization residual continuity;
- Floor First canonical case;
- Space Evenly;
- Strict per-row full-width frontier;
- Accessible transition residuals;
- Accessible EUR quantity family 21/23/25/27/29;
- stackability;
- payload;
- orientation restrictions;
- determinism;
- visualization consumers.

Expected for unaffected modes:

```text
same quantities
same deterministic geometry signatures
```

If another mode changes:

**STOP.** Do not update that mode’s expected output.

---

## 25. Diagnostics

Add only JSON-safe primitive diagnostics, such as:

```text
floor_first_composite_enabled
floor_first_composite_width_compositions_evaluated
floor_first_composite_length_combinations_evaluated
floor_first_composite_height_combinations_evaluated
floor_first_composite_candidates_evaluated
floor_first_composite_candidates_accepted
floor_first_composite_selected
```

For a selected composite, optionally report:

```text
row_index
orientation_a
orientation_b
nx_a
ny_a
nz_a
nx_b
ny_b
nz_b
qty_a
qty_b
qty_total
length_a
length_b
width_a
width_b
composite_width
composite_height
alignment_error_absolute
alignment_error_relative
alignment_quality
width_utilization
```

Use lists, numbers, strings, booleans, and `None` only. Do not put dataclasses, engine objects, `Space` objects, `Placement` objects, or other non-serializable values into result/session data.

---

## 26. Performance

Measure at least:

1. Existing Floor First fixture where composites are irrelevant.
2. Exact-alignment fixture.
3. 1% near-alignment fixture.
4. Representative multi-product Floor First fixture.
5. The protected 1,228-unit canonical case.

Report:

```text
baseline runtime
new runtime
width compositions evaluated
length combinations evaluated
height combinations evaluated
composite candidates evaluated
composite candidates accepted
composites selected
```

Do not create brittle timing assertions in automated tests. Investigate material regressions and stop if the bounded search becomes impractical.

---

## 27. Documentation

Document the operation as experimental and Floor First-only:

> Near-Aligned Composite Block: two complete homogeneous sub-blocks of the same product, using two allowed orientations, combined across width. Their longitudinal ends may differ by at most 2%. Physical placements remain exact and any resulting longitudinal notch remains real free space.

Document that:

- it is continuation-stage only in V1;
- it does not replace the existing homogeneous continuation;
- it does not alter other modes;
- it uses bounded arithmetic search;
- it does not guarantee global optimality.

---

## 28. Explicit non-goals

Do not implement:

- composite blocks in Space Evenly;
- composite blocks in Maximum Utilization;
- composite blocks in Sequence modes;
- composite main blocks at `x = 0`;
- different product rows inside one composite;
- three-orientation composites;
- vertical alignment tolerance;
- mirrored left/right search;
- beam search;
- global optimization;
- recursive composite search;
- new compaction;
- collision optimization;
- support changes;
- payload-semantic changes;
- UI changes;
- changes to shared Sequence helpers.

---

## 29. Required implementation order

Follow this order:

```text
1. Baseline tests and geometry signatures
        ↓
2. Pure width-composition helper
        ↓
3. Pure bounded length-alignment helper
        ↓
4. Pure bounded height/common-height helper
        ↓
5. Pure composite candidate tests
        ↓
6. Composite materialization
        ↓
7. Exact notch/free-space test
        ↓
8. Integrate as an additional Floor First continuation candidate
        ↓
9. Compare against existing frontier/reflow plan without nested branching
        ↓
10. Floor First A/B capacity regression
        ↓
11. All Transport mode regression
        ↓
12. Performance benchmark
        ↓
13. Documentation and final diff review
```

Do not jump directly into Floor First orchestration before the pure candidate mathematics are tested.

---

## 30. STOP conditions

Stop and report instead of improvising if:

- baseline tests fail;
- the composite requires changing another mode;
- existing homogeneous continuation cannot remain available;
- the parent-space contract cannot be preserved;
- the width/length/height search becomes combinatorial;
- the existing frontier/reflow logic must be rewritten;
- physical notch cannot be preserved with exact subtraction;
- composite reduces established Floor First capacity;
- Best-Fit guard must be changed;
- another Transport mode changes;
- performance degrades materially;
- implementation requires changing collision, support, stackability, or payload semantics.

Do not solve these by weakening tests or silently changing acceptance criteria.

---

## 31. Final report

Return:

### Baseline

- branch;
- Git status summary;
- files already modified before the task;
- tests before modification;
- current canonical fixture quantities and geometry signature.

### Architecture found

Exact Floor First functions involved and how the continuation/frontier path works.

### Parent-space geometry

Explain the exact one-space placement contract, A/B Y order, shared X/Z origin, and bounds checks.

### Width composition

Explain the bounded integer search with an example such as:

```text
7 × 1 + 2 × 2 = 11
```

### Length alignment

Report:

```text
3 × 800 = 2 × 1200 = 2400
```

and:

```text
4 × 2500 = 10000
3 × 3300 = 9900
```

Confirm that `10000 vs 9600` is rejected.

### Physical geometry

Confirm the shorter sub-block was not stretched and that the notch remains actual free space.

### Frontier interaction

State exactly how the composite was compared with the existing frontier/reflow plan and confirm that no nested Cartesian search was introduced.

### Capacity protection

Report Floor First composite-disabled versus composite-enabled quantities and confirm the existing Best-Fit guard is unchanged.

### Regression

Report Floor First, Maximum, Space Evenly, Accessible Sequence, Strict Sequence, visualization, and determinism results.

### Performance

Report candidate counts and representative runtimes.

### Files

List exact files changed and confirm no unrelated files were modified.

### Git

Confirm:

```text
No commit
No push
No merge
No deployment
```

---

## Definition of Done

The task is complete only when:

1. Existing Floor First behavior remains available.
2. Composite logic is additive.
3. Composite logic is Floor First-only.
4. One composite contains one product only.
5. Exactly two distinct allowed orientations are used.
6. Each orientation forms a complete homogeneous sub-block.
7. The composite is generated inside one real parent `Space`.
8. Both sub-blocks share exact starting `x` and `z`.
9. The A/B Y order is deterministic.
10. Explicit integer width compositions are searched.
11. Combined width never exceeds available width.
12. Perfect width fill is preferred but not required.
13. Longitudinal ends may differ by at most 2%.
14. Exact alignment is preferred to near alignment.
15. `10000 vs 9900` is accepted.
16. `10000 vs 9600` is rejected.
17. Final sub-block height is exactly aligned.
18. Physical dimensions are never stretched.
19. The longitudinal notch remains actual free space.
20. Candidate generation uses bounded arithmetic rather than collision-heavy search.
21. Existing homogeneous continuation remains available.
22. Composite search is not multiplied by the existing 24-way frontier search.
23. Composite cannot reduce final Floor First capacity.
24. Existing Best-Fit global guard is untouched.
25. Maximum Utilization is unchanged.
26. Space Evenly is unchanged.
27. Accessible Sequence is unchanged.
28. Strict Sequence is unchanged.
29. Item identity and quantities are preserved.
30. Bounds, overlap, support, stackability, rotation, and payload invariants pass.
31. Diagnostics remain JSON-safe.
32. Regression tests pass.
33. Runtime remains practical.
34. No unrelated refactoring is performed.

