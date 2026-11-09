# TC-REG-019 — Mixed-cargo support-bed orientation limitation

The generalized construction reaches 125 to 127 units across
all four R3 Progressive Infill variants. The screenshot's all-stackable case
reaches 127 with 15 B on A. The owner approved public selection after reviewing
the six changed outcomes. See [the current verification](generalized/results.md) and
[the earlier partial extension](implementation/results.md). The diagnosis
and proposal below record Phase 1. Its input and baseline metadata describe
that phase.

This ID follows the existing historical/rejected TC-REG-018; it does not reuse that ID.
The [central register](../../docs/engineering/known-issues-and-regressions.md)
retains TC-REG-001–017 and the retired experiment unchanged.

## A. Reproduction and physical evidence

Branch: `production`. Commit: `5924c8e9ba84db34e04104ae54f246c4790985a5`.
Engine SHA-256: `bdcaff48aa4afd94178f79f9a1ca85310410af3040b922a98742131f24088174`.
This matches the documented restored, approved implementation. Three documentation
files and unrelated artifacts were already dirty at task start; they were preserved.

### Input provenance

These are the **task's reconstructed inputs**, not a replay of an unavailable
original POST or screenshot. The container is 566.90 × 98.50 × 108.00 inches,
without payload or tare. Mode is `front_to_back_infill`.

| Row | L × W × H, in | Qty | Stackable | Sequence | Existing preset weight, lb |
|---|---|---:|---|---:|---:|
| A | 15.70 × 55.10 × 63.00 | 30 | Yes | 1 | 88.11 |
| B | 63.00 × 23.60 × 39.40 | 17 | **No** | 1 | 191.93 |
| C | 23.60 × 17.70 × 51.20 | 16 | Yes | 1 | 1198.76 |
| D | 31.50 × 47.20 × 15.70 | 48 | Yes | 3 | 11.02 |
| E | 47.20 × 47.20 × 21.70 | 14 | **No** | 3 | 1375.67 |
| F | 47.20 × 47.20 × 21.70 | 4 | Yes | 3 | 661.38 |
| G | 47.20 × 47.20 × 21.70 | 4 | Yes | 3 | 165.35 |

[input.json](input.json) is authoritative for this reconstruction. It declares
units, rotation configurations and provenance. The reproduction calls the current
service's unit validator, container builder, row normalizer and row validator:
inches → mm and pounds → kg, without display rounding. The canonical container is
14399.26 × 2501.90 × 2743.20 mm; A is 398.78 × 1399.54 × 1600.20 mm.

TC-REG-017 uses **A=15.75 × 55.15 × 63.00 inches**, all rotations. It is not
silently substituted here. The public semitrailer preset has the same dimensions
and weights as this task, but B/C are sequence 2 and B/E are stackable. Neither
that preset nor TC-REG-017 was edited. Weights are inherited evidence from those
fixtures, not independently verified original submitted weights.

A synthetic POST passes `item_stackable[]=1,0,1,1,0,1,1` through
`read_product_rows_raw()` and confirms the same Boolean values. Every rotation
experiment changes only R flags; normalized inputs and placement flags confirm
B/E remain non-stackable. Original screenshot checkbox values and its two exact
rotation combinations remain unavailable.

### Seven unchanged-engine outcomes

All requested rows use the listed combination. Counts are ordered A–G.
All seven outcomes pass independent physical validation and repeated signatures.

| Enabled families | Product order | Loaded A–G | Total | B fully on A | Occupied X, in |
|---|---|---|---:|---:|---:|
| R1 | A B C E F G D | 30,17,16,0,8,0,0 | 71 | 0 | 551.3 |
| R2 | B C A E F G D | 9,17,0,0,0,0,0 | 26 | 0 | 559.1 |
| **R3** | **B A C E F G D** | **26,17,10,0,0,0,0** | **53** | **0** | **558.6** |
| R1+R2 | A B C E F G D | 30,17,16,6,8,0,0 | 77 | 0 | 561.1 |
| R1+R3 | A B C E F G D | 30,17,16,42,14,4,4 | 127 | 15 | 566.8 |
| R2+R3 | B C A E F G D | 30,17,16,30,14,4,0 | 111 | 17 | 556.7 |
| R1+R2+R3 | A B C E F G D | 30,17,16,42,14,4,4 | 127 | 15 | 566.3 |

R3 placement evidence, in inches:

- B's non-repeatable Adaptive Mixed-Lane Block loads all 17 on the floor, from
  X=0 to 306.8: four 63-long units in one 23.6-wide lane and thirteen 23.6-long
  units in one 63-wide lane. Its actual width is 86.6 and height 39.4.
- C side infill contributes six units in B's window.
- A loads four six-unit blocks from X=306.8 to 527.2. Each uses
  `(55.1,15.7,63)`; two residual A extend to X=558.6. Four more C enter that window.
- B's remaining quantity is already zero when A's supported roof exists.
  C's original height 51.2 exceeds that roof's 45.0-inch clearance. A's
  remaining units are also too tall there. Sequence-3 infill is ineligible.
- The final roof-clear A rectangles are `(x,y,z,L,W,H)` =
  `(306.8,0,63,220.4,94.2,45)` and `(527.2,0,63,31.4,55.1,45)`.
  Their summed rectangular volume is 1,012,131.9 in³. This is geometric supported
  clearance, not a quantity/capacity certificate. B would fit the larger roof,
  but moving its already committed floor units there is outside the contract.

[baseline.json.gz](baseline.json.gz) contains every placement, signature, loading
phase, block/frontier/top-infill diagnostic, ordinary outcome, support-aware
trial, executed support-bed rejection guards, zero-layer constructions, canonical
inputs, final supported rectangles and validation results. Rejected-trial
diagnostics are labelled separately from actual placements.

### Independent certificates

The task's five-A/two-B witness passes full-base union-support checks: a
78.5 × 55.1 bed at Z=63 supports a 63 × 47.2 cap; combined height is 102.4 ≤ 108.
Non-stackable B can be upper cargo; it cannot support further cargo.

There is also an explicit, independently validated **123-unit R3 certificate**:
`[30,17,16,48,4,4,4]`, preserving or exceeding every current row count.

| Construction | Physical coordinates in inches |
|---|---|
| A30 foundation | Five X slices of 55.1, six Y lanes of 15.7, height 63; bed 275.5 × 94.2 |
| B15 on A | Four 63-long units in Y=0..23.6; eleven 23.6-long units in Y=23.6..86.6; Z=63 |
| B2 on floor | X=275.5 and 299.1, orientation 23.6 × 63 × 39.4 |
| C16 | X=322.7 and 340.4, four 23.6-wide lanes, two 51.2-high layers |
| D48 | Start X=358.1; five 31.5-long slices, two 47.2-wide lanes; first four slices five layers, final slice four layers |
| E4 on D | X=358.1 and 405.3, two 47.2-wide lanes, Z=78.5 |
| F4/G4 | X=515.6, two 47.2-wide lanes, four 21.7-high layers; F below G |

Maximum X is 562.8; maximum height is 102.4. These are explicit geometric
certificates, not another solver, an injected engine candidate, a loading-path
proof or a prescribed solution. The 123-unit certificate establishes useful
whole-load headroom, not global optimality or that the proposed algorithm can
find it. Ten E remain unplaced.

## B. Confirmed root cause and decision chain

1. `allowed_orientations()` correctly generates all enabled families.
   `sort_products()` ranks sequence, largest fitting footprint, volume, longest
   dimension, then input order. R permissions therefore legitimately change
   ordering; stackability is a separate normalized flag.
2. `_pack_container_front_to_back()` calls `_commit_support_bed()` before the
   current product's floor blocks, passing `ordered_products[product_index:]`.
   A is eligible when B comes first in R3. In the A-first runs it has already
   been consumed and is absent from B's later-only candidate set.
3. `_choose_support_bed()` uses `count = remaining[anchor.row_index]`. Its
   `required_depth = ceil(count / cap_lanes) * cap_length` constructs a roof
   for **all** remaining upper cargo. It does not enumerate partial caps.
   All enabled upper and foundation orientations are examined, subject to its
   sampled lanes/layers and caps. It synthesizes adjacent homogeneous columns,
   not a heterogeneous multi-SKU bed or an AMLB upper footprint.
4. For R3 B17, one- and two-lane 63-long caps need 1071 and 567 inches;
   both exceed 566.9. The viable-width three-lane candidate needs **35 A**
   columns, but only 30 exist. The rotated one-lane cap needs **40 A**.
   Four cap lanes need a foundation wider than the container. C beds need
   66–72 columns, versus 16 available. Thus `max_layers=0` for the remaining
   geometry; the layer loop never runs. Diagnostics report **zero evaluated
   B compounds**. Five A supporting two B is never a candidate in this search.
5. This R3 miss occurs **before local ranking, materialization, continuation or
   final dominance selection**. Neither full-base validation nor non-stackable
   upper eligibility rejects that partial arrangement. Ordinary and support-aware
   R3 outcomes are identical at 53 units; final dominance correctly keeps ordinary.
6. Other paths have different mechanisms. In R1 and R1+R2, A comes first and
   no longer participates in B's bed synthesis. B's five/eleven evaluated
   compounds with other foundations are rejected by the disjoint-tail projection
   gate. R1+R3 and all-rotation runs already load B15 on A through top closure;
   their selected E-on-D compound adds 30 units, 97→127. R2+R3 synthesizes
   A30/B17 and D30/E14 compounds and improves 58→111.

`_support_bed_tail_depth()` is an estimate using disjoint homogeneous rows.
Its `projected >= ordinary_depth` rejection is not proof that a compound is
globally useless, because continuation has side/top infill and adaptive blocks.
The guard is confirmed active in other runs; it is **not** the R3 root cause.
No claim is made that relaxing that guard alone improves those runs.

The independent `partial-r3` control also demonstrates a **separate projection
failure** relevant to any partial-cap implementation. Read-only calls to the
actual helper give ordinary completion 210 mm, the useful two-lower/one-upper
40-mm bed plus disjoint remainder 220 mm, and a four-lower/two-upper 80-mm bed
plus remainder 200 mm. The hard projection filter would exclude the independently
validated `[2,3]` improvement; minimum projected depth alone would favor the
longer compound. This is recorded in `projection_counterexample` in the baseline.
Partial generation alone is therefore insufficient if the old hard filter and
single local ranking are retained unchanged. Alternate continuations have not
been implemented or run.

### Remaining-quantity continuation

`_commit_support_bed()` already decrements exactly the foundation and upper
usage, advances each row's item index and loaded weight, then returns the new
frontier. Progressive Fill recomputes entering quantity and runs its ordinary
Product Block, Native/DGFE, side and top paths. The compound is inside the
current product window, so infill sees its physical geometry. Balanced Spread
uses separate orchestration and subsequently its own residual closure.

The state machinery can represent a partial upper request. Reusing it is a
code-supported design inference, **not verified partial-bed integration**:
the present generator never supplies that state. Tests must check every summary,
residual quantity, index and payload update when it does.

## C. Generality and independent cases

Fifteen unrelated controlled cases vary dimensions/aspect ratio, physical
orientations, quantities 1/2/3/5/7, alternate foundation availability,
multiple eligible foundation rows, height, sequence and payload. Their full
inputs/results are in the compressed baseline.

For a 100 × 40 × 40 mm container, stackable lower 20 × 30 × 20 / qty 8,
non-stackable upper 35 × 30 × 10 / qty 5, the engine loads `[0,3]`.
A 40-long bed of two lower units supports one upper, followed by two floor
uppers: `[2,3]`, five units with no row loss. Equivalent physical orientations
encoded separately through **R1-only, R2-only and R3-only** all reproduce
the same miss. An unrelated 72 × 27 × 34 case, lower 14 × 22 × 15 and
upper 25 × 22 × 9, also has `[0,3]` versus a validated `[2,3]` witness.

Eight controlled cases have dominating independent witnesses. Other cases
demonstrate important limits: complete upper quantities 1 and 2 already load
all lower units; quantity 3 loads `[6,3]` and beats the small manual witness;
height 29 cannot support the required 30-high compound; one foundation unit
cannot cover the cap; cross-sequence beds and a payload of 3 must remain
ineligible. At exact height 30 and sufficient payload 5 the useful partial
witness remains missed. The multiple-foundation case keeps rows distinct;
it tests alternative homogeneous supporters, not mixed-SKU bed synthesis.

This is a rotation-independent candidate-generation limitation exposed by
rotation-dependent geometry and ordering. It is not evidence that every
rotation combination should select a bed or produce the same packing.

Ordering alone does not explain the comparisons. R1 and R1+R2 load A first with
orientation `(55.1,63,15.7)`, one Y lane and six Z layers: the roof is at 94.2
inches and cannot accommodate B's R1 height of 63. R1+R3 and all rotations still
load A first, but choose `(55.1,15.7,63)`, six Y lanes and one layer: the roof
is at 63 and accommodates fifteen B through the existing top closure. This is
a confirmed orientation/block-construction effect with the same product order
and unchanged stackability, distinct from R3's B-first partial-bed failure.

## D. Proposed bounded extension — approval required

Preserve the current public result, including approved TC-REG-017 compounds,
as incumbent. Add **at most two** optional complete constructions through the
existing mode orchestration for incomplete mixed infill requests. Each uses a
fixed local ranking policy: projected completion depth first, or shorter useful
compound depth first. Keep the old chooser and its outcome unchanged.

```text
incumbent = existing approved pack_container construction
if baseline mode, complete request, or no eligible mixed pair: return incumbent

for each of the two fixed ranking policies, construct one complete outcome:
  at each uncommitted non-stackable anchor:
    derive a bounded set of homogeneous foundation shapes from enabled geometry,
        available quantity, support height, width, remaining X and payload
    reserve actual height for each enabled upper orientation
    ask existing Product Block generator/fill planner for upper cargo in that roof
        include existing adaptive mixed-lane upper plans
        allow 1 <= actual_upper_quantity <= remaining_upper_quantity
    materialize exact bed and cap; validate full union support and all geometry
    rank feasible compounds deterministically under that fixed policy;
        use tail estimate as a heuristic,
        not as a hard proof that a physically valid partial compound is useless
    commit at most one compound in this window
    continue remaining rows through the same parent Product Blocks/frontiers/infill

validate each complete additional outcome
accept only outcomes with total units strictly higher AND every row >= incumbent
choose the highest-unit admissible outcome, with stable policy-order ties
otherwise return the incumbent's exact placement list
```

Generate critical integral lane/column/layer counts from physical dimensions,
existing bounded-count sampling and quantity/payload limits; do not scan mm,
every possible requested integer or product permutations. Deduplicate geometries.
Budget the new path at **256 attempted bed/roof configurations per window**,
including rejected configurations, and **512 materialized bed+cap units** per
compound. Use stable orientation/product/shape keys and deterministic budget
fallback. The two extra parent runs limit the existing maximum of two runs to
four. These are two fixed-policy constructions, not per-candidate branches:
there is no frontier reopening, search tree or backtracking.

The proposed projected-policy key is `(estimated_completion_depth, compound_depth,
-upper_quantity, -foundation_quantity, stable_geometry_key)`. The compact-policy
key is `(compound_depth, -upper_quantity, -compound_loaded_volume,
estimated_completion_depth, stable_geometry_key)`. Both use actual materialized
quantities and the same validated candidate set. The existing zero-budget switch
must disable these paths too; no separate budget may bypass that protection.

Partial caps plus reuse of the existing upper AMLB planner address the confirmed
missing family. Changing only a `count` loop in the old single-orientation
builder would leave useful roof layouts and projection filtering unresolved.
The proposed new path retains homogeneous foundations and later-only pair
eligibility. A-first height reservation is a separate possible extension; it
has no demonstrated dominating witness here and is not included by assumption.

## E. Architectural impact

Proposed production coding scope is **engine.py only**, plus tests and contract
documentation. A small new partial-bed chooser would reuse the existing block
generator, fill planner, materializer and validators. `_commit_support_bed()`
would accept the planner/policy; `_pack_container_front_to_back()` and
`_pack_container_blocks()` would thread an internal opt-in flag through their
independent orchestration. `pack_container()` would preserve the approved
incumbent, construct the two bounded trials and apply complete-result
validation and no-row-loss selection. The old `_choose_support_bed()` path
and `_support_bed_tail_depth()` behavior remain available unchanged.

No proposed change to `sort_products()`, orientations, physical tolerances,
Balanced Product Blocks/Residual Frontier Closure V2, Native/DGFE candidates,
Pi footprint priority, marginal efficiency, deferred settlement, side/top
closure, Adaptive Mixed-Lane Blocks, mono-lane transition, or sequence policy.
The additional runs consume those paths; changed incoming quantities can change
their decisions, which is why complete-result comparison is essential.

Standalone, public/SEO, Flow, 3D, PDF/report, catalogue and serializer all consume
the same placements from the transport service. Future diagnostics must remain
primitive JSON-safe values; no new UI control or session configuration is
needed. Unit conversion stays in the service. Multi-product Container and Bag
use different engines and are not Transport consumers. Current active integration
tests assess the relevant shared surfaces; no surface behavior was changed here.

The skill's classification list still mentions retired Maximum/Sequence modes.
That list disagrees with the current dispatcher and authoritative domain contract;
this diagnosis uses the four current modes and does not reactivate retired modes.

## F. Regression protection and performance

The exact documented active command passed **210/210**, zero failures, errors
or skips, in **228.063 s** before any proposed engine work. This covers all
active TC-REG-001–017 modules: TOPS, EasyCargo, ExpV2-2 133-unit construction,
Native/DGFE, Balanced residuals, adaptive roofs, support beds, mono transitions,
sequence, Max qty, equivalent units and shared consumers. `manage.py check`
passed. Node sequence checks passed 2/2; current editable-unit checks passed 8/8.

Additional recorded-suite and BR700 baseline results are in
[verification.md](verification.md): the recorded repeat passed 210/210; all
**700 archived cases × four modes = 2,800 runs passed independent physical
validation**, with no omissions or invalid results. The cohort took 1,862.660 s
including recording/validation. Their compressed JSONL records preserve
per-row quantities, total units, complete coordinates, SHA-256 signatures,
physical checks, input identities and candidate counters where exposed.
The recorder delegates each call once to the actual engine and never supplies
different candidate decisions. Injected mock outcomes in an existing test are
explicitly separated from physical engine results.

Risks and protection:

- **A locally attractive bed can hurt later SKUs.** Compare all original rows
  with the current approved incumbent, including zero-loaded rows; reject any
  loss or equal total. Preserve the exact incumbent geometry on rejection.
- **More candidate families can change frozen geometry.** Both baseline modes
  and complete outcomes bypass the extension. The known incomplete frozen
  all-stackable fixture is also ineligible. Run every frozen assertion unchanged;
  no-row-loss alone does not prove signature preservation. Any remaining frozen
  signature change blocks implementation completion rather than being re-goldened.
- **Quantity-dependent continuation can differ.** Validate row identity, unique
  contiguous indices, quantities, unplaced totals and mass through every path.
- **Runtime can grow.** At most two extra runs and explicit budgets bound branching, but
  do not prove acceptable elapsed time. Current recorded timings are diagnostic,
  not CI thresholds; capture/parallel-cohort timings include instrumentation and
  contention. Future baseline/candidate comparisons need alternating repeated
  serial runs, high-quantity/cap fallback cases and candidate counts. Investigate
  a median >25% or >50 ms increase on a real case, and explain before acceptance.

No existing candidate family, protected count or golden signature may be removed,
weakened or silently rewritten. Archived cohort rows also retain no-row-loss
protection; improved non-frozen geometry differences must be explained separately.

## G. Implementation and validation plan

1. After explicit approval, record a fresh engine checksum and rerun the exact
   cumulative command in the testing guide. Keep this approved-engine evidence.
2. Add the bounded alternate planner and two fixed-policy runs above. Preserve the old
   public result as incumbent. Do not add fixture-name or dimension-specific rules.
3. Add permanent tests in `test_transport_mixed_cargo_infill`: partial and complete
   caps in every R family; R3 reference improvement with B genuinely above A;
   multiple eligible supporters; insufficient quantities and support gaps;
   exact/short heights; sequence isolation; payload; item-index and continuation
   accounting; the projection counterexample and both fixed policies;
   deterministic budget fallback; equal-total and row-losing trial
   rejection. Exercise each mixed mode separately and freeze both baseline modes.
   If constructor mocks need to cover the two added calls, extend only that mock
   wiring; preserve every existing rejection, quantity and signature assertion.
4. Add service inch/mm equivalence plus scene/report/Flow/JSON checks in
   `test_transport_unit_integration`. Preserve original input flags and all
   historical assertions. Confirm the standalone/public/catalogue contracts
   through the existing active modules and sequence/unit JavaScript checks.
5. Rerun the entire documented active command, Django check, both Node checks,
   recorded output comparisons and all BR700 inputs in four modes. Inspect every
   protected count/signature difference and independently validate final geometry.
6. Promote TC-REG-019 to Protected only when solved tests join the active suite,
   all active regressions pass unchanged and runtime is explained. Update the
   domain/consumer contracts in the same implementation change.

Acceptance requires strict whole-result improvement with no row loss against
the **current approved** R3 result, useful supported upper placement, physical
validity, JSON-safe state, deterministic bounded work, unchanged approved
sequence behavior and frozen signatures, and all cumulative checks passing.
`--assert-target` currently expresses the stronger known-feasible 123-unit target
and deliberately fails; it must not be weakened or relabelled as solved. If the
bounded prototype improves the load but misses that target, report the remaining
gap and seek a scoped decision instead of claiming this open target passed.

## H. Remaining uncertainties and approval gate

Original POST/screenshot flags and weights cannot be recovered from the provided
task. No claim is made to reproduce hidden screenshot state. The proposed
planner's selected compounds, complete continuation quantities, ability to reach
the 123-unit certificate, impact on other incomplete manifests and actual runtime
remain unproven until implementation. The need for A-first height reservation,
or a further expansion beyond the two fixed policies, is also unproven; these
are not silently added to this plan.

**Do you approve the proposed generalized support-bed improvement and the implementation plan? I will not modify the engine until you approve.**

## Reproduction commands and artifact map

Run from `C:\PackagingEngineering`:

```powershell
$casePath = 'regressions/TC-REG-019-mixed-cargo-support-bed-orientation'
.\.venv\Scripts\python.exe "$casePath/reproduce.py" --output "$casePath/baseline.json.gz"
# Expected exit 1: open optimization target, outside active test discovery.
.\.venv\Scripts\python.exe "$casePath/reproduce.py" --assert-target
.\.venv\Scripts\python.exe "$casePath/capture_baselines.py" suite
.\.venv\Scripts\python.exe "$casePath/capture_baselines.py" cohort
```

For the unmodified active test command use
[testing-and-verification.md](../../docs/engineering/testing-and-verification.md#complete-active-transport-suite).
`active-suite.log` records that command's result. `reproduction.log` and
`unresolved-target.log` distinguish a successful evidence run from the expected
red target. `protected-suite.log`/`protected-summary.json` describe the additional
recorded suite; `br700.log`/`br700-summary.json` describe the archived cohort.
`baseline.json.gz`, `protected-baseline.jsonl.gz` and `br700-baseline.jsonl.gz`
are ordinary UTF-8 JSON/JSONL compressed with gzip; Python's `gzip.open(...,'rt')`
can read them without additional dependencies. The two scripts are the only
executable additions and do not duplicate or modify the engine.

No commit, push, merge, deployment, Railway change, production migration or
production-data change was performed.
