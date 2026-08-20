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

## Upstream inheritance

A downstream tool must know whether an input was:

- inherited from the selected upstream output;
- loaded from a catalogue;
- manually entered;
- overridden by the user.

Inheritance should populate the shared tool contract, not bypass the standalone service.

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

## Future combined report

A proposed Packaging Flow Report would use selected/effective results from each step and present:

- executive chain summary;
- final package/pallet/transport KPIs;
- main visualization;
- step-by-step assumptions and details.

Do not build it by scraping rendered HTML or by re-running inconsistent calculations.
