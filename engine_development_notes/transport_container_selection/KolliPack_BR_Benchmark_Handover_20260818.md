# KolliPack Transport Container — BR1–BR7 Benchmark Research Handover

Date: 2026-08-18

## 1. Purpose

This handover captures the Bischoff–Ratcliff benchmark work for the KolliPack Transport Container engine and defines the next research loop.

The intended next phase is NOT to chase individual benchmark cases or convert KolliPack into a global-search solver. The objective is to use the worst cases diagnostically, identify repeated failure mechanisms, derive one generalizable deterministic principle at a time, implement it in a bounded way, and rerun the complete benchmark plus all golden regression cases.

A later deliverable is a KolliLabs/KolliPack blog article explaining the benchmark honestly and comparing KolliPack with published academic reference results.

---

## 2. Exact benchmark baseline

Engine tested:

`engine(20260817-215516).py`

SHA-256:

`73e18b73c63718828e7a45a7bf8a94da6ebc82e965215f86f1ffa7a3c224f758`

The engine is the current deterministic block-based Transport Container engine with Space Evenly, Load Front-to-Back, Mixed Cargo side infill, supported top infill, Native/DGFE frontier handling, support validation, payload accounting, and deterministic candidate ranking.

No benchmark-specific algorithm changes were made for the run.

---

## 3. Benchmark dataset

Dataset: Bischoff–Ratcliff BR1–BR7, from the OR-Library.

Source paper:

E. E. Bischoff and M. S. W. Ratcliff (1995), “Issues in the Development of Approaches to Container Loading,” Omega 23(4), 377–390.

Dataset structure:

- BR1: 100 instances, 3 box types
- BR2: 100 instances, 5 box types
- BR3: 100 instances, 8 box types
- BR4: 100 instances, 10 box types
- BR5: 100 instances, 12 box types
- BR6: 100 instances, 15 box types
- BR7: 100 instances, 20 box types
- Total: 700 instances
- Standard container dimensions: 587 × 233 × 220 dataset units
- Objective: maximize container volume utilization
- Each box dimension carries a 0/1 flag indicating whether that dimension may be vertical.

KolliPack orientation mapping used:

- OR height may be vertical -> R1 = True
- OR width may be vertical -> R2 = True
- OR length may be vertical -> R3 = True

All benchmark products:

- stackable = True
- weight = 0
- sequence = 1

The requested cargo volume averages approximately 99.448% of container volume across the 700 cases, with a range of approximately 97.403% to 99.999%. The suite is therefore a deliberately demanding utilization benchmark.

Official files used:

- thpack1.txt
- thpack2.txt
- thpack3.txt
- thpack4.txt
- thpack5.txt
- thpack6.txt
- thpack7.txt

---

## 4. Benchmark execution

All four KolliPack modes were run for every instance:

1. Space Evenly
2. Space Evenly – Mixed Cargo Infill
3. Load Front-to-Back
4. Load Front-to-Back – Mixed Cargo Infill

Total solves:

`700 × 4 = 2,800`

Every returned placement set was passed through the current engine global geometry validator for:

- container bounds
- positive-volume overlap
- full support of elevated placements

Validation result:

- Space Evenly: 700/700 valid
- Space Evenly Infill: 700/700 valid
- Front-to-Back: 700/700 valid
- Front-to-Back Infill: 700/700 valid

Total benchmark execution time in the test sandbox was approximately 648.9 seconds. Per-mode runtime numbers below are measurements from this environment only and must not be compared directly with historical academic CPU times.

---

## 5. KolliPack results — complete 700-case suite

| Mode | Average utilization | Median | Minimum | Maximum | Avg runtime | Median runtime |
|---|---:|---:|---:|---:|---:|---:|
| Space Evenly | 76.203% | 76.146% | 53.409% | 93.052% | 0.302 s | 0.011 s |
| Space Evenly – Infill | **83.666%** | **83.687%** | 68.341% | 93.052% | 0.349 s | 0.057 s |
| Front-to-Back | 67.414% | 67.522% | 41.782% | 91.918% | 0.119 s | 0.084 s |
| Front-to-Back – Infill | **82.541%** | **82.766%** | 67.009% | 92.660% | 0.152 s | 0.117 s |
| Best KolliPack mode per instance | **84.453%** | **84.476%** | — | — | — | — |

Mixed Cargo Infill provides a large measurable gain:

- Space Evenly: +7.463 percentage points on average
- Front-to-Back: +15.127 percentage points on average

Among the two infill modes:

- Space Evenly Infill wins 433 cases
- Front-to-Back Infill wins 257 cases
- 10 cases tie

This is consistent with the benchmark objective: Space Evenly has more geometric freedom, while Front-to-Back intentionally preserves a longitudinal operational loading philosophy.

---

## 6. Per-class results and academic full-support reference

Fanslau & Bortfeldt’s CLTRS packing variant guarantees full support from below and reports 94.2% average utilization over BR1–BR7.

| Class | Box types | KolliPack Space Evenly Infill | KolliPack FTB Infill | CLTRS full-support packing | Gap: CLTRS vs SE Infill |
|---|---:|---:|---:|---:|---:|
| BR1 | 3 | 84.952% | 83.335% | 94.51% | 9.558 pp |
| BR2 | 5 | 85.096% | 83.678% | 94.73% | 9.634 pp |
| BR3 | 8 | 84.711% | 83.743% | 94.74% | 10.029 pp |
| BR4 | 10 | 83.754% | 82.449% | 94.41% | 10.656 pp |
| BR5 | 12 | 83.192% | 82.244% | 94.13% | 10.938 pp |
| BR6 | 15 | 82.556% | 81.941% | 93.85% | 11.294 pp |
| BR7 | 20 | 81.403% | 80.394% | 93.20% | 11.797 pp |
| **BR1–BR7 average** | — | **83.666%** | **82.541%** | **94.2%** | **10.534 pp** |

Important interpretation:

- CLTRS is a tree-search method with generalized blocks and substantially more foresight/search than KolliPack.
- KolliPack is deliberately constructive, deterministic, bounded and explainable.
- The academic result is a benchmark reference, not a proven mathematical optimum for every case.
- The growing gap as heterogeneity increases is an important research signal.

---

## 7. Literature review — key results

### Bischoff–Ratcliff benchmark

The OR-Library BR1–BR7 instances are standard single-container loading benchmarks. The objective is maximum volume utilization. The benchmark includes orientation restrictions by box dimension.

### Fanslau & Bortfeldt — CLTRS

Paper/work:

Tobias Fanslau and Andreas Bortfeldt, “A Tree Search Algorithm for Solving the Container Loading Problem.”

Key concepts:

- generalized block building
- simple blocks plus general blocks with small internal gaps
- partition-controlled tree search (PCTRS)
- residual-space management
- packing variant with 100% support from below
- orientation restrictions respected

Published BR1–BR7 full-support packing result:

`94.2% average utilization`

Per-class full-support results:

BR1 94.51%, BR2 94.73%, BR3 94.74%, BR4 94.41%, BR5 94.13%, BR6 93.85%, BR7 93.20%.

The paper stresses that comparisons must distinguish methods that enforce the support constraint from methods that do not.

It also provides a useful explanation of heterogeneity:

- weak heterogeneity: boundary losses tend to dominate
- strong heterogeneity: internal losses in arrangements become increasingly important
- general blocks become increasingly valuable as the number of box types rises

This observation is directly relevant to KolliPack’s BR4–BR7 performance decline.

### Historical BR1–BR7 comparison reported by CLTRS

Support-constrained methods in the CLTRS comparison table include approximately:

- Terno et al. B&B: 88.5%
- Bortfeldt/Gehring GA: 90.1%
- Gehring/Bortfeldt parallel GA: 90.4%
- Eley TRS: 88.8%
- Bischoff: 90.5%
- Moura/Oliveira GRASP: 89.7%
- CLTRS packing variant: 94.2%

Methods in the same table that do NOT enforce the full-support constraint include results such as 87.6%, 92.7%, 93.2%, 93.8%, and the CLTRS cutting variant at 95.0%.

Therefore the blog must not mix support-constrained and unsupported results without clearly labelling the difference.

### LoadingMCP — commercial reference

LoadingMCP publicly states that it benchmarks against all 700 Bischoff–Ratcliff instances and reports, as of July 2026:

- BR1: 86.4%
- BR5: 85.3%
- BR7: 82.6%
- approximately 85% overall

LoadingMCP says its optimizer is built on PackingSolver. It also states that PackingSolver’s authors, Florian Fontan and Luc Libralesso, won the EURO/ROADEF 2022 Renault truck-loading optimization challenge. The official ROADEF/EURO final-results page confirms Fontan and Libralesso as the winning team.

This makes LoadingMCP a useful small-commercial-player reference, but its figures are vendor-published rather than an independent academic evaluation.

Relative to the published LoadingMCP class figures, KolliPack Space Evenly Infill is approximately:

- BR1: 84.95% vs 86.4% -> 1.45 pp lower
- BR5: 83.19% vs 85.3% -> 2.11 pp lower
- BR7: 81.40% vs 82.6% -> 1.20 pp lower

These are much smaller gaps than the gap to the CLTRS academic tree-search reference.

---

## 8. What the benchmark currently says about KolliPack

Do NOT frame the result as academic state of the art.

A defensible conclusion is:

“KolliPack’s current deterministic mixed-cargo engine reaches 83.67% average volume utilization across the 700 Bischoff–Ratcliff BR1–BR7 instances in Space Evenly Infill mode, while preserving full physical support validation and deterministic constructive loading. A published high-performance full-support academic tree-search reference, CLTRS, reports 94.2% on the same BR1–BR7 family.”

Commercial interpretation:

- KolliPack is not trying to replicate a global tree-search optimizer.
- It prioritizes fast, deterministic, explainable, operational-looking loading.
- Its current result is close enough to the approximately 85% self-reported LoadingMCP result to justify further focused research.
- The benchmark is particularly valuable because it reveals structural weaknesses instead of relying on visually attractive hand-picked cases.

---

## 9. Most important research signal

KolliPack Space Evenly Infill falls from:

- BR1: 84.95%
- BR2: 85.10%
- BR3: 84.71%
- BR4: 83.75%
- BR5: 83.19%
- BR6: 82.56%
- BR7: 81.40%

The decline with increasing heterogeneity strongly suggests that the next useful improvement is likely NOT another local top/side geometry patch. The next investigation should ask whether the current block/orchestration model loses too much flexibility when many box types compete.

This is only a hypothesis until the worst cases are diagnosed geometrically.

---

## 10. Initial worst-case set for diagnostic work

Rank by the BEST of the two Mixed Cargo Infill modes, so cases are genuinely difficult for KolliPack rather than merely difficult for one mode.

Top initial cases:

| Rank | Case | Best infill utilization | Best mode | SE Infill | FTB Infill |
|---:|---|---:|---|---:|---:|
| 1 | BR1-92 | 68.734% | SE Infill | 68.734% | 68.228% |
| 2 | BR2-92 | 71.404% | SE Infill | 71.404% | 69.952% |
| 3 | BR3-43 | 73.081% | FTB Infill | 68.341% | 73.081% |
| 4 | BR1-44 | 73.473% | SE Infill | 73.473% | 72.987% |
| 5 | BR7-20 | 74.926% | FTB Infill | 74.284% | 74.926% |
| 6 | BR1-71 | 74.948% | SE Infill | 74.948% | 72.936% |
| 7 | BR1-81 | 75.576% | FTB Infill | 71.091% | 75.576% |
| 8 | BR1-9 | 75.644% | SE Infill | 75.644% | 72.806% |
| 9 | BR1-88 | 75.906% | SE Infill | 75.906% | 75.674% |
| 10 | BR7-31 | 76.247% | SE Infill | 76.247% | 67.009% |

Do not implement fixes from this ranking alone. First render and inspect geometry/diagnostics.

---

## 11. Required research loop

CURRENT APPROVED ENGINE
        |
        v
Run complete BR benchmark
        |
        v
Rank worst cases
        |
        v
Inspect geometry + diagnostics
        |
        v
CLUSTER FAILURE MECHANISMS
        |
        +-- product ordering?
        +-- block construction?
        +-- residual quantity?
        +-- frontier depth?
        +-- side envelope?
        +-- top/support geometry?
        |
        v
Find ONE generalizable principle
        |
        v
Implement bounded change
        |
        v
RE-RUN EVERYTHING
        |
        +-- worst cluster improves?
        +-- 700-case average improves?
        +-- current golden cases unchanged?
        +-- runtime acceptable?
        +-- determinism unchanged?

---

## 12. Research guardrails

1. Do not optimize directly for a named BR instance.
2. Do not add a rule whose only justification is “BRx-y improves.”
3. Every proposed change must be expressible as a generic geometric/packing principle.
4. Preserve current golden customer-style regression cases.
5. Preserve deterministic output.
6. Preserve physical bounds, overlap and full-support validation.
7. Preserve fast constructive behavior.
8. No product permutation search.
9. No beam search.
10. No backtracking.
11. No global free-space search.
12. No recursive packing tree.
13. No legacy-engine import.
14. Prefer one bounded principle per iteration.
15. After each change rerun all 700 cases, not only the selected failures.
16. Record before/after per-case results, not only the global average.
17. Reject changes that improve the benchmark but materially damage normal/golden layouts.

---

## 13. Candidate failure-mechanism taxonomy

Use these only as hypotheses to classify evidence:

### A. Product ordering
A locally sensible first SKU creates poor downstream geometric compatibility.

### B. Product Block construction
The YZ/synchronized block family cannot express a useful mixed arrangement that appears repeatedly across poor cases.

### C. Residual quantity fragmentation
Large homogeneous blocks leave awkward quantities that cannot form efficient subsequent blocks.

### D. Frontier-depth commitment
A local frontier consumes or closes X depth that would be more valuable to another remaining SKU.

### E. Side residual envelope
Useful lateral residual geometry is not derived, merged or filled optimally under the current bounded rules.

### F. Supported top envelope
Useful roof-clear support exists but cannot be exploited because of envelope shape, support-plane fragmentation, orientation/block constraints or local-window timing.

### G. Heterogeneity / cross-product composition
The repeated mechanism may be that simple homogeneous Product Blocks are too restrictive when many box types must share a container. This is especially important because the CLTRS literature finds generalized blocks increasingly valuable as heterogeneity rises.

Do not assume G is the answer. Prove the cluster first.

---

## 14. Blog article framing

Possible working title:

“Benchmarking a Deterministic Container Loading Engine on 700 Academic Test Cases”

Recommended tone:

- transparent
- engineering-focused
- no claim of mathematical optimality
- no claim that KolliPack beats academic state of the art
- distinguish published academic references from vendor self-reported commercial numbers
- explain why determinism, explainability and constructive speed are product objectives alongside utilization

Suggested article structure:

1. Why benchmark a commercial loading engine?
2. What is the Bischoff–Ratcliff BR1–BR7 suite?
3. How KolliPack was mapped to the benchmark orientation rules
4. 2,800 solves: methodology and validation
5. Results of the four KolliPack modes
6. What Mixed Cargo Infill added
7. Comparison with CLTRS full-support academic result
8. Commercial context: LoadingMCP public benchmark
9. What KolliPack deliberately does differently
10. Where KolliPack loses utilization
11. Next step: systematic failure clustering, not benchmark overfitting
12. Commitment to rerun the complete suite after every generalizable improvement

Preferred academically careful wording:

- “published full-support reference result” rather than “the optimum”
- “approximately 10.5 percentage points below CLTRS on average” rather than “10.5% worse”
- “LoadingMCP self-reports approximately 85%” rather than presenting it as independently verified
- “same benchmark family” only when orientation/support assumptions are stated

---

# HANDOVER PROMPT FOR NEXT CHAT

We are continuing development and research of the KolliPack Transport Container loading engine.

The latest benchmark baseline is `engine(20260817-215516).py`, SHA-256 `73e18b73c63718828e7a45a7bf8a94da6ebc82e965215f86f1ffa7a3c224f758`.

The current engine is considered an approved strong commercial baseline. It is deterministic, fast, block-based, explainable, and physically validates bounds, overlaps and elevated support. It contains Space Evenly, Load Front-to-Back, Mixed Cargo Side Infill, Supported Top Infill, Native/DGFE frontier handling and deterministic residual closure. Protect these strengths.

We have now run the complete Bischoff–Ratcliff BR1–BR7 OR-Library benchmark against this engine.

Dataset:
- 7 classes × 100 instances = 700 cases
- BR1/BR2/BR3/BR4/BR5/BR6/BR7 contain 3/5/8/10/12/15/20 box types
- container 587 × 233 × 220 dataset units
- objective = maximize volume utilization
- orientation flags mapped to KolliPack as: original H vertical -> R1; original W vertical -> R2; original L vertical -> R3
- stackable = True, weight = 0, sequence = 1

We ran all four modes, total 2,800 solves, and globally validated every final placement set. All 2,800 were physically valid under the current engine validator.

Verified full-suite averages:
- Space Evenly = 76.203%
- Space Evenly Infill = 83.666%
- Front-to-Back = 67.414%
- Front-to-Back Infill = 82.541%
- best KolliPack mode per case = 84.453%

Space Evenly Infill per class:
- BR1 84.952%
- BR2 85.096%
- BR3 84.711%
- BR4 83.754%
- BR5 83.192%
- BR6 82.556%
- BR7 81.403%

Published academic reference:
Fanslau & Bortfeldt CLTRS packing variant guarantees full support and reports 94.2% average over BR1–BR7. Per class: 94.51, 94.73, 94.74, 94.41, 94.13, 93.85, 93.20%.

Commercial public reference:
LoadingMCP self-reports approximately 85% overall on the 700 BR instances, including 86.4% BR1, 85.3% BR5 and 82.6% BR7. LoadingMCP says it is built on PackingSolver; the official ROADEF/EURO results confirm PackingSolver authors Florian Fontan and Luc Libralesso won the 2022 Renault truck-loading challenge.

Our goal is NOT to turn KolliPack into CLTRS or chase individual benchmark instances.

RESEARCH PROCESS:

CURRENT APPROVED ENGINE
        |
        v
Run complete BR benchmark
        |
        v
Rank worst cases
        |
        v
Inspect geometry + diagnostics
        |
        v
CLUSTER FAILURE MECHANISMS
        |
        +-- product ordering?
        +-- block construction?
        +-- residual quantity?
        +-- frontier depth?
        +-- side envelope?
        +-- top/support geometry?
        |
        v
Find ONE generalizable principle
        |
        v
Implement bounded change
        |
        v
RE-RUN EVERYTHING
        |
        +-- worst cluster improves?
        +-- 700-case average improves?
        +-- current golden cases unchanged?
        +-- runtime acceptable?
        +-- determinism unchanged?

START THE NEXT SESSION IN DIAGNOSIS MODE, NOT CODING MODE.

First select approximately 10–20 of the genuinely worst cases, ranked by the BEST of Space Evenly Infill and Front-to-Back Infill, so we diagnose weaknesses shared by KolliPack rather than weaknesses of only one mode.

Initial worst cases include:
BR1-92, BR2-92, BR3-43, BR1-44, BR7-20, BR1-71, BR1-81, BR1-9, BR1-88 and BR7-31.

For each selected case:
1. reconstruct exact benchmark input;
2. capture both mixed-mode placements and diagnostics;
3. calculate requested vs loaded volume;
4. inspect top, side and longitudinal geometry;
5. identify where volume becomes irrecoverably unavailable;
6. label the dominant loss mechanism using the taxonomy above;
7. do NOT propose code until multiple cases reveal the same mechanism.

Then cluster the cases.

Only after a repeated failure mechanism is demonstrated should we brainstorm ONE deterministic, bounded and generalizable principle.

Any proposal must explicitly state:
- generic physical/geometric principle;
- which failure cluster it addresses;
- why it is not benchmark-specific;
- expected computational cost;
- exact parts of the approved engine that remain untouched;
- golden regression risks;
- new regression tests required.

Forbidden unless the user explicitly changes the design philosophy:
- global free-space search
- product permutations
- beam search
- branch-and-bound
- backtracking
- recursive packing trees
- randomized search
- historical reopening of closed regions
- legacy engine reuse/import

After implementation, always rerun:
1. all identified failure-cluster cases;
2. all existing golden KolliPack regression cases;
3. all 700 BR1–BR7 cases in the relevant benchmark mode(s);
4. determinism checks;
5. physical validation;
6. runtime comparison.

Judge an improvement on multiple dimensions:
- full-suite average utilization
- class-level utilization
- worst-case improvement
- number of regressions
- physical validity
- deterministic repeatability
- runtime
- visual/operational quality of the layouts

Do not accept a change solely because the global BR average increases.

The eventual blog article will explain the baseline benchmark, the academic literature comparison, and—if this research succeeds—the measurable improvement from one or more generalizable constructive principles.

---

## 15. Primary/reference sources for the next chat to verify on the web

1. OR-Library — “Container loading” dataset information page; files thpack1–thpack7; Bischoff & Ratcliff (1995).
2. Bischoff, E. E. & Ratcliff, M. S. W. (1995), “Issues in the Development of Approaches to Container Loading,” Omega 23(4), 377–390.
3. Fanslau, T. & Bortfeldt, A., “A Tree Search Algorithm for Solving the Container Loading Problem,” especially Tables 3 and 4 and the sections on generalized blocks, support constraint and heterogeneity.
4. LoadingMCP — “Research & benchmarks — where the engine comes from,” July 2026 benchmark figures.
5. ROADEF/EURO 2022 Trucks Loading Problem — official final results confirming Florian Fontan and Luc Libralesso as winners.

