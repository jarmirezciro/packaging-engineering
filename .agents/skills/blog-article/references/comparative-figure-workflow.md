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

Check what earlier figures have already established. Keep a panel or figure when it helps the reader interpret a result or make an engineering decision. A reference replay, an alternative carton, a different pallet constraint or a material trade-off can serve distinct purposes. Choose the smallest comparison the evidence supports and avoid repeating similar layouts or forcing a contrast between tools.

## 2. Use real source material

Use authentic source material for every calculated result: supplied application screenshots, actual application captures, verified deterministic backend renders or other verified technical outputs. Record the source file or timestamp and the calculation inputs or run reference for every result panel. Verify provenance from the source and composition record.

- Crop, resize and combine authentic panels while preserving visible numbers, counts and geometry. Place labels and presentation framing outside the technical result.
- Keep generative imagery for conceptual illustrations. Do not generate, AI-restyle or redraw calculated packing, change its counts or geometry, or recreate a vendor interface.
- Record source and reproduction status in the caption or surrounding text.

## 3. Compose deterministically

Build the figure with Pillow, SVG, Matplotlib, or an existing repository composition script.

- Use a consistent canvas, margin, typography, and panel spacing.
- Use neutral labels such as `Tool A`, `Tool B`, `8-pack`, or `16-pack` when appropriate.
- Keep the visual hierarchy clear at mobile width.
- Use brand styling for the article frame, not to alter source-tool output.
- Export an optimized WebP with a semantic filename.

## 4. Reusable layouts

Select the layout that matches the comparison:

### Case-study setup flow

Use a clean business chain without screenshots:

```text
product requirement → package quantity → package geometry → pallet or transport result → business decision
```

Include only the stages in the approved case scope.


<!-- BEGIN KOLLILABS_BLOG_SKILL_UPDATE_V1:comparative-scenario -->
### Modular Packaging Scenario Setup (approved editorial pattern)

When the reader benefits from understanding the physical packaging chain, precede application screenshots with a clear illustrated **Packaging Scenario Setup**. Follow `packaging-scenario-setup.md` and its approved visual reference. The stages may be partial, full, branching, or mixed—derive them from the article's scope; never add Transport simply because KolliPack supports it. Use the illustration for *conceptual context*, not as proof of an exact engine solution.

For a named-tool comparison, a useful figure sequence is: (1) physical scenario when helpful, (2) real software input comparison, (3) one result comparison per important alternative, and (4) an optional trade-off chart. Do not force all four figure types into every article; choose the minimum needed to tell the case clearly. Every important result figure should show complete, readable cases and pallet/container loads, with like-for-like framing and source labels.
<!-- END KOLLILABS_BLOG_SKILL_UPDATE_V1:comparative-scenario -->

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

If an input or result is unresolved, hold the affected panel or narrow what it shows. Continue the draft using the [visual evidence workflow](production-workflow-v2.md#missing-or-newly-supplied-visual-evidence).

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

<!-- BEGIN KOLLILABS-EDITORIAL-FIGURES-V1 -->
## Concept figures vs. evidence figures (KolliLabs Editorial Figures)

For conceptual packaging setup, engineering mechanisms, decision trade-offs and illustration-led summaries, use `../../kollilabs-editorial-figures/SKILL.md` and its owner-approved visual examples. For benchmark quantities and real application results, keep following **this comparative figure workflow** with actual screenshots/backend evidence. Never treat a newly generated packaging illustration as evidence of an exact vendor UI, packing geometry, stability or calculated result.
<!-- END KOLLILABS-EDITORIAL-FIGURES-V1 -->
