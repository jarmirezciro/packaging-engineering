"""Alternate compatibility and supported-construction timings in one process."""
from statistics import median
from time import perf_counter

from probe import inputs, r, trial_pack


def elapsed(pack, container, rows, mode):
    started = perf_counter()
    pack(container, rows, mode)
    return perf_counter() - started


for key, container, rows, mode in inputs():
    if not key.endswith("/r3/front_to_back_infill") and not (
        key.startswith("11/") and key.split("/")[1] == "r1-r2-r3"
    ):
        continue
    packs = [r.e._pack_container_compatible, trial_pack]
    samples = [[], []]
    for pack in packs:
        elapsed(pack, container, rows, mode)
    for iteration in range(6):
        for i in (range(2) if iteration % 2 == 0 else reversed(range(2))):
            samples[i].append(elapsed(packs[i], container, rows, mode))
    print(key, "median ms", [round(1000 * median(values), 1) for values in samples], flush=True)
