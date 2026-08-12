"""Named public Transport Container examples used by KolliLabs articles."""

from copy import deepcopy


TRANSPORT_CONTAINER_CASE_PRESETS = {
    "tops-max-load-high-cube-benchmark": {
        "label": "TOPS Max Load High Cube Benchmark",
        "config": {
            "container_source": "manual",
            "container_l": 12039,
            "container_w": 2362,
            "container_h": 2692,
            "max_weight": "",
            "tare_weight": "",
            "packing_mode": "maximum_utilization_floor_first",
        },
        "rows": [
            {
                "name": "SKU302473",
                "length": 457.2,
                "width": 279.4,
                "height": 317.5,
                "qty": 375,
                "max_qty": False,
                "stackable": True,
                "weight": 0.2427,
                "sequence": 4,
                "r1": True,
                "r2": False,
                "r3": False,
            },
            {
                "name": "SKU503739",
                "length": 431.8,
                "width": 318.77,
                "height": 317.5,
                "qty": 405,
                "max_qty": False,
                "stackable": True,
                "weight": 0.907,
                "sequence": 3,
                "r1": True,
                "r2": False,
                "r3": False,
            },
            {
                "name": "Case Pack 12",
                "length": 558.8,
                "width": 377.444,
                "height": 317.5,
                "qty": 288,
                "max_qty": False,
                "stackable": True,
                "weight": 0.907,
                "sequence": 1,
                "r1": True,
                "r2": False,
                "r3": False,
            },
            {
                "name": "Case Pack",
                "length": 558.8,
                "width": 355.6,
                "height": 381.0,
                "qty": 160,
                "max_qty": False,
                "stackable": True,
                "weight": 2.268,
                "sequence": 2,
                "r1": True,
                "r2": False,
                "r3": False,
            },
        ],
    },
}


def get_transport_container_case_preset(slug):
    """Return an isolated preset payload for a public Transport demo."""
    preset = TRANSPORT_CONTAINER_CASE_PRESETS.get(str(slug or "").strip())
    return deepcopy(preset) if preset else None
