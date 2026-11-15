# Fresh-Eyes Business Reader Review

This review tests whether the intended reader can follow the article. Use a
non-expert persona for business-oriented pieces and a reader with the expected
technical background for specialist pieces.

It is a review mode inside the same article agent, not a separate multi-agent system.

## Reader-only pass

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

Use these personas where they fit. A technical article may call for a packaging
engineer checking assumptions, a practitioner learning a method, or a KolliPack
user trying a new capability.

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

After one read, answer the questions relevant to the profile:

1. What engineering question, problem, decision, or change does the article address?
2. Can I understand the setup, method, or prerequisites before interpreting detailed results?
3. What is the main result, explanation, procedure, or change, and why does it matter?
4. Where alternatives are compared, what does the evidence show, and how does the article interpret the differences?
5. What assumptions, trade-offs, or limitations affect the answer?
6. What does KolliPack contribute, and what can I do next where applicable?

When an answer is unclear, revise the article.

For comparisons, ask the reader to identify the alternatives, explain their IDs, name the dimensions or constraints that distinguish them, and explain why those differences matter to the decision. Check that the article supplies the answers before the detailed results.

### Applied engineering articles

Ask whether a packaging engineer can picture the physical problem and a logistics practitioner can identify the operating constraints and verification needed. If a mechanism is difficult to explain in words, check whether a compact illustration would improve comprehension. Use the legend and caption in the reader-only pass to identify what the calculated objects represent and which quantities or dimensions matter.

Check that the conclusion gives the central verified result and its practical implication. Where the article informs a purchase or software decision, an operations or purchasing reader should be able to identify when the result matters and what they would measure before investing. Use case evidence and explicit conditions for that judgment.

## Jargon test

Identify terms a non-expert may not understand.

Examples:

| Term | Preferred treatment |
|---|---|
| Volumetric efficiency | Explain as percentage of internal box volume used |
| R1, R2, R3 | Define which entered dimension can stand vertical for each allowed orientation |
| FEFCO 0201 | Say standard slotted corrugated box first |
| Payload usage | Explain as percentage of weight capacity used |
| Residual space | Prefer unused space |
| Three.js | Remove from a business article |

Technical terms are allowed when they improve precision. Explain them once.

## Section purpose

For every section, ask:

> What job does this section do for the reader, and does it do that job at the right point in the article?

Check that the structure fits the article's actual purpose and that each section
does its intended work. Where applicable, distinguish the results, their
interpretation, the answer to the article's question, and evidence-grounded
lessons readers can transfer. Shorten or revise material that obscures these functions.

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

## Author and evidence pass

After the reader-only pass, reopen the brief, author outline, notes, and relevant
evidence. Compare the draft's section functions and sequence with the explicit
author outline. Where none exists, use the
[profile default](editorial-style.md#profile-defaults). Check that the draft
retains the major author observations and intended conclusion. For material
evidence-driven departures, check the reason is documented. Verify that
comparisons and takeaways follow from the evidence.

Judge editorial structure independently of the Visual Editorial Critic's
assessment of the figures and rendered page.

## Required revision behavior

Do not merely create a critique.

After the review:

1. List the three to seven highest-value corrections internally.
2. Revise the article.
3. Re-run the affected comprehension and author-fidelity checks.
4. Report only a concise summary in the final task report.

## Pass criteria

The article passes when:

- The intended reader can summarize the article's purpose and answer.
- The setup and sequence support that reader's interpretation of the evidence.
- The draft passes the applicable section-purpose and author-fidelity checks.
- Technical terms and implications are clear for the intended reader.
- KolliPack's role, limits of calculated output, and next actions are clear where applicable.
