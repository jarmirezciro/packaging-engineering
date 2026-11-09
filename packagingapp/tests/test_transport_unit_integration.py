import json
from copy import deepcopy
from html.parser import HTMLParser
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from packagingapp.models import Product, ProductCatalogue, UserPreferences
from packagingapp.tools.transport.presenter import attach_transport_result_presentation
from packagingapp.tools.container.service import resolve_product_from_form
from packagingapp.tools.transport.service import (
    analyze_transport_config,
    analyze_transport_capacity,
    build_container_from_config,
    normalize_transport_rows_for_calculation,
    transport_rows_for_display,
    validate_transport_unit_state,
)
from packagingapp.utils.box_selection.box_selection_tool_arrays_2_origin_coordinates import (
    allowed_product_orientations,
)
from packagingapp.views.full_packaging import (
    PALLETIZATION_VISUAL_SOURCE,
    _apply_payload_to_config,
    _mark_incomplete_transport_weight,
    _transport_rows_from_selected,
)


def _transport_config(**overrides):
    config = {
        "container_source": "manual",
        "packing_mode": "space_evenly",
        "container_l": 2400,
        "container_w": 1200,
        "container_h": 1200,
        "max_weight": 1000,
        "tare_weight": 200,
        "load_unit_dimension_unit": "mm",
        "load_unit_mass_unit": "kg",
        "transport_dimension_unit": "mm",
        "transport_mass_unit": "kg",
    }
    config.update(overrides)
    return config


def _transport_rows(**overrides):
    row = {
        "name": "Pallet A",
        "length": 1200,
        "width": 800,
        "height": 1000,
        "qty": 2,
        "max_qty": False,
        "stackable": True,
        "weight": 100,
        "sequence": 1,
        "r1": False,
        "r2": False,
        "r3": True,
    }
    row.update(overrides)
    return [row]


def _geometry_signature(result):
    return [
        (
            placement.row_index,
            placement.x,
            placement.y,
            placement.z,
            placement.l,
            placement.w,
            placement.h,
        )
        for placement in result["result"]["placements"]
    ]


class TransportResultUnitPresentationTests(SimpleTestCase):
    @staticmethod
    def _result(**row_values):
        return {
            "summary": {
                "loaded_weight": 39.9660237207,
                "tare_weight": None,
                "gross_weight": 39.9660237207,
                "container_max_weight": None,
                "occupied_length": 400.04999999999995,
                "occupied_width": 1600.1999999999998,
                "occupied_height": 0,
                "residual_length": 0,
                "residual_width": 0,
                "residual_height": 0,
                "product_rows": [{
                    "name": "Precision row", "length": 400.04999999999995,
                    "width": 1600.1999999999998, "height": 0,
                    "weight_each": 39.9660237207, "qty_requested": 2,
                    "qty_packed": 1, "sequence": 1, "stackable": True,
                    **row_values,
                }],
            },
            "threejs_scene": {"products": [{"length": 400.04999999999995}]},
        }

    def test_metric_and_imperial_cells_use_fixed_two_decimals(self):
        for dimension, mass, expected in (
            ("mm", "kg", ("400.05", "1600.20", "0.00", "39.97")),
            ("in", "lb", ("15.75", "63.00", "0.00", "88.11")),
        ):
            with self.subTest(dimension=dimension, mass=mass):
                original = self._result()
                result = attach_transport_result_presentation(deepcopy(original), {
                    "load_unit_dimension_unit": dimension, "load_unit_mass_unit": mass,
                    "transport_dimension_unit": "ft", "transport_mass_unit": "lb",
                })
                row = result["summary"]["product_rows"][0]
                self.assertEqual(tuple(row["table_display"].values()), expected)
                for key, value in original["summary"].items():
                    if key != "product_rows":
                        self.assertEqual(result["summary"][key], value)
                for key, value in original["summary"]["product_rows"][0].items():
                    self.assertEqual(row[key], value)
                self.assertEqual(
                    result["threejs_scene"]["products"][0]["length"],
                    original["threejs_scene"]["products"][0]["length"],
                )
                # Reports and scene legends retain their existing compact precision.
                self.assertEqual(
                    row["weight_each_display"],
                    "39.966 kg" if mass == "kg" else "88.11 lb",
                )
                self.assertEqual(result["display"]["summary"]["loaded_weight"], "88.11 lb")
                self.assertEqual(
                    result["display"]["summary"]["occupied_dimensions"],
                    "1.31 × 5.25 × 0 ft",
                )
                json.dumps(result, allow_nan=False)

    def test_zero_missing_and_negative_zero_cells(self):
        for dimension, mass in (("mm", "kg"), ("in", "lb")):
            for value, expected in (
                (0, "0.00"), (-0.0, "0.00"), (-0.00001, "0.00"),
                (None, "—"), ("", "—"),
            ):
                with self.subTest(dimension=dimension, mass=mass, value=value):
                    result = attach_transport_result_presentation(self._result(
                        length=value, width=value, height=value, weight_each=value,
                    ), {"load_unit_dimension_unit": dimension, "load_unit_mass_unit": mass})
                    self.assertEqual(
                        set(result["summary"]["product_rows"][0]["table_display"].values()),
                        {expected},
                    )
                    self.assertEqual(result["display"]["summary"]["tare_weight"], "—")

    def test_both_table_contexts_render_matching_units_and_formatted_cells(self):
        for dimension, mass, expected in (
            ("mm", "kg", ("400.05", "1600.20", "0.00", "39.97")),
            ("in", "lb", ("15.75", "63.00", "0.00", "88.11")),
        ):
            result = attach_transport_result_presentation(self._result(), {
                "load_unit_dimension_unit": dimension, "load_unit_mass_unit": mass,
            })
            for workflow, first_step in ((False, True), (True, True), (True, False)):
                with self.subTest(dimension=dimension, workflow=workflow, first_step=first_step):
                    html = render_to_string("container_tool/partials/_transport_product_section.html", {
                        "result": result, "is_workflow": workflow, "is_first_step": first_step,
                    }).split("Per-item summary", 1)[1].split("</table>", 1)[0]
                    for axis in ("L", "W", "H"):
                        self.assertIn(f"<th>{axis} ({dimension})</th>", html)
                    self.assertIn(f"<th>Weight each ({mass})</th>", html)
                    for value in expected:
                        self.assertIn(f"<td>{value}</td>", html)
                    self.assertNotIn("400.049999", html)
                    self.assertNotIn("1600.199999", html)
                    self.assertNotIn("39.9660237207", html)

    def test_web_summary_preserves_incomplete_weight_status(self):
        step = {"result": attach_transport_result_presentation(self._result(), {})}
        _mark_incomplete_transport_weight(step, {"weight_status": "unknown"})
        result = step["result"]
        self.assertEqual(
            result["summary"]["product_rows"][0]["table_display"]["weight_each_display"],
            "Unavailable",
        )
        self.assertIn("Unavailable", result["display"]["summary"]["loaded_weight"])
        html = render_to_string("container_tool/partials/_transport_result_section.html", {"result": result})
        self.assertIn("Loaded product weight: Unavailable", html)
        self.assertIn("Tare weight: Not set", html)
        self.assertIn("Max payload: Not set", html)

    def test_presentation_does_not_change_engine_results_in_any_active_mode(self):
        for mode in ("space_evenly", "front_to_back", "space_evenly_infill", "front_to_back_infill"):
            with self.subTest(mode=mode):
                config = _transport_config(packing_mode=mode)
                rows = _transport_rows(length=400.04999999999995, weight=39.9660237207)
                with patch(
                    "packagingapp.tools.transport.service.attach_transport_result_presentation",
                    side_effect=lambda result, config: result,
                ):
                    baseline = analyze_transport_config(config, rows)
                presented = analyze_transport_config(config, rows)
                self.assertTrue(presented["ok"], presented["messages"])
                self.assertEqual(presented["products"], baseline["products"])
                self.assertEqual(presented["container"], baseline["container"])
                self.assertEqual(presented["result"], baseline["result"])
                self.assertEqual(_geometry_signature(presented), _geometry_signature(baseline))
                # The complete canonical serialization, including diagnostics, survives.
                serialized = deepcopy(presented["serialized_result"])
                serialized.pop("display")
                for row in serialized["summary"]["product_rows"]:
                    for key in ("table_display", "dimensions_display", "weight_each_display"):
                        row.pop(key)
                for product in serialized["threejs_scene"]["products"]:
                    product.pop("display_dimensions")
                self.assertEqual(serialized, baseline["serialized_result"])


class TransportManualUnitBoundaryTests(SimpleTestCase):
    def test_partial_support_beds_reach_shared_outputs_with_equivalent_units(self):
        from pathlib import Path
        from packagingapp.tests.test_transport_mixed_cargo_infill import mixed_support_orientation_case

        path = Path(__file__).resolve().parents[2] / "regressions/TC-REG-019-mixed-cargo-support-bed-orientation/input.json"
        fixture = json.loads(path.read_text())
        selected, normalized_rows = mixed_support_orientation_case()
        metric_config = _transport_config(
            packing_mode="front_to_back_infill", container_l=selected["L"],
            container_w=selected["W"], container_h=selected["H"], max_weight="", tare_weight="",
        )
        metric_rows = [
            {key: value for key, value in row.items()
             if key != "canonicalized" and not key.startswith("canonical_")}
            for row in normalized_rows
        ]
        metric = analyze_transport_config(metric_config, metric_rows)
        imperial = analyze_transport_config(fixture["config"], fixture["rows"])
        for analysis in (metric, imperial):
            self.assertTrue(analysis["ok"], analysis["messages"])
            self.assertGreater(len(analysis["result"]["placements"]), 53)
            self.assertEqual(len(analysis["threejs_scene"]["items"]), len(analysis["result"]["placements"]))
            self.assertEqual(analysis["serialized_result"]["summary"]["placed_units"], len(analysis["result"]["placements"]))
            self.assertFalse(analysis["serialized_result"]["summary"]["product_rows"][1]["stackable"])
            self.assertTrue(analysis["serialized_result"]["front_to_back_infill_partial_support_beds"]["selected"])
            json.dumps(analysis["serialized_result"], allow_nan=False)
            json.dumps(analysis["safe_rows"], allow_nan=False)
        self.assertEqual(
            [tuple(round(value, 7) for value in item) for item in _geometry_signature(metric)],
            [tuple(round(value, 7) for value in item) for item in _geometry_signature(imperial)],
        )

    def test_support_beds_reach_scene_report_and_json_with_equivalent_units(self):
        from packagingapp.tests.test_transport_mixed_cargo_infill import stackability_expv2_2

        selected, rows = stackability_expv2_2()
        for mode in ("front_to_back_infill", "space_evenly_infill"):
            config = _transport_config(
                packing_mode=mode, container_l=selected["L"],
                container_w=selected["W"], container_h=selected["H"],
                max_weight="", tare_weight="",
            )
            metric = analyze_transport_config(config, rows)
            imperial = analyze_transport_config(
                {**config, "container_l": selected["L"] / 25.4,
                 "container_w": selected["W"] / 25.4, "container_h": selected["H"] / 25.4,
                 "transport_dimension_unit": "in", "load_unit_dimension_unit": "in"},
                [{**row, **{key: row[key] / 25.4 for key in ("length", "width", "height")}}
                 for row in rows],
            )
            for analysis in (metric, imperial):
                self.assertTrue(analysis["ok"], analysis["messages"])
                self.assertEqual(len(analysis["result"]["placements"]), 133)
                self.assertEqual(len(analysis["threejs_scene"]["items"]), 133)
                self.assertEqual(analysis["serialized_result"]["summary"]["placed_units"], 133)
                self.assertTrue(analysis["serialized_result"][f"{mode}_support_beds"]["selected"])
                json.dumps(analysis["serialized_result"], allow_nan=False)
                json.dumps(analysis["safe_rows"], allow_nan=False)
            self.assertEqual(
                [tuple(round(v, 7) for v in item) for item in _geometry_signature(metric)],
                [tuple(round(v, 7) for v in item) for item in _geometry_signature(imperial)],
            )

    def test_equivalent_manual_units_keep_identical_engine_geometry(self):
        metric = analyze_transport_capacity(_transport_config(), _transport_rows())
        imperial = analyze_transport_capacity(
            _transport_config(
                container_l=2400 / 304.8,
                container_w=1200 / 304.8,
                container_h=1200 / 304.8,
                max_weight=1000 / 0.45359237,
                tare_weight=200 / 0.45359237,
                load_unit_dimension_unit="in",
                load_unit_mass_unit="lb",
                transport_dimension_unit="ft",
                transport_mass_unit="lb",
            ),
            _transport_rows(
                length=1200 / 25.4,
                width=800 / 25.4,
                height=1000 / 25.4,
                weight=100 / 0.45359237,
            ),
        )

        self.assertTrue(metric["ok"], metric["messages"])
        self.assertTrue(imperial["ok"], imperial["messages"])
        self.assertEqual(_geometry_signature(metric), _geometry_signature(imperial))
        self.assertEqual(
            metric["summary"]["utilization_volume_pct"],
            imperial["summary"]["utilization_volume_pct"],
        )
        self.assertAlmostEqual(imperial["container"]["L"], 2400.0)
        self.assertAlmostEqual(imperial["container"]["max_weight"], 1000.0)
        self.assertAlmostEqual(imperial["summary"]["loaded_weight"], 200.0)
        self.assertEqual(imperial["result"]["packing_mode"], "space_evenly")

    def test_invalid_explicit_unit_is_rejected_but_missing_metadata_is_metric(self):
        invalid = analyze_transport_capacity(
            _transport_config(load_unit_dimension_unit="yard"),
            _transport_rows(),
        )
        self.assertFalse(invalid["ok"])
        self.assertTrue(
            any(
                "Unsupported load-unit dimension unit" in message
                for message in invalid["messages"]
            )
        )

        legacy = _transport_config()
        for key in (
            "load_unit_dimension_unit",
            "load_unit_mass_unit",
            "transport_dimension_unit",
            "transport_mass_unit",
        ):
            legacy.pop(key)
        result = analyze_transport_capacity(legacy, _transport_rows())
        self.assertTrue(result["ok"], result["messages"])
        self.assertEqual(result["container"]["L"], 2400.0)
        self.assertEqual(result["products"][0]["weight"], 100.0)

    def test_catalogue_and_inherited_canonical_scalars_bypass_display_rounding(self):
        catalogue_row = _transport_rows(
            length="47.24",
            width="31.5",
            height="39.37",
            weight="220.46",
            physical_source="catalogue",
            canonical_length=1200,
            canonical_width=800,
            canonical_height=1000,
            canonical_weight=100,
        )
        result = analyze_transport_capacity(
            _transport_config(
                load_unit_dimension_unit="in",
                load_unit_mass_unit="lb",
            ),
            catalogue_row,
        )
        self.assertTrue(result["ok"], result["messages"])
        self.assertEqual(result["products"][0]["length"], 1200.0)
        self.assertEqual(result["products"][0]["weight"], 100.0)

        inherited = _transport_rows_from_selected(
            {
                "label": "Palletized load",
                "length": 1225.4,
                "width": 825.4,
                "height": 1350,
                "weight_kg": 997.903214,
            }
        )
        display = transport_rows_for_display(inherited, "in", "lb")[0]
        self.assertEqual(display["length"], "48.24")
        self.assertEqual(display["weight"], "2200.00")
        self.assertEqual(display["canonical_length"], 1225.4)
        self.assertEqual(display["canonical_weight"], 997.903214)

    def test_new_and_legacy_generated_pallets_keep_height_vertical(self):
        config = _transport_config(container_l=1200, container_w=800, container_h=1000)
        legacy_flags = {"transport_r1": True, "transport_r2": False, "transport_r3": False}
        for flags in ({}, legacy_flags):
            with self.subTest(flags=flags):
                rows = _transport_rows_from_selected({
                    "label": "Palletized load",
                    "length": 1200,
                    "width": 800,
                    "height": 1000,
                    "source_type": PALLETIZATION_VISUAL_SOURCE,
                    "source_step_type": "pallet",
                    "package_type": "pallet",
                    **flags,
                })
                result = analyze_transport_capacity(config, rows)
                self.assertTrue(result["ok"], result["messages"])
                self.assertEqual(
                    [(p.l, p.w, p.h) for p in result["result"]["placements"]],
                    [(1200, 800, 1000)],
                )

    def test_catalogue_transport_unit_remains_canonical_with_manual_units_selected(self):
        material = SimpleNamespace(
            part_length=12032,
            part_width=2352,
            part_height=2395,
            part_weight=2200,
            packaging_type="CONTAINER",
        )
        container, messages = build_container_from_config(
            _transport_config(
                container_source="catalogue",
                container_l=1,
                container_w=1,
                container_h=1,
                tare_weight=9999,
                transport_dimension_unit="ft",
                transport_mass_unit="lb",
            ),
            selected_material=material,
        )
        self.assertEqual(messages, [])
        self.assertEqual(container["L"], 12032.0)
        self.assertEqual(container["tare_weight"], 2200.0)


class FullPackagingUnitInheritanceTests(SimpleTestCase):
    def test_pallet_inheritance_adapts_canonical_payload_to_selected_display_units(self):
        config = {
            "box_dimension_unit": "in",
            "mass_unit": "lb",
        }
        adapted = _apply_payload_to_config(
            config,
            "pallet",
            {
                "length": 254,
                "width": 127,
                "height": 50.8,
                "weight_g": 453.59237,
            },
        )
        self.assertAlmostEqual(adapted["box_l"], 10.0)
        self.assertAlmostEqual(adapted["box_w"], 5.0)
        self.assertAlmostEqual(adapted["box_h"], 2.0)
        self.assertAlmostEqual(adapted["box_weight"], 1.0)


class TransportUnitSelectorSurfaceTests(TestCase):
    def test_all_stackable_r3_post_uses_same_supported_load_for_scene_report_and_flow(self):
        from pathlib import Path

        path = Path(__file__).resolve().parents[2] / (
            "regressions/TC-REG-019-mixed-cargo-support-bed-orientation/input.json"
        )
        fixture = json.loads(path.read_text())
        rows = [{**row, "stackable": True} for row in fixture["rows"]]
        config = fixture["config"]
        analysis = analyze_transport_config(config, rows)
        self.assertTrue(analysis["ok"], analysis["messages"])
        result = analysis["serialized_result"]
        scene = analysis["threejs_scene"]
        summary = result["summary"]
        self.assertEqual(summary["placed_units"], 127)
        self.assertEqual(len(scene["items"]), summary["placed_units"])
        self.assertEqual(scene["units"], "mm")
        self.assertAlmostEqual(scene["transport_unit"]["length"], 566.9 * 25.4)
        self.assertTrue(all(row["stackable"] for row in summary["product_rows"]))
        self.assertEqual([row["qty_packed"] for row in summary["product_rows"]], [30, 17, 16, 48, 14, 2, 0])
        arrays = {
            f"item_{key}[]": [str(int(row[key])) if isinstance(row[key], bool) else str(row[key])
                               for row in rows]
            for key in ("name", "length", "width", "height", "qty", "max_qty", "weight",
                        "sequence", "stackable", "r1", "r2", "r3")
        }
        post = {key: str(value) for key, value in config.items()}
        for url_name in ("container_tool", "transport_container_calculator"):
            with self.subTest(url_name=url_name):
                response = self.client.post(reverse(url_name), {**post, **arrays, "action": "run_analysis"})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context["result"]["summary"], summary)
                self.assertEqual(response.context["threejs_scene"], scene)
                self.assertTrue(all(row["stackable"] for row in response.context["product_rows"]))
                report = self.client.session["transport_container_last_export"]
                self.assertEqual(report["summary"], summary)
                self.assertEqual(report["product_legend"], scene["products"])
                json.dumps(report, allow_nan=False)

        workflow_url = reverse("full_packaging_mode")
        self.client.post(workflow_url, {"action": "add_step", "after_index": "start", "step_type": "transport"})
        response = self.client.post(workflow_url, {
            **{f"{key}_0": value for key, value in post.items()}, **arrays,
            "action": "run_step", "index": "0", "step_action_0": "run_analysis",
        })
        self.assertEqual(response.status_code, 302)
        step = self.client.session["full_packaging_mode_session"]["steps"][0]
        self.assertEqual(step["result"]["summary"], summary)
        self.assertEqual(step["threejs_scene"], scene)
        json.dumps(step, allow_nan=False)

    def test_standalone_and_public_transport_render_shared_selectors(self):
        for url_name in ("container_tool", "transport_container_calculator"):
            response = self.client.get(reverse(url_name))
            self.assertEqual(response.status_code, 200)
            self.assertContains(
                response, 'data-unit-group="transport-load-unit-dimensions"'
            )
            self.assertContains(
                response, 'data-unit-group="transport-container-mass"'
            )
            self.assertContains(response, 'name="load_unit_dimension_unit"')
            self.assertContains(response, "Metric tonnes (t)")
            self.assertContains(response, "Pounds (lb)")
            self.assertContains(response, "js/unit_selector.js")
            row = response.context["product_rows"][0]
            self.assertEqual(tuple(row[flag] for flag in ("r1", "r2", "r3")), (False, False, True))
            self.assertContains(response, 'title="R1: Original length vertical"')
            self.assertContains(response, 'title="R2: Original width vertical"')
            self.assertContains(response, 'title="R3: Original height vertical"')

    def test_catalogue_permissions_are_preserved_through_the_public_calculator(self):
        catalogue = ProductCatalogue.objects.create(name="Rotation permissions", is_public=True)
        url = reverse("transport_container_calculator")
        for index, expected in enumerate(((300, 500, 200), (200, 500, 300), (200, 300, 500)), 1):
            with self.subTest(flag=index):
                item = Product.objects.create(
                    catalogue=catalogue,
                    product_id=f"ROTATION-{index}",
                    product_name=f"R{index} only",
                    product_length=200,
                    product_width=300,
                    product_height=500,
                    desired_qty=1,
                    rotation_1=index == 1,
                    rotation_2=index == 2,
                    rotation_3=index == 3,
                )
                dimensions, *flags = resolve_product_from_form(None, "catalogue", item)
                self.assertIn(expected, [
                    row["dimensions"] for row in allowed_product_orientations(dimensions, *flags)
                ])
                selected = self.client.post(url, {
                    "action": "select_product",
                    "product_catalogue_id": catalogue.pk,
                    "product_id_to_fill": item.pk,
                    "selected_row_index": "0",
                })
                self.assertEqual(selected.status_code, 200)
                row = selected.context["product_rows"][0]
                self.assertEqual(tuple(row[f"r{i}"] for i in range(1, 4)), tuple(flags))
                for key in ("length", "width", "height", "weight"):
                    self.assertRegex(row[key], r"^\d+\.\d{2}$")
                    self.assertNotEqual(row[f"canonical_{key}"], "")
                self.assertEqual(
                    _TransportFormParser(selected.content.decode()).fields["item_length[]"][0],
                    "200.00",
                )

                config = _transport_config(**dict(zip(
                    ("container_l", "container_w", "container_h"), expected
                )))
                analysis = analyze_transport_capacity(config, [row])
                self.assertTrue(analysis["ok"], analysis["messages"])
                self.assertEqual(
                    [(p.l, p.w, p.h) for p in analysis["result"]["placements"]],
                    [expected],
                )
                response = self.client.post(url, {
                    **config,
                    "action": "run_analysis",
                    **{f"item_{field}[]": [str(row[field])] for field in (
                        "name", "length", "width", "height", "qty", "weight", "r1", "r2", "r3",
                    )},
                })
                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    [(p["dx"], p["dy"], p["dz"]) for p in response.context["threejs_scene"]["items"]],
                    [expected],
                )

    def test_workflow_keeps_prefixed_unit_state_and_canonical_scene(self):
        self.client.post(
            reverse("full_packaging_mode"),
            {
                "action": "add_step",
                "after_index": "start",
                "step_type": "transport",
            },
        )
        response = self.client.post(
            reverse("full_packaging_mode"),
            {
                "action": "run_step",
                "index": "0",
                "step_action_0": "run_analysis",
                "container_source_0": "manual",
                "packing_mode_0": "space_evenly",
                "container_l_0": str(2400 / 304.8),
                "container_w_0": str(1200 / 304.8),
                "container_h_0": str(1200 / 304.8),
                "max_weight_0": str(1000 / 0.45359237),
                "tare_weight_0": str(200 / 0.45359237),
                "load_unit_dimension_unit_0": "in",
                "load_unit_mass_unit_0": "lb",
                "transport_dimension_unit_0": "ft",
                "transport_mass_unit_0": "lb",
                "item_name[]": ["Pallet A"],
                "item_length[]": [str(1200 / 25.4)],
                "item_width[]": [str(800 / 25.4)],
                "item_height[]": [str(1000 / 25.4)],
                "item_qty[]": ["2"],
                "item_max_qty[]": ["0"],
                "item_stackable[]": ["1"],
                "item_weight[]": [str(100 / 0.45359237)],
                "item_sequence[]": ["1"],
                "item_r1[]": ["0"],
                "item_r2[]": ["0"],
                "item_r3[]": ["1"],
            },
        )
        self.assertEqual(response.status_code, 302)

        workflow = self.client.session["full_packaging_mode_session"]
        step = workflow["steps"][0]
        self.assertEqual(step["config"]["load_unit_dimension_unit"], "in")
        self.assertEqual(step["config"]["transport_mass_unit"], "lb")
        self.assertEqual(step["result"]["summary"]["placed_units"], 2)
        self.assertEqual(step["threejs_scene"]["units"], "mm")
        self.assertEqual(step["threejs_scene"]["transport_unit"]["length"], 2400.0)
        self.assertEqual(
            [item["dz"] for item in step["threejs_scene"]["items"]], [1000.0, 1000.0]
        )
        json.dumps(workflow)

        page = self.client.get(reverse("full_packaging_mode"))
        self.assertContains(page, 'name="load_unit_dimension_unit_0"')
        self.assertContains(
            page, 'data-unit-group="transport-load-unit-dimensions_0"'
        )
        self.assertRegex(
            page.content.decode(),
            r'name="load_unit_dimension_unit_0"[\s\S]*?value="in"',
        )
        for _ in range(2):
            refreshed = self.client.get(reverse("full_packaging_mode"))
            self.assertContains(refreshed, "<th>L (in)</th>", html=True)
            self.assertContains(refreshed, "<th>Weight each (lb)</th>", html=True)
            self.assertContains(refreshed, "<td>47.24</td>", html=True)
            self.assertContains(refreshed, "<td>220.46</td>", html=True)
            self.assertRegex(refreshed.content.decode(), r"Occupied L × W × H: [\d.]+ × [\d.]+ × [\d.]+ ft")

    def test_account_defaults_and_manual_overrides_survive_analysis_and_refresh(self):
        user = get_user_model().objects.create_user(username="transport-unit-defaults")
        preferences = UserPreferences.objects.create(
            user=user, default_length_unit="in", default_large_mass_unit="lb",
        )
        self.client.force_login(user)
        standalone_url = reverse("container_tool")
        initial = self.client.get(standalone_url)
        self.assertEqual(initial.context["transport_values"], {
            "load_unit_dimension_unit": "in", "load_unit_mass_unit": "lb",
            "transport_dimension_unit": "in", "transport_mass_unit": "lb",
        })
        self.client.post(reverse("full_packaging_mode"), {
            "action": "add_step", "after_index": "start", "step_type": "transport",
        })
        workflow = self.client.session["full_packaging_mode_session"]
        for key, value in initial.context["transport_values"].items():
            self.assertEqual(workflow["steps"][0]["config"][key], value)

        for dimension, mass, length, width, height, weight, expected_length, expected_weight in (
            ("mm", "kg", "400.04999999999995", "300", "200", "39.9660237207", "400.05", "39.97"),
            ("in", "lb", "15.75", "12", "8", "88.11", "15.75", "88.11"),
        ):
            with self.subTest(dimension=dimension, mass=mass):
                post = {
                    **_transport_config(load_unit_dimension_unit=dimension, load_unit_mass_unit=mass),
                    "action": "run_analysis", "item_name[]": ["Precision row"],
                    "item_length[]": [length], "item_width[]": [width], "item_height[]": [height],
                    "item_weight[]": [weight], "item_qty[]": ["2"], "item_sequence[]": ["1"],
                    "item_r1[]": ["0"], "item_r2[]": ["0"], "item_r3[]": ["1"],
                }
                # A browser refresh of the standalone POST resubmits the form.
                for _ in range(2):
                    response = self.client.post(standalone_url, post)
                    self.assertIsNotNone(response.context["result"], response.context["row_errors"])
                    self.assertContains(response, f"<th>L ({dimension})</th>", html=True)
                    self.assertContains(response, f"<th>Weight each ({mass})</th>", html=True)
                    self.assertContains(response, f"<td>{expected_length}</td>", html=True)
                    self.assertContains(response, f"<td>{expected_weight}</td>", html=True)
                    self.assertEqual(response.context["transport_values"]["load_unit_dimension_unit"], dimension)
                # The same choices survive Flow's redirect and repeated GET refreshes.
                flow_post = {f"{key}_0": value for key, value in post.items() if not key.endswith("[]") and key != "action"}
                flow_post.update({key: value for key, value in post.items() if key.endswith("[]")})
                flow_post.update(action="run_step", index="0", step_action_0="run_analysis")
                self.assertEqual(self.client.post(reverse("full_packaging_mode"), flow_post).status_code, 302)
                for _ in range(2):
                    response = self.client.get(reverse("full_packaging_mode"))
                    self.assertContains(response, f"<th>L ({dimension})</th>", html=True)
                    self.assertContains(response, f"<td>{expected_weight}</td>", html=True)
                json.dumps(self.client.session["full_packaging_mode_session"], allow_nan=False)
        preferences.refresh_from_db()
        self.assertEqual(preferences.default_length_unit, "in")
        self.assertEqual(preferences.default_large_mass_unit, "lb")

    def test_workflow_source_switch_preserves_manual_payload_constraint(self):
        self.client.post(
            reverse("full_packaging_mode"),
            {
                "action": "add_step",
                "after_index": "start",
                "step_type": "transport",
            },
        )
        response = self.client.post(
            reverse("full_packaging_mode"),
            {
                "action": "run_step",
                "index": "0",
                "step_action_0": "refresh",
                "container_source_0": "catalogue",
                "packing_mode_0": "space_evenly",
                "container_l_0": "1",
                "container_w_0": "1",
                "container_h_0": "1",
                "max_weight_0": str(1000 / 0.45359237),
                "tare_weight_0": "",
                "load_unit_dimension_unit_0": "mm",
                "load_unit_mass_unit_0": "kg",
                "transport_dimension_unit_0": "ft",
                "transport_mass_unit_0": "lb",
                "item_name[]": ["Pallet A"],
                "item_length[]": ["1200"],
                "item_width[]": ["800"],
                "item_height[]": ["1000"],
                "item_qty[]": ["1"],
                "item_max_qty[]": ["0"],
                "item_stackable[]": ["1"],
                "item_weight[]": ["100"],
                "item_sequence[]": ["1"],
                "item_r1[]": ["0"],
                "item_r2[]": ["0"],
                "item_r3[]": ["1"],
            },
        )
        self.assertEqual(response.status_code, 302)
        config = self.client.session["full_packaging_mode_session"]["steps"][0][
            "config"
        ]
        self.assertEqual(config["transport_dimension_unit"], "ft")
        self.assertEqual(config["transport_mass_unit"], "lb")
        self.assertAlmostEqual(config["max_weight"], 1000.0)


class TransportEditablePrecisionTests(SimpleTestCase):
    def test_inherited_rows_render_clean_values_and_exact_metadata_in_both_contexts(self):
        inherited = _transport_rows_from_selected({
            "label": "Exact upstream load", "length": 400.04999999999995,
            "width": 1600.1999999999998, "height": 1000.7599999999998,
            "weight_kg": 300.000000123,
        })
        for dimension, mass, expected in (
            ("mm", "kg", ["400.05", "1600.20", "1000.76", "300.00"]),
            ("in", "lb", ["15.75", "63.00", "39.40", "661.39"]),
        ):
            displayed = transport_rows_for_display(inherited, dimension, mass)
            for workflow in (False, True):
                with self.subTest(dimension=dimension, workflow=workflow):
                    html = render_to_string("container_tool/partials/_transport_product_section.html", {
                        "product_rows": displayed, "is_workflow": workflow, "is_first_step": False,
                    })
                    fields = _TransportFormParser(html).fields
                    for key, value in zip(("length", "width", "height", "weight"), expected):
                        self.assertEqual(fields[f"item_{key}[]"], [value])
                        self.assertEqual(
                            float(fields[f"item_canonical_{key}[]"][0]),
                            inherited[0][f"canonical_{key}"],
                        )

    def test_all_supported_units_preserve_canonical_values_for_every_row_source(self):
        canonical = {
            "length": 400.04999999999995, "width": 1600.1999999999998,
            "height": 1000.7599999999998, "weight": 300.000000123,
        }
        for source in ("manual", "catalogue", "inherited"):
            for dimension in ("mm", "cm", "m", "in", "ft"):
                for mass in ("g", "kg", "t", "oz", "lb"):
                    with self.subTest(source=source, dimension=dimension, mass=mass):
                        rows = _transport_rows(**canonical, physical_source=source, canonicalized=True)
                        original = deepcopy(rows)
                        displayed = transport_rows_for_display(rows, dimension, mass)
                        self.assertEqual(rows, original)
                        for key, value in canonical.items():
                            self.assertRegex(displayed[0][key], r"^\d+\.\d{2}$")
                            self.assertEqual(displayed[0][f"canonical_{key}"], value)
                        state, errors = validate_transport_unit_state(_transport_config(
                            load_unit_dimension_unit=dimension, load_unit_mass_unit=mass,
                        ))
                        self.assertEqual(errors, [])
                        normalized, errors = normalize_transport_rows_for_calculation(displayed, state)
                        self.assertEqual(errors, [])
                        for key, value in canonical.items():
                            self.assertEqual(normalized[0][key], value)
                        json.dumps(displayed, allow_nan=False)

    def test_rounded_manual_rows_rerun_with_identical_results_in_every_mode(self):
        for mode in ("space_evenly", "front_to_back", "space_evenly_infill", "front_to_back_infill"):
            with self.subTest(mode=mode):
                config = _transport_config(
                    packing_mode=mode, container_l=5000, container_w=2000,
                    load_unit_dimension_unit="in", load_unit_mass_unit="lb",
                )
                original = analyze_transport_config(config, _transport_rows(
                    length=15.749999999999998, width=62.99999999999999,
                    height=39.39999999999999, weight=661.3799999999999,
                ))
                self.assertTrue(original["ok"], original["messages"])
                rows = transport_rows_for_display(original["safe_rows"], "in", "lb")
                self.assertEqual([rows[0][key] for key in ("length", "width", "height", "weight")],
                                 ["15.75", "63.00", "39.40", "661.38"])
                for _ in range(3):
                    repeated = analyze_transport_config(config, rows)
                    self.assertTrue(repeated["ok"], repeated["messages"])
                    self.assertEqual(repeated["result"], original["result"])
                    self.assertEqual(repeated["serialized_result"], original["serialized_result"])
                    rows = transport_rows_for_display(repeated["safe_rows"], "in", "lb")

    def test_weight_only_edit_preserves_dimensions_and_blank_fields_remain_blank(self):
        rows = _transport_rows(
            length=400.04999999999995, width=300.0123456789,
            height=200.0987654321, weight=300.000000123, canonicalized=True,
        )
        display = transport_rows_for_display(rows, "in", "lb")
        display[0].update(weight="662.123456789", canonical_weight="")
        state, _ = validate_transport_unit_state(_transport_config(
            load_unit_dimension_unit="in", load_unit_mass_unit="lb",
        ))
        normalized, errors = normalize_transport_rows_for_calculation(display, state)
        self.assertEqual(errors, [])
        for key in ("length", "width", "height"):
            self.assertEqual(normalized[0][key], rows[0][key])
        self.assertAlmostEqual(normalized[0]["weight"], 662.123456789 * 0.45359237, places=12)
        blank = transport_rows_for_display(_transport_rows(length="", weight=""), "in", "lb")[0]
        self.assertEqual(blank["length"], "")
        self.assertEqual(blank["weight"], "")
        zero = transport_rows_for_display(_transport_rows(weight=-0.0), "mm", "kg")[0]
        self.assertEqual(zero["weight"], "0.00")
        self.assertEqual(zero["canonical_weight"], -0.0)


class _TransportFormParser(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.fields = {}
        self.template_depth = 0
        self.feed(html)

    def handle_starttag(self, tag, attributes):
        if tag == "template":
            self.template_depth += 1
        if tag != "input" or self.template_depth:
            return
        attrs = dict(attributes)
        name = attrs.get("name", "")
        if name.startswith("item_") and name.endswith("[]") and attrs.get("type") != "checkbox":
            self.fields.setdefault(name, []).append(attrs.get("value", ""))

    def handle_endtag(self, tag):
        if tag == "template":
            self.template_depth -= 1


class TransportEditablePrecisionSurfaceTests(TestCase):
    def test_standalone_and_flow_rerun_the_actual_rendered_form_without_precision_loss(self):
        for workflow in (False, True):
            with self.subTest(workflow=workflow):
                url = reverse("full_packaging_mode" if workflow else "container_tool")
                config = _transport_config(
                    container_l=5000, container_w=2000,
                    load_unit_dimension_unit="in", load_unit_mass_unit="lb",
                )
                if workflow:
                    self.client.post(url, {"action": "add_step", "after_index": "start", "step_type": "transport"})
                rows = {
                    "item_name[]": ["Exact manual row"], "item_length[]": ["15.749999999999998"],
                    "item_width[]": ["62.99999999999999"], "item_height[]": ["39.39999999999999"],
                    "item_weight[]": ["661.3799999999999"], "item_qty[]": ["2"],
                    "item_r1[]": ["0"], "item_r2[]": ["0"], "item_r3[]": ["1"],
                }
                previous = None
                for _ in range(3):
                    post = {f"{key}_0" if workflow else key: value for key, value in config.items()}
                    post.update(rows)
                    post.update({"action": "run_step", "index": "0", "step_action_0": "run_analysis"}
                                if workflow else {"action": "run_analysis"})
                    response = self.client.post(url, post, follow=workflow)
                    self.assertEqual(response.status_code, 200)
                    if workflow:
                        step = self.client.session["full_packaging_mode_session"]["steps"][0]
                        result = step["result"]
                        json.dumps(step, allow_nan=False)
                    else:
                        result = response.context["result"]
                    self.assertIsNotNone(result)
                    if previous is not None:
                        self.assertEqual(result, previous)
                    previous = deepcopy(result)
                    rows = _TransportFormParser(response.content.decode()).fields
                    for key, expected in (("length", "15.75"), ("width", "63.00"),
                                          ("height", "39.40"), ("weight", "661.38")):
                        self.assertEqual(rows[f"item_{key}[]"], [expected])
                        self.assertNotEqual(rows[f"item_canonical_{key}[]"], [""])
                    self.assertEqual(rows["item_qty[]"], ["2"])
                    self.assertEqual(rows["item_sequence[]"], ["1"])
                    self.assertContains(response, "<th>Weight each (lb)</th>", html=True)
