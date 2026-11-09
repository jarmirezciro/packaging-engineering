"""Compare the screenshot and all affected frozen cases on the same inputs."""
import argparse
import json
from pathlib import Path

from probe import inputs, r, trial_pack
from packagingapp.tests.test_transport_mixed_cargo_infill import (
    INFILL_MODES, container, product, semitrailer_roof_experiment,
)


def review_inputs():
    screenshot = next(item for item in inputs() if item[0] == "11/r3/front_to_back_infill")
    yield "Screenshot · all stackable, R3", *screenshot[1:]
    for perturbed in (False, True):
        geometry = "Perturbed" if perturbed else "Original"
        for g_sequence in (3, 4):
            for mode in INFILL_MODES:
                label = f"{geometry} semitrailer · G group {g_sequence}"
                yield label, container(mode, length=567, width=98.5, height=107), (
                    semitrailer_roof_experiment(perturbed=perturbed, g_sequence=g_sequence)
                ), mode
    selected = {"L": 12032.0, "W": 2352.0, "H": 2395.0, "max_weight": 26500.0}
    rows = [
        product("P1", 1200, 800, 1100, 20, weight=900, r2=True, r1=True),
        product("P2", 500, 400, 700, 100, r2=True, r1=True),
        product("P3", 500, 200, 700, 400, r2=True, r1=True),
    ]
    for mode in INFILL_MODES:
        yield "P3 current-row top-infill case study", selected, rows, mode


def scenario(label, selected, rows, mode):
    before = r.e._pack_container_compatible(selected, rows, mode)
    after = trial_pack(selected, rows, mode)
    if before["placements"] == after["placements"]:
        return None
    records = []
    for outcome in (before, after):
        record = r.record(selected, rows, outcome, diagnostics=False)
        supports = [p for p in outcome["placements"] if p.row_index == 0]
        record["pieces"] = [
            [p.row_index, p.x, p.y, p.z, p.l, p.w, p.h,
             len(rows) == 7 and p.row_index == 1 and r.fully_supported_by(p, supports)]
            for p in outcome["placements"]
        ]
        record["P3_top"] = outcome[f"{mode}_top_infill_units_by_product"].get("2", 0)
        record["P3_self_anchor"] = any(
            action["anchor_product"] == "P3" and action["filler_product"] == "P3"
            and action["anchor_eligible"] for action in outcome[f"{mode}_top_actions"]
        )
        records.append({key: record.get(key) for key in (
            "counts", "total", "pieces", "B_on_A", "P3_top", "P3_self_anchor",
        )})
    a, b = records
    assert b["total"] > a["total"] and all(y >= x for x, y in zip(a["counts"], b["counts"]))
    label_mode = "Progressive Infill" if mode == r.MODE else "Balanced Infill"
    return {
        "label": f"{label} · {label_mode}", "size": [selected[k] for k in ("L", "W", "H")],
        "rows": [[row["name"], row["qty"]] for row in rows], "outcomes": records,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, help="Write exact placements for the review.")
    args = parser.parse_args()
    cases = []
    for case in review_inputs():
        result = scenario(*case)
        if result is None:
            continue
        cases.append(result)
        a, b = result["outcomes"]
        detail = (
            f"B on A {a['B_on_A']} -> {b['B_on_A']}" if a["B_on_A"] is not None
            else f"P3 top infill {a['P3_top']} -> {b['P3_top']}, "
                 f"own anchor action {a['P3_self_anchor']} -> {b['P3_self_anchor']}"
        )
        print(f"{result['label']} | {a['counts']} -> {b['counts']} | {detail}", flush=True)
    if args.json:
        args.json.write_text(json.dumps(cases, separators=(",", ":"), allow_nan=False), encoding="utf-8")


if __name__ == "__main__":
    main()
