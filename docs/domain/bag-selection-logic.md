# Bag Selection Tool logic

## Purpose

Select the smallest feasible bag from a catalogue, or analyse a chosen bag, for a rectangular product/base unit while accounting for fit, sealing space, tolerances, quantity, and optional weight limits.

## Established behaviour

- Single Bag analysis returns the maximum feasible quantity for the chosen bag.
- Product and packaging dimensions use their selected display units and are calculated in millimetres.
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
2. Generate supported regular-grid arrangements and retain the identity of each bundle axis.
3. For each bundle, use each of its three spans as the insertion depth. The other two spans define the opening plane.
4. Add tolerance only to the dimensions defined by the engine.
5. Add sealing space only to the bag-length closure direction.
6. Evaluate candidate bag dimensions against required width and length.
7. If multiple units can be arranged in one bag, evaluate only the packing arrangements supported by the engine; do not assume arbitrary 3D bin packing.
8. Apply payload/weight constraints separately from geometry.
9. In Single mode, return maximum feasible quantity and the governing constraint.
10. In Optimal mode, rank feasible candidates, normally preferring the smallest suitable bag/material area and least excess space.

## Lay-flat sizing formula

For a rectangular bundle in a conventional non-gusseted bag, the opening
plane is perpendicular to the insertion depth. The shared Bag engine applies
both allowances in millimetres. Users can edit sealing allowance and fit
tolerance in every mode, including when selecting catalogue bags. Both fields
accept finite, non-negative decimals and use the bag-dimension unit selector.

```text
default_fit_tolerance = 2 mm
default_sealing_allowance = 10 mm
required_bag_width  = opening_a + opening_b + fit_tolerance
required_bag_length = insertion_depth + min(opening_a, opening_b) + fit_tolerance + sealing_allowance
```

Standalone, the public calculator, and each Packaging Flow Bag step keep the
entered values as strings in the selected bag-dimension unit. The shared
service validates and converts them to millimetres once per calculation. Old
configurations without either field receive the corresponding physical default.
An explicit zero is valid. A submitted blank is a validation error.

Sizing, capacity, catalogue fitting, utilization, and body dimensions use the
same values. Results, PDFs and selected workflow outputs carry the assumptions
used. Design candidate IDs continue to identify the arrangement and insertion
direction when the user changes the allowances. Multi-product Bag Selection
uses the same engine with the historical defaults.

Single and Optimal evaluate the three insertion depths for each supported
regular grid in descending span order, carrying the original product axes
with their grid counts. Within each grid, equal flat sizes retain the first
equivalent direction. Manual and catalogue fitting compare physical length
to required length and opening width to required width. Utilization is
required flat area divided by the physical flat bag area at the evaluated
quantity. The shortest and middle insertion depths have the same required
length. The shortest depth can require a wider opening, so it can improve
utilization and change selection without raising the geometric quantity limit.

## Product dimensional allowance

Bag Selection uses the same shared product-dimension transformation as
Container Selection. Each optional length, width, and height allowance is
converted to canonical millimetres and added once to the matching nominal axis
before the existing bag-sizing, Design, Single, Optimal, and capacity-only
calculations run. Existing sealing, fit-tolerance, material, and arrangement
formulas are unchanged.

Nominal product dimensions remain the physical values used by the product
Three.js scene and catalogue data; effective dimensions are separate transient
packing inputs and report fields. Blank/missing allowances are zero for
backward compatibility. Catalogue-backed product fields and allowances use
the same active product-dimension selector as manual entries; catalogue
dimensions remain canonical millimetres at the service boundary and are
converted for display by the picker.

## Assumptions

Unless current code says otherwise:

- product is represented by a rectangular bounding box;
- bag is represented by usable flat width and length;
- material thickness, stretch, gusset mechanics, valve geometry, and irregular product compressibility are not inferred automatically;
- sealing space is unavailable for product occupancy;
- catalogue dimensions use the same measurement convention as the engine;
- supported quantity arrangements are deterministic and enumerated; Bag Design does not expose R1/R2/R3 restrictions because the complete flexible-bag arrangement may be rotated during handling.

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
rows x columns x layers grid and every axis-aligned product orientation. Bag
Design deliberately does not apply R1/R2/R3 restrictions: unlike an RSC, the
complete flexible-bag arrangement may be rotated freely during handling to meet
product-orientation needs. The shared generator then normalizes horizontal axes
so bundle length is not shorter than bundle width, keeps height distinct, and
retains one deterministic representative for each canonical bundle `(L, W, H)`.
Design evaluates insertion along `L`, `W`, and `H` in each canonical
arrangement. Each arrangement produces up to three distinct flat sizes
with a width-side opening and 100% flat-area utilization. The canonical
arrangement IDs, cubicity ordering and representative product placements
come from the shared Container Design generator. Bag Design keeps the first
proposal for each matching flat size and insertion-relative grid. Packed
bundles with more than one product also retain distinct upright spans and
layer counts because these distinguish downstream packing. For a single
90 × 60 × 25 mm product, nine proposals consolidate to three. Older IDs for
removed rotations resolve to the retained proposal with the same flat size.
Squareness is not a Bag Design metric. Design Mode accepts only product weight
for optional net-content weight. Packaging weight, total package weight, and
payload metrics belong to later package evaluation and are not read or
serialized by Design Mode. Selection Mode keeps its length/opening convention,
weight and payload handling, and Top 5 scoring.

Single, Optimal, and Design results serialize the selected authoritative bag
arrangement into the shared `packageType=bag` Three.js scene. The standalone,
Packaging Flow, public calculator, and Multi-product Bag consumer all render
that contract. No active Bag result path writes a Matplotlib PNG. Standalone
PDFs embed the validated current Three.js snapshot.

The scene's `bag.insertion` carries the selected depth and opening-plane
axes and spans in millimetres. Design axes refer to the canonical bundle.
Selection axes refer to the original product grid before it is placed in
the bag. `bag.film` identifies the depth axis and dimensions in the actual
placement coordinates, so the viewer can form the film around the bundle
without moving the products.

## Bag area in result tables

Design alternatives and Optimal Top 5 rows display the flat-bag area to two
decimal places. The bag-dimension selector determines the display unit. Use
cm² for mm, cm, and m, and in² for in and ft. Calculation and ranking use the
canonical area in mm².

## Case compendium

`/regressions` lists the Bag Selection cases from
`packagingapp/tools/bag/case_presets.py`. Each case opens the standalone tool
with its configured inputs and units and runs the normal analysis on load.
Submissions use the current form values. To add a case from a screenshot,
transcribe its mode, manual inputs and units into a new registry entry, then
verify the resulting quantity or candidates against the current tool.
