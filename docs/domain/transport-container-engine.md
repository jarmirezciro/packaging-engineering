# KolliPack Transport Container Engine — Space Evenly and Load Front-to-Back DGFE

## Status and authority

This is the technical deep dive for the current Transport Container calculation
engine and the checked-out repository baseline (August 2026). The authoritative
implementation is:

`packagingapp/utils/container_tool/engine.py`

The active engine contains four isolated deterministic modes: the approved
baselines **Space Evenly with V1 Product Blocks and Residual Frontier Closure
V2** and **Load Front-to-Back with DGFE**, plus their opt-in **Mixed Cargo
Infill** variants. The canonical identifiers are `space_evenly`,
`front_to_back`, `space_evenly_infill`, and `front_to_back_infill`.
Load Front-to-Back retains `maximum_utilization`,
`maximum_utilization_floor_first`, `front_to_back_blocks`, and
`load_front_to_back` as input compatibility aliases only. Its baseline internal
strategy remains `front_to_back_blocks`. The transport service, forms, views, templates,
serializers, and tests are supporting consumers and must be checked against
the engine when behavior changes.

`packagingapp/utils/container_tool/engine_legacy.py` is retained historical code.
It is not the current algorithm specification and is not imported by the active
engine. A requested mode other than the four canonical modes or a recognized
compatibility alias returns a graceful unsupported result with no placements.

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

## Mixed Cargo Infill variants

The two infill variants preserve their parent macro orchestration and add one
shared constructive closure over each bounded local product/frontier window.
Space Evenly closes a current product's contiguous span after all of its
approved complete blocks are committed, and then closes each committed
Space-Evenly residual frontier in its own X window. Load Front-to-Back closes
after the current product's complete blocks and its approved Native/DGFE
transition are committed. Every window is fixed in X and is never reopened
after the phase is closed. Residual-frontier candidate selection is completed
before its optional side closure; side infill never changes the winning
candidate, depth, or frontier score.

Within that window, side residuals are derived from the actual committed
placement geometry. X breakpoints come from the window edges and every
intersecting placement's `x`/`x + l`; each X slab is complemented against the
projected occupied Y intervals. The complements are floor-to-ceiling spaces:

```text
x = slab_start ... slab_end
y = each free interval in 0 ... container width
z = 0 ... container height
```

Only complete-face-compatible neighbours are merged. A Product Block boundary
is therefore computational only: a physically continuous residual can span
multiple blocks, and a partial filler leaves its unused X tail for the next
local closure iteration. Z is intentionally ignored when projecting occupied
XY footprints; this V1 closure solves lateral side spaces, not top cavities.
Mixed Cargo Infill then runs a separate supported-top closure in the same fixed
X window. It collects coplanar top planes from actual stackable placements,
coordinate-compresses the support union and any cargo above that plane, and
emits only roof-clear rectangles. Different support heights never merge;
complete-face-compatible atomic cells may merge within one plane. Top fillers
reuse the Product Block candidate generator and are physically validated
against local committed placements, with bottom-up re-derivation after every
committed block. The closure order is therefore side first, supported top
second, then window close.

Top closure may evaluate the current/anchor product when its remaining quantity
is positive; it competes with the existing permitted later-product set under
the same sequence, payload, orientation, support, overlap, and bounds rules.
Side closure continues to exclude the current anchor product.

The filler reuses the active Product Block candidate generator inside each
derived space. It selects one product/candidate, commits whole modules and at
most one deterministic partial final module, then re-derives the local envelope
from the committed placements. There is no global free-space search and no
historical window reopening.

Candidate ranking is stable and local to the current residual:

1. maximum actual packed volume;
2. maximum Product Block transverse utilization in the residual;
3. maximum quantity;
4. minimum X depth required;
5. largest valid footprint in the residual;
6. larger unit volume and longest dimension;
7. parent product order and Product Block stable orientation key.

The parent block quantity is authoritative. Fillers use enabled R1/R2/R3
orientations, the existing non-stackable vertical cap, and the shared payload
arithmetic. Materialized filler blocks start on the floor; physical overlap is
excluded by deriving the next residual envelope from all committed geometry.

Only the infill variants retain input sequence values. One distinct sequence
means unrestricted later-product cooperation. More than one distinct sequence
activates protection: side infill is limited to later products in the current
sequence group. Space Evenly closes residual frontiers one sequence group at a
time. Front-to-Back retains its existing immediate Pi/Pi+1 transition, so any
cross-group interaction is limited to the adjacent transition frontier. A
later sequence group cannot fill an earlier closed side strip or leapfrog an
intermediate group.

The implementation performs no permutation, historical-gap scan, recursion,
backtracking, beam search, or container cloning. Candidate work is bounded by
committed side residuals × eligible products × geometry-derived Product Block
candidates. Quantity affects the committed module count and final placement
materialization, not the number of future packing branches.

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

> **Space Evenly is a deterministic two-phase transport-loading heuristic that first converts large product quantities into YZ-optimized regular blocks and then closes bounded, union-supported residual frontiers, following a Y → Z → X filling philosophy.**

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

1. Optimize the current width and discover valid support planes.
2. Fill the complete bounded residual frontier before consuming more length.
3. Advance the longitudinal frontier after the selected candidate is validated.

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

This is automatic ordering, not a user loading sequence. It determines the
order of Phase 1 Product Blocks and is the primary residual-anchor priority in
Phase 2. A lower-priority SKU may still fill valid capacity inside the active
anchor frontier.

## Two-phase architecture

```text
SPACE EVENLY
      |
      +-- PHASE 1 — REGULAR PRODUCT BLOCKS
      |
      +-- complete frontier
      |
      +-- PHASE 2 — RESIDUAL FRONTIER CLOSURE V2
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

## Phase 2 — Residual Frontier Closure V2

Phase 2 keeps the common residual pool and starts at the unchanged Phase 1
frontier. The first feasible product in `ordered_products` is the residual
anchor Pi. Support potential does not override that priority.

For every enabled Pi orientation, the engine evaluates Bottom-Up Row-First and
deferred Top-Down Row-First candidates. Pi is materialized with the maximum
payload- and geometry-feasible quantity in the smallest actual X footprint.
That placement-derived footprint defines the Native Frontier; an orientation's
nominal length is not assumed to be the whole footprint.

The remaining SKUs are then processed in `ordered_products` priority inside the
complete bounded frontier. Every enabled orientation is evaluated, and the
selected orientation maximizes quantity, Y utilization, and local volume
utilization before preferred-orientation and stable-index ties. Candidate
positions include the floor and top planes of stackable local placements.

Elevated cargo requires full rectangular base support from the **union** of
coplanar stackable lower surfaces. Contiguous seams are valid; unsupported gaps
and overhangs are not. The frontier is therefore not split into independent
per-unit support columns, and upper cargo is not centered on one supporter.

Deferred candidates reserve Pi cuboids from the top, fill other residual SKUs,
then settle Pi vertically without changing X, Y, or orientation. Settlement
requires a clear vertical path. Every final trial is checked for bounds,
positive-volume overlap, full-base support, stackability, height, and payload
before it can be ranked or committed.

Candidate ranking is:

1. maximum Pi quantity;
2. minimum actual Pi X footprint;
3. maximum frontier volume efficiency;
4. maximum other-product packed volume and quantity;
5. minimum committed depth;
6. Row-First, Bottom-Up, and stable orientation ties.

The frontier volume efficiency is packed local volume divided by the complete
`depth × container width × container height` prism. A bounded extension may add
the first clean row implied by the next remaining SKU. Its extra packed volume
is divided by only the extra X prism and compared with a clean whole-pool Pj
frontier built by the same Native physics. The extension remains eligible only
when its marginal efficiency exceeds that clean alternative; a tolerance tie
closes Native.

Only the selected trial mutates placements, quantities, weight, item indices,
and the X frontier. The loop stops when residuals are complete, no physical
candidate exists, payload is exhausted, or X is exhausted. The previous
`SupportSurface` greedy helpers remain in the module for compatibility testing
but are not the active Space Evenly Phase 2 path.

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
Blocks, residual-frontier candidates, diagnostics, and placements. Stable orientation
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
| `space_evenly_residual_frontiers` | selected anchor, geometry, scores, physical validation, and JSON-safe candidate diagnostics for each closed frontier |
| `space_evenly_residual_bands` | compatibility alias for the selected residual frontiers |
| `space_evenly_support_surface_count` | contiguous stackable top surfaces in committed residual frontiers |
| `space_evenly_support_checks` | compatibility count for local placement evaluations |
| `space_evenly_residual_local_placement_evaluations` | deterministic local candidate-position evaluations |
| `space_evenly_support_relationship_count` | committed elevated placements requiring support |
| `space_evenly_residual_units` | all residual units sent to Phase 2 |
| `space_evenly_residual_packed_units` | residual units placed |
| `space_evenly_block_candidates_generated` | generated Phase 1 candidates |
| `space_evenly_block_candidates_evaluated` | Phase 1 candidates evaluated |
| `space_evenly_residual_candidates_evaluated` | Phase 2 candidates evaluated |
| `space_evenly_x_used` | final occupied longitudinal frontier |
| `front_to_back_frontiers` | bounded transition diagnostics, all orientation/strategy/family outcomes, final physical state, and the selected winner |
| `front_to_back_product_blocks` | per-product block, residual, and carry-forward summaries |
| `front_to_back_frontier_candidates_evaluated` | next-product orientation evaluations across the isolated transition candidates |
| `space_evenly_infill_*` / `front_to_back_infill_*` | bounded side-residual counts, volume, units by product, block candidate counts, sequence status, and deterministic action records |
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

Space Evenly does not prove or calculate:

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
- ordered residual-anchor priority and quantity-agnostic compact Pi footprints;
- whole-frontier floor/top-plane population and combined union support;
- unsupported gaps, non-stackable foundations, and non-stackable upper cargo;
- Bottom-Up and deferred Top-Down Row-First trials;
- clean-frontier versus marginal-extension efficiency and Native tie preference;
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

Maximum Utilization and Maximum Utilization Floor First remain recognizable
input compatibility values and may be referenced by older regression material;
they are not current user-facing labels. Sequence Loading and Strict Sequence
Loading remain unsupported historical values. Their former algorithm descriptions
are historical compatibility context, not active behavior in the current
`engine.py`. The former generic sequence-loading algorithms remain historical
compatibility context and are not imported by the current engine. The
`maximum_utilization` and `maximum_utilization_floor_first` values now route to
Load Front-to-Back with DGFE; other historical values return an explicit
unsupported-mode result.

## Glossary

| Term | Definition |
|---|---|
| Space Evenly | The structured two-phase heuristic using V1 regular Product Blocks and Residual Frontier Closure V2. |
| Load Front-to-Back | The approved block-and-local-frontier DGFE heuristic, canonically `front_to_back`. |
| Mixed Cargo Infill | An opt-in parent-mode extension that constructively fills only the current Product Block's bounded side strip with compatible later products. |
| Deferred-Gravity Frontier Envelope (DGFE) | A bounded Front-to-Back candidate construction that temporarily reserves a top-down residual, fills the next product around it, and restores vertical gravity before validation. |
| Stepped Frontier Envelope (SFE) | The physically valid local boundary produced by residual construction, next-product population, and any deferred settlement. |
| Product Block | A regular one-SKU module repeated longitudinally. |
| Transverse Pattern | The Y × Z arrangement defining a Product Block. |
| Module Capacity | Units in one complete longitudinal Product Block module. |
| Transverse Capacity | Units represented in the Y × Z cross-section before X repetitions. |
| Synchronized Depth | Common X depth satisfying `rA × dA = rB × dB` for mixed lanes. |
| Residual Quantity | Requested units remaining after complete regular blocks. |
| Residual Frontier | One bounded, physically validated local XYZ section established by the current residual anchor Pi. |
| Native Frontier | The residual frontier ending at Pi's actual compact X footprint. |
| Union Support | Complete elevated base coverage supplied by one or more coplanar stackable placements without gaps. |
| Frontier | Current X coordinate after the completed regular or residual region. |
