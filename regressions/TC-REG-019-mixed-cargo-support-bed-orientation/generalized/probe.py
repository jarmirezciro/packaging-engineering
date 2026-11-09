"""Exercise the public supported portfolio through the parent engines."""
import sys
from time import perf_counter

from matrix import capture, inputs, r


trial_pack = r.e.pack_container


def reference():
    for key, container, rows, mode in inputs():
        if not key.endswith("/r3/front_to_back_infill"):
            continue
        start = perf_counter()
        result = trial_pack(container, rows, mode)
        rec = r.record(container, rows, result, diagnostics=False)
        print(key, rec["counts"], rec["total"], "B on A", rec["B_on_A"],
              "seconds", round(perf_counter() - start, 3), flush=True)
        search = result[mode + "_supported_constructions"]
        for trial in search["trials"]:
            print(" ", trial["policy"], trial["units_by_product"], trial["rejection_reason"],
                  trial["support_beds"]["candidates_evaluated"],
                  [(act["foundation_row_index"], act["upper_row_index"], act["units_by_product"],
                    act["middle_units_by_product"], round(act["x_end"] / 25.4, 1))
                   for act in trial["support_beds"]["actions"]], flush=True)


if __name__ == "__main__":
    if sys.argv[1:] == ["--assert-target"]:
        r.main()
    elif len(sys.argv) > 1:
        capture(trial_pack, sys.argv[1])
    else:
        reference()
