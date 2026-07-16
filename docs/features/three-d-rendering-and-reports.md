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

## Report verification

Automated or practical checks should confirm:

- HTTP status/content type;
- non-empty PDF;
- selected part number/result appears;
- image path exists or failure is handled;
- count/dimensions/weight equal web result;
- no clipping or blank first page;
- original L/W/H labels are correct.
