# Research Notes — 700 Container-Loading Tests: An Honest Benchmark of KolliPack

## Brief

- Mode: research
- Article profile: engineering_deep_dive
- Intended reader: operations / logistics manager with enough technical interest to review a loading-engine benchmark
- Primary question: How can container-loading algorithms be benchmarked fairly, and what do 700 BR1–BR7 cases reveal about KolliPack?
- Search intent: informational; understand how to compare container-loading engines and interpret benchmark results
- Primary keyword: container loading benchmark
- Article promise: show the exact test contract, report the frozen KolliPack result honestly, explain the 10.534-point academic gap, and turn the benchmark into a non-overfitting engineering loop
- Proposed CTA: Try KolliPack Transport Container Loading → `/free-container-loading-calculator/`
- Research date: 2026-08-20
- Frozen KolliPack run date: 2026-08-18

## Editorial contract

- Reader problem: a single attractive 3D load does not establish optimizer quality, while different support and orientation assumptions can make numerical comparisons misleading.
- Business decision: decide whether a loading engine is suitable for a geometric shortlist, and what validation is still required before an operational load is released.
- Business consequence: better geometric utilization can reduce unused container volume, but the benchmark score must not be confused with transport safety, access, balance, or physical approval.
- Approved workflow scope: benchmark and interpretation only; no engine, application, UI, export, or deployment changes.
- First-block result: 700 public cases × 4 KolliPack modes = 2,800 solves; Space Evenly – Mixed Cargo Infill = 83.666% average; CLTRS packing reference = 94.2% average.
- Comparison claim: KolliPack performs credibly and improves materially with Mixed Cargo Infill, but the published full-support CLTRS reference is substantially higher on pure volume utilization.
- Figure plan: four deterministic figures plus a simple thumbnail; no vendor UI recreation and no interpolated commercial values.

## Title laboratory

| Angle | Candidate | Decision |
|---|---|---|
| Result-led | 83.7% vs 94.2%: What 700 Container-Loading Tests Taught Us | Strong but too number-led for the visible title |
| Problem-led | How Should a Container-Loading Engine Be Benchmarked? | Clear informational title; less KolliPack-specific |
| Engineering-led | Benchmarking a Deterministic 3D Container-Loading Engine | Accurate and restrained |
| SEO-led | Container Loading Benchmark: KolliPack on 700 BR Cases | Good metadata title |
| Curiosity-led | Can an Explainable Loading Engine Compete with Tree Search? | Useful question; does not state the result |
| Transparency-led | 700 Container-Loading Tests: An Honest Benchmark of KolliPack | Selected visible title |

Final visible title: **700 Container-Loading Tests: An Honest Benchmark of KolliPack**

SEO title: **Container Loading Benchmark: KolliPack on 700 BR Cases**

Thumbnail headline: **700 CASES / HONEST BENCHMARK / 83.7%**

## Outline

1. Result and comparison disclosure.
2. Why 700 cases are stronger evidence than a screenshot.
3. BR1–BR7 provenance and dataset structure.
4. Frozen KolliPack test contract.
5. Four-mode results and Mixed Cargo Infill effect.
6. CLTRS full-support academic reference and historical spectrum.
7. Engineering trade-off: bounded constructive loading versus broader search.
8. Heterogeneity signal and internal research hypothesis.
9. LoadingMCP vendor-published commercial context.
10. What BR1–BR7 does and does not measure.
11. Anti-overfitting development loop.
12. Fair-benchmark contract and restrained CTA.

## Source ledger

| Source | Claim supported | Source type | Accessed | Article section |
|---|---|---|---|---|
| [OR-Library container loading](https://people.brunel.ac.uk/~mastjjb/jeb/orlib/thpackinfo.html) | `thpack1`–`thpack7` provenance; single-container objective; dimension orientation flags; source paper citation | Public dataset documentation | 2026-08-20 | BR1–BR7 suite; methodology |
| [Bischoff & Ratcliff (1995)](https://doi.org/10.1016/0305-0483%2895%2900015-G) | Original benchmark paper and benchmark-generation provenance | Journal record / DOI | 2026-08-20 | BR1–BR7 suite |
| [Fanslau & Bortfeldt, INFORMS](https://doi.org/10.1287/ijoc.1090.0338) | 3D-CLP framing; packing vs nonsupport variants; generalized blocks; partition-controlled tree search | Publisher article page | 2026-08-20 | Academic gap; engineering explanation |
| [Fanslau & Bortfeldt full paper PDF](https://www.fernuni-hagen.de/wirtschaftswissenschaft/forschung/download/beitraege/db426.pdf) | 100 cases per class; BR1–BR7 class values; 94.2% packing result; Table 4 historical support-constrained comparison; heterogeneity/internal-loss discussion | Author-hosted paper PDF | 2026-08-20 | Results; heterogeneity; historical context |
| [LoadingMCP Research & benchmarks](https://loadingmcp.com/research) | Vendor-published BR1 86.4%, BR5 85.3%, BR7 82.6%, about 85% overall; PackingSolver statement | Vendor public research page | 2026-08-20 | Commercial reference |
| [ROADEF/EURO 2022 final results](https://roadef.org/challenge/2022/en/finalresult.php) | Florian Fontan and Luc Libralesso listed as final winner team S41 | Official competition results | 2026-08-20 | Commercial reference |
| `engine_development_notes/transport_container_selection/kollipack_br1_br7_benchmark_20260818.csv` | All 2,800 KolliPack rows, four modes, utilization, validity, class and mode values | Frozen local benchmark CSV | 2026-08-20 | All numerical KolliPack claims |
| `engine_development_notes/transport_container_selection/KolliPack_BR_Benchmark_Handover_20260818.md` | Frozen engine snapshot; assumptions; validation; mode interpretation; diagnostic workflow | Frozen local handover | 2026-08-20 | Methodology; development loop |
| `engine_development_notes/transport_container_selection/kollipack_br1_br7_benchmark_summary_20260818.json` | Summary averages, medians, min/max, class results, wins, validity | Frozen local summary | 2026-08-20 | Results |

## Independent verification record

- CSV rows: 2,800.
- Cases: 700 unique `(class, instance)` pairs.
- Modes: `space_evenly`, `space_evenly_infill`, `front_to_back`, `front_to_back_infill`.
- Valid rows: 2,800/2,800 with `valid=True`.
- CSV recomputation with repository `.venv` and pandas matched the handover/JSON for all four mode averages, medians, min/max, per-class infill averages, 433/257/10 infill wins, and the 84.453450% best-of-all-four-mode envelope.
- Best of the two infill modes only is 84.448966%; do not confuse it with the handover's best-of-all-four-mode envelope.
- No benchmark rerun was performed during article work.
- No current engine code was changed or called for a fresh benchmark.

## Verified KolliPack values

| Mode | Average | Median | Minimum | Maximum |
|---|---:|---:|---:|---:|
| Space Evenly | 76.203259% | 76.146153% | 53.408996% | 93.051753% |
| Space Evenly – Mixed Cargo Infill | 83.666441% | 83.686883% | 68.341169% | 93.051753% |
| Front-to-Back | 67.413785% | 67.521949% | 41.781957% | 91.918499% |
| Front-to-Back – Mixed Cargo Infill | 82.540533% | 82.765675% | 67.008689% | 92.660253% |
| Retrospective best of all four modes per case | 84.453450% | 84.476318% | — | — |

Per-class Space Evenly Infill: BR1 84.952353%; BR2 85.096030%; BR3 84.711384%; BR4 83.753898%; BR5 83.192104%; BR6 82.556058%; BR7 81.403256%.

Per-class Front-to-Back Infill: BR1 83.334561%; BR2 83.678322%; BR3 83.742955%; BR4 82.448722%; BR5 82.244029%; BR6 81.941185%; BR7 80.393957%.

Mixed Cargo Infill changes: Space Evenly +7.463181 percentage points; Front-to-Back +15.126748 percentage points.

Infill head-to-head: Space Evenly Infill wins 433 cases; Front-to-Back Infill wins 257; ties 10.

## Academic comparison record

- Comparison uses CLTRS **packing variant**, not the cutting variant.
- Packing variant requires full support from below; cutting variant does not enforce that support constraint.
- Published BR1–BR7 packing averages: 94.51%, 94.73%, 94.74%, 94.41%, 94.13%, 93.85%, 93.20%; overall 94.2% as reported in Table 4.
- Gap against KolliPack Space Evenly Infill: 94.2% − 83.666441% = approximately 10.534 percentage points.
- Historical support-constrained Table 4 values used compactly: Terno B&B 88.5%; Bortfeldt/Gehring GA 90.1%; Gehring/Bortfeldt parallel GA 90.4%; Eley TRS 88.8%; Bischoff 90.5%; Moura/Oliveira GRASP 89.7%; CLTRS packing 94.2%.
- Do not call 94.2% a current state-of-the-art, world record, global optimum, or exact optimum.
- Do not compare paper CPU seconds directly with KolliPack runtime.

## Commercial comparison record

- LoadingMCP page accessed 2026-08-20; page labels benchmark July 2026.
- Public values used exactly as displayed: BR1 86.4%; BR5 85.3%; BR7 82.6%; about 85% overall.
- These figures were not independently reproduced by KolliLabs.
- No BR2/BR3/BR4/BR6 values were fabricated or interpolated.
- KolliPack versus LoadingMCP on published classes: BR1 84.952353% vs 86.4% (~1.45 pp); BR5 83.192104% vs 85.3% (~2.11 pp); BR7 81.403256% vs 82.6% (~1.20 pp).
- LoadingMCP states that its optimizer is built on PackingSolver; official ROADEF/EURO results confirm Fontan/Libralesso won the 2022 final truck-loading challenge.
- Disclosure required: vendor-published result, not independently reproduced; limited benchmark comparison, not product parity or complete evaluation; KolliLabs independent/not affiliated.
- Human review required before publication because a named commercial comparator and relative performance claims are included.

## Claims requiring caution

| Claim | Status | Reason/action |
|---|---|---|
| KolliPack reaches 83.666% | Verified | Frozen CSV recomputation; scope to Space Evenly – Mixed Cargo Infill and 2026-08-18 run |
| CLTRS reaches 94.2% | Verified published reference | Scope to Fanslau–Bortfeldt BR1–BR7 packing variant; not current best or mathematical optimum claim |
| All 2,800 results are valid | Verified narrowly | Say internal bounds/overlap/support validation; do not say physical certification or transport safe |
| KolliPack is near LoadingMCP | Bounded inference | Say similar numerical range only; vendor values not independently reproduced |
| LoadingMCP won ROADEF | Prohibited wording | Say LoadingMCP states it is built on PackingSolver; official results name Fontan/Libralesso as winners |
| More heterogeneity causes lower KolliPack utilization | Verified trend, not causality | Describe as diagnostic signal/hypothesis; connect to published internal-loss/general-block discussion |
| Best KolliPack mode = 84.453% | Verified envelope | Explain it selects the best of four modes per case; never present as standalone |

## Image plan

| Image | Purpose | Method | Status | Output path |
|---|---|---|---|---|
| Thumbnail | Simple 700 CASES / HONEST BENCHMARK / 83.7% headline | Deterministic Matplotlib/Pillow composition; no UI or generated logo | Created | `static/img/blog/container-loading-benchmark-kollipack-br1-br7/thumbnail.webp` |
| Figure 1 | Average utilization for four KolliPack modes + separate CLTRS reference | Deterministic Matplotlib chart from frozen CSV/reference values | Created | `static/img/blog/container-loading-benchmark-kollipack-br1-br7/figure-1-700-case-utilization.webp` |
| Figure 2 | BR1–BR7 heterogeneity trend for two KolliPack infill modes + CLTRS | Deterministic Matplotlib line chart | Created | `static/img/blog/container-loading-benchmark-kollipack-br1-br7/figure-2-heterogeneity-curve.webp` |
| Figure 3 | BR1/BR5/BR7 commercial comparison | Deterministic Matplotlib grouped bars; only published LoadingMCP values | Created | `static/img/blog/container-loading-benchmark-kollipack-br1-br7/figure-3-commercial-reference.webp` |
| Figure 4 | Approved engine → benchmark → diagnostics → bounded change → full rerun | Deterministic Matplotlib flow diagram | Created | `static/img/blog/container-loading-benchmark-kollipack-br1-br7/figure-4-engineering-improvement-loop.webp` |

No real KolliPack UI screenshot was needed; all visuals are charts or conceptual process graphics based on numeric evidence. No official logo was redrawn.

## Fresh-Eyes review target

Persona: operations / logistics manager.

Pass questions: What was tested? Why are 700 cases meaningful? What score did KolliPack obtain? What score did the academic reference obtain? Why is there a gap? Why might an operational engine make different trade-offs? What does LoadingMCP contribute? What will KolliLabs do next?

Planned revision principles: define utilization in plain language; label the 84.453% envelope; keep LoadingMCP status explicit; distinguish internal geometry validation from physical approval; make the anti-overfitting loop actionable.
