"""Shared Bag outputs for normal workflow calculations and capacity trials."""

from ...units import g_to_kg
from .dimensions import resolve_bag_outer_dimensions


def bag_design_outer_dimensions(candidate):
    flat = (
        candidate.get("flat_bag_length_mm", candidate["bag_length"]),
        candidate.get("flat_bag_width_mm", candidate["bag_width"]),
    )
    bundle = candidate.get("packed_bundle_mm") or tuple(
        candidate.get(f"bundle_{axis}") for axis in ("length", "width", "height")
    )
    legacy = (candidate["bag_length"], candidate["bag_width"], candidate.get("bundle_height"))
    return resolve_bag_outer_dimensions(flat, bundle, candidate, legacy=legacy)


def build_bag_design_pending_result(candidate, *, upstream=None, common=None):
    quantity = candidate["design_quantity"]
    payload = {
        "units_per_parent": quantity,
        "total_base_units": quantity,
        "mode": "design",
        "desired_quantity": candidate.get("desired_quantity", quantity),
        "design_quantity": quantity,
        "additional_capacity": candidate.get("additional_capacity", 0),
        "selected_candidate_id": candidate.get("candidate_id"),
        "selected_arrangement": candidate.get("arrangement"),
        "selected_orientation": candidate.get("product_orientation"),
        "render_data": candidate.get("render_data"),
        **(common or {}),
        **bag_design_outer_dimensions(candidate),
        "label": "Designed bag",
        "selected_arrangement_id": candidate.get("arrangement_id"),
        **({"insertion": candidate["insertion"]} if "insertion" in candidate else {}),
        **({"bag_assumptions": candidate["bag_assumptions"]} if "bag_assumptions" in candidate else {}),
        "metrics": {
            "cubicity": candidate.get("bundle_cubicity_score"),
            "bag_area": candidate.get("bag_area"),
            "bundle_volume": (
                float(candidate.get("bundle_length") or 0)
                * float(candidate.get("bundle_width") or 0)
                * float(candidate.get("bundle_height") or 0)
            ),
        },
    }
    return attach_bag_workflow_weight(payload, candidate, upstream=upstream)


def attach_bag_workflow_weight(payload, report, *, upstream=None):
    net = report.get("net_content_weight_g", report.get("net_content_weight"))
    tare = report.get("bag_tare_g")
    upstream_status = (upstream or {}).get("weight_status")
    incomplete = upstream_status in {"net_only", "unknown", "incomplete"}
    gross = net + tare if net is not None and tare is not None and not incomplete else None
    payload.update({
        **{key: value for key, value in report.items() if key.startswith(("film_", "bag_tare_"))},
        "net_content_weight_g": net,
        "gross_bag_weight_g": gross,
    })
    payload.pop("weight_g", None)
    payload.pop("weight_kg", None)
    if gross is not None:
        estimated = (report.get("bag_tare_source") or "").startswith("estimated_")
        payload["weight_status"] = "gross_estimated" if estimated or upstream_status == "gross_estimated" else "gross_known"
        payload["weight_g"] = gross
        payload["weight_kg"] = float(g_to_kg(gross))
    elif net is not None and not incomplete:
        payload["weight_status"] = "net_only"
        payload["weight_g"] = net
        payload["weight_kg"] = float(g_to_kg(net))
    else:
        payload["weight_status"] = "unknown"
    return payload
