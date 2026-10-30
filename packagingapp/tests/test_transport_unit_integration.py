import json
from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from packagingapp.tools.transport.service import (
    analyze_transport_capacity,
    build_container_from_config,
    transport_rows_for_display,
)
from packagingapp.views.full_packaging import (
    _apply_payload_to_config,
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
        "r1": True,
        "r2": False,
        "r3": False,
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


class TransportManualUnitBoundaryTests(SimpleTestCase):
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
        self.assertAlmostEqual(display["length"], 1225.4 / 25.4)
        self.assertAlmostEqual(display["weight"], 997.903214 / 0.45359237)
        self.assertEqual(display["canonical_length"], 1225.4)
        self.assertEqual(display["canonical_weight"], 997.903214)

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
                "item_r1[]": ["1"],
                "item_r2[]": ["0"],
                "item_r3[]": ["0"],
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
                "item_r1[]": ["1"],
                "item_r2[]": ["0"],
                "item_r3[]": ["0"],
            },
        )
        self.assertEqual(response.status_code, 302)
        config = self.client.session["full_packaging_mode_session"]["steps"][0][
            "config"
        ]
        self.assertEqual(config["transport_dimension_unit"], "ft")
        self.assertEqual(config["transport_mass_unit"], "lb")
        self.assertAlmostEqual(config["max_weight"], 1000.0)
