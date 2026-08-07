from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from packagingapp.tools.palletization.height import DEFAULT_PALLET_HEIGHT_MM
from packagingapp.tools.palletization.presenter import build_pallet_pending_result
from packagingapp.tools.palletization.serializers import serialize_pallet_threejs_scene
from packagingapp.tools.palletization.service import (
    analyze_palletization_config,
    build_effective_palletization_config,
)
from packagingapp.tools.palletization.state import default_palletization_config
from packagingapp.utils.palletization.engine import Placement3D, run_palletization_analysis


class PalletHeightTests(SimpleTestCase):
    def _manual_config(self, **updates):
        config = default_palletization_config()
        config.update({
            "box_l": 400,
            "box_w": 400,
            "box_h": 200,
            "pallet_l": 1200,
            "pallet_w": 800,
            "max_stack_height": 1200,
        })
        config.update(updates)
        return config

    def _catalogue_pallet(self, height):
        return SimpleNamespace(
            external_length=1200,
            external_width=800,
            external_height=height,
            part_length=None,
            part_width=None,
            part_height=None,
        )

    def test_manual_blank_height_and_old_session_resolve_to_shared_default(self):
        built = build_effective_palletization_config(self._manual_config())

        self.assertTrue(built["ok"])
        self.assertEqual(DEFAULT_PALLET_HEIGHT_MM, 150.0)
        self.assertEqual(built["effective_config"]["pallet_height"], 150.0)

    def test_manual_entered_height_is_used(self):
        built = build_effective_palletization_config(
            self._manual_config(pallet_height="130")
        )

        self.assertTrue(built["ok"])
        self.assertEqual(built["effective_config"]["pallet_height"], 130.0)

    def test_catalogue_height_and_missing_catalogue_height(self):
        config = self._manual_config(pallet_source="catalogue")

        catalogue = build_effective_palletization_config(
            config,
            selected_pallet_material=self._catalogue_pallet(144),
        )
        missing = build_effective_palletization_config(
            config,
            selected_pallet_material=self._catalogue_pallet(None),
        )

        self.assertEqual(catalogue["effective_config"]["pallet_height"], 144.0)
        self.assertEqual(missing["effective_config"]["pallet_height"], 150.0)

    def test_engine_uses_total_height_to_calculate_carton_layers(self):
        rows = run_palletization_analysis(
            box_l=400,
            box_w=400,
            box_h=200,
            pallet_l=1200,
            pallet_w=800,
            pallet_height=150,
            max_stack_height=1200,
        )

        self.assertTrue(rows)
        self.assertEqual({row["layers"] for row in rows}, {5})
        self.assertEqual({row["used_height_mm"] for row in rows}, {1000})
        pending = build_pallet_pending_result(1200, 800, 150, rows[0])
        self.assertEqual(pending["height"], 1150.0)

    def test_serialized_result_exposes_finished_palletized_load_height(self):
        analysis = analyze_palletization_config(
            self._manual_config(pallet_height=150)
        )

        selected = analysis["serialized_result"]["selected_result"]
        self.assertEqual(selected["used_height_mm"], 1000.0)
        self.assertEqual(selected["pallet_height_mm"], 150.0)
        self.assertEqual(selected["total_height_mm"], 1150.0)

    def test_invalid_total_height_does_not_execute_engine(self):
        config = self._manual_config(pallet_height=150, max_stack_height=150)

        with patch("packagingapp.tools.palletization.service.run_palletization_analysis") as engine:
            result = analyze_palletization_config(config)

        self.assertFalse(result["ok"])
        self.assertIn("Max stack height must be greater than pallet height.", result["messages"])
        engine.assert_not_called()

    def test_scene_uses_resolved_height_for_pallet_and_carton_offset(self):
        placement = Placement3D(
            x=0,
            y=0,
            z=0,
            l=400,
            w=400,
            h=200,
            orientation="LxW",
            layer_kind="base",
            layer_index=0,
        )
        scene = serialize_pallet_threejs_scene(
            {"placements3d": [placement]},
            self._manual_config(pallet_height=130),
            {"layers": 1, "total_boxes": 1, "used_height_mm": 200},
        )

        self.assertEqual(scene["pallet"]["height"], 130.0)
        self.assertEqual(scene["placements"][0]["z"], 130.0)
        self.assertEqual(scene["metadata"]["total_render_height_mm"], 330.0)


class PalletGeometryFeasibilityTests(SimpleTestCase):
    def _run(self, **updates):
        inputs = {
            "box_l": 400,
            "box_w": 300,
            "box_h": 200,
            "pallet_l": 1200,
            "pallet_w": 800,
            "pallet_height": 150,
            "max_stack_height": 1200,
            "max_length_stickout": 0,
            "max_width_stickout": 0,
        }
        inputs.update(updates)
        return run_palletization_analysis(**inputs)

    def test_carton_taller_than_available_height_skips_pattern_generation(self):
        with patch(
            "packagingapp.utils.palletization.engine.get_base_and_interlock_layers",
            side_effect=AssertionError("patterns must not run"),
        ):
            rows = self._run(
                box_l=88,
                box_w=69,
                box_h=1216,
                pallet_l=1219,
                pallet_w=1016,
                pallet_height=141,
                max_stack_height=1346,
            )

        self.assertEqual(rows, [])

    def test_carton_footprint_that_fits_neither_orientation_skips_patterns(self):
        with patch(
            "packagingapp.utils.palletization.engine.get_base_and_interlock_layers",
            side_effect=AssertionError("patterns must not run"),
        ):
            rows = self._run(
                box_l=1100,
                box_w=900,
                pallet_l=1000,
                pallet_w=800,
            )

        self.assertEqual(rows, [])

    def test_rotated_footprint_orientation_remains_feasible(self):
        rows = self._run(
            box_l=1100,
            box_w=700,
            pallet_l=1000,
            pallet_w=1200,
            pallet_height=100,
            max_stack_height=500,
        )

        self.assertTrue(rows)
        self.assertEqual(rows[0]["total_boxes"], 2)
        self.assertEqual({row["layers"] for row in rows}, {2})

    def test_configured_overhang_is_included_in_footprint_feasibility(self):
        without_overhang = self._run(
            box_l=1100,
            box_w=700,
            pallet_l=1000,
            pallet_w=800,
            pallet_height=100,
            max_stack_height=500,
        )
        with_overhang = self._run(
            box_l=1100,
            box_w=700,
            pallet_l=1000,
            pallet_w=800,
            pallet_height=100,
            max_stack_height=500,
            max_length_stickout=200,
        )

        self.assertEqual(without_overhang, [])
        self.assertTrue(with_overhang)
        self.assertEqual(with_overhang[0]["total_boxes"], 2)

    def test_exact_height_boundary_and_known_standard_capacity_are_preserved(self):
        exact_height = self._run(box_h=1050)
        standard = self._run()

        self.assertTrue(exact_height)
        self.assertEqual(exact_height[0]["total_boxes"], 8)
        self.assertEqual({row["layers"] for row in exact_height}, {1})
        self.assertEqual(standard[0]["total_boxes"], 40)
        self.assertEqual({row["layers"] for row in standard}, {5})
