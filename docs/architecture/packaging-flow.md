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

## Future combined report

A proposed Packaging Flow Report would use selected/effective results from each step and present:

- executive chain summary;
- final package/pallet/transport KPIs;
- main visualization;
- step-by-step assumptions and details.

Do not build it by scraping rendered HTML or by re-running inconsistent calculations.
