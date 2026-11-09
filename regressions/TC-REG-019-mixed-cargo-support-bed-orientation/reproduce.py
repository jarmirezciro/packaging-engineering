"""Read-only TC-REG-019 diagnostics; no packing rules or candidate injection.

Run from the repository root with .venv/Scripts/python.exe <this file>.
Use --assert-target to check the approved 123-unit threshold and synthetic witnesses.
"""
import argparse
import ast
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
import hashlib
import gzip
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "packagingproject.settings")
import django
django.setup()

from packagingapp.tools.transport.service import (
    build_container_from_config, normalize_transport_rows_for_calculation,
    read_product_rows_raw, validate_transport_rows, validate_transport_unit_state,
)
from packagingapp.tests.transport_physical_validator import (
    assert_transport_result_physical, _subtract_rectangle,
)
from packagingapp.utils.container_tool import engine as e
from django.http import QueryDict

MODE = "front_to_back_infill"
CHECK = unittest.TestCase()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def normalize(fixture, flags):
    cfg = fixture["config"]
    units, errors = validate_transport_unit_state(cfg)
    assert not errors, errors
    container, errors = build_container_from_config(cfg, unit_state=units)
    assert not errors, errors
    rows = [{**r, **{key: key in flags for key in ("r1", "r2", "r3")}}
            for r in fixture["rows"]]
    rows, errors = normalize_transport_rows_for_calculation(rows, units)
    assert not errors, errors
    rows, errors = validate_transport_rows(rows)
    assert not errors, errors
    return container, rows


def physical(result, container, rows):
    checks = assert_transport_result_physical(CHECK, result, container, rows)
    for p in result["placements"]:
        CHECK.assertEqual(p.stackable, rows[p.row_index]["stackable"])
        CHECK.assertEqual(p.product_name, rows[p.row_index]["name"])
        CHECK.assertAlmostEqual(p.weight, rows[p.row_index]["weight"])
    return {"valid": True, **checks}


def fully_supported_by(p, supports):
    uncovered = [(p.x, p.y, p.l, p.w)]
    for s in supports:
        if not s.stackable or abs(s.z + s.h - p.z) > e.TOLERANCE:
            continue
        uncovered = [piece for rect in uncovered
                     for piece in _subtract_rectangle(rect, (s.x, s.y, s.l, s.w))
                     if piece[2] > e.TOLERANCE and piece[3] > e.TOLERANCE]
    return not uncovered and p.z > e.TOLERANCE


def record(container, rows, result, elapsed=None, diagnostics=True):
    placements = [asdict(p) for p in result["placements"]]
    counts = Counter(p.row_index for p in result["placements"])
    output = {
        "container": container, "products": rows,
        "counts": [counts[i] for i in range(len(rows))],
        "total": len(placements), "placements": placements,
        "signature_sha256": digest(placements),
        "physical": physical(result, container, rows),
        "elapsed_seconds_untraced": elapsed,
    }
    if len(rows) == 7:
        b = [p for p in result["placements"] if p.row_index == 1]
        a = [p for p in result["placements"] if p.row_index == 0]
        output["B_on_A"] = sum(fully_supported_by(p, a) for p in b)
        output["B_floor"] = sum(p.z <= e.TOLERANCE for p in b)
    if diagnostics:
        output["diagnostics"] = {k: v for k, v in result.items()
                                  if k not in {"placements", "unplaced"}}
        output["unplaced"] = result["unplaced"]
    return output


def trace_beds(container, rows):
    """Observe executed guards in the actual function without changing it."""
    source, start = inspect.getsourcelines(e._choose_support_bed)
    tree = ast.parse("".join(source))
    guards = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            for child in node.body:
                if isinstance(child, ast.Continue):
                    guards[start + child.lineno - 1] = ast.unparse(node.test)
    layer_line = next(start + i for i, line in enumerate(source)
                      if "for layers in _bounded_adaptive_lane_counts(max_layers)" in line)
    calls = []

    def local(frame, event, arg):
        values = frame.f_locals
        entry = calls[-1]
        if event == "line" and frame.f_lineno in guards:
            key = guards[frame.f_lineno]
            entry["executed_rejection_guards"][key] += 1
        elif event == "line" and frame.f_lineno == layer_line and values["max_layers"] <= 0:
            entry["zero_layer_constructions"].append({
                "foundation": values["foundation"].name,
                "cap_orientation": values["cap_orientation"],
                "cap_lanes": values["cap_lanes"],
                "foundation_orientation": values["orientation"],
                "foundation_columns_required": values["nx"] * values["ny"],
                "foundation_available": values["remaining"][values["foundation"].row_index],
                "height_layers_available": e._fit_count(values["container"]["H"] - values["cap_height"], values["height"]),
            })
        elif event == "return":
            selected, evaluated = arg
            entry["evaluated_compounds"] = evaluated
            entry["selected_compound"] = ({k: v for k, v in selected.items()
                                            if k != "placements"} if selected else None)
        return local

    def global_trace(frame, event, arg):
        if event == "call" and frame.f_code is e._choose_support_bed.__code__:
            values = frame.f_locals
            calls.append({
                "anchor": values["anchor"].name,
                "upper_remaining": values["remaining"].get(values["anchor"].row_index),
                "x_start": values["x_start"],
                "active_later_products": [p.name for p in values["products"]],
                "remaining": dict(values["remaining"]),
                "executed_rejection_guards": Counter(),
                "zero_layer_constructions": [],
            })
            return local
        return None

    old = sys.gettrace()
    try:
        sys.settrace(global_trace)
        result = e.pack_container(container, rows, MODE)
    finally:
        sys.settrace(old)
    return calls, result


def explicit_result(placements, rows, mode=MODE):
    counts = Counter(p.row_index for p in placements)
    return {"placements": placements, "loaded_weight": sum(p.weight for p in placements),
            "packing_mode": mode,
            "unplaced": [{"row_index": i} for i, r in enumerate(rows)
                         for _ in range(r["qty"] - counts[i])]}


def unit(rows, row, item, x, y, z, dims):
    r = rows[row]
    return e.Placement(r["name"], item, row, r["sequence"], r["weight"],
                       r["stackable"], x, y, z, *dims)


def reference_witness(container, rows):
    """The task's explicit 5-A/2-B witness, not an optimization algorithm."""
    scale = 25.4
    placements = [unit(rows, 0, i, i * 15.7 * scale, 0, 0,
                       tuple(d * scale for d in (15.7, 55.1, 63))) for i in range(5)]
    placements += [unit(rows, 1, i, 0, i * 23.6 * scale, 63 * scale,
                        tuple(d * scale for d in (63, 23.6, 39.4))) for i in range(2)]
    return record(container, rows, explicit_result(placements, rows))


def full_reference_witness(container, rows):
    """Explicit 123-unit R3 certificate, not a proposed engine construction.

    A30 bed, documented 4+11 B roof pattern, B2 floor, C16, D48,
    E4 on D, then F4/G4. Coordinates below are in inches before conversion.
    """
    units = []
    def add(row, x, y, z, dims):
        item = sum(p.row_index == row for p in units)
        units.append(unit(rows, row, item, x * 25.4, y * 25.4, z * 25.4,
                          tuple(d * 25.4 for d in dims)))
    for x in range(5):
        for y in range(6):
            add(0, x * 55.1, y * 15.7, 0, (55.1, 15.7, 63))
    for x in range(4):
        add(1, x * 63, 0, 63, (63, 23.6, 39.4))
    for x in range(11):
        add(1, x * 23.6, 23.6, 63, (23.6, 63, 39.4))
    for x in range(2):
        add(1, 275.5 + x * 23.6, 0, 0, (23.6, 63, 39.4))
    for x in range(2):
        for y in range(4):
            for z in range(2):
                add(2, 322.7 + x * 17.7, y * 23.6, z * 51.2, (17.7, 23.6, 51.2))
    for x in range(5):
        for y in range(2):
            for z in range(5 if x < 4 else 4):
                add(3, 358.1 + x * 31.5, y * 47.2, z * 15.7, (31.5, 47.2, 15.7))
    for x in range(2):
        for y in range(2):
            add(4, 358.1 + x * 47.2, y * 47.2, 78.5, (47.2, 47.2, 21.7))
    for z in range(4):
        for y in range(2):
            add(5 if z < 2 else 6, 515.6, y * 47.2, z * 21.7, (47.2, 47.2, 21.7))
    return record(container, rows, explicit_result(units, rows), diagnostics=False)


def checkbox_evidence(fixture):
    post = QueryDict("", mutable=True)
    mapping = {"name": "item_name[]", "length": "item_length[]",
               "width": "item_width[]", "height": "item_height[]", "qty": "item_qty[]",
               "weight": "item_weight[]", "sequence": "item_sequence[]",
               "stackable": "item_stackable[]", "r1": "item_r1[]",
               "r2": "item_r2[]", "r3": "item_r3[]"}
    for key, field in mapping.items():
        post.setlist(field, [str(int(r[key])) if isinstance(r[key], bool) else str(r[key])
                             for r in fixture["rows"]])
    raw = read_product_rows_raw(post)
    return {"source": "Synthetic POST of the supplied task values; original POST unavailable",
            "posted_stackable": post.getlist("item_stackable[]"),
            "parsed_stackable": [r["stackable"] for r in raw]}


def product(name, dims, qty, stackable=True, sequence=1, flags=("r3",)):
    return dict(name=name, length=dims[0], width=dims[1], height=dims[2], qty=qty,
                weight=1, stackable=stackable, sequence=sequence,
                **{key: key in flags for key in ("r1", "r2", "r3")})


def general_cases():
    cases = []
    # Hand-built, independent configurations. Physical lower/upper dimensions
    # stay equivalent in the three orientation-family experiments.
    for family, lower, upper in (
        ("r3", (20, 30, 20), (35, 30, 10)),
        ("r1", (20, 20, 30), (10, 35, 30)),
        ("r2", (20, 20, 30), (35, 10, 30)),
    ):
        rows = [product("Lower", lower, 8, flags=(family,)),
                product("Upper", upper, 5, False, flags=(family,))]
        cases.append((f"partial-{family}", {"L": 100, "W": 40, "H": 40}, rows, True))
    base_c, base_r = deepcopy(cases[0][1:3])
    for name, changes in (
        ("complete-upper", {"upper_qty": 1}),
        ("two-upper", {"upper_qty": 2}),
        ("three-upper", {"upper_qty": 3}),
        ("seven-upper", {"upper_qty": 7}),
        ("short-foundation", {"lower_qty": 1}),
        ("height-shortage", {"H": 29}),
        ("height-exact", {"H": 30}),
        ("different-sequence", {"lower_sequence": 2}),
        ("payload-shortage", {"max_weight": 3}),
        ("payload-sufficient", {"max_weight": 5}),
        ("multiple-foundations", {"another": True}),
    ):
        c, r = deepcopy(base_c), deepcopy(base_r)
        for key in ("H", "max_weight"):
            if key in changes:
                c[key] = changes[key]
        r[0]["qty"] = changes.get("lower_qty", r[0]["qty"])
        r[1]["qty"] = changes.get("upper_qty", r[1]["qty"])
        r[0]["sequence"] = changes.get("lower_sequence", 1)
        if changes.get("another"):
            r.append(product("Other lower", (19, 29, 18), 3))
        witness = name in {"height-exact", "payload-sufficient", "multiple-foundations",
                           "three-upper", "seven-upper"}
        cases.append((name, c, r, witness))
    cases.append(("unrelated-aspect-ratio", {"L": 72, "W": 27, "H": 34},
                  [product("Lower", (14, 22, 15), 7),
                   product("Upper", (25, 22, 9), 5, False)], True))
    return cases


def general_witness(c, rows):
    # Explicit short bed plus two floor caps. No search or engine candidate.
    if c["L"] == 72:
        lower, upper = (14, 22, 15), (25, 22, 9)
    else:
        lower, upper = (20, 30, 20), (35, 30, 10)
    end = 2 * lower[0]
    placements = [unit(rows, 0, i, i * lower[0], 0, 0, lower) for i in range(2)]
    placements += [unit(rows, 1, 0, 0, 0, lower[2], upper)]
    placements += [unit(rows, 1, i + 1, end + i * upper[1], 0, 0,
                        (upper[1], upper[0], upper[2])) for i in range(2)]
    return explicit_result(placements, rows)


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--assert-target", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    fixture = json.loads((HERE / "input.json").read_text())
    output = {
        "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "engine_sha256": hashlib.sha256(Path(e.__file__).read_bytes()).hexdigest(),
        "fixture_sha256": digest(fixture), "checkbox_evidence": checkbox_evidence(fixture),
        "reference": {}, "generalization": {},
    }
    for flags in fixture["rotation_configurations"]:
        c, r = normalize(fixture, flags)
        started = time.perf_counter()
        result = e.pack_container(c, r, MODE)
        elapsed = time.perf_counter() - started
        rec = record(c, r, result, elapsed)
        trace, repeated = trace_beds(c, r)
        CHECK.assertEqual(rec["signature_sha256"], digest([asdict(p) for p in repeated["placements"]]))
        rec["support_bed_trace"] = trace
        ordinary = e._pack_container_blocks(c, r, MODE)
        trial = e._pack_container_blocks(c, r, MODE, enable_support_beds=True)
        rec["ordinary"] = record(c, r, ordinary, diagnostics=False)
        rec["support_trial"] = record(c, r, trial)
        rec["final_roof_clear_supported_rectangles"] = [asdict(s) for s in
            e.derive_local_top_residuals(result["placements"], c, 0, c["L"])]
        output["reference"]["+".join(flags)] = rec
        print("reference", "+".join(flags), rec["counts"], rec["total"], "B/A", rec["B_on_A"], flush=True)
    c, r = normalize(fixture, ["r3"])
    output["local_5A_2B_witness"] = reference_witness(c, r)
    output["full_R3_witness"] = full_reference_witness(c, r)
    current = output["reference"]["r3"]
    certificate = output["full_R3_witness"]
    approved = json.loads(gzip.decompress((HERE / "baseline.json.gz").read_bytes()))
    # Preserve the original defect certificate; a better engine outcome can
    # legitimately exceed this particular witness in an individual row.
    original = approved["reference"]["r3"]
    CHECK.assertGreater(certificate["total"], original["total"])
    CHECK.assertTrue(all(a >= b for a, b in zip(certificate["counts"], original["counts"])))
    for flags, rec in output["reference"].items():
        CHECK.assertTrue(all(a >= b for a, b in zip(rec["counts"], approved["reference"][flags]["counts"])))
    output["full_witness_dominates_current"] = (
        certificate["total"] > current["total"]
        and all(a >= b for a, b in zip(certificate["counts"], current["counts"]))
    )
    unresolved = []
    for name, c, r, witness in general_cases():
        started = time.perf_counter()
        result = e.pack_container(c, r, MODE)
        rec = record(c, r, result, time.perf_counter() - started)
        trace, repeated = trace_beds(c, r)
        CHECK.assertEqual(rec["signature_sha256"], digest([asdict(p) for p in repeated["placements"]]))
        rec["support_bed_trace"] = trace
        if witness:
            cert = record(c, r, general_witness(c, r), diagnostics=False)
            rec["independent_witness"] = cert
            better = cert["total"] > rec["total"] and all(a >= b for a, b in zip(cert["counts"], rec["counts"]))
            rec["witness_dominates_current"] = better
            if better:
                unresolved.append(name)
        output["generalization"][name] = rec
        print("generalization", name, rec["counts"], rec.get("witness_dominates_current"), flush=True)
    output["unresolved_dominating_witnesses"] = unresolved
    _, projection_container, projection_rows, _ = general_cases()[0]
    projection_products = e.sort_products(e.normalize_products(projection_rows), projection_container)
    output["projection_counterexample"] = {
        "case": "partial-r3", "ordinary_depth": e._support_bed_tail_depth(
            projection_products, {0: 8, 1: 5}, projection_container),
        "useful_two_lower_one_upper_depth": 40 + e._support_bed_tail_depth(
            projection_products, {0: 6, 1: 4}, projection_container),
        "four_lower_two_upper_depth": 80 + e._support_bed_tail_depth(
            projection_products, {0: 4, 1: 3}, projection_container),
        "note": "Read-only calls to the current projection helper; no packing candidate injection or alternate continuation implemented",
    }
    assert output["checkbox_evidence"]["parsed_stackable"] == [True, False, True, True, False, True, True]
    if args.output:
        if (args.output.resolve() == (HERE / "baseline.json.gz").resolve()
                and output["engine_sha256"] != approved["engine_sha256"]):
            raise ValueError("Refusing to overwrite approved Phase 1 evidence; use implementation/results.json.gz")
        encoded = json.dumps(output, separators=(",", ":"), allow_nan=False, default=asdict).encode()
        args.output.write_bytes(gzip.compress(encoded, mtime=0) if args.output.suffix == ".gz" else encoded)
    if args.assert_target:
        CHECK.assertGreaterEqual(current["total"], certificate["total"],
                                 f"UNRESOLVED {fixture['id']}: R3 physical witness loads 123 (no row loss against approved 53-unit baseline) vs current {current['total']}; synthetic misses: {unresolved}")
        assert not unresolved, f"UNRESOLVED {fixture['id']}: physical no-row-loss witnesses beat current results: {unresolved}"


if __name__ == "__main__":
    main()
