# TC-REG-019 verification record — 2026-11-08

This is the historical Phase 1 baseline. Current implementation validation is
recorded in [implementation/results.md](implementation/results.md).

This record describes the approved unchanged engine, not a proposed fix.
Engine SHA-256 is
`bdcaff48aa4afd94178f79f9a1ca85310410af3040b922a98742131f24088174`;
commit is `5924c8e9ba84db34e04104ae54f246c4790985a5`, branch `production`.

## Commands and outcomes

Run from `C:\PackagingEngineering`:

```powershell
.\.venv\Scripts\python.exe manage.py test packagingapp.tests.test_transport_mixed_cargo_infill packagingapp.tests.test_transport_adaptive_mixed_lane packagingapp.tests.test_transport_adaptive_mixed_lane_benchmarks packagingapp.tests.test_transport_front_to_back packagingapp.tests.test_transport_mono_lane_transition packagingapp.tests.test_transport_easycargo_preset packagingapp.tests.test_transport_sequence_semantics packagingapp.tests.test_space_evenly_stabilization packagingapp.tests.test_space_evenly_residual_frontier_closure packagingapp.tests.test_transport_max_quantity_solver packagingapp.tests.test_transport_unit_integration packagingapp.tests.test_transport_visualization packagingapp.tests.test_transport_sequence_ui packagingapp.tests.test_full_packaging_case --noinput
.\.venv\Scripts\python.exe manage.py check
node packagingapp/tests/js/test_transport_sequence.js
node packagingapp/tests/js/test_transport_units.js
```

| Verification | Result | Evidence |
|---|---|---|
| Exact documented active Transport suite | **210 passed, 0 failures/errors/skips**, 228.063 s | `active-suite.log` |
| Django system check | Passed; no issues | Command output; also reported in both suite logs |
| Sequence JavaScript | 2 passed, 0 failed/skipped | Command output |
| Editable-unit JavaScript | 8 passed, 0 failed/skipped | Command output |
| Recorded repeat of active suite | **210 passed, 0 failures/errors/skips**, 334.185 s | `protected-suite.log`, `protected-summary.json` |
| Archived BR1–BR7 cohort | **700 cases × 4 modes = 2,800 valid runs**, 0 invalid/omitted; 1,862.660 s including validation/recording | `br700.log`, `br700-summary.json`, `br700-baseline.jsonl.gz` |
| Task reconstruction | 7 rotation combinations, 15 independent controls; all produced outcomes physically valid and repeat signatures identical | `baseline.json.gz`, `reproduction.log` |
| Independent geometry | Local 5A/2B and complete 123-unit R3 certificates valid; eight unrelated/control cases have dominating witnesses | `baseline.json.gz` |
| Explicit unresolved target | **Expected exit 1**: current R3 53 < known-feasible 123 | `unresolved-target.log`; excluded from active suite |
| Artifact checks | Both Python files parse; compressed JSON and 604 captured records parse; saved signatures match; non-R row inputs identical across rotations; B false in all normalized rows and placements | Diagnostic command output |
| Diff checks | `git diff --check` passed; no engine or existing test diff | Diagnostic command output |

The testing guide's older restoration counts are historical observations;
210 is the count of the exact current active command. No expectations were
added to or removed from it by this task. The logs include the existing
`staticfiles` directory warning and an expected bad-request PDF test response;
both suites still pass.

## Protected output capture

`capture_baselines.py suite` recorded **727 calls**, retaining **604 distinct
test/input/output records** with full placements and canonical input values.
All 604 pass the independent physical checker. One record is explicitly labelled
`explicit_mock_injection=true`: an existing whole-outcome selection test controls
the internal constructor with mocks, and the returned incumbent is physically
valid. There are no validation exceptions.

The recorder changes only the in-process public entry-point binding to a wrapper
which delegates once to the original engine and records its return. It restores
the binding afterwards. It does not generate candidates or change decisions.
Direct-helper tests and services which imported the entry point before the
wrapper are verified by their normal assertions, rather than by individual
JSONL records. This is not a claim to have traced every internal candidate in
the active suite. The reference-case rejection trace is separate and observes
the actual support-bed function through Python tracing without replacing it.

Every JSONL record includes the test ID, container/products, row counts,
total, actual placement coordinates/identity/sequence/stackability/weight,
signature hash, physical result, engine-only elapsed time and exposed scalar
candidate counters/support-bed diagnostics. The signature format is SHA-256
over sorted-key, compact JSON of the complete placement dictionaries. It is an
additional baseline format, **not a replacement for existing golden digests**.

Representative protected outcomes (row counts follow their original inputs):

| Protected fixture | Progressive / Progressive Infill | Balanced / Balanced Infill |
|---|---|---|
| Original TOPS | 375,405,288,160 = **1228** | Same = **1228** |
| Optimized TOPS reconstruction | 400,405,288,160,32 = **1285** | Same = **1285** |
| TOPS independent probe A | 434,405,288,160,32 = **1319** | 430,405,288,160,32 = **1315** |
| TOPS independent probe B | 400,405,288,160,40 = **1293** | 400,392,288,160,40 = **1280** |
| ExpV2-2 / TC-REG-017 mixed modes | Infill: 30,17,16,48,14,4,4 = **133** | Infill: same = **133** |
| EasyCargo seven-row all-rotation and R3 fixtures | Infill: 220,130,193,58,26,193,58 = **878** | Not this test's scope |

The TOPS optimized/probe P5 rotations retain the existing test's reconstruction
assumption; these are KolliPack outcomes, not newly researched competitor claims.

All active register protections ran. TC-REG-001 has its EasyCargo clean-row
assertions; TC-REG-002/006 mono-lane geometry and caps; TC-REG-003/004 Native/DGFE
and deferred settlement; TC-REG-005/010 adaptive/TOPS; TC-REG-007/008 Balanced
phase and residual closure; TC-REG-009/013/014 side/top and supported roofs;
TC-REG-011 Max qty; TC-REG-012 sequence/UI; TC-REG-015 equivalent units;
TC-REG-016 service/scene/report/Flow; TC-REG-017 complete support beds. Their
original assertions are unchanged and passed. New TC-REG-019 is not falsely
counted as protected or solved.

## Archived BR1–BR7 cohort

The additional runner calls the established benchmark module's **unmodified**
`make_container()` and `make_products()`, including its archived R1/R3 mapping.
All 700 inputs run in the four active modes. Payload is omitted as prescribed
by that geometry benchmark. Per-case rows, placements, signatures, physics,
timings and candidate counters are retained in `br700-baseline.jsonl.gz`.
Final counts and elapsed time are recorded in `br700-summary.json`.

Completion and integrity checks confirm exactly **2,800 unique case/mode records**,
700 in each mode, all physically valid, with every saved placement signature
recomputed successfully. Input CSV SHA-256 is
`8ed970b177b832a4f89a1fb0201ccf5fef48a1b939cbd1975ce9e984fd4f6536`.
The completed cohort's engine checksum matches the approved source above.

Recorded engine-call times (seconds; diagnostic, partly CPU-contended):

| Mode | Median | Maximum |
|---|---:|---:|
| Balanced Spread | 0.045045 | 17.262800 |
| Balanced Spread Infill | 0.254517 | 26.629691 |
| Progressive Fill | 0.184934 | 3.024212 |
| Progressive Fill Infill | 0.345006 | 3.845337 |

The slower 20-row BR7 cases are existing-engine behavior. This task does not
change or optimize those timings. Future implementation comparisons must retain
the same inputs, distinguish ineligible/eligible support-bed requests, and
explain any additional cost separately.

These are current approved-engine baselines. Saved August counts and rejected
LTHR outputs are not used as acceptance results. No algorithm candidate has
been implemented or compared. Recorded-suite and cohort timings include
recording overhead and concurrent CPU work; they must not be presented as
an algorithm performance regression. Future timings require controlled serial
alternating runs.

## Changed files and safety

This task adds only this regression directory and one **Unresolved** row in
`docs/engineering/known-issues-and-regressions.md`. The domain document, testing
guide and pre-existing retired-TC-REG-018 text were already changed by earlier
work and are preserved. Engine and existing test files have no diff.

No commit, push, merge, deployment, Railway operation, production migration
or production-data write was performed. Implementation remains gated on the
user's explicit approval.
