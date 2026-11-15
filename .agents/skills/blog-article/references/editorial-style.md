# KolliLabs Editorial Style

## Voice

Write as an experienced packaging engineer explaining practical decisions to another professional or business decision-maker.

The article should be:

- Technically credible.
- Clear and direct.
- Practical rather than academic for its own sake.
- Honest about assumptions and limitations.
- Helpful before promotional.
- Confident without exaggeration.
- Understandable without specialist packaging knowledge when the article is business-oriented.

## Preserve the author's voice

When polishing or rewriting Alejandro's draft:

- Preserve the engineering judgment and intended meaning.
- Develop the author's observations rather than merely correcting grammar.
- Keep useful first-hand reasoning when it adds credibility.
- Correct grammar, transitions, and cohesion without making the article sound generic.
- Avoid replacing precise packaging language with vague marketing terms.

Use **we** for investigations and runs performed by KolliLabs, **KolliPack** for what the application does, and third-person attribution for actions observed in external demonstrations. Keep each claim tied to its source.

## Structure priority

1. **Explicit author structure.** Check the brief, `discussion.txt`, and supplied
   instructions for an outline or `Article flow`. Extract each intended section
   and its purpose. Preserve the sequence, substantive observations, and intended
   conclusion. Improve headings, transitions, and wording, and consolidate
   repeated material. If verified evidence requires narrowing a claim or changing
   the sequence or conclusion, document the material change and its reason in
   existing research notes or the final report. Follow the applicable evidence
   policy for unresolved conflicts.
2. **Profile default.** When the author has supplied no explicit structure, use the
   default for the article's primary reader objective below.
3. **General editorial guidance.** Use voice, storytelling, and quality guidance
   to refine the chosen structure within those priorities.

Before drafting, identify the profile, whether an explicit author outline exists,
the main engineering question or reader objective, the intended sequence, the
evidence each substantive section needs, and the conclusion the evidence supports.
Keep this check internal and lightweight.

## Profile defaults

Select by what the reader needs to learn or do. The sequences describe editorial
functions. Rename headings freely, combine related sections, expand where needed,
and omit functions that genuinely do not apply. Preserve the substantive work of
each applicable function. Set `article_type` independently using the
[approved schema](article-schema.md#approved-article-types).

### Comparative Benchmark

Use when the main question compares KolliPack with another application, a published
engineering study, or a reference benchmark. This editorial structure uses the
existing metadata type that fits the article, such as `demo_case_study` for a
runnable case or `engineering_deep_dive` for a technical benchmark study.

1. **Introduction** — the actual engineering problem, reference source, and comparison objective.
2. **Case Setup** — physical scenario, dimensions, quantities, restrictions, and relevant inputs.
3. **Reference or Competitor Setup** — observed method, settings, and reported results.
4. **KolliPack Setup** — reproduction inputs, restrictions, calculation mode, and method.
5. **Comparative Results** — verified like-for-like metrics, appropriate tables, and authentic comparative figures where supported.
6. **Discussion** — interpret similarities, differences, limitations, and engineering implications.
7. **Conclusion** — state what this specific comparison demonstrates.
8. **Key Takeaways** — give evidence-grounded lessons readers can transfer.
9. **Explore KolliPack** — give a contextual invitation and a verified case link where applicable.

Introduce the actual study and engineering question before presenting the finding.
Compare and interpret the verified results directly. Distinguish verified matches
from additional alternatives. Follow
[comparative benchmarking](comparative-benchmarking.md) for evidence and scope.
CapePack stock-box selection, EasyCargo mixed-cargo loading, TOPS MaxLoad, and
BR1–BR7 illustrate different ways to organize this comparison.

### Practical Demo / Case Study

Use `demo_case_study` when the main objective is to demonstrate a reproducible
KolliPack calculation, as in the Product Orientation case.

1. Introduction and Engineering Objective
2. Case Setup
3. KolliPack Configuration
4. Calculation Results
5. Explanation of the Result
6. Practical Engineering Implications
7. Conclusion
8. Key Takeaways
9. Try the Reproducible Case

Give readers the inputs and settings they need to reproduce the result. Keep
theory and commercial context proportionate to the engineering decision. Follow
the [demo evidence and case requirements](demo-case-study-profile.md).

### Engineering Deep Dive

Use `engineering_deep_dive` to explain geometry, optimization, formulas,
algorithms, or material calculations, as in Box Selection and 3D Bin Packing or
RSC Material Optimization.

1. Engineering Question
2. Physical or Mathematical Context
3. Assumptions and Definitions
4. Theory, Method, or Derivation
5. Worked Engineering Example
6. Results and Interpretation
7. Engineering Applications and Limitations
8. Conclusion
9. Key Takeaways

Make the reasoning traceable through explicit assumptions, relevant formulas,
diagrams, and a worked example. Include commercial context or external comparisons
when they directly support the technical explanation.

### Practical Guide

Use `practical_guide` when the reader needs to carry out an engineering task.

1. Problem and Objective
2. Required Inputs
3. Step-by-Step Method
4. Worked Example
5. How to Verify the Result
6. Common Mistakes and Limitations
7. Key Takeaways
8. Relevant KolliPack Tool

State the inputs, units, assumptions, and checks needed to repeat the procedure.

### Business Insight

Use the `business_insight` editorial profile when the reader needs to make a
purchasing or operational decision. Choose the closest valid `article_type` for
the actual content, such as `practical_guide` for a decision guide. The
editorial profile identifier `business_insight` is outside the approved schema.

1. Business Problem
2. Operational Context
3. Available Alternatives
4. Supporting Evidence and Trade-offs
5. Business Implications
6. Recommendation or Decision Framework
7. Key Takeaways

Use technical details that change the decision. Ground costs, savings, customer
details, and commercial assumptions in evidence. Label any illustrative assumptions.

### KolliPack Update

Use `kollipack_update` to explain a new capability or meaningful improvement.

1. What Changed
2. Why It Matters
3. How It Works
4. Example or Screenshot
5. How to Use It
6. Limitations or Availability
7. Explore KolliPack

Keep the explanation short and direct. Add comparison methodology or a formal
conclusion only when it serves the update.

### Sustainability Analysis

Use `sustainability` when the main question concerns material consumption,
waste, transport efficiency, or environmental effects.

1. Environmental or Resource-Efficiency Question
2. Baseline and System Boundaries
3. Data and Assumptions
4. Calculation Method
5. Alternative Scenarios
6. Results
7. Trade-offs, Uncertainties, and Limitations
8. Conclusion
9. Key Takeaways

Distinguish measured data, calculated estimates, and unverified impacts. Make
claims about environmental savings or certified lifecycle impacts only when the
evidence supports them.

## Openings and endings

Open with the specific question, problem, decision, or change the reader needs
to understand. An early verified result can work when the reader has enough
context and the chosen structure supports it. Avoid generic industry trends,
feature lists, and unexplained input inventories.

Before interpreting detailed results, readers need the relevant inputs and alternatives.
Explain any case IDs and the dimensions or constraints that matter. Label subsets and
illustrative context clearly. Use a short table, authentic screenshot, or prose as appropriate.

Where applicable, use Results to show what was found, Discussion to explain
why it matters and where it applies, Conclusion to answer the article's specific
question, and Key Takeaways to state transferable lessons grounded in evidence.
Give reader actions a contextual purpose. Use descriptive headings and
short-to-medium paragraphs.

## Ending substantive articles

Where Key Takeaways apply, use the existing takeaway box for two to four concise,
transferable lessons grounded in the evidence. Retain material qualifications.

Where the chosen structure calls for an Explore KolliPack invitation, tie it to
the reader’s next engineering task and verify the destination. When both serve
the reader, use one invitation to the broader tool alongside a contextual,
verified case link and the case footer CTA. Follow the [article schema](article-schema.md)
for these fields.

## Business language

Explain technical terms once in ordinary language.

Show what a metric changes:

- More products per box.
- Fewer boxes.
- More boxes per pallet.
- More products per container.
- Less estimated material.
- A narrower shortlist.

Do not include software implementation detail unless the article is explicitly technical.

## Limitations

State important assumptions and limitations clearly, but do not weaken every paragraph with a disclaimer.

Prefer one concise limitations or next-validation section.

## Avoid

- Unsupported superlatives.
- Invented savings percentages.
- Invented companies or customer requirements.
- Claims that KolliPack guarantees an outcome.
- Keyword stuffing.
- Repetitive introductions and conclusions.
- Repeating the same numbers in every section.
- Empty marketing phrases.
- Presenting assumptions as universal facts.
- Aggressive sales language.
- Engine architecture in business articles.
- Sections that exist only to demonstrate technical sophistication.
