# 3D rendering and reports

## Separation of concerns

- Engine calculates placements.
- Presenter normalizes placements and labels.
- Renderer draws them.
- Report builder composes approved values and images.

A renderer must not invent extra placements or recompute a different count.

## Matplotlib server rendering

Historical container rendering used:

```python
matplotlib.use("Agg")
```

and saved images under `MEDIA_ROOT`. Maintain server-safe rendering, close figures, and use unique filenames.

## Clean versus debug render

Provide explicit render modes:

- **clean:** customer-facing, no axes, grid, panes, or leftover-region wireframes;
- **debug:** axes and translucent subbox/zone overlays for engineering validation.

Do not expose debug visuals in normal results or reports.

## Base product render

Detailed results and reports should include a base product/unit representation when useful:

- original user-entered L/W/H;
- readable dimension badges or guides;
- no misleading orientation swap;
- proportions approximately preserved;
- clean neutral background.

## Interactive 3D contract

For browser 3D results:

- drag rotates;
- wheel zooms;
- right-drag/pan where supported;
- Reset/Top/other view buttons are beside the section title;
- initial framing fits the complete object with slight margin;
- no redundant paragraph explaining controls when concise labels suffice;
- standalone, Flow, and the corresponding multi-product consumer share the same scene/placement data and UI/rendering component where applicable.

### Bag and Container product-shape visualization

Bag and Container Selection accept `cuboid`, `cylinder`, `bottle`, and
`pillow_bag` as visualization-only product shapes. Packing, ranking, collision,
capacity, efficiency, weight, and payload calculations continue to use the
original rectangular L/W/H bounding dimensions. The selected standalone,
Packaging Flow, and public-calculator scene adds:

- `productShape`, normalized to an approved value with `cuboid` fallback;
- `productDefinition` with the original JSON-safe length, width, and height;
- `orientationIndex` on each product item, using the authoritative six-axis
  orientation order.

The shared Three.js viewer creates the approved geometry from those fields and
positions it at the existing calculated cuboid centre. Missing or invalid shape
metadata stays on the historical cuboid path. Multi-product Bag and Container
Selection intentionally expose no shape selector or shape/orientation metadata
and therefore remain cuboid-only. The existing current-canvas snapshot remains
the PDF visualization source.

### Palletization browser scene

Palletization serializes the selected engine `Placement3D` set into one
JSON-safe scene contract. The standalone tool, Packaging Flow pallet step, and
public SEO calculator render that contract with the shared Three.js pallet
viewer. The payload uses Python coordinates `X=length`, `Y=width`, `Z=height`;
the browser maps them to Three.js `X=length`, `Y=height`, `Z=width`.

The scene includes the pallet base, allowed overhang footprint, carton
placements, layer indices, selected pattern metadata, and stack metrics.
Three.js is the primary customer-facing pallet stack renderer. The historical
Matplotlib renderer remains a backend helper only and is not the primary web or
PDF visualization.

### Transport browser scene

Transport loading serializes the authoritative engine `Placement` objects into
one JSON-safe scene used by the standalone tool, the public Container Loading
Calculator, and the Packaging Flow transport step. Python coordinates use
`X=length`, `Y=width`, `Z=height`; the browser maps them to Three.js
`X=length`, `Y=height`, `Z=width`.

Three.js is the primary customer-facing transport renderer. Standalone Transport
PDF export captures fixed Main, Top, and Opposite-side JPEG views from the shared
viewer. The server validates and stores all three snapshots under `MEDIA_ROOT`;
missing or invalid snapshots return HTTP 400 and never fall back to the legacy
Matplotlib report images. Legacy server images remain transitional inputs only
for the separate combined Packaging Flow report.

For the direct Packaging Flow sequence Palletization -> Transport, the Flow
scene may additionally reference the upstream authoritative pallet scene. Each
marked transport cuboid is rendered by the shared pallet assembly builder as a
parent group containing the pallet base and carton placements. The group is
centered on the engine cuboid and receives the matching orthogonal orientation;
the cuboid remains the sole calculation, collision, capacity, and metrics
model. Other Transport consumers and inputs continue to render generic cuboids.

<<<<<<< HEAD
=======
### Bag Selection browser scene

Bag Design, Single bag analysis, and the selected Optimal Bag result serialize
the authoritative engine arrangement into one JSON-safe `packageType=bag`
scene. The shared viewer draws the usable bag body, width-side opening, reserved
length sealing strip, and exactly the selected calculated product placements.
Standalone Bag Selection, Packaging Flow, the public calculator, and
Multi-product Bag Selection consume the shared placement contract; the
multi-product surface uses its intentional cuboid-only fallback.

The active Bag result path does not create a Matplotlib PNG. Single, Optimal,
and Design PDF actions capture the current shared Three.js canvas, validate the
snapshot on the server, and embed it through the existing ReportLab builder.
The selected table row therefore remains the source for both the browser scene
and the PDF image.

>>>>>>> pre-production

## Graphics propagation rule

A renderer or visualization refactor is a shared-tool change, not a standalone-page change. For Bag and Container Selection, verify the corresponding multi-product tool in the same task. This includes:

- clean versus debug modes;
- base-product rendering;
- dimension labels and units;
- colors/materials and camera framing;
- selected-result synchronization;
- image paths and PDF embedding;
- interactive controls where used.

A result that is numerically correct but still displays the legacy graphics in a multi-product consumer is an incomplete refactor.

## PDF reports

Reference tools use ReportLab PDFs. Reports should:

- use selected result, not merely first candidate;
- repeat all important input units and assumptions;
- show key metrics, selected packaging/load unit, and visualization;
- include product and packaging images where available;
- remain concise and readable, with one-page reports preferred for single-tool results;
- not rely on the browser’s accidental current camera state unless the product specification explicitly says so;
- use the same normalized data as the web result.

The Palletization report is an explicit exception to the fixed-camera guidance:
the user-selected Three.js camera is part of the report specification. Its PDF
button captures a bounded JPEG canvas data URL, the server validates and stores
the image under `MEDIA_ROOT`, and ReportLab embeds that snapshot. A missing or
invalid snapshot returns HTTP 400; the report must not silently fall back to the
legacy Matplotlib stack image.

## Report verification

Automated or practical checks should confirm:

- HTTP status/content type;
- non-empty PDF;
- selected part number/result appears;
- image path exists or failure is handled;
- count/dimensions/weight equal web result;
- no clipping or blank first page;
- original L/W/H labels are correct.
