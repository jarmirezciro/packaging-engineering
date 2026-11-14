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

## Open with the engineering decision

For demo and business articles, establish what the reader needs to decide and why it matters. Introduce the strongest verified result within the first 100 words, once the reader can interpret it. For benchmarks, open with the actual engineering problem and source where relevant. Explain what KolliLabs investigated, then distinguish verified matches from additional alternatives. Preserve the author’s reasoning. Use a hypothetical customer, order or requirement only when it explains something the evidence alone cannot, and label it as illustrative.

Prefer:

> When the shipping case is fixed, orientation can change how many units it holds. In this trial the case held 15 upright units and 18 when all permitted orientations were enabled.

Avoid beginning with:

- Generic industry trends.
- Definitions.
- Tool feature lists.
- Long input descriptions.
- “In today's fast-paced world.”

## Structure

Prefer a coherent decision story:

1. Result or problem.
2. Concrete business situation.
3. Apparent answer.
4. Comparison or method.
5. Main result.
6. Business consequence.
7. Remaining validation or trade-off.
8. Key Takeaways.
9. Explore KolliPack invitation.

This is a story guide, not a mandatory heading template.

Before readers interpret detailed results, establish the relevant input set. Explain what the alternatives and their IDs represent, which verified dimensions or constraints distinguish them, and why they matter. Use a short table, authentic screenshot or prose according to the case. Label a subset as such and reuse input context already clear in the article.

Use familiar, descriptive engineering headings such as “Case Setup.” Name the subject clearly for engineers and business readers. Use short-to-medium paragraphs. Use lists only when they improve scanning.

## Ending substantive articles

Close the technical discussion of an engineering deep dive, benchmark, practical demo or substantive business article with **Key Takeaways**. Use the existing takeaway box, usually with two to four concise implications grounded in the article. Keep material qualifications. For a short announcement, omit a formal list when there are no useful takeaways.

Immediately after the takeaways, add one short paragraph inviting readers to try a relevant KolliPack capability. Start from the engineering question, identify what the reader can actually do next, and verify the destination in the current application. Keep this separate from an article-specific case link that reproduces a verified run. Where both help, use a contextual case link and the existing case footer CTA, with one text invitation to the broader tool before the author and footer components. Store the invitation using the [article schema](article-schema.md).

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
