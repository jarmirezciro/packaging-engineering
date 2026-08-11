# Comparative Figure Workflow

Use this reference when an article compares two or more tools, result sets, settings, or packaging alternatives.

The purpose of a comparative figure is to make one decision easier to understand. It is not to reproduce every screen from the source package.

## 1. Define the visual message

Before composing, state:

- the one conclusion or question the figure should communicate;
- the comparison columns, such as Tool A and Tool B;
- the comparison rows, such as case quantity, carton alternative, or pallet result;
- the values that must remain readable;
- whether each panel is source output, independent reproduction, or a combined view.

Choose the smallest layout that communicates the comparison.

## 2. Use real source material

Use supplied screenshots, renders, result tables, or deterministic application outputs when the figure supports a factual claim.

- Preserve visible numbers, labels, and geometry.
- Crop interface chrome, unused whitespace, and unrelated controls.
- Do not redraw a vendor interface or create a synthetic source result.
- Record source and reproduction status in the caption or surrounding text.

## 3. Compose deterministically

Build the figure with Pillow, SVG, Matplotlib, or an existing repository composition script.

- Use a consistent canvas, margin, typography, and panel spacing.
- Use neutral labels such as `Tool A`, `Tool B`, `8-pack`, or `16-pack` when appropriate.
- Keep the visual hierarchy clear at mobile width.
- Use brand styling for the article frame, not to alter source-tool output.
- Export an optimized WebP with a semantic filename.

Do not use image generation to recreate a technical interface or change a numerical result.

## 4. Reusable layouts

Select the layout that matches the comparison:

### Case-study setup flow

Use a clean business chain without screenshots:

```text
product requirement → package quantity → package geometry → pallet or transport result → business decision
```

Include only the stages in the approved case scope.

### Comparative setup collage

Place the setup view for each tool in a consistent row or column. Show only the inputs needed to establish a like-for-like comparison.

### Comparative render matrix

Use columns for tools and rows for quantities or alternatives. Each cell may combine comparable package and pallet renders when that helps the reader follow the decision from package to unit load.

### Comparative result-table matrix

Use a compact table collage when the number of alternatives is itself relevant. Keep each table legible, label the tool and quantity, and explain that row counts or ranking conventions may not be directly equivalent.

## 5. Editorial and evidence checks

Before integrating a figure, verify:

- every visible number matches the source;
- the panels compare like-for-like metrics;
- unit conversions and rounding are stated when material;
- the caption explains what the reader should notice;
- the figure does not imply broader parity, superiority, or physical validation than the evidence supports.

If the source panels, labels, tables, or independent reproduction are incoherent or contradictory,
stop figure composition and ask for corrected evidence or clarification. Do not align conflicting
values, hide a discrepancy, or choose the panel that produces the better comparison.

Prefer three to six purposeful figures per business article. Combine related screenshots rather than displaying a sequence of oversized raw captures.

## 6. Reusable composition prompt

Use this prompt when asking for a deterministic figure composition:

```text
Create a compact editorial comparison figure from the supplied real screenshots and renders.

Message: [one decision or comparison the reader should understand]
Columns: [Tool A, Tool B, ...]
Rows: [quantity, alternative, or result]
Required visible values: [list]
Layout: [setup collage, render matrix, result-table matrix, or setup flow]

Crop irrelevant interface content, preserve all source values, use consistent labels and spacing,
and keep the figure readable at mobile width. Do not invent UI, arrangements, numbers, logos,
or conclusions. Export an optimized WebP with a semantic filename.
```
