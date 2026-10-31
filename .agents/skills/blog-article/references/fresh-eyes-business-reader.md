# Fresh-Eyes Business Reader Review

This review tests whether a reader with no packaging-engineering background can understand the article.

It is a review mode inside the same article agent, not a separate multi-agent system.

## Review isolation

During this review, ignore:

- `discussion.txt`
- Backend notes
- Author explanations
- Internal editorial plan
- Intended meaning not present in the draft

Read only:

- Visible title
- Article body
- Figures
- Captions
- CTA

The reviewer must not fill gaps using information unavailable to the reader.

## Choose one primary persona

### Purchasing or packaging buyer

Asks:

- What am I comparing?
- Does the result affect price, material, or logistics?
- Is KolliPack recommending a purchase or creating a shortlist?
- What should I ask the supplier?
- What must be physically tested?

### General business manager

Asks:

- Why should I care?
- What changed?
- How large is the consequence?
- What decision follows?
- Is the claim credible?

### Operations or logistics manager

Asks:

- Does the result affect handling, storage, pallets, or transport?
- Is the proposal operationally realistic?
- What restrictions could change the answer?
- What should be tested next?

## Comprehension test

After one read, answer:

1. What problem is the company solving?
2. What is the main result?
3. Why does it matter commercially?
4. Which option appears strongest or most relevant?
5. Why is the final decision not necessarily complete?
6. What does KolliPack contribute?
7. What should the reader do next?

When an answer is unclear, revise the article.

## Jargon test

Identify terms a non-expert may not understand.

Examples:

| Term | Preferred treatment |
|---|---|
| Volumetric efficiency | Explain as percentage of internal box volume used |
| R1, R2, R3 | Define once as permitted upright orientations |
| FEFCO 0201 | Say standard slotted corrugated box first |
| Payload usage | Explain as percentage of weight capacity used |
| Residual space | Prefer unused space |
| Three.js | Remove from a business article |

Technical terms are allowed when they improve precision. Explain them once.

## Manager-interest test

For every section, ask:

> Does this help the reader understand the problem, result, consequence, decision, or next action?

When the answer is no:

- Remove it.
- Shorten it.
- Rewrite it around the business meaning.
- Move it to a technical article.

## Buyer challenge

Challenge unsupported or ambiguous statements.

Weak:

> Alternative 7 is the best design.

Challenge:

> Best by which criterion?

Better:

> Alternative 7 is a strong candidate because it reaches the maximum calculated transport capacity with a more balanced geometry. Supplier drawings and physical tests are still required.

## Repetition and caveats

Check:

- Are the same numbers repeated too often?
- Is the same conclusion stated after every figure?
- Are caveats weakening every result?
- Can one compact limitations paragraph replace repeated disclaimers?


<!-- BEGIN KOLLILABS_BLOG_SKILL_UPDATE_V1:fresh-eyes-figures -->
## Figure comprehension test (alongside visual QA)

Treat figures as part of the article, not decoration. After a quick look at the *actual rendered images*, can the reader identify:

- Which physical packaging units are involved and how they relate?
- What is held constant and what is changing?
- Which two cases, products or tools are being compared?
- What is the main consequence and why should a manager care?
- What should the reader explore or validate next?

If the visuals cannot answer these questions, revise the figure/figure order first; do not automatically add long prose to compensate for unclear diagrams. This review concerns **meaning**; the separate `visual-editorial-critic.md` enforces render completeness, legibility and editorial quality. A conceptual figure may explain a physical relationship but must not be presented as exact count/geometry evidence without verification.
<!-- END KOLLILABS_BLOG_SKILL_UPDATE_V1:fresh-eyes-figures -->

## Required revision behavior

Do not merely create a critique.

After the review:

1. List the three to seven highest-value corrections internally.
2. Revise the article.
3. Re-run the comprehension questions.
4. Report only a concise summary in the final task report.

## Pass criteria

The article passes when:

- A non-expert can summarize it in one sentence.
- The main result is visible within the first 100 words.
- The commercial meaning is explicit.
- Technical terms are explained or removed.
- The role of KolliPack is clear.
- Calculated output is distinguished from final validation.
- The reader knows what to do next.
- No section exists only to sound technically sophisticated.
- No more than roughly 10% can be cut without losing an important idea.
