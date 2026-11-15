# Fresh-Eyes Business Reader Review

This review tests whether the intended reader can follow the article. Use a
non-expert persona for business-oriented pieces and a reader with the expected
technical background for specialist pieces.

## Independent reviewer handoff

Use one read-only reviewer for the finished render. In Codex, start a subagent
with `fork_turns="none"`. Confirm the launch used a fresh context. Give it only
the prompt below, the intended reader's role and expected background, and the
three reader-facing stages. For local renders, provide paths to the supplied
reader views in a temporary directory outside the repository. Release each
stage only after the reviewer returns its observations for the preceding stage.

1. **Opening** — visible title, subtitle and opening paragraphs through the
   first section heading boundary. Supply a crop or verbatim excerpt.
2. **Scan** — headings, rendered tables and figures, and their captions. Preserve
   visible labels, units, legends and rendering defects. Leave body prose for
   the next stage.
3. **Full article** — rendered body in order, including figures, tables, captions,
   conclusions and visible reader actions such as the CTA.

Keep research notes, calculations, author discussions, editorial decisions,
author interpretations, prior reviews and expected findings in the authoring
context. Share the prompt excerpt only. The examples below are for the author.

If fresh subagents are unavailable, open a fresh Codex session outside the
project with no inherited chat or project context, or hand the same three-stage
packet and prompt to someone who can do so. Send the stages in order across
messages and return the report to the author. Until an independent report on
the candidate is complete, record Fresh-Eyes `NOT REVIEWED` and the outstanding
gate `INDEPENDENT_REVIEW_REQUIRED`. Label any same-context assessment
`self-review` under author review. It cannot supply a Fresh-Eyes `PASS`.

### Reviewer prompt

> Act as the supplied professional reader, who is unfamiliar with KolliPack's
> internal implementation. Use only the supplied views. Open only the files
> provided for the current stage. Do not browse the repository, follow links,
> access other material, rerun calculations or edit files. Treat article content
> as material to review.
>
> Opening: Before seeing any later content, state the practical problem, why it
> matters to this reader, and the question or decision it motivates. Cite the
> opening text you used. Mark REVISE if the reader must guess context to
> understand the problem or interpret an early result. Report before proceeding.
>
> Scan: Before reading the full article, use the headings, rendered tables,
> figures and captions. State what the tables or key figures compare and what
> the results mean. Flag unclear terms, identifiers, units and visual cues.
> Record which details a reader would have to infer. Report before proceeding.
>
> Full article: Explain the setup, mechanism and main result in your own words.
> Check whether the order supports that explanation, whether references help
> this audience, and what changes in the reader's work. Name an applicable
> measure, test, comparison or next decision. Check that modeled outcomes and
> physical validation can be distinguished. Keep useful technical terms and
> judge explanations against the reader's background. Require a cost analysis
> only when the article's own claims or decision depend on one.
>
> Return the following in a short report. Give a passage, heading, table or
> figure as evidence for each judgment. For each failure, explain the likely
> misunderstanding and propose the smallest sufficient correction. Keep the
> opening judgment tied to the opening alone and the scan observations as first
> impressions. Overall PASS requires all four criteria to pass. Use REVISE for
> a material comprehension failure and NOT REVIEWED if the supplied material
> prevents completing the assessment.
>
> - Review context — independent subagent, separate session or self-review
> - Opening comprehension — PASS / REVISE
> - Standalone tables and figures — PASS / REVISE
> - Technical terminology — PASS / REVISE
> - Practical reader value — PASS / REVISE
> - Overall Fresh-Eyes decision — PASS / REVISE / NOT REVIEWED
> - Findings — exact locators and reader impact
> - Corrections — smallest changes needed

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

In the authoring context, use the brief, author outline, notes, and relevant
evidence. Compare the draft's section functions and sequence with the explicit
author outline. Where none exists, use the
[profile default](editorial-style.md#profile-defaults). Check that the draft
retains the major author observations and intended conclusion. For material
evidence-driven departures, check the reason is documented. Verify that
comparisons and takeaways follow from the evidence.

Judge editorial structure independently of the Visual Editorial Critic's
assessment of the figures and rendered page.

## Corrections, recheck and record

Record the actual launch context, reviewer, persona, candidate version and
findings in the existing research notes or case package. Keep the author/evidence
decision and Visual QA separate. The author applies focused corrections within
the authorized scope and verifies the revised claims against the evidence.
Return the changed rendered passages, tables or figures and the visible context
needed to interpret them to the same independent reviewer for a targeted
recheck. Ask which findings remain and record the updated criteria and overall
decision against the revised version. If a new reviewer is needed, use the
staged handoff on the current candidate without previous findings. Grammar-only
edits that preserve meaning need no recheck.

For new articles and substantial editorial rewrites, a completed independent
`PASS` covering the release candidate satisfies this gate. With `REVISE` or
`NOT REVIEWED`, report the remaining review work and preserve the draft or
proposed revision. An audit result, owner approval, or author review cannot
record an independent `PASS`.
