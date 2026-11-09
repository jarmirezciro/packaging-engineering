"""Read-only reproduction of the owner's subsequent all-stackable screenshots.

Uses the actual transport service, actual engine, independent physical checks,
and a separately labelled feasibility certificate. Never changes packing rules.
"""
from copy import deepcopy
from dataclasses import asdict, replace
import gzip
import hashlib
import json
from pathlib import Path

import reproduce as r
from packagingapp.tools.transport.service import analyze_transport_capacity


def main():
    fixture = json.loads((r.HERE / "input.json").read_text())
    cases = {}
    for b, e in ((False, False), (True, False), (False, True), (True, True)):
        source = deepcopy(fixture)
        for row in source["rows"]:
            row["stackable"] = True
        source["rows"][1]["stackable"] = b
        source["rows"][4]["stackable"] = e
        analysis = analyze_transport_capacity(source["config"], source["rows"])
        assert analysis["ok"], analysis.get("messages")
        container, products = analysis["container"], analysis["products"]
        result = r.e.pack_container(container, products, r.MODE)
        assert r.digest([asdict(p) for p in result["placements"]]) == r.digest(
            [asdict(p) for p in analysis["result"]["placements"]])
        record = r.record(container, products, result)
        record["checkbox_parser_evidence"] = r.checkbox_evidence(source)
        cases[f"B={b},E={e}"] = record
        print(b, e, record["counts"], record["total"], "B on A", record["B_on_A"])

    screenshot = cases["B=True,E=True"]
    assert screenshot["counts"] == [30, 17, 16, 4, 14, 2, 0]
    assert screenshot["B_on_A"] == 0
    assert not any(key.endswith("support_beds") for key in screenshot["diagnostics"])
    assert screenshot["checkbox_parser_evidence"]["parsed_stackable"] == [True] * 7

    # Explicit physical certificate: reuse geometry found under the stricter
    # B=false input, then restore the screenshot's B=true flag. Allowing that
    # cargo to support others does not invalidate its supported placements.
    stricter = cases["B=False,E=True"]
    units = [r.e.Placement(**p) for p in stricter["placements"]]
    units = [replace(p, stackable=True) if p.row_index == 1 else p for p in units]
    certificate = r.record(screenshot["container"], screenshot["products"],
                           r.explicit_result(units, screenshot["products"]), diagnostics=False)
    assert certificate["total"] == 123 and certificate["B_on_A"] == 15
    assert all(a >= b for a, b in zip(certificate["counts"], screenshot["counts"]))
    output = {
        "engine_sha256": hashlib.sha256(Path(r.e.__file__).read_bytes()).hexdigest(),
        "provenance": "Owner's two screenshots: all seven stackability boxes checked, R3 only, A/B/C sequence 1; original POST unavailable. Synthetic checkbox parser evidence and service result agree with displayed counts.",
        "comparisons": cases,
        "all_stackable_certificate": certificate,
        "certificate_status": "Independently validated geometry for the all-stackable inputs, not selected by the engine for those inputs",
    }
    (r.HERE / "stackable-screenshot-evidence.json.gz").write_bytes(gzip.compress(
        json.dumps(output, separators=(",", ":"), allow_nan=False, default=asdict).encode(), mtime=0))
    print("Independent all-stackable certificate", certificate["counts"], certificate["total"],
          "B on A", certificate["B_on_A"], "no row loss", True)


if __name__ == "__main__":
    main()
