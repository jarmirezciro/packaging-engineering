# TC-REG-019 generalized supported construction

The shared engine now considers the generalized planner for both Mixed Cargo
Infill modes. The compatibility outcome remains the incumbent. The owner
approved public selection after reviewing the side-by-side layouts.

The reference uses Progressive Fill – Mixed Cargo Infill, R3 only, in a
566.9 × 98.5 × 108-inch container. Each row's quantity floor comes from its
own pre-change result.

| B stackable | E stackable | Before | After | After counts A–G |
|---|---|---:|---:|---|
| No | No | 119 | 127 | 30, 17, 16, 48, 8, 4, 4 |
| No | Yes | 123 | 125 | 30, 17, 16, 40, 14, 4, 4 |
| Yes | No | 97 | 127 | 30, 17, 16, 48, 8, 4, 4 |
| Yes | Yes | 83 | 127 | 30, 17, 16, 48, 14, 2, 0 |

The screenshot configuration is the last row. Its selected layout includes
15 B units directly supported by A. Its two F units support E on D without
displacing any of the 14 E units. The three-tier constructions use actual
stackability, rotation permissions, dimensions and weights. The complete
candidate comparison keeps the 123-unit incumbent row floors for the
B non-stackable and E stackable variant. Its larger 127-unit local trial
loses F and G and is rejected.

The request-local planner samples homogeneous foundations and uses existing
roof Product Blocks, including stackable adaptive blocks on validated support.
A staged candidate uses coplanar panels that tile individual upper footprints.
The planner can use different intermediate rows in different columns. It
reserves upper capacity and payload before assigning those panels. Its search
uses two role preferences, a shortlist and a single intermediate tier.

`before.json.gz` freezes loaded row counts and placement signatures for all
112 inputs. It was captured from engine SHA-256
`75baac144a2d9c9203e185d9e94ab3c2726c582cb8c1a1ae474935e4d3e17d3c`.
The initial active Django suite passed 220 tests in 246.903 seconds. The
diagnostic matrix improved 23 of 56 mixed cases and preserved the placement
signatures of the other 33. All 56 baseline mode signatures matched.
The 2,800 archived benchmark runs were waived by the owner for this change.

## Approved changes to frozen public outcomes

The pre-activation suite exposed six protected subcases. Independent validation
confirmed that each candidate loads more units, with every row preserved. The
original exact expectations are retained on the compatibility path. The same
tests now verify the approved quantities and support behavior through public
selection.

| Protected input | Mode | Pieces | Other protected behavior |
|---|---|---:|---|
| Semitrailer, original geometry, G group 3 | Progressive Infill | 121 → 133 | B on A remains 15 |
| Semitrailer, original geometry, G group 4 | Progressive Infill | 125 → 131 | B on A falls from 15 to 1 |
| Semitrailer, perturbed geometry, G group 3 | Balanced Infill | 129 → 133 | B on A remains 17 |
| Semitrailer, perturbed geometry, G group 4 | Balanced Infill | 129 → 133 | B on A remains 17 |
| Semitrailer, perturbed geometry, G group 4 | Progressive Infill | 129 → 133 | B on A remains 17 |
| Current-row top-infill case study | Balanced Infill | 459 → 460 | P3 no longer uses its own anchor action for the protected top-infill assertion |

The frozen methods are
`SupportedTopAdaptiveMixedLaneTests.test_complete_reconstructed_semitrailer_experiments_keep_physics_and_sequence`
and `MixedCargoInfillTests.test_case_study_current_product_is_eligible_for_supported_top_infill`.
`frozen_comparison.py` runs the screenshot and protected inputs through both
paths. Run it from the repository root to print every changed row vector and
the supported-top differences. Its optional `--json` argument records the
actual coordinates for both layouts.
The pre-promotion suite also exposed two legacy mocks with a fixed count of
parent calls. They now exercise their original compatibility portfolio directly,
and their assertions pass unchanged.

## Timing

The median of six alternating serial runs for the all-stackable R3
Progressive Infill case was 43 ms on the compatibility path and 217 ms with
the diagnostic planner. Across all four R3 cases, the median additional time
was 86 to 174 ms. With all rotations and stackability enabled, median times
were 117 to 596 ms for Progressive Infill and 79 to 418 ms for Balanced Infill
when comparing compatibility with the new planner. See `timings-serial.log`.

## Pre-activation verification

- The full active Transport Django command in the testing guide passed all
  224 tests in 172.584 seconds with public compatibility and diagnostic test
  coverage. See `active-suite-compatible.log`.
- `probe.py --assert-target` passed the original 123-unit R3 target and all
  synthetic witnesses. See `diagnostic-target.log`.
- `diagnostic-matrix.json.gz` records the final 112-case comparison against
  `before.json.gz`. Both baseline modes retain their exact signatures.
- `manage.py check`, the two Transport sequence JavaScript checks and the
  eight Transport unit JavaScript checks passed.
- The standalone calculator, public calculator and Packaging Flow were
  exercised through real POSTs with diagnostic selection in the tests. The
  scene, report payload and Flow session used the same selected placements.
- The engine, mixed-cargo and unit-integration tests, domain contracts, and
  central regression and testing guides were updated. No deployment action
  was taken.

## Public-path verification

- The full active Transport Django command in the testing guide passed all
  224 tests in 318.782 seconds after activation. See `active-suite-public.log`.
- `matrix.py public-matrix.json.gz` ran all 112 cases through the public entry
  point. Every row vector and placement signature matched the reviewed
  diagnostic matrix. Of the 56 mixed cases, 23 improved over compatibility.
  Both baseline modes retained all 56 original signatures.
- `reproduce.py --assert-target` passed through the public entry point. It
  reached 127 in the original R3 case and passed the independent synthetic
  witnesses. See `public-target.log`.
- The two original regression methods and the all-stackable POST method
  passed focused checks. The POST method exercised the standalone calculator,
  public calculator and Packaging Flow with normal dispatch and checked
  the shared scene, report payload and session.
- `manage.py check` and all 10 Transport JavaScript checks passed.
