# KolliPack Assistant knowledge evaluation — Session 8.5B

Date: 2026-10-08
Active surface: Container Selection
Provider path: local OpenAI through the normal KolliPack readiness, Redis
throttle, external policy, Structured Outputs, and final Assistant Response
validation path
Model: `gpt-5.6-sol`
Reasoning effort: `xhigh`
Provider timeout: 30 seconds
Server-owned maximum output: 3,000 tokens
Local evaluation throttle: 100 requests / 3,600 seconds through Redis
Knowledge bounds: 6 sections, 2,500 characters per section, 12,000 total
documentation characters
Response contract: Assistant Response `1.0`; one provider call; no retries

## Diagnostic taxonomy and rubric

Primary diagnoses are `retrieval_good`, `retrieval_gap`, `documentation_gap`,
`instruction_gap`, `model_quality_issue`, `token_budget_issue`, and
`expected_state_boundary`.

Scores are recorded as `G/C/Cl/B`:

- Grounding: 0 unsupported/wrong, 1 partial, 2 fully grounded;
- Completeness: 0 failed, 1 incomplete, 2 adequate;
- Clarity: 0 confusing, 1 understandable, 2 clear;
- Boundary correctness: 0 violated, 1 correct.

A good response requires Grounding `2` and Boundary correctness `1`.

## Session 8.5A baseline diagnosis

The 12-case Session 8.5A report showed that most common questions already had
adequate retrieval. The weak cases were not one generic retrieval failure:

| Observed weakness | Primary cause | Evidence |
|---|---|---|
| Container efficiency returned an honest limitation | `documentation_gap` | No approved Container-specific definition existed. |
| Restriction was useful but informal | `documentation_gap` | Rotation examples existed, but no concise definition existed. |
| P1/P2 was only high-level | `documentation_gap` | The exact `L × W` versus `W × L` mapping was absent. |
| Four complex `xhigh` answers returned `unavailable` at 1,000 tokens | `token_budget_issue` | The same four named cases passed an explicit 3,000-token follow-up. |
| Generic result questions initially selected sections containing “result” | `retrieval_gap` | Non-concept terms were suppressed in 8.5A. |
| Container efficiency initially risked a generic/Transport inference | `instruction_gap` | The 8.5A no-match instruction corrected the repeated answer. |
| Bag recommendation question from Container | `expected_state_boundary` | General Bag logic was available, but no live Bag state existed. |

The broader 8.5B deterministic baseline additionally found concrete misses for
`frontier efficiency`, `inherited input`, and pending-versus-selected results;
an unqualified `block` could borrow Pallet or Transport material; and the
Palletization-versus-Container comparison did not reliably reserve each tool's
purpose section.

## Token-budget decision

**Selected: Option B — increase the current external Assistant default
globally to 3,000 tokens.**

This is the smallest architecture because the current external Assistant has
one read-only capability and every ask request already carries a bounded
Knowledge Context, including `no_match`. A separate knowledge-token branch
would currently distinguish no meaningful second provider workload. The value
remains server-owned, the browser cannot select it, configuration validation
still caps it at 4,096, the final message remains capped at 4,000 characters,
and SDK/application retries remain disabled.

Evidence:

| Run | Bound | Outcome |
|---|---:|---|
| Session 8.5A full pass | 1,000 | Four complex `xhigh` cases normalized to `unavailable`. |
| Session 8.5A explicit follow-up | 3,000 | All four named cases returned valid responses. |
| Session 8.5B 40-case pass | 3,000 | 40/40 returned validated responses; 0 `unavailable`. |
| Session 8.5B targeted prompt verification | 3,000 | Unsupported and current-result cases both passed in one call each. |

The provider-context bounds were not increased. The evidence favored better
selection and a bounded output increase, not more input text.

## Before/after mandatory cases

| Question | 8.5A/baseline behavior | 8.5B behavior |
|---|---|---|
| What is cubicity? | Formula was recoverable from the broad Design section. | Exact Cubicity section explains meaning, ranking use, and what the metric does not prove. |
| What does efficiency mean? | Correct `no_match`; Container definition missing. | Exact Container Design-efficiency definition; no Transport contamination. |
| What is a restriction? | Useful examples, but no formal definition. | Exact Container restriction definition and payload boundary. |
| How does Design Mode work? | Grounded, but one of the complex knowledge shapes depended on extra output headroom. | Complete requested quantity → supported quantity → orientations → factors → grids → deduplication → ranking explanation at 3,000 tokens. |
| Why is Design efficiency 100%? | No explicit approved definition. | Explains exact regular-grid bounding box and excludes material, manufacture, strength, cushioning, and protection claims. |
| What is sealing margin? | Grounded and already useful. | Preserved; scoped Bag retrieval remains grounded. |
| Container Selection vs Bag Selection | Both tools were retrieved. | Both purpose sections are explicitly reserved and contrasted. |
| What is P1/P2? | High-level meaning only; exact axis mapping absent. | Exact P1 `L × W` and P2 `W × L` mapping. |
| What is a Product Block? | Retrieval worked. | Preserved and scoped to Transport; Pallet Block is now explicitly distinguished. |
| Why did my Bag Selection result select this bag? (Container active) | Correctly refused to invent Bag state. | Returns a clarifying boundary response and states that the current Container context has no Bag result. |

## Final 40-case provider evaluation

All cases used active tool `container_selection`. `C/D/R` means Container /
Design / ready with `result=null`; `C/S/C` means Container / Single / complete.
The refs below are the primary retrieved semantic refs and their heading names;
the local command also emitted the complete bounded ref and heading arrays for
each case. No raw provider metadata or secrets were recorded.

| # | Question | State | Primary retrieved refs / headings | Type and result | Diagnosis | Score G/C/Cl/B |
|---:|---|---|---|---|---|---|
| 1 | What is cubicity? | C/D/R | `container-selection-logic#cubicity` (Cubicity) | Answer; definition, ranking, limits correct | `retrieval_good` | 2/2/2/1 |
| 2 | What does efficiency mean in Design Mode? | C/D/R | `container-selection-logic#design-efficiency` (Design efficiency) | Answer; exact bounding-box ratio, real-world exclusions | `retrieval_good` | 2/2/2/1 |
| 3 | What is additional capacity? | C/D/R | `container-selection-logic#design-quantity-and-additional-capacity` | Answer; exact subtraction and scope | `retrieval_good` | 2/2/2/1 |
| 4 | What is a restriction? | C/D/R | `container-selection-logic#restriction`; `#rotation-restrictions` | Answer; server-enforced feasibility boundary | `retrieval_good` | 2/2/2/1 |
| 5 | What do R1, R2 and R3 mean? | C/D/R | `container-selection-logic#r1-r2-and-r3` | Answer; L/W/H vertical mapping; cites current axes fact | `retrieval_good` | 2/2/2/1 |
| 6 | How does Single Mode work? | C/D/R | `container-selection-logic#single-mode` | Answer; chosen-container capacity semantics | `retrieval_good` | 2/2/2/1 |
| 7 | How does Optimal Mode work? | C/D/R | `container-selection-logic#optimal-mode`; `#design-mode` | Answer; catalogue evaluation and current-mode boundary | `retrieval_good` | 2/2/2/1 |
| 8 | How does Design Mode work? | C/D/R | `container-selection-logic#design-mode`; `#design-efficiency`; `#design-quantity-and-additional-capacity`; `#cubicity` | Answer; full deterministic user-level process | `retrieval_good` | 2/2/2/1 |
| 9 | How is Design Mode different from Optimal Mode? | C/D/R | `container-selection-logic#design-mode`; `#optimal-mode` | Answer; generated package versus evaluated catalogue | `retrieval_good` | 2/2/2/1 |
| 10 | Why does Design Mode sometimes design more units? | C/D/R | `container-selection-logic#design-quantity-and-additional-capacity`; `#design-mode` | Answer; 2/3/5-smooth supported quantity | `retrieval_good` | 2/2/2/1 |
| 11 | Why is Design efficiency 100%? | C/D/R | `container-selection-logic#design-efficiency` | Answer; exact idealized bounding box, no overclaim | `retrieval_good` | 2/2/2/1 |
| 12 | Does Container Selection guarantee global optimality? | C/D/R | `container-selection-logic#assumptions`; `#multi-product-container-selection-consumer` | Answer: no; bounded heuristic explained | `retrieval_good` | 2/2/2/1 |
| 13 | What does Bag Selection do? | C/D/R | `terminology#bag-selection`; `bag-selection-logic#purpose` | Answer; lay-flat fit, sealing/tolerance/weight scope | `retrieval_good` | 2/2/2/1 |
| 14 | What is sealing margin? | C/D/R | `bag-selection-logic#constraints-and-invariants`; `terminology#bag-selection` | Answer; closure-only added length | `retrieval_good` | 2/2/2/1 |
| 15 | Why is sealing margin added to bag length? | C/D/R | `bag-selection-logic#conceptual-calculation-flow`; `terminology#bag-selection` | Answer; closure direction and non-occupancy | `retrieval_good` | 2/2/2/1 |
| 16 | How does Bag Design work? | C/D/R | `bag-selection-logic#design-mode`; `#assumptions` | Answer; supported quantity, grid, formula, boundaries | `retrieval_good` | 2/2/2/1 |
| 17 | How is Bag Design different from Container Design? | C/D/R | `bag-selection-logic#design-mode`; `container-selection-logic#design-mode`; both Purpose sections | Answer; shared generator and distinct dimensions/orientations | `retrieval_good` | 2/2/2/1 |
| 18 | Does Bag Selection use R1/R2/R3? | C/D/R | `bag-selection-logic#assumptions`; `#design-mode` | Answer; Design does not; Selection-mode naming remains undocumented | `documentation_gap` | 2/1/2/1 |
| 19 | How does bag tolerance work? | C/D/R | `terminology#bag-selection`; `bag-selection-logic#design-mode`; `#constraints-and-invariants` | Answer; tolerance separated from sealing | `retrieval_good` | 2/2/2/1 |
| 20 | Container Selection vs Bag Selection | C/D/R | `container-selection-logic#purpose`; `bag-selection-logic#purpose` | Answer; rigid 3D placement versus lay-flat bag fit | `retrieval_good` | 2/2/2/1 |
| 21 | Why did my Bag Selection result select this bag? | C/D/R | Bag calculation/ranking sections | Clarifying boundary; no live Bag state invented | `expected_state_boundary` | 2/2/2/1 |
| 22 | What are P1 and P2? | C/D/R | `palletization-logic#p1-and-p2` | Answer; exact footprint-axis mapping | `retrieval_good` | 2/2/2/1 |
| 23 | What is a block in Palletization? | C/D/R | `palletization-logic#block-pattern` | Answer; one-orientation grid; Transport distinction | `retrieval_good` | 2/2/2/1 |
| 24 | What is a brick pattern? | C/D/R | `palletization-logic#brick-pattern` | Answer; verified 2:1 bonded/staggered semantics | `retrieval_good` | 2/2/2/1 |
| 25 | What is a pinwheel? | C/D/R | `palletization-logic#pinwheel` | Answer; alternating orientations around center/block | `retrieval_good` | 2/2/2/1 |
| 26 | What is a mosaic solution? | C/D/R | `palletization-logic#split-and-mosaic-patterns` | Answer; non-overlapping zones and fillers | `retrieval_good` | 2/2/2/1 |
| 27 | Palletization vs Container Selection | C/D/R | `palletization-logic#purpose`; `container-selection-logic#purpose` | Answer; carton-to-pallet versus product-to-container | `retrieval_good` | 2/2/2/1 |
| 28 | What does Transport Container loading do? | C/D/R | `transport-selection-logic#purpose`; `terminology#transport-loading` | Answer; transport-unit scope and physical caveats | `retrieval_good` | 2/2/2/1 |
| 29 | What is a Product Block? | C/D/R | `transport-container-engine#product-block-definition`; `#glossary` | Answer; regular one-SKU Y×Z module repeated in X | `retrieval_good` | 2/2/2/1 |
| 30 | What is Space Evenly? | C/D/R | `transport-container-engine#what-space-evenly-is`; `transport-selection-logic#how-space-evenly-behaves-for-users` | Answer; two-phase deterministic heuristic | `retrieval_good` | 2/2/2/1 |
| 31 | What is Front-to-Back? | C/D/R | `transport-container-engine#load-front-to-back-with-dgfe`; corresponding user section | Answer; bounded transition frontier behavior | `retrieval_good` | 2/2/2/1 |
| 32 | What is DGFE? | C/D/R | `transport-container-engine#load-front-to-back-with-dgfe`; `#glossary` | Answer; deferred vertical settlement boundary | `retrieval_good` | 2/2/2/1 |
| 33 | What does frontier efficiency mean? | C/D/R | `transport-container-engine#frontier-efficiency` | Answer; local prism ratio, not overall/Container efficiency | `retrieval_good` | 2/2/2/1 |
| 34 | Transport loading vs Palletization | C/D/R | `transport-selection-logic#purpose`; `palletization-logic#purpose` | Answer; load-space versus pallet-layer responsibilities | `retrieval_good` | 2/2/2/1 |
| 35 | What is Packaging Flow? | C/D/R | `packaging-flow#purpose`; `#assistant-scope` | Answer; independent-tool chain | `retrieval_good` | 2/2/2/1 |
| 36 | What does inherited input mean? | C/D/R | `packaging-flow#inherited-input` | Answer; normalized upstream physical output | `retrieval_good` | 2/2/2/1 |
| 37 | Pending versus selected results | C/D/R | `packaging-flow#pending-and-selected-results`; `#assistant-scope` | Answer; fresh calculated versus user-committed output | `retrieval_good` | 2/2/2/1 |
| 38 | Can the Assistant see every Packaging Flow step? | C/D/R | `packaging-flow#assistant-scope` | Answer: no; only active Container step Tool Context | `retrieval_good` | 2/2/2/1 |
| 39 | Explain this result. | C/S/C | `no_match` as intended; Tool Context facts | Answer; current result, payload/thickness assumptions, mismatch surfaced | `retrieval_good` | 2/2/2/1 |
| 40 | Which adhesive chemistry is compatible with polyethylene? | C/D/R | `no_match` | First pass gave generic advice (`instruction_gap`); `read_only/v3` rerun gave explicit documentation limitation | `instruction_gap` resolved | 2/1/2/1 |

The phrase scanner flagged several safe negative global-optimality disclaimers
because it is intentionally lexical. Human review confirmed that the answers
said the result was **not** globally optimal; these were not grounding failures.

## Retrieval changes justified by failures

- Added deterministic term routing for distinctive Bag, Palletization,
  Transport, and Packaging Flow phrases.
- Added active-tool scoping for ambiguous `design`, `efficiency`, `cubicity`,
  `additional capacity`, `restriction`, and `block` terms.
- Applied heading-specific tool tags to the mixed-tool terminology document.
- Reserved each named tool's Purpose section for comparison questions.
- Increased title weighting and required a stronger lexical signal for
  inferred-tool/body-only matches, preventing unsupported single-word noise.

No embeddings, vector store, LLM router, additional source files, or larger
knowledge context were added.

## Prompt change justified by evaluation

The first unsupported-question run had `knowledge_status=no_match` but returned
generic adhesive-selection advice. This was an `instruction_gap`, not a
retrieval or documentation problem. `read_only/v3` now states that when neither
Knowledge Context nor current Tool Context supports the requested answer, the
provider must not substitute general model packaging advice. The one-case
rerun returned the expected documentation limitation. The current-result
`no_match` case was also rerun and continued to use Tool Context correctly.

## Documentation changes and backlog

Resolved clarifications were limited to behavior verified in the current
repository: Container restriction and R1/R2/R3, design quantity/additional
capacity, cubicity, Design efficiency, Pallet P1/P2, Pallet Block/Brick,
Transport frontier efficiency, and Packaging Flow inherited/pending/selected
and Assistant scope.

| Concept | Current source | Problem | Suggested change | Status |
|---|---|---|---|---|
| Cubicity | `container-selection-logic.md` | Definition was embedded in implementation prose. | Add user-facing meaning, use, and limits. | resolved 8.5B |
| Container Design efficiency | `container-selection-logic.md` | No explicit explanation of 100%. | Define exact-grid bounding-box semantics and exclusions. | resolved 8.5B |
| Additional capacity | `container-selection-logic.md` | Formula/purpose not explicit. | Define supported design quantity minus request. | resolved 8.5B |
| Restriction and R1/R2/R3 | Container domain + terminology | Formal meaning/mapping absent. | Add verified server rule and L/W/H vertical mapping. | resolved 8.5B |
| P1/P2; Block; Brick | `palletization-logic.md` | Exact mapping/pattern meaning incomplete. | Add verified current implementation notes. | resolved 8.5B |
| Frontier efficiency | `transport-container-engine.md` | Term existed without a concise formula/scope. | Define the local frontier-prism ratio and distinguish DGFE marginal efficiency. | resolved 8.5B |
| Packaging Flow state terms | `packaging-flow.md` | Inherited/pending/selected and Assistant visibility were implicit. | Add concise current implementation notes. | resolved 8.5B |
| Bag Selection R1/R2/R3 | `bag-selection-logic.md` | Design is clear; Selection-mode control naming is not explicit. | Verify current Selection engine/UI and document without borrowing Container semantics. | open |
| Bag ranking tie-breakers | `bag-selection-logic.md` | Exact current ordering is still marked for verification. | Verify engine/service before documenting a specific recommendation cause. | open |
| `PackagingMaterial.part_weight` unit | architecture/domain backlog | Repository semantics conflict between grams and kilograms. | Resolve separately; do not expose a claimed unit meanwhile. | open |
| Container Tool Context desired/requested quantity | assistant adapter fixture | Complete Single result reports 45 while input desired quantity is 20. | Review the existing Tool Context result contract separately. | open |

## Hot reload, trace, privacy, and boundedness

- The existing hot-reload regression edits Markdown between two retrievals in
  one process and confirms the next request reparses it without restart or
  vector reindexing.
- With `DEBUG=true` and the explicit trace flag, endpoint/UI tests expose only
  title, heading path, and semantic ref under “Knowledge used.” With either
  gate disabled, no trace is returned or rendered.
- Provider input remains limited to application instructions, one current
  question, validated Tool Context, and selected approved Knowledge Context.
- The 6-section / 2,500-character / 12,000-character bounds are unchanged.
- One KolliPack request still makes at most one provider call; no automatic
  retry was added.
- No question, response, knowledge selection, trace, or conversation is
  persisted.

## Decision

The 40-case run produced 40 validated responses, no output-budget failures,
correct cross-tool retrieval, correct active-tool ambiguity handling, correct
no-result behavior, and no invented other-tool state. The only new provider
instruction failure was corrected and verified with targeted unsupported and
current-result reruns. Remaining backlog items are narrow documentation/data-
contract work and do not justify another general retrieval session.

`READY_FOR_SESSION_9 = YES`

Recommended next session: **Session 9 — Structured AI input-change proposals
with a user-visible diff, but no Apply.**
