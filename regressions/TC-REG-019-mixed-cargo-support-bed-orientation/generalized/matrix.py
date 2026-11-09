"""Freeze the current four-mode rotation and stackability reference matrix."""
from copy import deepcopy
from dataclasses import asdict
from itertools import combinations, product
import gzip
import hashlib
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import reproduce as r


def inputs():
    fixture = json.loads((r.HERE / "input.json").read_text())
    for b, e in product((False, True), repeat=2):
        source = deepcopy(fixture)
        source["rows"][1]["stackable"] = b
        source["rows"][4]["stackable"] = e
        for n in range(1, 4):
            for flags in combinations(("r1", "r2", "r3"), n):
                container, rows = r.normalize(source, flags)
                for mode in ("front_to_back", "space_evenly", "front_to_back_infill", "space_evenly_infill"):
                    yield f"{int(b)}{int(e)}/{'-'.join(flags)}/{mode}", container, rows, mode


def capture(pack, output):
    records = {}
    for key, container, rows, mode in inputs():
        start = time.perf_counter()
        result = pack(container, rows, mode)
        elapsed = time.perf_counter() - start
        counts = [sum(p.row_index == i for p in result["placements"]) for i in range(len(rows))]
        records[key] = {
            "counts": counts, "signature": r.digest([asdict(p) for p in result["placements"]]),
            "elapsed": elapsed, "physical": r.physical(result, container, rows),
        }
        print(key, counts, round(elapsed, 3), flush=True)
    evidence = {"engine_sha256": hashlib.sha256(Path(r.e.__file__).read_bytes()).hexdigest(),
                "cases": records}
    Path(output).write_bytes(gzip.compress(json.dumps(evidence, allow_nan=False).encode(), mtime=0))


if __name__ == "__main__":
    capture(r.e.pack_container, sys.argv[1])
