# Recommended generalization for TC-REG-019 — proposal only

The next change should introduce one bounded supported-construction planner.
It must cover stackable/non-stackable upper cargo, partial quantities and staged
support through the same physical rules. The previous non-stackable-upper gate
and a separate intermediate-tier patch are insufficient individually.
This document changes no engine behavior.

## 1. Correct the physical contract

| Role | Eligibility |
|---|---|
| Lower unit carrying another unit | Must be stackable and provide full coplanar base support |
| Upper unit resting on valid support | May be stackable or non-stackable |
| Cargo above that upper unit | Allowed only when the upper unit is stackable |

Stackable permits additional layers; it does not require maximum stacking.
Keep single-layer and multi-layer constructions available when physically valid.
Never fake a product's stackability to obtain another layout. Enabled R1/R2/R3,
weights, quantities, sequences and canonical dimensions remain unchanged.

## 2. Decide before floor commitment

At the current uncommitted frontier, generate ordinary floor options and supported
compounds. The current product must participate, either as upper cargo over an
eligible later foundation or as a foundation for eligible later upper cargo.
The latter permits reserving upper clearance before maximizing the foundation's
own height. This addresses rotation-dependent product order without a global
product permutation or reopening previous windows.

Use normalized inputs and necessary geometry/quantity/sequence checks for entry
eligibility. Do not require a non-stackable row or the presence of a diagnostic
key from the old chooser. Require distinct positive-quantity rows; preserve the
mono-product contract and zero-row behavior. Both baseline modes and already
complete outcomes bypass the new work.

## 3. Compose geometry and quantities jointly

Generate the compound from existing Product Blocks and actual support planes:

```text
homogeneous foundation
    -> optional bounded intermediate support rows
    -> selected upper batch
    -> ordinary parent-mode continuation for all remaining quantities
```

Evaluate direct support and optional intermediate support in the same planner.
Keep foundation and upper orientations independent. Include partial and complete
upper batches, and zero/partial/complete intermediate batches. Reserve the
selected upper batch's actual envelope and payload while evaluating middle rows;
do not require the entire remaining upper request to fit in the compound.

Simply filling the middle greedily before placing the upper cargo is another
local trap: it can consume capacity required by the upper batch. A candidate must
jointly specify foundation usage, intermediate usage and upper usage. Re-derive
the real coplanar support union after each materialized block. Validate every
level and use actual placed units/height/footprint rather than virtual capacity.
Initially bound this to a foundation, an optional intermediate tier, and upper
cargo. That is an explicit search-complexity limit, not a product-name rule or a
claim to solve arbitrary multi-level bin packing.

Use `build_product_block_candidates()`, materializers, local top-space derivation
and the existing support/bounds/overlap/payload helpers. Admit supported stackable
adaptive plans only in this explicitly validated compound context. Keep regular
Product Block eligibility and both parents' frontier/scoring semantics unchanged.

## 4. Compare complete outcomes

Compute the current public result once and preserve it, including today's full
and partial support-bed successes. Candidate ranking is a pruning/ranking aid;
the tail projection is not a feasibility certificate or a sufficient global score.

Retain a small, deterministic set of construction families across support roles,
layer heights and direct/staged support. Do not let one row or the first rotation
consume the whole budget. Seed minimum useful shapes, quantity/module boundaries
and maximum feasible bed shapes before sampling larger count ranges. Enabling
stackability or a rotation should not remove an already legal geometric family.

For every complete alternative, enforce:

1. Physical validity, enabled orientations, identity, contiguous item indices,
   exact quantities, payload and existing sequence rules.
2. No row below the current result for the **same input configuration**.
3. Strictly more total loaded units.
4. Exact incumbent geometry on rejection or an equal total.

The result must not be forced to put B on A if another valid complete outcome is
better. Direct planner tests must demonstrate generation of the known beneficial
support candidates; whole-load tests assess the selected complete result.

Do not promise universal per-SKU monotonicity across different input constraints.
Different feasible outcomes can trade row quantities. Test that previously legal
geometry remains legal after permissions are relaxed, and protect each registered
input's own incumbent quantities. All-stackable 83 and B/E=false 119 have different
row minima and must not be conflated.

## 5. Put all new work under a fixed budget

Preserve the existing compatibility outcome. Start with at most two additional
generalized complete constructions, making the existing worst-case four parent
runs at most six. Direct/staged support and rotations are candidate families
inside those constructions; adding a capability must not add another full run.

Suggested initial new-work limits: 256 attempted configurations per window,
1,024 per request across the new trials, and 512 materialized units per compound
including foundation, middle and upper cargo. These budgets supplement, rather
than truncate, calculation of the preserved compatibility incumbent. Report
exhaustion explicitly and retain the incumbent when nothing admissible is found.

Cache pure geometry and candidate generation within the request. Cache keys must
include orientations, actual support geometry, quantities and payload state where
those affect the result; do not reuse state across incompatible continuations or
put engine objects in sessions. Prune physical impossibilities before expensive
materialization. No millimetre scanning, unbounded permutations or backtracking.

Measure eligible cases with alternating serial runs. The present extension already
adds about 66–764 ms in the measured seven-row configurations. Broader eligibility
activates previously bypassed all-stackable requests, so archived-cohort timings
cannot be assumed unchanged. Establish and report the new cost before promotion.

## 6. Define acceptance before coding

R3 reference targets, with every current row quantity preserved for that input:

| B stackable | E stackable | Current total | Minimum reference acceptance |
|---|---|---:|---|
| No | No | 119 | At least 123; preserve D48/E8 and every other current row |
| Yes | No | 97 | At least 123; preserve every current row |
| No | Yes | 123 | At least 123; preserve D38/E14/F4/G4 and every other current row |
| Yes | Yes | 83 | At least 123 using the screenshot's unchanged flags; preserve E14/F2 and every other current row |

These are corresponding-input acceptance floors, not assertions that the proposed
algorithm is already proven to find them. Existing physical certificates support
the reference headroom. The 127-unit B/E=false certificate does not substitute for
an all-stackable case if it reduces that case's E14 quantity.

Build a parameterized matrix of all four B/E flag combinations × seven nonempty
rotation combinations × both mixed modes (56 cases), freezing each current row
vector first. Add independent dimensions, renamed products, independent lower/
upper rotation families, single/partial/multi-layer quantities, multiple eligible
supporters, height/support gaps, payload, sequences, scale and equivalent units.
Do not demand a supported bed where no dominating supported outcome is known.

Also freeze the corresponding baseline-mode signatures. Run the complete active
Transport suite and all 700 archived inputs in four modes. Broader eligibility
may change archived infill outcomes: require valid geometry and no row loss;
investigate each change. Any changed **frozen** expectation needs an explicit
owner decision, never a silent re-golden or a fixture-specific bypass.

Add real service/POST tests for the all-true screenshot checkbox values and
assert the selected placements, scene/report identity, canonical units and JSON
state. Check standalone, public and Flow through the shared service; Multi-product
Container/Bag remain separate-engine consumers unless a shared dependency changes.

## Implementation scope and delivery

Production logic remains in `engine.py`: role-based entry checks, generalized
compound generation, atomic usage/commit accounting, bounded portfolio selection
and primitive diagnostics. The existing Product Block and physical helpers remain
authoritative. Do not change the global product sort, UI inputs, unit conversion,
session schema, rendering calculations, Native/DGFE rules or Balanced closure.

Implement and exercise the planner in the diagnostic harness first. Enable its
public mixed-mode selection only after the reference acceptance matrix, physical
checks, existing frozen regressions and runtime review pass. Validate the actual
all-stackable service/UI case before claiming the regression is solved.

This is the recommended replacement scope for the earlier narrower follow-up.
No packing code, golden result, commit, deployment or production data was changed
while preparing this proposal.
