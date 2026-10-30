# KolliPack metric unit system audit

## Purpose and authority

This audit records the physical-unit contracts verified on the `production`
branch in October 2026. Current code remains the source of truth for exact
paths and behavior. The contract is intentionally metric at storage and engine
boundaries; the shared conversion layer also defines the alternative-unit
vocabulary needed by later input/display work.

Alternative units are an input/display concern:

```text
input/display unit -> shared conversion -> canonical metric value
                   -> existing service/engine -> canonical metric result
```

No Imperial engine, catalogue record, database field, workflow branch, or
Three.js coordinate system is introduced by this contract.

## Supported conversion vocabulary

The centralized definitions are in `packagingapp/units/`.

| Quantity | Supported units | Canonical conversion base |
|---|---|---|
| Length | `mm`, `cm`, `m`, `in`, `ft` | millimetres |
| Mass | `g`, `kg`, `t`, `oz`, `lb` | grams |

`t` means metric tonne (`1000 kg`). `ton`, US short ton, UK long ton, and
fractional-inch parsing are intentionally unsupported. Conversion is numeric
only and performs no display rounding. `Decimal` input produces `Decimal`
output; other real numeric input produces `float` output.

Exact definitions:

```text
1 in = 25.4 mm
1 ft = 304.8 mm
1 kg = 1000 g
1 t  = 1,000,000 g
1 oz = 28.349523125 g
1 lb = 453.59237 g
```

## Audited contracts

| Area | Field / payload | Storage unit | Form/display unit | Service unit | Engine/result unit | Notes |
|---|---|---:|---:|---:|---:|---|
| Product catalogue | `Product.product_length`, `product_width`, `product_height` | mm | mm | mm | mm | `Decimal(12,3)`; Excel template states mm. |
| Product catalogue | `Product.weight` | kg | kg in catalogue surfaces | kg until tool adapter | tool-specific | `Decimal(12,3)`; Excel template states kg. |
| Packaging catalogue | `PackagingMaterial.part_length`, `part_width`, `part_height` | mm | mm | mm | mm | Internal/primary dimensions. |
| Packaging catalogue | `external_length`, `external_width`, `external_height` | mm | mm | mm | mm | Optional complete external triplet. |
| Packaging catalogue | `box_thickness_mm` | mm | mm | mm | mm | Optional `Decimal(8,3)`. |
| Packaging catalogue | `part_weight` | kg | kg in catalogue/selection summaries | adapted per consumer | tool-specific | `Decimal(12,3)`; Excel template states kg. |
| Container Selection | manual product L/W/H | — | mm | mm | mm | Engine geometry is unchanged. |
| Container Selection | manual product weight | — | g | g | g report fields | Informational; geometry capacity is unchanged. |
| Container Selection | catalogue product weight | kg | catalogue row/summary: kg | kg -> g in shared Container service | g report fields | `kg_to_g` occurs once at the service/form boundary. |
| Container Selection | manual packaging tare / max payload | — | g | g | g report fields | Payload remains informational for current Container capacity. |
| Container Selection | catalogue packaging tare | kg | catalogue row/summary: kg | kg -> g in shared Container service | g report fields | No catalogue payload model field currently exists. |
| Bag Selection | manual product L/W/H and bag L/W | — | mm | mm | mm | Sealing/tolerance geometry remains unchanged. |
| Bag Selection | manual product, bag tare, max payload | — | g | g | g report fields | Payload feasibility/report contract is gram-based. |
| Bag Selection | catalogue product / bag tare | kg | catalogue row/summary: kg | kg -> g in shared Bag service | g report fields | Conversion is not performed inside the bag engine. |
| Palletization | carton and pallet dimensions, heights, overhang | catalogue/manual mm | mm | mm | mm | Catalogue carton/pallet uses external dimensions first, then internal fallback. |
| Palletization | manual carton weight / max bottom-carton load | — | g | g | g | Engine propagates the caller's mass unit; KolliPack's caller contract is grams. |
| Palletization | catalogue carton tare | kg | catalogue row/summary: kg | kg -> g in shared Palletization service | g | Manual `450 g` and catalogue `0.450 kg` are equivalent. |
| Palletization | `max_bottom_load_g`, `avg_bottom_load_g`, `weight_limit_g` | — | g | g | g | Correct names. Legacy `_kg` aliases remain temporarily and contain the same gram values. |
| Palletization | catalogue pallet tare | kg | kg | kg in Packaging Flow | not an engine input | Standalone Palletization does not include pallet tare in its stacking algorithm. |
| Palletization | result height fields | — | mm | mm | mm | `used_height_mm`, `pallet_height_mm`, `total_height_mm`. |
| Transport Container | internal transport-unit L/W/H | catalogue/manual mm | mm | mm | mm | Engine geometry and placements remain millimetres. |
| Transport Container | load-unit weight | catalogue/manual kg | kg | kg | kg | Product catalogue kg is already the correct Transport input; no conversion occurs. |
| Transport Container | transport-unit tare / max payload | catalogue/manual kg | kg | kg | kg | Catalogue `2200 kg` remains `2200 kg`. Tare is excluded from payload and added to gross. |
| Packaging Flow | selected step physical mass | session JSON | kg authoritative; g derived | kg authoritative | downstream-specific | `weight_kg` is authoritative; `weight_g` is derived without display rounding. |
| Packaging Flow | Container/Bag -> Palletization | session JSON | — | derived `weight_g` | Palletization g | No catalogue value is reinterpreted as grams. |
| Packaging Flow | Container/Bag/Palletization -> Transport | session JSON | — | authoritative `weight_kg` | Transport kg | Legacy g-only payloads are read once and adapted to kg for session compatibility. |
| Packaging Flow | palletized load | session JSON | kg/g pair | kg authoritative | Transport kg | Upstream package kg × cartons + catalogue pallet tare kg. |
| Corrugated strength | box L/W/H, joint, sheet margin, pallet dimensions/heights | — | mm | `Decimal` mm | specialized mm/m equations | No equation or constant changed. |
| Corrugated strength | product net weight | — | g | g | g | Produces finished/gross box weight fields in grams. |
| Corrugated strength | pallet weight | — | kg | kg | kg | Gross box grams are explicitly divided by `1000` before kg strength/load calculations. |
| Container/Bag PDF | normalized analysis mass fields | — | formatted g/kg | g | g | Catalogue kg is converted before export formatting. |
| Palletization PDF | bottom-load fields | — | g | g | g | Reads corrected `_g` keys and falls back to legacy aliases. |
| Transport PDF | item, payload, tare, gross | — | kg | kg | kg | Same normalized Transport summary as web result. |
| Packaging Flow PDF | effective output mass | session JSON | kg | kg | kg | Prefers `weight_kg`; legacy `weight_g` is converted for display only. |
| Container Three.js | scene `units` | — | mm | mm | mm | `units = "mm"`; coordinates unchanged. |
| Bag Three.js | scene `units` | — | mm | mm | mm | `units = "mm"`; coordinates unchanged. |
| Pallet Three.js | scene `units` | — | mm | mm | mm | Serializer explicitly emits `units = "mm"`; coordinates unchanged. |
| Transport Three.js | scene `units` | — | mm | mm | mm | `units = "mm"`; coordinates unchanged. |
| Product-unit Three.js | scene `unit` | — | mm | mm | mm | `unit = "mm"`; visualization-only shapes retain bounding dimensions. |

## Conversion boundaries

The high-risk boundaries use `packagingapp.units.kg_to_g` or `g_to_kg`:

- `packagingapp/tools/container/service.py`: catalogue Product and
  PackagingMaterial kg to Container report/form grams.
- `packagingapp/tools/bag/service.py`: catalogue Product and bag material kg to
  Bag report/form grams.
- `packagingapp/tools/palletization/service.py`: catalogue carton kg to
  Palletization engine grams.
- `packagingapp/views/full_packaging.py`: catalogue/manual inputs normalize to
  authoritative `weight_kg`, derive `weight_g` for gram consumers, and pass kg
  to Transport.
- `packagingapp/tools/container/assistant_actions.py`: existing Assistant
  proposal conversions use the shared conversion primitives while retaining
  their existing accepted-unit surface.

Authoritative calculation conversions do not occur in packing algorithms,
templates, or JavaScript. The shared JavaScript selector only converts the
currently displayed form value; the server normalizes submitted values into
the canonical calculation units before invoking an engine.

## Consumer assessment

| Consumer | Assessment |
|---|---|
| Standalone Container | Shared service converts selected catalogue kg to g; reports/PDF receive normalized grams. |
| Packaging Flow Container | Reuses the shared service; selected package output stores authoritative kg plus derived g. |
| Multi-product Container | Current calculation is geometry-focused. Catalogue payload/display remains kg and no gram engine input is created. |
| Public Container calculator | Manual-only example already uses mm/g; no visible alternative-unit change. |
| Standalone Bag | Shared service converts selected catalogue kg to g; reports/PDF receive normalized grams. |
| Packaging Flow Bag | Reuses the shared service; selected package output stores authoritative kg plus derived g. |
| Multi-product Bag | Current calculation is geometry-focused. Catalogue payload/display remains kg and no gram engine input is created. |
| Public Bag calculator | Manual-only example already uses mm/g; no visible alternative-unit change. |
| Standalone/Flow/Public Palletization | All use the shared service/serializer and corrected gram result keys. |
| Standalone/Flow/Public Transport | Transport inputs and summaries remain kg; engine code is unchanged. |
| Catalogue import/export | Metric-only mm/kg schema is unchanged. |
| Session serialization | Only strings, booleans, numbers, lists, dictionaries, and `None`; `Decimal` is converted before session payload storage. |
| PDF/report export | Uses each tool's normalized presenter/report contract; no report-side physical recalculation added. |
| Three.js | All geometry remains canonical millimetres; only the Pallet scene gained an explicit unit marker. |

## Compatibility and remaining ambiguity

- Palletization's historical `max_bottom_load_kg`, `avg_bottom_load_kg`, and
  `weight_limit_kg` keys were semantically grams. Correct `_g` keys are now
  primary. The old keys remain as temporary aliases with identical gram values
  for stored sessions and external consumers; they must not be interpreted as
  kilograms.
- `PackagingMaterial` has one generic `part_weight` field and no max-payload
  field. Its verified storage contract is kg. Container/Bag code still probes
  optional payload-like attributes for forward compatibility, but no such
  model field exists on this branch. No speculative catalogue payload
  conversion was introduced.
- Palletization has no manual pallet-tare input and does not include pallet
  tare in its stacking engine. Packaging Flow can add a selected catalogue
  pallet's kg tare to the downstream physical load mass.
- Multi-product Container and Bag currently serialize/display catalogue kg but
  do not feed those values into a gram-based feasibility calculation. A later
  feature that adds weight feasibility there must attach to the same explicit
  conversion boundary.

## Future attachment point

Future inline selectors such as `Length (mm)` or `Weight (g)` should convert
only at form/input and presentation boundaries. Canonical catalogue storage,
workflow `weight_kg`, stable engine-local metric units, report calculations,
and Three.js coordinates must remain independent of rounded display values.

## Task 2 — Palletization manual-input selector pilot

Palletization manual physical inputs now expose the centralized alternative-unit
vocabulary through a small shared inline selector. The unit state is explicit,
JSON-safe form/workflow data and defaults to the existing metric contract when
it is absent:

- carton dimensions: `mm`, `cm`, `m`, `in`, `ft`;
- pallet/layout dimensions, maximum stack height, and overhang: `mm`, `cm`,
  `m`, `in`, `ft`;
- carton weight and maximum bottom-carton load: `g`, `kg`, `t`, `oz`, `lb`.

Carton dimensions share one linked state, pallet/layout values share a second
linked state, and the two manual mass inputs share one mass state. The server
converts submitted manual values once at the Palletization service boundary to
`mm` and `g`; the Palletization engine and all result calculations remain
metric and unchanged. Browser conversion is only an interaction aid and
maintains a canonical client-side value to avoid repeated-switching drift.

Catalogue values remain canonical: catalogue dimensions stay in `mm`,
catalogue weights remain stored/displayed in `kg` and are converted directly to
the Palletization engine's `g` boundary. They are not routed through a rounded
alternative-unit display. Palletization result presentation, PDF/report units,
and Three.js geometry remain metric (`mm`/`g`) for this pilot.

## Task 3 — Container and Bag manual-input selectors

Container Selection and Bag Selection now use the same shared selector partial,
unit vocabulary, browser interaction, and server-side conversion boundary as
the Palletization pilot. Each selector is hidden input state plus a visible
menu; state is strings only and therefore remains JSON-safe in Packaging Flow.

Container Selection links the following fields:

| Selector state | Linked manual fields | Canonical service unit |
|---|---|---|
| `product_dimension_unit` | product length, width, height | mm |
| `product_mass_unit` | product weight | g |
| `container_dimension_unit` | box length, width, height, thickness | mm |
| `container_mass_unit` | box tare, maximum payload | g |

Bag Selection uses the equivalent groups:

| Selector state | Linked manual fields | Canonical service unit |
|---|---|---|
| `product_dimension_unit` | product length, width, height | mm |
| `product_mass_unit` | product weight | g |
| `bag_dimension_unit` | bag length, width | mm |
| `bag_mass_unit` | bag tare, maximum payload | g |

The server validates each submitted token and converts manual values once to
the canonical unit before calling the existing Container or Bag service and
engine. Invalid units are rejected; they are never silently treated as metric.
Missing unit metadata defaults to the historical `mm`/`g` contract for legacy
requests and sessions. Catalogue branches do not display or reinterpret these
manual selectors: catalogue dimensions remain millimetres and catalogue mass
continues through the existing `kg_to_g` boundary exactly once.

The same prefixed unit state is carried through Full Packaging. Inherited
product values are adapted between the upstream canonical `mm`/`g` values and
the selected downstream manual display units, while the workflow's
authoritative package mass remains `weight_kg` with a derived `weight_g` only
for gram-based consumers. No Container/Bag engine, ranking, report, or
Three.js coordinate contract changes.

## Task 4 — Product and Packaging Catalogue integration

Task 4 adds alternative-unit presentation and manual catalogue entry without
changing the database or machine-facing metric contracts.

| Catalogue surface | Canonical storage | Display/input units | Save boundary |
|---|---|---|---|
| Product Catalogue | dimensions in mm; weight in kg | length `mm`, `cm`, `m`, `in`, `ft`; mass `g`, `kg`, `t`, `oz`, `lb` | submitted display values convert to mm/kg, then use existing model precision and validation |
| Packaging Catalogue | internal/external dimensions and thickness in mm; part weight in kg | one linked length state covers internal, external, and thickness; one linked mass state covers weight | submitted display values convert to mm/kg, then use existing model precision and validation |

Catalogue list/detail tables convert canonical values only for presentation. A
single no-arrow selector controls all related dimensions, and a second selector
controls mass. Display formatting is limited to readable precision and never
feeds a tool calculation. Existing records are converted to the selected
input unit when an edit form opens; saving an unchanged imperial presentation
returns the same canonical physical value at the model field precision.

The catalogue display state is JSON-safe session state under
`catalogue_length_unit` and `catalogue_mass_unit`, with `mm` and `kg` as the
legacy-safe defaults. The shared browser selector also keeps the state in
local storage and URL parameters so detail, filter, pagination, add, and edit
links can preserve the current presentation. No UserPreferences model was
introduced.

Catalogue numeric dimension and weight filters convert the selected threshold
once to canonical mm/kg before ORM filtering. Database ordering remains
canonical and is never performed on formatted strings. Volume filters remain
canonical because the existing UI has no volume-unit selector.

At the Task 4 stage, catalogue selection widgets inside Container, Bag,
Palletization, Transport, and Full Packaging remained metric. Task 7 later
adds local-unit picker presentation without changing their adapters: they
still consume exact canonical catalogue values; Product kg still crosses the
Container/Bag gram boundary exactly once, Packaging kg still crosses the
Palletization gram boundary exactly once, and Transport continues to consume
kg directly. Displaying a catalogue value as `lb` or `in` cannot alter those
paths.

Excel upload/download and other bulk interfaces remain Metric-only (`mm` and
`kg`) and do not depend on the current catalogue display state. Three.js
geometry remains canonical mm. No catalogue schema migration, engine change,
ranking change, report-unit redesign, or User Settings implementation is part
of Task 4.

## Task 5 — Transport Container and Packaging Flow integration

Transport now uses the same shared inline selector and browser anti-drift
contract at four grouped manual-input boundaries:

| Selector state | Linked editable fields | Canonical service unit |
|---|---|---|
| `load_unit_dimension_unit` | all manual load-row length, width, and height values | mm |
| `load_unit_mass_unit` | all manual load-row unit weights | kg |
| `transport_dimension_unit` | manual internal transport length, width, and height | mm |
| `transport_mass_unit` | manual maximum payload and tare | kg |

Missing metadata retains the legacy `mm`/`kg` behavior. Explicit unsupported
tokens are rejected before packing. The Transport service converts supported
display values once, before row validation, max-quantity preprocessing, or any
active packing mode. The engine, placement coordinates, serialized Three.js
scene, result cards, and PDF/report values remain canonical metric.

The multi-row Transport table deliberately shares one dimension state and one
mass state. Catalogue-selected and Flow-inherited rows additionally carry
JSON-safe exact canonical scalars beside their editable presentation values.
Unit switching changes only the presentation values; the service consumes the
canonical scalars until a user explicitly edits a physical field, at which
point that row becomes a normal manual row. This prevents rounded `in`/`lb`
presentation from becoming a calculation input. Catalogue-backed transport
units continue using model dimensions and tare directly in `mm`/`kg`.

Packaging Flow stores the four prefixed Transport unit states in the existing
step config. Inherited package and pallet payloads remain canonical
`length`/`width`/`height` in millimetres and authoritative `weight_kg`; the
downstream row is converted only for the selected local display state. The
same display adaptation is applied when canonical upstream values populate a
Palletization step whose carton or mass selector is non-metric. Accepted
workflow payloads, capacity orchestration, visualization decoration, and
session serialization remain canonical and JSON-safe.

## Task 6 — final integration and result/report presentation

Task 6 completes the representation layer. The centralized
`packagingapp.units.format_length`, `format_mass`, and `format_dimensions`
helpers convert canonical numeric values into readable strings (at most three
decimal places by default). These strings are attached by presenters and
report-payload builders; templates do not perform conversion, and formatted
values are never written back to engine, catalogue, or workflow state.

Corrugated Material & Strength now has five linked selector states:

| State | Editable fields | Canonical destination |
|---|---|---|
| `box_dimension_unit` | internal L/W/H, manufacturer joint, sheet margin | mm |
| `product_mass_unit` | product net weight | g |
| `pallet_dimension_unit` | pallet L/W/H and maximum palletized height | mm |
| `pallet_mass_unit` | pallet tare | kg |
| `material_dimension_unit` | actual caliper override | mm |

The server serializer validates and normalizes these values before calling the
existing Corrugated service. Missing unit metadata retains the historical
`mm`/`g`/`kg` defaults. ECT (`lb/in` reference and `kN/m` metric contract), BCT
and force (`N`), grammage (`g/m²`), area (`m²`), and CO₂ screening
(`kg CO₂e`) remain explicit specialist contracts. Their formulas and
constants were not changed.

### Final unit-system matrix

This matrix is the current presentation contract and supersedes the historical
presentation notes in the Task 2–5 rollout sections above.

| Area | Input/display units | Canonical calculation/storage | Result display | PDF/report |
|---|---|---|---|---|
| Product Catalogue | length vocabulary; mass vocabulary | mm / kg database fields | selected catalogue units | detail/export schemas remain distinct: page display selected, bulk metric |
| Packaging Catalogue | linked length and mass vocabulary | mm / kg database fields | selected catalogue units | Excel/bulk remains mm/kg |
| Container | product and container length groups; product and package mass groups | mm / g service and engine boundary | product context uses product units; container/thickness uses container units; mass/payload uses its relevant mass state | presenter strings from the same canonical analysis report |
| Bag | product and bag length groups; product and bag mass groups | mm / g service and engine boundary | product, bag, required size, tare and payload use their local states | presenter strings from the same canonical analysis report |
| Palletization | carton length, pallet/layout length, and carton/load mass groups | mm / g; legacy `_kg` aliases still contain grams | dimensions/heights use pallet or carton context; load limits use mass state | selected row and ranking consume the same display strings |
| Transport | load-row length/mass and transport length/mass groups | mm / kg | load rows use load-unit state; occupied/residual size uses transport length; payload/tare/gross uses transport mass | report payload uses the same attached display contract |
| Full Packaging | per-step local unit states | dimensions in mm; `weight_kg` authoritative with derived `weight_g` | input, output, compact chain, and accepted-result summaries follow each step's local context | each report step is decorated from canonical payload plus that step's unit metadata; legacy state defaults metric |
| Corrugated | five linked states listed above | existing mm / g / kg service contracts | ordinary dimensions/masses follow their relevant state; specialist quantities remain explicit | PDF consumes the same Corrugated display contract as the web result |
| Three.js | surrounding labels may be display-aware | all dimensions, placements, and coordinates remain mm | optional annotations only; geometry unchanged | snapshots represent unchanged geometry |
| Excel/bulk interfaces | no display-state dependency | mm / kg schema | Metric-only | Metric-only |

### Catalogue picker review

Catalogue database values, hidden identifiers, and machine data attributes stay
canonical. Picker rows now use transient server-rendered display attributes and
the shared browser display metadata; rounded text is never submitted as a
calculation input. Picker header selectors reuse the owning tool's existing
unit group, so changing a header changes the same local state used by manual
fields and other linked displays.

### Hard-coded-unit classification

The final search covered Python views/services/presenters/serializers, HTML
templates, JavaScript, and report builders. Remaining visible or named metric
tokens fall into these intentional categories:

1. canonical machine contracts and compatibility field names (`*_mm`, `*_g`,
   `*_kg`, workflow `weight_kg`);
2. legacy-safe unit defaults applied only when metadata is absent;
3. Excel/bulk schemas, which remain Metric-only;
4. Three.js scene markers and coordinates (`mm`);
5. Corrugated specialist engineering units (ECT, BCT/force, grammage, area,
   and carbon screening);
6. explanatory text that explicitly describes a canonical engine assumption
   or conversion boundary;
7. test fixtures and SEO example data.

Ordinary result cards, compact summaries, selected-item summaries, and report
payloads no longer bind a selected-unit label to an unconverted canonical
number.

### Regression conclusions

Physical-equivalence coverage now includes Container, Bag, Palletization,
Transport, Corrugated, catalogue entry/display, and a complete
Container → Palletization → Transport Packaging Flow. The complete Flow is
run once in historical metric units and once with product `in/lb`, container
`cm/g`, pallet `mm/kg`, and Transport `ft/lb`. Accepted package and pallet
payloads, arrangement decisions, placed quantities, placement coordinates,
and utilization remain equivalent within numeric conversion tolerance. Shared
conversion tests also exercise round trips; the browser selector retains a
per-input canonical value during repeated switching to avoid display-rounding
drift.

### Intentional Metric-only surfaces

- catalogue database fields and migrations;
- packing and Corrugated engine inputs/results before presentation;
- Packaging Flow authoritative physical payloads;
- all Three.js geometry and placement coordinates;
- catalogue Excel import/export and other bulk schemas;
- machine-facing Assistant/action contracts;
- multi-product Container and Multi-product Bag picker tables, which remain
  metric because those surfaces do not expose an active editable unit state;
- specialist Corrugated quantities without an approved alternative vocabulary.

## Task 7 — User default unit preferences

Task 7 adds one account-owned `UserPreferences` record per authenticated user.
It reuses the centralized `packagingapp.units` vocabulary for validation and
labels; no new conversion units or formulas were introduced.

The three persisted fields are:

```text
default_length_unit      → mm (legacy-safe default)
default_small_mass_unit  → g  (legacy-safe default)
default_large_mass_unit  → kg (legacy-safe default)
```

The settings page is `/account/settings/` and is available only to the logged-in
owner of the current account. Anonymous users do not need a preference record
and continue to receive the historical metric defaults.

### Task 7 preference matrix

| Context | Length default | Mass default |
|---|---|---|
| Product/Container | `default_length_unit` | `default_small_mass_unit` |
| Bag | `default_length_unit` | `default_small_mass_unit` |
| Palletization carton/load | `default_length_unit` | `default_small_mass_unit` |
| Product Catalogue | `default_length_unit` | `default_small_mass_unit` |
| Packaging Catalogue | `default_length_unit` | `default_small_mass_unit` |
| Transport load and transport unit | `default_length_unit` | `default_large_mass_unit` |
| Corrugated product | `default_length_unit` | `default_small_mass_unit` |
| Corrugated pallet | `default_length_unit` | `default_large_mass_unit` |
| Full Packaging new step | step-specific length | step-specific small/large mass |

Multi-product Container and Multi-product Bag remain catalogue-driven
canonical-metric selection surfaces on this branch and expose no editable unit
selector to initialize. Their catalogue rows, calculations, and Excel output
therefore remain metric and are not silently rewritten by account preferences.

### Precedence and compatibility

The implemented precedence is:

1. explicit current form or workflow unit state;
2. existing tool/session override;
3. existing catalogue local display state;
4. authenticated user default;
5. historical metric fallback (`mm`/`g`/`kg`).

User preferences initialize only missing or genuinely new state. A new
standalone tool GET and a newly added Full Packaging step use the account
defaults; a posted selector, old session, existing workflow step, or catalogue
session override is retained. Changing an inline selector never writes to
`UserPreferences`; only the account settings form does.

Old workflows without unit metadata remain metric and their numeric values are
not reinterpreted after a user changes account preferences. Existing catalogue
records remain stored in `mm`/`kg`; catalogue display falls back to the account
length and small-mass defaults only when no query/session/local override exists.
Once catalogue state is changed locally, that state remains the active display
state. Corrugated initial values are converted for display before submission;
the serializer still returns canonical metric values.

Engines, catalogue storage, workflow `weight_kg`, Three.js coordinates, and
Excel/bulk schemas are unchanged. Reports continue consuming the selected
presentation metadata from the existing Task 6 contracts.

## Task 7 — Catalogue picker unit coherence

Embedded catalogue pickers now speak the local unit language of the tool that
owns them. The implementation is presentation-only: catalogue dimensions stay
stored in `mm`, catalogue mass stays stored in `kg`, and row selection remains
an ID-based action that resolves the canonical model object before entering the
existing service boundary.

### Picker mapping

| Picker | Length state | Mass state |
|---|---|---|
| Container Product | `product_dimension_unit` | `product_mass_unit` |
| Container Packaging | `container_dimension_unit` | `container_mass_unit` |
| Bag Product | `product_dimension_unit` | `product_mass_unit` |
| Bag Packaging | `bag_dimension_unit` | `bag_mass_unit` |
| Palletization Carton | `box_dimension_unit` | `mass_unit` |
| Palletization Pallet | `pallet_dimension_unit` | `mass_unit` |
| Transport Load Unit Product | `load_unit_dimension_unit` | `load_unit_mass_unit` |
| Transport Packaging / Transport Unit | `transport_dimension_unit` | `transport_mass_unit` |

Palletization has no separate pallet-tare selector. Its existing `mass_unit`
is therefore the verified shared presentation state for both carton/load mass
and catalogue pallet tare. This does not reinterpret the historical pallet
result `_kg` compatibility aliases, which remain gram-valued aliases.

### Precedence and workflow propagation

The effective picker state is the existing tool state, with the established
precedence of explicit local selector/form state over initialized account
defaults and historical metric fallback. User Preferences reach pickers
indirectly: a new standalone tool or Full Packaging step initializes its unit
state from the account defaults, and the picker reads that state. A local
selector change updates the same hidden unit group, so the picker follows the
local override rather than querying `UserPreferences` or creating a second
picker-only state.

Container, Bag, Palletization, and Transport public/shared pages use the same
partials and annotations. Full Packaging uses each step's prefixed contract:
Container, Palletization, and Transport pickers can therefore display
different units on the same workflow page. The catalogue-to-tool services and
the existing Container/Bag/Palletization `kg → g` boundaries are unchanged;
Transport continues consuming canonical `kg`.

### Intentional exceptions

- Picker volume columns remain on their existing canonical `mm³` contract.
  This task does not invent a general volume-unit vocabulary.
- Multi-product Container and Multi-product Bag remain metric catalogue-driven
  surfaces because they do not expose an active editable unit state.
- Standalone catalogue detail pages retain their own catalogue display state;
  this task only adds coherence to pickers embedded in engineering tools.
- Three.js, PDF/report architecture, Excel/bulk schemas, engines, and database
  units are unchanged.
