# Figure Specification and Template Routing

## Required before authoring
Record: one audience question; source of claims; figure message; layout name; physical stages or decision branches; essential confirmed parameters and units; illustration role; intended caption; alt text; out-of-scope stages; source version/date when a tool/vendor is named.

The JSON schema is `../schema/figure-spec.schema.json`. The examples are editable *illustrations* of the contract; **do not reproduce their bottle counts, pallet dimensions or carton dimensions** in unrelated articles.

## Template routing rules
- `setup_flow`: 2–5 real physical stages. Consecutive arrows; complete object art; no phantom transport stage.
- `concept_flow`: 2–4 related mechanisms or effects; use arrows only for real causality.
- `tradeoff`: benefit vs. drawback / constraint, or parameter → benefit → validation. **No victory badges** if there are unresolved engineering risks.
- `comparison`: side-by-side alternatives, shared axes/units if quantified; no connecting arrows for independent options.
- `summary`: 1–5 supported findings. Prefer one visual hero if more compelling than a three-card template.
- `single_explainer`: one central subject with concise label and takeaway; do not add cards just to fill space.

## Source rule
For each exact number shown in the final image, point to a reliable user-supplied case input, trusted published source or backend result. When a figure spans several cases, state that values are a *range* and do not imply one single package satisfies incompatible inputs.

## Captions
A caption explains how to interpret the illustration (e.g., conceptual setup, not exact packing geometry). The image alt text describes its information rather than duplicating the caption verbatim.

## Layout and output
- Compose as 1680px wide default, height selected by card-row count; export WebP and narrow preview.
- A different article width may be specified in tokens after a design-system revision, not ad hoc for a single article.
- A figure that fails text fit, full-object framing or source validation must remain `REVISE` / `FAIL`.
