"""Compare TC-REG-019 implementation with immutable approved-engine evidence.

cohort uses four independent worker processes (not packing search branches).
timing loads the checksum-verified Git baseline only for serial measurements.
No saved baseline, golden expectation or production setting is changed.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time
import types

import reproduce as r
from capture_baselines import compact

OUT = r.HERE / "implementation"
MODES = ("space_evenly", "space_evenly_infill", "front_to_back", "front_to_back_infill")


def cohort_case(job):
    case_id, container, products = job
    records = []
    for mode in MODES:
        started = time.perf_counter()
        result = r.e.pack_container(container, products, mode)
        rec = compact(container, products, result, time.perf_counter() - started)
        rec.update(case_id=case_id, mode=mode)
        records.append(rec)
    return records


def cohort(workers):
    source = r.ROOT / "engine_development_notes/transport_container_selection/run_kollipack_br_benchmark.py"
    spec = importlib.util.spec_from_file_location("approved_br_inputs", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    baseline_summary = json.loads((r.HERE / "br700-summary.json").read_text())
    input_hash = hashlib.sha256(module.INPUT_FILE.read_bytes()).hexdigest()
    assert input_hash == baseline_summary["input_sha256"]
    baseline = {(v["case_id"], v["mode"]): v for v in (
        json.loads(line) for line in gzip.open(r.HERE / "br700-baseline.jsonl.gz", "rt")
    )}
    jobs = [(str(case_id), module.make_container(rows), module.make_products(rows))
            for case_id, rows in module.pd.read_csv(module.INPUT_FILE).groupby("case_id", sort=False)]
    summary = {"cases": 0, "runs": 0, "valid": 0, "quantity_regressions": [],
               "signature_regressions": [], "changed_outcomes": [], "invalid": []}
    started = time.perf_counter()
    with ProcessPoolExecutor(max_workers=workers) as pool, gzip.open(OUT / "br700-after.jsonl.gz", "wt") as stream:
        for records in pool.map(cohort_case, jobs):
            for rec in records:
                key = (rec["case_id"], rec["mode"])
                before = baseline[key]
                counts = {str(row): qty for row, qty in rec["counts"].items()}
                row_loss = any(counts.get(row, 0) < qty for row, qty in before["counts"].items())
                if row_loss or rec["total"] < before["total"]:
                    summary["quantity_regressions"].append(key)
                if rec["signature_sha256"] != before["signature_sha256"]:
                    summary["changed_outcomes"].append(key)
                    if rec["mode"] in ("space_evenly", "front_to_back") or rec["total"] <= before["total"]:
                        summary["signature_regressions"].append(key)
                summary["runs"] += 1
                summary["valid"] += int(rec["physical"]["valid"])
                if not rec["physical"]["valid"]:
                    summary["invalid"].append({"key": key, "physical": rec["physical"]})
                stream.write(json.dumps(rec, separators=(",", ":"), allow_nan=False) + "\n")
            stream.flush()
            summary["cases"] += 1
            if summary["cases"] % 25 == 0:
                print(summary["cases"], summary["runs"], summary["valid"], flush=True)
    summary.update(workers=workers, elapsed_seconds=time.perf_counter() - started,
                   engine_sha256=hashlib.sha256(Path(r.e.__file__).read_bytes()).hexdigest(),
                   baseline_engine_sha256=baseline_summary["engine_sha256"], input_sha256=input_hash)
    (OUT / "br700-comparison.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    assert summary["cases"] == 700 and summary["runs"] == summary["valid"] == 2800
    assert not summary["quantity_regressions"] and not summary["signature_regressions"]


def timing():
    baseline = json.loads(gzip.decompress((r.HERE / "baseline.json.gz").read_bytes()))
    source = subprocess.check_output(
        ["git", "show", baseline["commit"] + ":packagingapp/utils/container_tool/engine.py"], cwd=r.ROOT,
    )
    if hashlib.sha256(source).hexdigest() != baseline["engine_sha256"]:
        # Git stores LF; the recorded approved Windows checkout used CRLF.
        source = source.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    assert hashlib.sha256(source).hexdigest() == baseline["engine_sha256"]
    # Read-only validation snapshot, never imported by the application.
    name = "packagingapp.utils.container_tool._tc019_timing_baseline"
    previous = types.ModuleType(name)
    sys.modules[name] = previous
    exec(compile(source, "<checksum-verified-approved-engine>", "exec"), previous.__dict__)
    fixture = json.loads((r.HERE / "input.json").read_text())
    records = []
    try:
        for flags in fixture["rotation_configurations"]:
            container, products = r.normalize(fixture, flags)
            previous.pack_container(container, products, r.MODE)
            r.e.pack_container(container, products, r.MODE)
            before, after = [], []
            for repetition in range(5):
                order = ((previous, before), (r.e, after)) if repetition % 2 == 0 else ((r.e, after), (previous, before))
                for module, values in order:
                    start = time.perf_counter()
                    result = module.pack_container(container, products, r.MODE)
                    values.append(time.perf_counter() - start)
            record = {"flags": flags, "approved_seconds": before, "implementation_seconds": after,
                      "approved_source_sha256": hashlib.sha256(source).hexdigest(),
                      "approved_median_ms": statistics.median(before) * 1000,
                      "implementation_median_ms": statistics.median(after) * 1000,
                      "partial_trials": result.get(r.MODE + "_partial_support_beds")}
            records.append(record)
            print(flags, round(record["approved_median_ms"], 3), round(record["implementation_median_ms"], 3), flush=True)
    finally:
        del sys.modules[name]
    (OUT / "serial-timing.json").write_text(json.dumps(records, indent=2, allow_nan=False) + "\n")


def certificate():
    """Explicit reference-only physical certificate; never a packing candidate."""
    data = json.loads(gzip.decompress((OUT / "results.json.gz").read_bytes()))
    current = data["reference"]["r3"]
    assert current["counts"] == [30, 17, 16, 48, 8, 0, 0]
    products, container = current["products"], current["container"]
    units = [r.e.Placement(**p) for p in current["placements"]]
    caps = [p for p in units if p.row_index == 4]
    assert len(caps) == 8
    from dataclasses import replace
    raised = [replace(p, z=p.z + products[5]["height"]) if p.row_index == 4 else p for p in units]
    for index, cap in enumerate(caps):
        row = 5 if index < 4 else 6
        source = products[row]
        raised.append(r.e.Placement(source["name"], index % 4, row, source["sequence"],
                                    source["weight"], source["stackable"], cap.x, cap.y, cap.z,
                                    source["length"], source["width"], source["height"]))
    result = r.explicit_result(raised, products)
    rec = r.record(container, products, result, diagnostics=False)
    assert rec["counts"] == [30, 17, 16, 48, 8, 4, 4] and rec["total"] == 127
    assert all(a >= b for a, b in zip(rec["counts"], current["counts"]))
    assert r.e._partial_support_bed_outcome_reason(result, container, r.e.normalize_products(products)) is None
    output = {"basis_engine_sha256": data["engine_sha256"],
              "status": "Independent physical certificate; not generated or selected by the engine",
              "construction": "Retain the 119-unit placements; place F4/G4 at the eight E bases, then raise those E by 21.7 in. D62.8 + F/G21.7 + E21.7 = 106.2 in.",
              "certificate": rec}
    (OUT / "127-unit-certificate.json.gz").write_bytes(gzip.compress(json.dumps(output, separators=(",", ":"), allow_nan=False).encode(), mtime=0))
    print("Independent certificate", rec["counts"], rec["total"], "physical", rec["physical"]["valid"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("action", choices=("cohort", "timing", "certificate"))
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if args.action == "cohort":
        cohort(max(1, min(args.workers, 4)))
    elif args.action == "timing":
        timing()
    else:
        certificate()
