# Testing and verification

## Test layers

### Domain unit tests

Test formulas, placements, bounds, overlap, orientation restrictions, ranking, and governing constraints without Django templates.

### Service/serializer tests

Test:

- manual and catalogue inputs normalize identically;
- engine results serialize to primitives;
- selected candidate remains stable;
- report/presenter values match service values;
- numpy/Decimal/model objects do not leak into session contracts.

### Django view tests

Test:

- GET defaults;
- valid and invalid POST;
- permissions;
- correct template/context;
- PDF/image endpoints;
- public SEO demo versus normal defaults.

### Template/interaction tests

Where practical, test or manually verify:

- unique prefixed IDs;
- catalogue row selection;
- hidden-field hydration;
- repeated same-type workflow steps;
- result selection and downstream invalidation;
- no unexpected page-to-top scroll;
- collapsible instructions and 3D view controls.

## Shared consumer matrix

Every relevant change should record:

| Surface | Automated | Manual | Result |
|---|---|---|---|
| Standalone |  |  |  |
| Packaging Flow |  |  |  |
| Multi-product Container |  |  |  |
| Multi-product Bag |  |  |  |
| SEO/public |  |  |  |
| PDF/report |  |  |  |
| Catalogue source |  |  |  |

## Geometry assertions

For placement engines, tests should assert data, not only snapshots:

- `x >= min_x`, `y >= min_y`, `z >= min_z`;
- placement max coordinates stay within usable bounds/overhang;
- pairwise boxes/rectangles do not overlap;
- count equals placement list length;
- orientation is allowed;
- total weight and height are recomputed from primitives;
- deterministic ordering.

## Visual regression fixtures

Use stable fixtures for known sensitive layouts:

- container leftover packing;
- pallet 230×170×130 on 1200×800 pinwheel/mosaic;
- bag sealing margin displayed on length;
- transport door end and Main/Opposite/Top/Side views;
- base product L/W/H labels;
- equivalent one-row fixtures render identically in standalone and the related multi-product tool;
- genuine multi-row Bag/Container fixtures use the current shared graphics rather than legacy renderers.

Images may be compared with coordinate fixtures or approved snapshots, but never use image appearance as the only correctness test.

## Django checks and commands

Use commands actually configured in the repository. Typical examples:

```powershell
python manage.py check
python manage.py test <relevant_app_or_test_module>
```

Do not run a broad destructive migration or production command as a substitute for focused verification.

## Transport Container engine regression contract

The current active `engine.py` dispatch implements stabilized Space Evenly V1
and Load Front-to-Back V1 through the existing compatibility values
`maximum_utilization` and `maximum_utilization_floor_first`. Older fixture material may refer to the
former Maximum, Accessible, or Strict Sequence implementations; those legacy
paths are not imported by the current engine. Run focused checks for both
active modes and treat failures isolated to legacy-only modes as stale
compatibility expectations unless a task explicitly reactivates one.

Before changing Transport Container packing behavior, run or establish a direct engine regression module (preferably `packagingapp/tests/test_transport_container_engine.py`). These tests are independent of Three.js/HTML and complement visualization tests.

For each protected mode fixture, record a deterministic geometry signature containing at least `row_index`, `x`, `y`, `z`, `l`, `w`, and `h`, plus loaded counts by row. Assert the shared physical invariants (bounds, no positive-volume overlap, allowed orientations, support/stackability, and payload).

For a change scoped to one mode:

- the changed mode receives explicit acceptance assertions;
- unaffected established modes must keep their accepted count/signature fixtures unless the task explicitly approves a semantic change;
- a shared-helper change is incomplete until every unaffected established mode has been checked;
- visual appearance alone is never sufficient evidence of a packing-engine fix.

Use the canonical fixture definitions and mode semantics in `docs/domain/transport-container-engine.md`; do not duplicate the complete fixture specification here.
