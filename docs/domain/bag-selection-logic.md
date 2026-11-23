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
10. In Optimal mode, rank feasible catalogue candidates by highest bag usage and then smallest flat-bag area.

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
- supported quantity arrangements are deterministic and enumerated. Bag Design evaluates the product orientations permitted by R1/R2/R3.

## Constraints and invariants

- All dimensions must be positive.
- Sealing space and tolerance cannot be negative.
- A candidate cannot pass because of volume alone.
- Weight feasibility must include the correct number of products and packaging tare according to current definitions.
- A graphical bag must show the sealing margin at the length end, not as extra width.
- PDF values and image labels must match the selected candidate and original product dimensions.

## Ranking and tie-breaking

Bag Design ranks deduplicated alternatives by ascending unrounded flat-bag
area in canonical mm². Equal areas retain generation order. Capacity-only
analysis and steps with downstream packaging use this engineering order when
no valid candidate ID is supplied. Standalone and terminal workflow use the
first visible row after [display grouping](#terminal-display-grouping).

Optimal Mode ranks feasible catalogue bags by highest bag usage and then by
smallest area. Packaging Flow's optional final-capacity optimization ranks
Design trials by highest downstream base-unit count, using the underlying
area-based Bag Design rank to break ties.

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
rows x columns x layers grid for the axis-aligned product orientations enabled
by [product rotation permissions](#product-rotation-permissions). The shared
generator then normalizes horizontal axes
so bundle length is not shorter than bundle width, keeps height distinct, and
retains one deterministic representative for each canonical bundle `(L, W, H)`.
Design evaluates insertion along `L`, `W`, and `H` in each canonical
arrangement. Each arrangement produces up to three distinct flat sizes
with a width-side opening and 100% flat-area utilization. Canonical
arrangement IDs, generation order and representative product placements
come from the shared Container Design generator. Bag Design keeps the first
proposal for each matching flat size and insertion-relative grid. Packed
bundles with more than one product also retain distinct upright spans and
layer counts because these distinguish downstream packing. For a single
90 × 60 × 25 mm product, nine proposals consolidate to three. Older IDs for
removed rotations resolve to the retained proposal with the same flat size.
Squareness is not a Bag Design metric. Each Design candidate carries the
net content mass and resolves its own tare from the candidate's flat stock.
Selection Mode uses the selected stock's dimensions. Tare and film properties
do not participate in Top 5 scoring or change geometric capacity.

### Terminal display grouping

Standalone, the public calculator, and the final Packaging Flow step group
rotation-equivalent designs for display. Each canonical axis descriptor pairs
the product size, grid count, and packed span in millimetres at the scene's
six-decimal geometry precision. Matching designs have the same quantity and
canonical flat dimensions and construction. The depth axis and the renderer's
long and short opening axes must have matching descriptors after rotation.
Designs with insufficient scene metadata stay visible. Older scenes with
insertion metadata can use their recorded bundle and flat dimensions.

A valid selected candidate represents its group. For other groups, a height-axis
mouth is preferred because the viewer places it above the products. If that
orientation is unavailable, the first eligible candidate represents the group.
Visible rows rank by ascending unrounded flat area, then descending cubicity,
then original order. Display ranks are computed separately from stored ranks.

With twelve 90 × 60 × 25 mm products, three rotations use the same 267 × 197 mm
bag and one represents their grid in the terminal display. Two different grids
use the 252 × 212 mm bag. Both remain visible, each with its own representative.
Adding any downstream step restores all candidates already held by the workflow
and preserves the selected ID. The engine and downstream capacity trials use
the complete candidate set.

### Product rotation permissions

Bag Design uses the same original product axes as Container Selection. R1
permits length vertical, R2 permits width vertical, and R3 permits height
vertical. The Product Additional parameters panel shows the three permissions
in Design mode. All three default to enabled for new manual products and saved
manual configurations without permissions. The panel shows the catalogue
product's stored settings as read-only when a catalogue product is selected.
Manual permissions are saved separately and restored when returning to manual
input. Each Packaging Flow Bag step keeps its own manual settings.

Design requires at least one permitted orientation. Both interactive Design and
capacity-only analysis apply the same filter before canonical arrangements and
insertion alternatives are selected. Independent permitted arrangements may
produce the same flat bag dimensions. Surviving IDs and aliases can be selected
as before. When the previously selected alternative is unavailable, Design
selects the first row in its context. These permissions apply within
the Bag Design calculation. Single and Optimal use their existing sizing rules,
and downstream steps receive the selected bag as a packed unit.

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

## Bag area and weight in result tables

All user-facing flat-bag dimensions follow Length × Width (L × W). Length
is the insertion-direction dimension and includes the sealing allowance.
Width is the bag-opening dimension. Results keep that order regardless of
which dimension is larger. Design candidate identities retain their legacy
width-first tuples internally.

Design alternatives and Optimal Top 5 rows display the flat-bag area to two
decimal places. The bag-dimension selector determines the display unit. Use
cm² for mm, cm, and m, and in² for in and ft. Calculation and ranking use the
canonical area in mm².

The Bag weight column shows resolved empty-bag tare. Metric mass selections
use three decimal places in grams. Ounce and pound selections use four
decimal places in ounces. A dash indicates unavailable tare. Positive values
that would round to zero display as less than the smallest displayed unit.

## Flexible film properties and tare

The shared film resolver applies to manual, Design, and catalogue evaluations.
New manual and Design configurations start with LDPE 1.2 mil. The LDPE
reference presets use 0.920 g/cm³ and the cast PP reference presets use
0.900 g/cm³. These densities are reference assumptions. Catalogue data and
Custom film may supply independent single-ply caliper and grammage.

Caliper converts to millimetres at the service boundary (1 µm = 0.001 mm,
1 mil = 0.0254 mm). Preset grammage in g/m² equals caliper in µm times the
density in g/cm³, so LDPE 1.2 mil yields 28.0416 g/m². A 127 × 87 mm
lay-flat bag has 0.022098 m² of two-wall film and an estimated tare of
0.6196632768 g. The full flat length includes the existing sealing allowance.

Tare precedence is explicit manual weight, actual supplier weight, estimated
catalogue film weight, estimated selected film weight, then unavailable. A
catalogue selection with missing properties retains that uncertainty. The
estimate requires simple non-gusseted two-wall construction. It excludes
closures, printing, reinforcements, and other contributions beyond the two
film walls. Film calculations do not alter the Three.js geometry.

Bag results group film properties, allowances, tare and its source inside
the collapsed Detailed analysis table. Packaging Flow includes the selected
bag's flat, packed bundle and outer dimensions in that table. Single and
Optimal also show total weight in the main result summary.

## Case compendium

`/regressions` lists the Bag Selection cases from
`packagingapp/tools/bag/case_presets.py`. Each case opens the standalone tool
with its configured inputs and units and runs the normal analysis on load.
Submissions use the current form values. To add a case from a screenshot,
transcribe its mode, manual inputs and units into a new registry entry, then
verify the resulting quantity or candidates against the current tool.
