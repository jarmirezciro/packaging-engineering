"""Capture existing engine outputs without changing packing rules.

suite repeats the documented suite with a recording wrapper; the unmodified
command and uninstrumented runtime are recorded separately in active-suite.log.
cohort uses the established BR runner's input conversion, all 700 x 4 modes.
Both write compressed JSONL including coordinates and independent validation.
"""
import argparse
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
from functools import wraps
import gzip
import importlib.util
import json
from pathlib import Path
import time
import unittest
from unittest.mock import Mock

import reproduce as r
from packagingapp.utils.container_tool import engine as e

MODULES = (
    "test_transport_mixed_cargo_infill test_transport_adaptive_mixed_lane "
    "test_transport_adaptive_mixed_lane_benchmarks test_transport_front_to_back "
    "test_transport_mono_lane_transition test_transport_easycargo_preset "
    "test_transport_sequence_semantics test_space_evenly_stabilization "
    "test_space_evenly_residual_frontier_closure test_transport_max_quantity_solver "
    "test_transport_unit_integration test_transport_visualization "
    "test_transport_sequence_ui test_full_packaging_case"
).split()


def compact(container, products, result, elapsed):
    # Retain actual coordinates, identities, flags, sequence, weight and hashes.
    placements = [asdict(p) for p in result["placements"]]
    counts = Counter(p.row_index for p in result["placements"])
    counters = {k: v for k, v in result.items() if isinstance(v, (int, float, bool, str, type(None)))
                and ("candidate" in k or "mode" in k or "strategy" in k or "x_used" in k)}
    try:
        validation = r.physical(result, container, products)
    except (AssertionError, KeyError, ValueError) as exc:
        validation = {"valid": False, "error": str(exc)[:1200]}
    return dict(container=container, products=products, counts=dict(sorted(counts.items())),
                total=len(placements), placements=placements,
                signature_sha256=r.digest(placements), physical=validation,
                elapsed_seconds_engine=elapsed, counters=counters,
                support_beds={k: v for k, v in result.items() if k.endswith("_support_beds")})


def suite():
    from django.test.runner import DiscoverRunner
    current = {"test": None}
    actual_pack, actual_run = e.pack_container, unittest.TestCase.run
    seen = set()
    stats = Counter()
    statuses = []
    path = r.HERE / "protected-baseline.jsonl.gz"
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        def test_run(self, *args, **kwargs):
            previous = current["test"]
            current["test"] = self.id()
            try:
                return actual_run(self, *args, **kwargs)
            finally:
                current["test"] = previous

        @wraps(actual_pack)
        def recording_pack(container, products, *args, **kwargs):
            c, p = deepcopy(container), deepcopy(products)
            injected = isinstance(e._pack_container_blocks, Mock)
            started = time.perf_counter()
            result = actual_pack(container, products, *args, **kwargs)
            elapsed = time.perf_counter() - started
            stats["pack_calls"] += 1
            key = r.digest([current["test"], c, p, args, kwargs,
                            [asdict(v) for v in result["placements"]]])
            if key not in seen:
                seen.add(key)
                rec = compact(c, p, result, elapsed)
                rec.update(test=current["test"], input_and_output_key=key,
                           explicit_mock_injection=injected)
                stats["unique_records"] += 1
                stats["physical_valid" if rec["physical"]["valid"] else "physical_invalid"] += 1
                if not rec["physical"]["valid"]:
                    statuses.append({k: rec[k] for k in ("test", "explicit_mock_injection", "physical")})
                stream.write(json.dumps(rec, separators=(",", ":"), allow_nan=False) + "\n")
                stream.flush()
            return result

        class RecordingRunner(DiscoverRunner):
            def run_suite(self, test_suite, **kwargs):
                result = super().run_suite(test_suite, **kwargs)
                stats.update(tests_run=result.testsRun, failures=len(result.failures),
                             errors=len(result.errors), skipped=len(result.skipped))
                return result

        unittest.TestCase.run = test_run
        e.pack_container = recording_pack
        try:
            failed = RecordingRunner(verbosity=1, interactive=False).run_tests(
                ["packagingapp.tests." + module for module in MODULES])
        finally:
            e.pack_container = actual_pack
            unittest.TestCase.run = actual_run
    summary = {**stats, "validation_exceptions": statuses,
               "engine_sha256": r.hashlib.sha256(Path(e.__file__).read_bytes()).hexdigest()}
    (r.HERE / "protected-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return bool(failed)


def cohort():
    source = r.ROOT / "engine_development_notes/transport_container_selection/run_kollipack_br_benchmark.py"
    spec = importlib.util.spec_from_file_location("approved_br_runner", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    df = module.pd.read_csv(module.INPUT_FILE)
    stats = Counter()
    started_all = time.perf_counter()
    with gzip.open(r.HERE / "br700-baseline.jsonl.gz", "wt", encoding="utf-8") as stream:
        for case_id, case_rows in df.groupby("case_id", sort=False):
            c, p = module.make_container(case_rows), module.make_products(case_rows)
            for mode in module.MODES:
                started = time.perf_counter()
                result = e.pack_container(c, p, mode)
                rec = compact(c, p, result, time.perf_counter() - started)
                rec.update(case_id=case_id, mode=mode)
                stream.write(json.dumps(rec, separators=(",", ":"), allow_nan=False) + "\n")
                stream.flush()
                stats["runs"] += 1
                stats["valid" if rec["physical"]["valid"] else "invalid"] += 1
            stats["cases"] += 1
            if stats["cases"] % 25 == 0:
                print(dict(stats), flush=True)
    summary = {**stats, "elapsed_seconds_including_validation": time.perf_counter() - started_all,
               "engine_sha256": r.hashlib.sha256(Path(e.__file__).read_bytes()).hexdigest(),
               "input_sha256": r.hashlib.sha256(module.INPUT_FILE.read_bytes()).hexdigest(),
               "conversion": "Unmodified make_container/make_products, including archived R1/R3 swap"}
    (r.HERE / "br700-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    assert stats["cases"] == 700 and stats["runs"] == 2800
    return bool(stats["invalid"])


if __name__ == "__main__":
    approved = json.loads(gzip.decompress((r.HERE / "baseline.json.gz").read_bytes()))
    if r.hashlib.sha256(Path(e.__file__).read_bytes()).hexdigest() != approved["engine_sha256"]:
        raise SystemExit("Phase 1 evidence is immutable; use validate_implementation.py for the changed engine")
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("action", choices=("suite", "cohort"))
    args = parser.parse_args()
    raise SystemExit(suite() if args.action.endswith("suite") else cohort())
