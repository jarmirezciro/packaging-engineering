# Lessons from the First KolliPack Demo Articles

These lessons come from the Packaging Flow and Container Selection demo articles.

Use them as quality guidance. Do not copy their exact structure into every article.

# Packaging Flow case

## Strong evidence

- Same product and quantity per box.
- One design produced 9,600 products per container.
- Stronger alternatives produced 14,400.
- The result connected box design, palletization, and transport.
- Several maximum-capacity alternatives still required engineering judgment.

## What worked

- Real calculations and real renders.
- Clear downstream business consequence.
- Honest shortlist instead of claiming a universal winner.
- Interactive prepopulated case.
- Material-use comparison as a secondary decision criterion.
- Container image as proof of the final flow result.

## What needed improvement

- The strongest numerical contrast appeared too late.
- The Transport Container discussion became too technical.
- Engineering-judgment disclaimers were repeated.
- Some sections behaved like software documentation.
- The visible title was clear but not sufficiently result-led.

## Editorial rule

Lead with the 9,600-versus-14,400 result. Keep the engine invisible. Discuss the container outcome, not the rendering architecture.

# Container Selection orientation case

## Strong evidence

- Same product dimensions.
- Same box dimensions.
- R3-only result: 15 products.
- All allowed orientations: 18 products.
- Capacity increased 20%.
- Weight and payload remained practical constraints.
- The result could be translated into fewer boxes for an illustrative order.

## What worked

- Simple and understandable comparison.
- Good match for an informational SEO question.
- Prepopulated calculator let readers reproduce the case.
- Orientation comparison figure communicated the result.

## What needed improvement

- The introduction was generic.
- Interface inputs were explained before the story developed.
- R1/R2/R3 and metrics were repeated.
- The article felt more like tool documentation.
- The fictional product context was not concrete enough.
- The title was SEO-friendly but not memorable.

## Editorial rule

Lead with 15 to 18 products. Explain orientation once. Move directly from result to business consequence.

# Shared lessons

## The content is strongest when

- A surprising result can be stated in one sentence and one number.
- The case concerns a real business decision.
- The calculation narrows alternatives without pretending to certify the final design.
- Readers can open the exact case.
- Figures show real KolliPack evidence.
- The article explains what the number changes.

## Comparative figure lessons

For comparisons with another tool or result set:

- Build one figure around one reader decision.
- Use real source screenshots, renders, and tables as evidence, then crop and compose them into a deterministic layout.
- Use a setup flow for the business chain, a setup collage for inputs, a render matrix for quantities or alternatives, and a result-table matrix when alternative breadth matters.
- Keep tool names, quantities, and source-versus-reproduction status visible.
- Preserve source values and distinguish calculated output from physical validation.
- Keep the figure compact and readable at mobile width; do not turn the article into a raw screenshot sequence.

See `comparative-figure-workflow.md` for the reusable composition procedure and prompt.

## Scope alignment

The article, figure plan, and prepopulated case should describe the same calculation chain. Do not
add palletization or transport merely because the application can support it. Include a downstream
stage only when it is part of the approved business question.

## Avoid

- Generic optimization introductions.
- Long feature descriptions.
- Repeated metrics.
- Repeated caveats.
- Engine or rendering implementation detail.
- Keyword-heavy prose.
- Identical heading rhythm across every article.
- Artificial company stories with invented facts.

## Recommended editorial standard

Every demo article should answer:

1. What looked reasonable?
2. What did KolliPack reveal?
3. How large was the difference?
4. Why does it matter?
5. What still needs human or physical validation?
6. Can the reader reproduce the case?
