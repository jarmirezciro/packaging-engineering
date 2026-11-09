# Packaging Flow architecture

## Purpose

Packaging Flow (historically called Full Packaging Mode) chains independent tools while preserving each tool’s standalone usefulness.

Established chain:

```text
Container/Box Selection
  → Bag Selection where applicable
  → Palletization
  → Transport Container Loading
```

The exact available step order may be more flexible in the current UI.

## Stable shell behaviour

The workflow shell is a product feature and must not be casually redesigned. Historically approved behaviour includes:

- session-based steps;
- add/remove steps;
- expand/collapse controls;
- selected-result summary;
- inline add-step bar;
- no nested forms;
- no automatic collapse after calculation;
- downstream invalidation when an upstream selection changes;
- a tool can run as the first step using the same capability as standalone;
- later steps can inherit the effective output of previous steps.

## Historical session contract

The workflow used:

```python
SESSION_KEY = "full_packaging_mode_session"
```

Representative step fields included:

```python
{
    "type": "...",
    "expanded": True,
    "selected": {...} | None,
    "summary": {...} | None,
    "candidates": [...],
    "result_image_url": "..." | None,
    "config": {...},
    "messages": [...],
}
```

Verify the current schema before editing.

## JSON-safe state

Session values must be JSON-compatible:

- strings;
- integers/floats;
- booleans;
- `None`;
- lists/dictionaries containing only these values.

Serialize or flatten:

- Django models and QuerySets;
- `Decimal`;
- dataclasses;
- numpy values;
- placement objects;
- paths/URLs;
- engine-specific result classes.

Past failures included `TypeError: Object of type PackagingMaterial is not JSON serializable`. The prevention belongs in shared serializers, not ad hoc workflow patches.

## Physical mass contract

Packaging Flow uses kilograms as the authoritative physical-mass value in a
selected/pending output (`weight_kg`). A JSON-safe `weight_g` value is derived
from the same physical value only for downstream gram-based tools such as
Container Selection, Bag Selection, and Palletization. Transport consumes
`weight_kg` directly. Catalogue `Product.weight` and
`PackagingMaterial.part_weight` are kilograms; manual Container/Bag/Pallet
inputs are converted from grams once at the workflow boundary. See
`../UNIT_SYSTEM_AUDIT.md` for the complete contract and compatibility rules.

The Palletization step stores optional `max_pallet_load` as ordinary JSON-safe
prefixed form state in the selected display mass unit. The shared service
normalizes it to grams and the shared engine returns `actual_pallet_load_g` for
the carton cargo. Flow uses that authoritative cargo result when constructing
the downstream pallet mass, then adds catalogue pallet tare in kilograms. The
maximum pallet load itself always excludes pallet tare.

Container Selection follows the same boundary for carton tare. Its shared
report resolves explicit analysis tare, catalogue tare, calculated eligible-RSC
material tare, or unavailable in that order. For a selected manual or catalogue
box, a corrugated-board choice calculates the finished FEFCO 0201 material mass
from that candidate's dimensions; it is not a second packing or thickness
calculation. The Container Flow adapter copies the report's gross carton
weight once into the downstream payload's authoritative `weight_kg` and keeps
the tare source metadata JSON-safe. If product weight is unknown, tare may be
reported independently but gross weight remains unavailable rather than
silently treating tare as total contents.

Container analysis overrides live in prefixed form/session state, scoped to the
selected packaging/product IDs. Advanced controls use the same presenter and
resolver as standalone; their collapsed state does not disable fields. Accepted
outputs carry a JSON-safe, versioned `effective_specification` containing source
IDs, effective internal/external dimensions, caliper, grammage, provenance,
product mass, net/tare/gross mass, payload and packed quantity. Palletization and
Transport copy it to `upstream_packaging_specification`, preserving the original
carton ID while using the accepted physical dimensions and mass. They do not
reload catalogue defaults to reconstruct the accepted carton.

An edited Container specification clears its accepted output and invalidates
dependent results through the existing mechanism. Acceptance recalculates any
submitted Container fields first. Client edits mark the displayed result stale
and disable acceptance and report export until recalculation. Catalogue product
and packaging records are read-only throughout this analysis path.

## Manual unit display state

Each embedded shared tool keeps its own prefixed, JSON-safe manual unit tokens
in the existing step config. These tokens are presentation/input state only.
Selected and pending workflow payloads continue to carry canonical physical
geometry and authoritative `weight_kg` (with derived `weight_g` for gram
consumers).

When canonical upstream values populate a downstream manual form, Flow adapts
them to that form's selected display unit before rendering. Transport retains
exact canonical scalars for inherited load rows and converts those scalars only
for the visible multi-row inputs. Server normalization then restores the same
`mm`/`kg` Transport contract before the shared service runs. Returning to a
step or accepting its result therefore cannot relabel a canonical millimetre
or kilogram value as inches, feet, ounces, or pounds.

## Upstream inheritance

A downstream tool must know whether an input was:

- inherited from the selected upstream output;
- loaded from a catalogue;
- manually entered;
- overridden by the user.

Inheritance should populate the shared tool contract, not bypass the standalone service.

### Inherited input

**Current implementation note:** an inherited input is a JSON-safe physical
output from the effective upstream step that is normalized into the downstream
tool's ordinary input contract. It records upstream provenance but does not
bypass the downstream form, service, validation, or engine. A user override is
distinct from an inherited value and must remain explicit.

### Pending and selected results

**Current implementation note:** a pending result is the freshest successfully
calculated output displayed by a step before the user explicitly accepts it. A
selected result is the output the user has committed for downstream
propagation. Where a consumer needs the freshest physical output for the active
step, current orchestration prefers `pending_result` and otherwise falls back to
`selected`; it does not silently turn a pending result into an explicit user
selection.

### Assistant scope

**Current implementation note:** the current Assistant pilot is attached only
to Container Selection steps. One Assistant request receives the active
Container step's validated Tool Context plus approved documentation. It does not
receive every Packaging Flow step, and documentation about Bag, Palletization,
or Transport never supplies those tools' live inputs, pending result, selected
result, or calculation state.

Bag and Container Selection store one authoritative `mode` value: `design`,
`single`, or `optimal`. The short-lived legacy `tool_mode=design` state is read
as `mode=design` and then discarded; new state never writes `tool_mode`.
Design results store requested and designed quantities, selected stable
candidate ID, arrangement, orientation, designed dimensions, metrics, and a
JSON-safe Three.js scene. Package weight and payload fields are not Design Mode
result properties. The explicitly selected candidate becomes the
pending/committed package output; downstream steps must not silently replace it
with the first-ranked candidate.

## Transport layout parity

A historically approved workflow transport arrangement was:

1. transport-container section at the top with collapse control;
2. 3D result and summary below the transport unit;
3. product/load-unit section below the result area.

The current standalone wrapper is still the source of truth. Workflow should adapt it, not recreate it.

## Direct pallet-to-transport visualization

When a Palletization step directly precedes Transport, the pallet output keeps
the authoritative JSON-safe pallet browser scene beside its existing transport
bounding dimensions under an explicit `palletization_result` source marker.
Transport calculations still consume only the inherited rectangular row. After
the shared transport service returns its authoritative cuboid placements, the
Flow view decorates those scene items with a reference to the one shared pallet
visualization payload and an orthogonal orientation code. The browser then
clones one detailed pallet assembly per placement and applies the cuboid center
and orientation to the parent group.

This decoration is Flow-only. Standalone Transport, the public calculator, and
non-palletized Flow inputs retain generic load cuboids. The adapter validates
the complete pallet-and-carton assembly against the calculated bounds and falls
back to the cuboid if the source scene is incomplete or extends outside them.

## Top quantity summary

Packaging Flow presents a compact, always-visible quantity summary above the
step cards. It reads the active JSON-safe chaining payload from each step and
shows both the immediate conversion and cumulative base-product quantity, for
example: products per box, boxes and products per pallet, and pallets, boxes,
and products per transport container.

The summary is presentation-only. It must not rerun tool engines or create a
second quantity calculation path. It prefers the current pending result, falls
back to the explicitly selected result, and fails closed after an incomplete or
inconsistent stage. Existing collapsed-step summaries remain unchanged. Desktop
uses a compact horizontal chain; mobile uses a collapsed summary row that can be
expanded into a stacked chain.

Physical text in the compact summary and combined report is also
presentation-only. Each stage decorates its canonical `length`/`width`/`height`
and authoritative `weight_kg` with that stage's local input/output unit context.
The stored workflow payload is not mutated. Legacy steps without unit metadata
use Container/Bag/Palletization `mm`/`g` or Transport `mm`/`kg` defaults.

## Design final-capacity ranking

Container Selection and Bag Selection Design steps can optionally rank their
existing alternatives by cumulative base-product units at the actual final
Packaging Flow step. This is a Flow-only orchestration feature: it walks the
ordered downstream `workflow["steps"]` slice and runs capacity-only service
entry points on temporary step copies. Those entry points reuse each tool's
authoritative numeric engine and shared workflow-payload builders, but skip PNG,
Three.js, analysis-report, and other presentation work. Engine candidate
generation, normal standalone ranking, and interactive rendering are unchanged.

The source step stores JSON-safe `design_chain_optimization` metadata keyed by
stable `candidate_id`. Canonical Design candidates remain in engine order; the
Flow view builds a transient annotated display list. Structural changes and
relevant source/downstream input changes clear stored optimization state, while
selecting another candidate from the unchanged source table preserves it.
Palletization POSTs compare normalized capacity inputs after inherited defaults
are applied; UI-only advanced-panel changes and no-op refreshes preserve the
ranking. Pallet row/pattern selection is treated as presentation-only, so users
can explore layouts without losing optimization results. A changed pallet
dimension, constraint, or material clears the stale ranking and tells the user
to run the optimization again.

### Container dimensions passed downstream

Container Selection keeps internal dimensions in explicit `internal_*` result
fields, while its generic workflow `length`, `width`, and `height` represent the
resolved physical external carton size. Palletization therefore receives the
outside carton dimensions. Normal selected Design candidates and temporary
Packaging Chain Optimizer candidates use the same shared Container dimension
resolver and payload builder, so both paths provide identical carton dimensions
to downstream capacity evaluation. Missing thickness in an older workflow
payload remains valid and resolves through the centralized 4 mm assumption.

### Product dimensional allowances

The first Container or Bag product step owns the product allowance inputs and
passes them through the shared standalone service boundary. The allowance is
applied once per product axis before that step's packing engine runs; nominal
product geometry and weight remain unchanged. The resulting JSON-safe workflow
payload contains the calculated outer package dimensions, not a second copy of
the product allowance.

When a downstream packaging step inherits dimensions from an upstream package,
the adapter treats those inherited dimensions as already effective and resets
the downstream product allowance fields to zero. This prevents double-counting
while preserving the existing downstream quantity and outer-dimension
propagation rules. Full Packaging Workflow does not introduce a separate
allowance calculation path.

## Combined report

The entitled Packaging Flow PDF uses the current effective results and each
step's local unit context. It reads the same workflow state as the summary.
Downstream invalidation also clears cached pallet results and package analysis
reports so their metrics cannot appear in the export after an upstream edit.

## Named cases in the Regression & Case Compendium

The **Packaging Flow Cases** section at `/regressions` opens the registered
Python presets through the existing case route with `?reset=1`. Each slug has
its own session key. Article links without the reset parameter resume that
case's session. The preset initializes ordinary Flow steps and accepts their
shared-service results. Subsequent edits, optimization, summaries,
visualizations, and entitled PDF exports follow the regular Flow paths.

The counts below are current Flow results. Quantities in each chain are
expressed per unit of the next packaging stage.

| Case | Historical reference or fixture | Current Flow result |
| --- | --- | --- |
| PF-01 Think Beyond the Box | [Published study](../../packagingapp/content/blog/articles/think-beyond-the-box-packaging-flow-case-study.md) compares 16 and 24 cartons per pallet, both at 50 pallets per transport unit. | Opens on Alternative 7 with 12 products/carton × 24 cartons/pallet × 48 pallets = 13,824 products. The compact design now gives 20 cartons/pallet and 11,520 products. Alternative 23 now gives 21 cartons/pallet and 12,096 products. |
| PF-02 TOPS Product and Pallet Optimization Benchmark | [TOPS comparison](../../packagingapp/content/blog/articles/tops-pro-case-size-optimization-kollipack-comparison.md) records 144 cartons and 1,152 products for the 8-pack, and 77 cartons and 1,232 products for the 16-pack. | Both counts reproduce. The 8-pack opens at 288 × 161 × 194 mm external because the preset's preferred 314 × 148 × 194 mm is an external size and the loader matches internal dimensions before falling back to the default candidate. For the 16-pack, select 356 × 280 × 153 mm internal, which passes 364 × 288 × 169 mm external to the pallet. |
| PF-03 216 or 240 Cartons per Pallet? | [CapePack comparison](../../packagingapp/content/blog/articles/cartons-per-pallet-case-design-exploration.md) uses 12 primary cartons per shipping case. | The 20 × 18 × 8 in internal design opens at 20 cases and 240 primary cartons per pallet. The 15 × 12 × 16 in internal design gives 18 cases and 216 primary cartons. Palletization inherits the external size in both runs. |
| PF-04 CapePack Parameter Fine-Tuning | [CapePack continuation](../../packagingapp/content/blog/articles/capepack-parameter-fine-tuning.md) uses a 72 in total height limit. | The starting 12-pack gives 30 cases and 360 primary cartons per pallet. Set the quantity to 16 and select the 16 × 12 × 20 in internal design to reproduce 24 cases and 384 primary cartons. |
| PF-05 Full Chain with Bag | New demonstration based on the [public Bag Selection fixture](../../packagingapp/tools/bag/case_presets.py). | 6 products/bag × 4 bags/carton × 12 cartons/pallet × 30 pallets = 8,640 products. |
| PF-06 Bag Design Final Capacity | New demonstration using the existing Bag Design and final-capacity services. | Starts at 4 products/bag × 24 bags/carton × 8 cartons/pallet = 768 products. Optimize final capacity ranks the 272 × 112 × 20 mm bag first. Accept and recalculate it to get 4 × 126 × 8 = 4,032. |
| PF-07 Mixed Units Across the Chain | New demonstration based on [the metric-equivalence test](../../packagingapp/tests/test_task6_unit_presentation.py). | 60 products/carton × 18 cartons/pallet × 30 pallets = 32,400 products. The inherited pallet mass is 497.979756 kg before conversion for display in pounds. |
| PF-08 Nested Packaging Chain | New demonstration using two ordinary Container Selection steps. | 55 products/inner carton × 2 inner cartons/outer carton × 6 outer cartons/pallet × 30 pallets = 19,800 products. |
| PF-09 CapePack Bottle — 24 Units | [Bottle benchmark case A](../research/benchmarks.md#palletization-cases) | 24 bottles/carton × 21 cartons/layer × 2 layers = 1,008 bottles. Zero overhang reproduces the captured layout. |
| PF-10 CapePack Bottle — 15 Units | Bottle benchmark case B | 15 bottles/carton × 18 cartons/layer × 4 layers = 1,080 bottles, with the captured 1.45 in length and 1 in width overhang. |
| PF-11 CapePack Bottle — 20 Units | Bottle benchmark case C | 20 bottles/carton × 12 cartons/layer × 4 layers = 960 bottles, with zero overhang. |

The bottle presets start Design Mode with the shared Container Selection
inputs. Flow resolves the reference candidate by its internal dimensions and
arrangement, then passes the generated external carton to Palletization.

### PF-01 transport discrepancy

The current selected 600 × 250 × 300 mm internal carton is 608 × 258 × 316 mm
external. The pallet has four layers above its 80 mm deck. Its configured
transport envelope is 1,225.4 × 825.4 × 1,344 mm, including the footprint
allowance. The 12,032 × 2,352 × 2,698 mm transport unit takes 10 lengthwise
and 14 rotated pallets on each of two levels, occupying 2,688 mm in height.

With these upright orientations a horizontal slice can have at most two
pallets across its width, and the 1,225.4 mm-wide orientation can appear at
most 14 times along the length because two of them cannot sit side by side.
Even with 14 of the shorter orientation, 25 pallets would require 25,035 mm
of summed length across the two available positions, which provide 24,064 mm.
That caps each horizontal slice at 24 pallets. Across the full height,
49 pallets would require 65,856 pallet-mm of height and the unit provides at
most 64,752. The current 48 is therefore a geometric limit for this envelope.

A capacity-only run with the same height, transport unit, and rotation rules
returned 50 when only the footprint changed to the nominal 1,200 × 800 mm.
The rotated lane then takes 15 pallets instead of 14 on each level.
The earliest committed preset (`68fc1ec`) used zero overhang. Commit
`b635c34` added 25.4 mm allowances in both axes, and `f6061c0` records the
earlier automated result of 38 moving to 48. The archived article's pallet
capture shows a 1,200 mm carton stack. The exact transport row from the
historical capture is unavailable, so the footprint comparison isolates a
verified cause of the two-load difference without assigning unrecorded
settings to the article. The current preset leaves product mass unspecified.

### Demonstration inputs

- PF-05 uses a 180 × 120 × 40 mm, 250 g product and a 450 mm length × 330 mm
  opening-width bag with 18 g tare and a 5 kg payload limit. The public fixture requests four
  products and Single mode selects its capacity of six. The downstream
  physical bundle envelope is 318 × 208 × 120 mm and weighs 1.518 kg.
  The carton is 590 × 390 × 250 mm internal with 4 mm caliper, 450 g tare,
  and a 15 kg payload limit.
- PF-06 uses a 90 × 60 × 20 mm, 50 g product and requests a four-product bag
  design. Bag Design carries content mass. No material or bag tare is
  specified. The carton uses a 375 mm internal height so every generated
  bag design fits. Its 30 kg payload limit accommodates the top-ranked
  design's 25.2 kg of contents per carton.
- PF-07 uses a 100 × 80 × 60 mm product entered in inches at 1 lb, a
  40 × 30 × 25 cm internal carton with 450 g tare and a 35 kg payload limit,
  and a pallet that reads carton dimensions in inches and mass in kilograms.
  Its bottom-carton load limit is 100 kg. The transport and load inputs use
  feet and pounds.
- PF-08 starts from the PF-07 physical product and carton in metric units
  and applies a 5 mm product length allowance at the first step. The second
  step receives the finished 408 × 308 × 266 mm carton at 25.39758 kg with
  zero inherited allowance. The outer carton is 820 × 320 × 280 mm internal
  with 650 g tare and an 80 kg payload limit.
- PF-05 through PF-08 use a 1,200 × 800 × 144 mm manual pallet, zero overhang,
  and a 1,200 mm total height limit. No empty-pallet tare is entered. The
  complete chains use a 6,000 × 2,500 × 2,600 mm transport unit with a
  20,000 kg maximum gross weight and 1,000 kg tare.
