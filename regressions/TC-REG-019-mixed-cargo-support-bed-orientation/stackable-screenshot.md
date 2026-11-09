# Screenshot follow-up: stackable B is excluded from constructed support beds

This records the compatibility outcome before activation. The current public
engine loads 127 pieces with 15 B units on A for the same inputs. Run
`generalized/frozen_comparison.py` to reproduce both layouts. See
[public-path verification](generalized/results.md).

The owner supplied two new screenshots. The displayed inputs have **all seven
rows stackable**, R3 only, A/B/C sequence 1 and D/E/F/G sequence 3. Dimensions,
quantities, units, weights and blank payload match `input.json`; B/E stackability
differs from that earlier fixture. This is a distinct input configuration.

The shared transport service and current engine reproduce the displayed result
exactly: **A30, B17, C16, D4, E14, F2, G0 — 83 units**. Independently checked
placements contain **zero B fully supported by A**. A synthetic POST through
the current checkbox parser returns seven `true` values. Original browser POST
data is unavailable, so this is a reproduction of the visible settings rather
than a claimed capture of that POST.

## Confirmed mechanism

1. `_pack_container_approved()` returns its ordinary result when every requested
   row is stackable. No full-request support-bed trial or diagnostic is produced.
2. The partial-bed wrapper requires that diagnostic to exist, so it also returns
   early. Both bed choosers independently reject `anchor.stackable` as well.
3. R3's footprint ordering puts B before A. B commits two eight-unit blocks:
   four Y lanes, two Z layers, two 63-inch X slices. One residual B then loads
   on the floor. Nine B are on the floor and eight are on B, at Z=39.4 inches.
4. B has zero remaining quantity when A's main support roof exists. Local top
   closure does not relocate cargo out of an already committed frontier.
   The transition instead puts one A on the residual B, matching the small
   elevated orange unit visible in the screenshot.

This is an eligibility limitation in the implementation. A **stackable** B is
physically allowed above A; its flag additionally allows it to support cargo.
The earlier extension generalized partial quantity and orientation handling but
explicitly retained non-stackable-upper eligibility. Its 119-unit result applies
to B/E=false and does not describe this all-stackable screenshot case.

## Independent evidence of useful headroom

| B stackable | E stackable | Engine A–G counts | Total | B on A |
|---|---|---|---:|---:|
| No | No | 30,17,16,48,8,0,0 | 119 | 15 |
| Yes | No | 30,17,16,30,4,0,0 | 97 | 0 |
| No | Yes | 30,17,16,38,14,4,4 | 123 | 15 |
| Yes | Yes | 30,17,16,4,14,2,0 | 83 | 0 |

The geometry generated under the stricter B=false/E=true input also passes
independent full physical validation after restoring B=true. It is a valid
**123-unit all-stackable certificate**, with 15 B on A and no row losing quantity
against the screenshot's 83 units. This certificate is not the engine's selected
all-stackable output. It demonstrates that a beneficial supported arrangement
exists with the owner's stackability flags unchanged.

The required next correction is stackability-independent upper eligibility:
allow stackable upper candidates, preserve their real stackability and vertical
capacity, admit their supported adaptive plans, and apply the same complete-result
no-row-loss gate. Removing only the outer gate is insufficient because both
choosers and the adaptive fill-plan eligibility also need assessment. This can
activate work in previously bypassed all-stackable requests, so runtime and
the full frozen/cumulative regression contracts must be checked before acceptance.
The previously proposed intermediate tier does not remove this earlier gate.

## Reproduction and status

```powershell
.\.venv\Scripts\python.exe regressions/TC-REG-019-mixed-cargo-support-bed-orientation/diagnose_stackable_screenshot.py
```

The script records the current failing optimization baseline and the separately
labelled physical certificate in `stackable-screenshot-evidence.json.gz`. It is
outside active test discovery and does not claim the optimization is solved.
Engine SHA-256 remains
`75baac144a2d9c9203e185d9e94ab3c2726c582cb8c1a1ae474935e4d3e17d3c`.
Only this diagnostic, its script and reference evidence/register notes were
added during the follow-up. No engine behavior, existing expectations, commit,
push, merge, deployment or production data changed.
