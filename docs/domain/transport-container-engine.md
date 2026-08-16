# KolliPack Transport Container Engine — Space Evenly and Load Front-to-Back DGFE

## Status and authority

This is the technical deep dive for the current Transport Container calculation
engine and the checked-out repository baseline (August 2026). The authoritative
implementation is:

`packagingapp/utils/container_tool/engine.py`

The active engine contains two isolated deterministic modes: **Space Evenly
V1** and **Load Front-to-Back with DGFE**. Space Evenly remains the stabilized
baseline. Load Front-to-Back is exposed through the existing compatibility
values `maximum_utilization` and `maximum_utilization_floor_first`; its internal strategy is
`front_to_back_blocks`. The transport service, forms, views, templates,
serializers, and tests are supporting consumers and must be checked against
the engine when behavior changes.

`packagingapp/utils/container_tool/engine_legacy.py` is retained historical code.
It is not the current algorithm specification and is not imported by the active
engine. A requested mode other than Space Evenly or the compatibility
Front-to-Back values returns a graceful unsupported result with no placements.

## Load Front-to-Back with DGFE

Load Front-to-Back reuses the Space Evenly normalizer, product ordering,
R1/R2/R3 orientation families, Product Block candidate generation and ranking,
block materialization, payload checks, and placement structures. Its distinct
orchestration is:

```text
complete Product Block
→ current-product orientation × four residual base candidates
→ derive each candidate's actual Pi residual X footprint
→ preserve Native and DGFE Extended family outcomes
→ all-orientation next-product evaluation inside the Native footprint
→ bounded Row-First next-product population
→ deferred-gravity settlement where applicable
→ final physical validation and extension-value comparison
→ select the bounded transition winner
→ close frontier
→ next product's complete Product Block
```

When a next product exists, every enabled current-product orientation is paired
with exactly four strategies: deferred Top-Down Row First, deferred Top-Down
Column First, Bottom-Up Row First, and Bottom-Up Column First. Residual
construction is quantity-agnostic and uses one orientation per candidate.
Top-Down candidates reserve real three-dimensional cuboids from the ceiling;
the reserved cuboids are collision obstacles, not temporary supports.

Each orientation/strategy base preserves two isolated family outcomes. The
**Native Frontier Candidate** ends at the actual Pi residual X footprint:

```text
D_pi = max(Pi placement x + Pi placement length) - frontier_start_x
```

This is measured from materialized candidate geometry, so residuals spanning
multiple X slices are handled without assuming that one orientation length is
the complete footprint. The **DGFE Extended Candidate** keeps the established
bounded envelope: every Pi+1 X row intersecting Pi's projection plus the first
fully clean re-synchronization row. The extension never mutates or erases its
paired Native result.

The established all-orientation next-product evaluator remains authoritative.
It evaluates the exact residual frontier and selects the incoming orientation
using the existing quantity, width-utilization, preferred-orientation, and
stable tie rules. The selected next product then populates Bottom-Up Row First
through every valid local position. Native population is bounded by `D_pi`;
DGFE population uses the intersecting-plus-first-clean-row envelope. A partial
row does not terminate a later clean row.

After next-product population, a deferred residual may move only in negative Z.
X, Y, and orientation remain fixed. Settlement processes lower reserved units
first, requires a collision-free vertical path, and accepts complete base
coverage from the union of coplanar stackable supports. The virtual state is
never scored or committed; bounds, overlap, support, stackability, and payload
are validated on the final settled state.

For a valid Native/Extended pair, extension value is measured only over its
additional X prism:

```text
D_extra = D_extended - D_native
V_extra = V_extended - V_native
marginal_efficiency = V_extra / (D_extra × container_width × container_height)
```

The benchmark is the transverse utilization of the normal Pi+1 Product Block
selected by the shared generator and selector for the quantity, payload, and
length remaining after Native. DGFE remains eligible only when its marginal
efficiency exceeds that benchmark by tolerance. An effective tie prefers
Native. If no regular block is feasible, a valid extension that adds volume
remains eligible. If Native cannot reach a valid settled physical state but its
paired DGFE outcome can, the valid DGFE outcome remains eligible.

Candidate ranking applies validity, maximum Pi residual quantity, minimum
actual Pi residual X footprint, paired Native-versus-extension eligibility,
local frontier efficiency, useful Pi+1 quantity, and smaller total envelope
depth in that order. Effective ties prefer Row First, Bottom-Up, and stable
orientation order. The last product retains its established Bottom-Up Row-First
residual behavior without look-ahead. A committed frontier is never reopened by
later products. There is no global residual-at-the-end phase, free-space tree,
lateral gravity, compaction, or legacy solver import. All products remain
forced to sequence `1` and use the same deterministic size ordering as Space
Evenly.

## What Space Evenly is

Space Evenly is a deterministic, explainable, block-based heuristic for
rectangular transport loads. It is intended to create a structured candidate
layout for several rectangular load-unit types, particularly when quantities
are large enough to form repeated blocks. It is not a mathematical optimizer
and does not claim global optimality.

Its defining vocabulary is:

- structured candidate;
- deterministic;
- block based;
- support aware;
- width conscious;
- explainable.

The concise definition is:

> **Space Evenly is a deterministic two-phase transport-loading heuristic that first converts large product quantities into YZ-optimized regular blocks and then packs residual quantities using width-optimized, support-aware rows and surfaces, following a Y → Z → X filling philosophy.**

## Coordinate system and loading philosophy

The engine uses the transport unit's internal usable dimensions:

```text
x = transport-unit length (back wall toward the doors)
y = transport-unit width
z = transport-unit height (floor upward)
```

The construction philosophy is:

```text
Y → Z → X
```

1. Fill or optimize the current width row.
2. Use the support surfaces generated by that row for the next vertical pass.
3. Advance the longitudinal frontier when the current residual band cannot
   accept useful cargo.

This is a construction order, not arbitrary traversal of individual items. It
does not mean that every placement is globally searched in Y, then Z, then X.

## Physical invariants

The active construction must preserve these result-level invariants:

1. positive-volume placements do not overlap;
2. every placement is within container length, width, and height;
3. only enabled orthogonal rotations are used;
4. a positive maximum payload is not exceeded;
5. a non-stackable load unit does not support another unit;
6. elevated units have a full rectangular base on an accepted support surface;
7. identical normalized inputs produce deterministic results;
8. requested quantities and `row_index` product identity remain traceable.

These are geometry and operational rules. The engine does not model cargo
securing, structural strength, friction, or legal transport compliance.

## Inputs and orientation families

Products are normalized with dimensions, quantity, unit weight, stackability,
row identity, and enabled rotation families. Container dimensions are normalized
as `L`, `W`, and `H`, with optional `max_weight` and `tare_weight`.

The application uses the R1/R2/R3 terminology already shown in the form. Each
enabled family contributes axis-aligned permutations in stable order:

| Family | Generated `(length, width, height)` permutations |
|---|---|
| R1 | `(L, W, H)`, `(W, L, H)` |
| R2 | `(L, H, W)`, `(H, L, W)` |
| R3 | `(W, H, L)`, `(H, W, L)` |

Duplicate tuples are removed. These flags are hard constraints: a disabled
family cannot appear in a placement. No diagonal or arbitrary-angle placement
is generated.

## Space Evenly sequence semantics and product order

Space Evenly deliberately has one common loading group:

```text
all products are normalized to sequence = 1
```

The service sets each Space Evenly row to sequence `1` before validation, the
template renders the field as read-only in that mode, and the engine enforces
the same rule again before normalization. A stale posted sequence value cannot
change Space Evenly allocation.

The engine still retains a sequence key internally because the shared result
contract supports other historical mode values. For the active Space Evenly and
Load Front-to-Back paths, all rows therefore share the same sequence and the
effective deterministic product order is:

1. larger valid footprint among enabled orientations that fit the container;
2. larger unit volume;
3. larger longest dimension;
4. original input order.

This is automatic ordering, not a user loading sequence. It primarily determines
the order of Phase 1 Product Blocks and supplies stable tie-break context in
residual selection.

## Two-phase architecture

```text
SPACE EVENLY V1
      |
      +-- PHASE 1 — REGULAR PRODUCT BLOCKS
      |
      +-- complete frontier
      |
      +-- PHASE 2 — SUPPORT-AWARE RESIDUAL GREEDY
```

The global ordering is important:

```text
ALL PRODUCTS — complete regular blocks first
then
ALL PRODUCT RESIDUALS — one common Space Evenly residual group
```

The engine does not load a product's residual immediately after that product's
regular block. Residual quantities are collected for every product after Phase
1, then Phase 2 starts at the complete-block frontier.

## Phase 1 — Product Blocks

### Product Block definition

> **Product Block:** a regular cuboidal loading module for one SKU, constructed
> by optimizing its transverse Y × Z geometry and repeating that module along X.

A Product Block:

- contains one SKU;
- uses one orientation or at most two enabled orientations of that SKU;
- is regular and explainable;
- has a flat longitudinal frontier;
- may contain mixed orientation lanes when their geometry can be synchronized.

Mixed orientation is not inherently undesirable. The block remains a regular
module as long as its lanes share compatible height and a common X depth.

### Transverse pattern and capacity

The **transverse pattern** is the arrangement in the container's Y × Z plane
before the module is repeated along X. For one orientation `(d, w, h)`:

```text
ny = floor(container_width  / w)
nz = floor(container_height / h)
```

For a non-stackable product the regular block caps `nz` at `1`.

```text
occupied_width  = ny × w
occupied_height = nz × h

YZ utilization =
    occupied_width × occupied_height
    ---------------------------------
    container_width × container_height
```

The transverse capacity is `ny × nz`. A module's `module_capacity` also
includes X repetitions when a synchronized mixed block needs more than one
copy of an orientation along its common depth.

Example transverse sketch:

```text
z ↑
A A A
A A A
A A A  → y
```

### Mixed orientation and synchronized depth

The candidate generator tests pairs of enabled orientations from the same SKU.
The pair is eligible only when:

- both orientations have compatible heights;
- both fit the transverse container geometry;
- their X depths can share an exact integer common depth.

For orientation depths `dA` and `dB`, the engine finds integer repetitions:

```text
rA × dA = rB × dB
```

The resulting common value is the **synchronized depth**. Lane groups then end
on one flat X frontier instead of leaving one orientation group shorter than
the other.

```text
AAAA | BBB
AAAA | BBB
```

The pair's lane counts and repetition counts determine its occupied width,
transverse capacity, module capacity, and common depth. Non-stackable products
still use only one vertical layer (`nz <= 1`) in a mixed block.

### Quantity-independent candidate geometry

Candidate geometry is generated from product/container geometry and the current
remaining length. It is not designed around the requested quantity. Quantity
controls whether a candidate is eligible:

```text
module_capacity <= payload-feasible quantity
module_depth    <= remaining container length
```

This separation keeps the geometry structurally consistent across quantity
scenarios while allowing a small request to defer to residual handling.

### Candidate ranking

After invalid candidates are removed, the staged ranking is:

1. maximize YZ utilization;
2. retain candidates within the YZ utilization equivalence tolerance;
3. maximize transverse capacity;
4. minimize synchronized/module X depth;
5. prefer one orientation when geometrically equivalent;
6. apply the stable orientation/lane/repetition tie-break.

The code constant is:

```text
YZ_UTILIZATION_EQ_TOL = 0.0025
```

This is an **absolute normalized-utilization fraction**, equal to 0.25
percentage points. It is a ranking-equivalence tolerance, not a physical-fit
tolerance.

### Complete repetition and residual definition

For a selected candidate:

```text
complete_blocks = min(
    floor(payload_feasible_quantity / module_capacity),
    floor(remaining_length / module_depth)
)
```

All complete modules are materialized contiguously from the current X frontier.
Phase 1 does not greedily fill partial module gaps. The deferred quantity is:

```text
residual_qty = requested_qty - regular_qty
```

Residuals for all products are collected before Phase 2. If payload prevents a
positive-weight unit from being loaded, it remains unplaced even when geometric
space is still visible.

## Phase 2 — support-aware residual greedy

### Residual X Band

> **Residual X Band:** one longitudinal residual loading section beginning at
> the current frontier and using the selected foundation orientation's X
> dimension as its band depth.

Each band starts with a floor foundation row at `z = 0`, filling the available
width first. The foundation orientation's X dimension defines the band depth.
The band is not a generic free-space tree and is not a search for arbitrary
side/front/top cuboids.

### Foundation selection

Foundation candidates are evaluated against:

- remaining product quantity;
- enabled orientation;
- available X length;
- container width and height;
- payload availability;
- the support surface created by the foundation row;
- local support potential after the row is removed.

Foundation **SKU selection** is support-aware before orientation/width
optimization. The engine first compares each SKU's best local support potential,
then uses deterministic product order and orientation/width criteria to choose
the foundation candidate. It is not simply “choose the row that fills the most
floor width.”

### Support Potential

> **Support Potential:** the local count of remaining product types for which at
> least one enabled orientation fits a candidate support surface, subject to
> stackability and container height.

The measure is intentionally local. It is not recursive global optimization, a
graph solver, compressive-strength analysis, or a model of material mechanics.

### SupportSurface

> **SupportSurface:** a rectangular coplanar top region created by one
> contiguous homogeneous run of load units and used as the parent region for
> potential upper rows.

The runtime record contains:

```text
surface index
x, y, top z
length, width
product / row identity
orientation index
source placement count
stackable
```

The surface `z` is its top elevation. A surface belongs to one SKU, one
orientation, one top plane, and one contiguous run. Different SKUs or
orientations remain separate surfaces; arbitrary unions with gaps are not
represented as one support surface.

Several adjacent lower units can form one continuous rectangular support region
for a child row. A child therefore does not need to fit on one individual lower
unit when the combined surface is continuous:

```text
       BBBBBBB
┌──────┬──────┬──────┐
│  A   │  A   │  A   │
└──────┴──────┴──────┘
```

Seams between contiguous supporters are acceptable. Unsupported gaps are not
silently bridged, and the engine does not calculate a partial-support
percentage.

### Stackability and surface compatibility

If `support_surface.product.stackable == False`, the surface cannot receive an
upper row. Stackability is a Boolean geometric/operational rule, not a
structural load model. The engine does not calculate compression strength,
maximum top load, pallet bending, crushing, or material mechanics.

An upper orientation must satisfy the equivalent of:

```text
surface.stackable == True
upper_x <= surface.length
upper_y <= surface.width
surface.top_z + upper_height <= container_height
```

Quantity and payload feasibility are checked at the same decision point.

### Width-optimized upper rows

For an upper row, available width is the parent SupportSurface width. The
foundation uses the full container width. Width utilization is:

```text
width utilization = occupied row width / available support width
```

The residual row planner constructs max-fill single-orientation plans and a
bounded set of two-orientation plans for the **same selected SKU**:

```text
n1 × w1 + n2 × w2 <= available_width
```

This is a small one-dimensional width search, not generic bin packing. The
ranking is:

1. maximum width utilization;
2. maximum row quantity;
3. fewer orientation runs when equivalent;
4. greater support potential;
5. smaller maximum X depth when equivalent;
6. stable orientation/count tie-break.

The code constant is:

```text
RESIDUAL_WIDTH_UTILIZATION_EQ_TOL = 0.001
```

This is an absolute ranking-equivalence fraction (0.1 percentage points), not
a physical tolerance.

### Current-product and pattern continuity

**Current-product continuity** means that once a residual SKU is being loaded,
the engine prefers to continue that SKU while it remains feasible. This is a
residual-row preference and is separate from the Phase 1 product order.

**Pattern continuity** applies when the same SKU continues on top of its own
SupportSurface. The engine first attempts to repeat the parent surface's
orientation and run pattern, including a partial final row, before invoking the
general width optimizer:

```text
same SKU continues on its own surface?
        |
        +-- parent orientation feasible -> repeat it
        |
        +-- otherwise ------------------> general optimizer
```

The intended effect is a stable vertical pattern:

```text
AAAAA
AAAAA
AAA
```

rather than an unnecessary rotation of the same SKU in the terminal row. A
terminal row selected by the general optimizer may be preferred when its new
surface leaves local support potential for another remaining SKU, but feasible
same-SKU parent-pattern continuation takes precedence.

### Breadth-first residual passes

SupportSurfaces are processed in passes. Within each pass they are ordered by
Y, then X, then surface index. Children produced by that pass form the next
active pass:

```text
PASS 1 — foundation surfaces across Y
PASS 2 — child surfaces across Y
PASS 3 — next child surfaces across Y
```

This is breadth-first. It prevents one support column from being built to the
ceiling before neighboring Y regions receive their opportunity to continue.

### Frontier progression and intentional simplifications

When a residual band ends:

```text
frontier = band_x + foundation_orientation_x
```

The next band starts at that new longitudinal frontier. If the foundation does
not fill the full container width, Space Evenly V1 does **not** launch a generic
search for another SKU in the unused floor strip. It uses the established
foundation surface upward and then advances X.

The active residual loop retains sequence-group scaffolding for the shared
result contract, but Space Evenly has only the common sequence `1`; it does not
create user-controlled sequence zones.

### Collision avoidance philosophy

Space Evenly V1 avoids most runtime collision search by constructing geometry
through block and parent-surface invariants:

- Phase 1 uses known regular block coordinates.
- Phase 2 keeps children inside compatible, non-overlapping parent surfaces.
- Bounds, support, stackability, payload, and overlap are result invariants
  validated by the engine regression harness and consumer checks.

Collision helpers may exist elsewhere in the application, but all-pairs free
space splitting is not the active Space Evenly placement strategy.

## Payload behavior

When a positive maximum payload is configured, the engine tracks loaded cargo
weight and bounds additional positive-weight units by:

```text
remaining_payload = max_payload - loaded_weight
```

For a positive-weight SKU, the payload-feasible quantity is limited by the
remaining payload divided by unit weight. With no positive payload limit, or
with zero unit weight, geometry and quantity determine the available count.
Geometry can remain available after payload capacity is exhausted; the result
then reports unplaced units and the payload reason.

The transport summary separately reports cargo weight, optional tare, gross
weight (`tare + cargo` when tare is supplied), and payload utilization.

## Determinism and bounded work

Identical normalized inputs should produce the same product order, Product
Blocks, residual bands, SupportSurfaces, and placements. Stable orientation
order, row identity, input order, and explicit tie-break keys make results
reproducible for tests, engineering review, PDF/report output, and scenario
comparison.

The search is bounded by geometry and quantity feasibility. It does not perform
a beam search, global combinatorial search, arbitrary lateral-direction search,
or a generic item permutation search. Diagnostics expose candidate counts so
performance changes can be reviewed without treating timing as a correctness
threshold.

## Technical diagnostics

The active result keeps JSON-safe `space_evenly_*` metadata. The most useful
fields are:

| Diagnostic | Meaning |
|---|---|
| `space_evenly_product_order` | normalized product order and common sequence |
| `space_evenly_product_blocks` | per-product requested, regular, residual, and selected-block summaries |
| `space_evenly_main_blocks` | materialized complete Product Block summaries |
| `space_evenly_main_blocks_end_x` | complete-block frontier |
| `space_evenly_residual_bands` | residual foundations, upper rows, surfaces, and quantities |
| `space_evenly_support_surface_count` | total surfaces created in residual bands |
| `space_evenly_support_checks` | surface/orientation compatibility checks |
| `space_evenly_support_relationship_count` | compatible support relationships found |
| `space_evenly_residual_units` | all residual units sent to Phase 2 |
| `space_evenly_residual_packed_units` | residual units placed |
| `space_evenly_block_candidates_generated` | generated Phase 1 candidates |
| `space_evenly_block_candidates_evaluated` | Phase 1 candidates evaluated |
| `space_evenly_residual_candidates_evaluated` | Phase 2 candidates evaluated |
| `space_evenly_x_used` | final occupied longitudinal frontier |
| `front_to_back_frontiers` | bounded transition diagnostics, all orientation/strategy/family outcomes, final physical state, and the selected winner |
| `front_to_back_product_blocks` | per-product block, residual, and carry-forward summaries |
| `front_to_back_frontier_candidates_evaluated` | next-product orientation evaluations across the isolated transition candidates |
| `residual_strategy_candidates` | Native and DGFE Extended outcomes with current orientation, gravity mode, traversal, virtual/settled coordinates, next orientation/quantity, support, validity, value metrics, and compact phase diagnostics |
| `selected_residual_orientation` | current-product orientation selected for the committed frontier |
| `pi_residual_x_footprint` | actual Pi placement footprint from the local frontier start, independent of total envelope depth |
| `candidate_family` / `selected_candidate_family` | whether an outcome is the compact `native` baseline or `dgfe_extended` envelope |
| `native_frontier_depth`, `extended_frontier_depth`, `extra_extension_depth` | paired envelope depths and the additional X consumed by DGFE |
| `native_next_product_qty`, `extended_next_product_qty` | Pi+1 quantities in the paired family outcomes |
| `dgfe_extra_packed_volume`, `dgfe_marginal_efficiency` | volume gained by DGFE and its utilization of only the additional X prism |
| `next_product_regular_block_efficiency`, `extension_value_delta` | shared Product Block benchmark and DGFE marginal advantage/disadvantage |
| `selected_frontier_volume_efficiency` | packed current-plus-next frontier volume divided by the candidate frontier prism volume |

The result also retains compatibility aliases such as
`space_evenly_residual_miniblocks`, target counts, packed volume, actual height,
and zero beam-state counts. These aliases are output compatibility metadata;
they do not imply a legacy mini-block or beam algorithm is active.

## Intended operating profile

The architecture is particularly suited to several rectangular load-unit types
with moderate or relatively large quantities. Complete Product Blocks handle a
large share of the request, leaving the bounded residual phase to resolve
leftovers. Small quantities are supported, but they tend to produce fewer
complete blocks and delegate a larger share of the load to the heuristic
residual phase. The result remains a candidate layout, not a proof of the best
possible packing.

## Limitations

Space Evenly V1 does not prove or calculate:

- global mathematical optimum;
- cargo securing, lashing, or dunnage design;
- structural compression strength or crushing limits;
- axle loads or center-of-gravity compliance;
- forklift accessibility or an exact loading path through doors;
- friction, dynamic stability, or route vibration;
- regulatory or dangerous-goods compliance;
- refrigeration airflow or thermal constraints;
- irregular, deformable, or non-rectangular geometry;
- diagonal or arbitrary-angle placement.

Internal dimensions must be usable loading dimensions. Door aperture, handling
clearance, practical loading/unloading order, and legal transport checks remain
engineering responsibilities outside this geometric candidate solver.

## Validation recommendations

Direct engine regression should check, at minimum:

- deterministic repeated geometry;
- bounds and enabled orientations;
- positive-volume non-overlap;
- full-base support for elevated units;
- non-stackable support rejection;
- quantity accounting and unplaced reasons;
- payload-limited cases;
- sequence forcing to one for Space Evenly;
- regular-before-residual phase order;
- synchronized mixed-block flat frontiers;
- combined contiguous support surfaces;
- parent-pattern continuation;
- breadth-first residual pass order;
- frontier advancement without floor side-gap filler;
- Front-to-Back orientation × traversal base candidates and both family outcomes;
- four residual strategies per current orientation and quantity-agnostic residuals;
- actual Pi X-footprint compactness before local frontier efficiency;
- Native preservation, bounded DGFE extension, marginal extra-X efficiency, and
  the shared Pi+1 regular Product Block benchmark;
- deferred vertical-only settlement, collision-free paths, and union support;
- partial intersecting rows followed by the first clean re-synchronization row;
- current-residual priority, effective Row-First ties, and carry-forward quantity;
- JSON-safe diagnostics and standalone/Packaging Flow parity.

The engine is the source of truth for any discrepancy. Historical handoffs and
older mode descriptions must be treated as context, not as evidence against
the active implementation.

## Historical mode note

Maximum Utilization, Maximum Utilization Floor First, Sequence Loading, and
Strict Sequence Loading remain recognizable UI/configuration values and may be
referenced by older regression material. Their former algorithm descriptions
are historical compatibility context, not active behavior in the current
`engine.py`. The former generic sequence-loading algorithms remain historical
compatibility context and are not imported by the current engine. The
`maximum_utilization` and `maximum_utilization_floor_first` values now route to
Load Front-to-Back with DGFE; other historical values return an explicit
unsupported-mode result.

## Glossary

| Term | Definition |
|---|---|
| Space Evenly | The stabilized structured transport-loading heuristic. |
| Load Front-to-Back | A block-and-local-frontier heuristic exposed through `maximum_utilization` and `maximum_utilization_floor_first`. |
| Deferred-Gravity Frontier Envelope (DGFE) | A bounded Front-to-Back candidate construction that temporarily reserves a top-down residual, fills the next product around it, and restores vertical gravity before validation. |
| Stepped Frontier Envelope (SFE) | The physically valid local boundary produced by residual construction, next-product population, and any deferred settlement. |
| Product Block | A regular one-SKU module repeated longitudinally. |
| Transverse Pattern | The Y × Z arrangement defining a Product Block. |
| Module Capacity | Units in one complete longitudinal Product Block module. |
| Transverse Capacity | Units represented in the Y × Z cross-section before X repetitions. |
| Synchronized Depth | Common X depth satisfying `rA × dA = rB × dB` for mixed lanes. |
| Residual Quantity | Requested units remaining after complete regular blocks. |
| Residual X Band | One longitudinal section used by the residual support-aware phase. |
| SupportSurface | A rectangular top region from a contiguous homogeneous run that can support upper cargo. |
| Support Potential | Remaining product types locally compatible with a candidate SupportSurface. |
| Width Utilization | Fraction of available Y width occupied by a residual row. |
| Pattern Continuity | Preference for repeating an established parent orientation for a continuing SKU. |
| Frontier | Current X coordinate after the completed regular or residual region. |
