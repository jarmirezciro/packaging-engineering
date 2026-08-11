# Comparative Benchmarking

Use this reference whenever an article compares KolliPack with a named external tool,
vendor, tutorial, public result, or commercial product.

## Purpose and boundary

A benchmark article is a bounded, reproducible technical comparison. It is not:

- a complete product review;
- proof that one product is universally better;
- a certification of packaging or transport safety;
- a legal opinion;
- a substitute for human legal review when publication risk is material.

Keep the comparison useful by stating exactly what was tested and what was not.

## Required comparison record

Before drafting, record:

- comparator name and vendor;
- public source URL or supplied evidence package;
- source capture date and region, when relevant;
- product name, edition, version, plan, or tutorial date, when available;
- KolliPack project version and backend entry point;
- exact inputs, unit systems, conversions, rounding, and settings;
- supported constraints compared and constraints omitted;
- outputs reproduced by each side;
- whether the result is calculated, observed in a screenshot/video, or physically validated;
- known discrepancies and unresolved uncertainties;
- rights or permission status for screenshots, logos, recordings, and extracts.

Do not silently convert approximate or rounded source values into exact claims.

## Comparison language

Prefer bounded wording:

- “In this case, both tools found…”
- “The supplied tutorial shows…”
- “Under the stated inputs, KolliPack produced…”
- “The visible alternatives differed in…”
- “This comparison does not test…”

Avoid or qualify wording such as:

- “best,” “worst,” “faster,” “cheaper,” or “more accurate”;
- “equivalent” or “full parity”;
- “proves,” “guarantees,” or “always”;
- unsupported claims about market position, customer outcomes, safety, compliance, or savings.

If a stronger comparative claim is necessary, define the metric, test set, versions,
sample size, and limitations explicitly, then flag it for human/legal review.

## Required disclosure

Use a compact disclosure adapted to the case, normally near the opening:

> This article presents a focused comparison using the stated inputs and public source material available on [date]. It is not a complete product evaluation, and the result should not be generalized beyond the tested case. KolliLabs/KolliPack is independent of and not affiliated with [vendor].

Add a separate engineering limitation when relevant:

> The calculated geometry is decision support, not a certification of physical stability, compression performance, transport safety, compliance, or released packaging. Supplier specifications, physical testing, and operational approval remain separate decisions.

Do not imply that the comparator reviewed, approved, endorsed, or participated in the article unless that is documented.

## Evidence and visual material

- Prefer official vendor documentation, public tutorials, or directly reproducible outputs.
- Link the source and state what was observed versus independently reproduced.
- Keep screenshots faithful; do not alter visible values or create synthetic vendor UI.
- Label screenshots, renders, and tables so readers can distinguish source material from KolliPack output.
- Compare like-for-like metrics only. If utilization, efficiency, or ranking conventions differ, say so instead of aligning the percentages.
- Report discrepancies rather than selecting the value that favors KolliPack.

If a discrepancy makes the comparison incoherent or could change the conclusion, stop drafting and
request corrected evidence or clarification from the author. Do not proceed with an unresolved
interpretation merely to complete the article.

For comparison figures, use the vendor-neutral workflow in
`comparative-figure-workflow.md`. Prefer compact, labeled composites that show the tested
decision and distinguish source output from independent reproduction. Do not turn the article
into a sequence of raw vendor screenshots.

## Human/legal review triggers

Escalate for human/legal review before external publication when the article:

- alleges deception, infringement, misconduct, unsafe behavior, or regulatory non-compliance;
- makes a broad superiority, parity, pricing, market-share, or customer-outcome claim;
- relies on current pricing, availability, legal status, compliance, or other time-sensitive commercial claims;
- uses non-public, confidential, scraped, leaked, or restricted material;
- reproduces vendor branding, screenshots, recordings, or substantial text without a clear rights basis;
- is intended for paid advertising, direct competitor targeting, sales collateral, or a high-risk public campaign;
- received a complaint, takedown request, correction request, or vendor response.

The blog skill can identify and document these triggers. It must not represent its wording
as legal approval or waive the need for counsel.

## Publication gate

Do not publish until the article record shows:

- a bounded comparison question;
- reproducible or clearly sourced evidence;
- exact assumptions and source date/version;
- neutral, case-scoped conclusions;
- affiliation and engineering limitation disclosures;
- image and quotation rights checked;
- human/legal review completed when a trigger applies;
- the prepopulated KolliPack case verified when the article includes one.
