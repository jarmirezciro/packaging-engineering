# Bag Selection Tool logic

## Purpose

Select the smallest feasible bag from a catalogue, or analyse a chosen bag, for a rectangular product/base unit while accounting for fit, sealing space, tolerances, quantity, and optional weight limits.

## Established behaviour

- Single Bag analysis returns the maximum feasible quantity for the chosen bag.
- Product and packaging dimensions are shown in mm.
- Product weight, packaging weight, and optional maximum payload are part of the result logic/UI where provided.
- Sealing margin belongs to **bag length**, not bag width.
- Product dimensions do not consume the sealing area; sealing space is reserved after the product-fit requirement is calculated.
- Width receives only its defined fit/tolerance allowance.
- Catalogue/product/packaging tables avoid redundant Select buttons when row selection exists.
- Results, instructions, images, and PDF follow the shared-tool direction and must also work in Packaging Flow and Multi-product Bag Selection.

## Multi-product Bag Selection consumer

Multi-product Bag Selection consumes the same bag-fit logic and, where applicable, the same presenter, graphics renderer, result labels, catalogue rows, and report components as the standalone Bag Selection Tool.

Its multi-product-specific responsibilities may include:

- accepting and normalizing several product rows;
- applying the documented combination/grouping strategy;
- aggregating product weights and quantities;
- presenting per-product and combined feasibility;
- serializing multiple rows safely.

These responsibilities do not justify a fork of the underlying bag equations or an outdated copy of the visualization. When standalone Bag graphics, sealing-margin representation, result cards, units, or PDF content change, explicitly test and update Multi-product Bag Selection in the same task.

**Repository verification required:** document the exact current grouping/combination algorithm after inspecting the multi-product engine. Do not assume that multiple products may be arbitrarily mixed, compressed, nested, or rearranged beyond the implemented strategy.

## Conceptual calculation flow

1. Normalize original product dimensions, quantity, weight, tolerance, and sealing space.
2. Generate the allowed planar product orientations used by the current bag engine.
3. For each orientation, compute the minimum required lay-flat bag width and length using the existing bag-fit equations.
4. Add tolerance only to the dimensions defined by the engine.
5. Add sealing space only to the bag-length closure direction.
6. Evaluate candidate bag dimensions against required width and length.
7. If multiple units can be arranged in one bag, evaluate only the packing arrangements supported by the engine; do not assume arbitrary 3D bin packing.
8. Apply payload/weight constraints separately from geometry.
9. In Single mode, return maximum feasible quantity and the governing constraint.
10. In Optimal mode, rank feasible candidates, normally preferring the smallest suitable bag/material area and least excess space.

## Exact formula policy

**Repository verification required:** the precise lay-flat equations and supported multi-unit arrangements must be read from the current bag engine before editing. Do not replace them with a generic web formula.

When documenting or refactoring exact equations, record them explicitly in this file using named variables. At minimum distinguish:

```text
product_length
product_width
product_height
fit_tolerance
sealing_space
required_bag_width
required_bag_length
```

## Assumptions

Unless current code says otherwise:

- product is represented by a rectangular bounding box;
- bag is represented by usable flat width and length;
- material thickness, stretch, gusset mechanics, valve geometry, and irregular product compressibility are not inferred automatically;
- sealing space is unavailable for product occupancy;
- catalogue dimensions use the same measurement convention as the engine;
- orientation restrictions and quantity arrangement are deterministic and enumerated.

## Constraints and invariants

- All dimensions must be positive.
- Sealing space and tolerance cannot be negative.
- A candidate cannot pass because of volume alone.
- Weight feasibility must include the correct number of products and packaging tare according to current definitions.
- A graphical bag must show the sealing margin at the length end, not as extra width.
- PDF values and image labels must match the selected candidate and original product dimensions.

## Ranking and tie-breaking

Document the current implementation after inspection. Intended transparent tie-breakers are:

1. feasible for desired quantity;
2. smallest bag area/material proxy;
3. smallest excess width/length;
4. lower packaging weight or other explicit business preference;
5. stable catalogue order/part number.

Do not silently change ranking while making a UI-only edit.

## Test cases to retain

- product fits exactly before tolerance and sealing margin;
- sealing margin changes required length only;
- increasing product height affects the lay-flat fit according to the existing formula;
- one dimension fits but the other does not;
- payload becomes the governing constraint;
- candidate ordering is deterministic;
- manual and catalogue inputs produce the same result;
- standalone, Packaging Flow, and Multi-product Bag Selection use the same authoritative fit rules and serialize compatible primitives;
- graphics changes appear in standalone and Multi-product Bag Selection;
- PDF and visualization use the selected result.

## Design Mode

Design Mode reuses the Bag Selection smooth-number rule that accepts quantities
whose prime factors are limited to 2, 3, and 5. The rule and recursive
prime-factor distribution now live in
`packagingapp/utils/quantity_decomposition.py`; the existing Bag Selection
functions import that source so Selection Mode behavior is preserved.

For Design Mode, the design quantity is the first smooth quantity greater than
or equal to the requested quantity. Bag Design and Container Design consume the
same canonical three-axis arrangement generator in
`packagingapp/utils/package_design_arrangements.py`. It enumerates every
permitted rows x columns x layers grid, applies the authoritative R1/R2/R3
orientation mapping, normalizes horizontal axes so bundle length is not shorter
than bundle width, keeps height distinct, and retains one deterministic
representative for each canonical bundle `(L, W, H)`. For an arrangement body
`(L, W, H)`, the existing equations remain:

```text
required_length = L + H + fit_tolerance + sealing_allowance
required_width  = W + H + fit_tolerance
```

The horizontal bundle normalization makes the first formula result the bag
length and the second the bag width; no second 90-degree bag option is created.
The opening is on bag width. There is exactly one Bag proposal per shared
canonical arrangement, and Bag rows use the same arrangement IDs, cubicity
ranking, representative orientation, and ordering as Container Design.
Squareness is not a Bag Design metric. Design Mode accepts only product weight
for optional net-content weight. Packaging weight, total package weight, and
payload metrics belong to later package evaluation and are not read or
serialized by Design Mode. Selection Mode's calculations, length/opening
convention, weight/payload handling, and Top 5 ranking are unchanged.

Single, Optimal, and Design results serialize the selected authoritative bag
arrangement into the shared `packageType=bag` Three.js scene. The standalone,
Packaging Flow, public calculator, and Multi-product Bag consumer all render
that contract. No active Bag result path writes a Matplotlib PNG. Standalone
PDFs embed the validated current Three.js snapshot.
