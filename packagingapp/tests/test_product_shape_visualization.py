import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase

from packagingapp.forms import BagSelectionForm, ContainerSelectionMode1Form
from packagingapp.tools.bag.serializers import sanitize_bag_config_for_session
from packagingapp.tools.bag.service import analyze_bag_config
from packagingapp.tools.bag.state import default_bag_config
from packagingapp.tools.container.serializers import (
    sanitize_container_config_for_session,
)
from packagingapp.tools.container.service import analyze_container_form
from packagingapp.tools.container.state import default_container_config
from packagingapp.tools.product_shape import (
    ORIENTATION_AXIS_ORDERS,
    PRODUCT_SHAPE_CHOICES,
    build_product_unit_scene,
    decorate_product_scene,
    normalize_product_shape,
    orientation_index_from_axis_order,
    orientation_index_from_dimensions,
)
from packagingapp.utils.bag_selection.engine import (
    build_bag_design_candidates,
    compute_max_quantity_for_bag,
    run_bag_mode1_and_render,
)
from packagingapp.utils.box_selection.box_selection_tool_arrays_2_origin_coordinates import (
    allowed_product_orientations,
)
from packagingapp.utils.box_selection.engine import (
    build_container_design_candidates,
    run_mode1_and_render,
)
from packagingapp.views.bag_selection import (
    _build_shared_bag_ui_contract,
    _read_raw_bag_config,
)
from packagingapp.views.container_selection import (
    _build_single_export_payload,
    _build_shared_container_ui_contract,
    _read_raw_container_config,
)
from packagingapp.views.full_packaging import (
    _new_bag_step,
    _new_container_step,
    _prepare_bag_step_view_model,
    _prepare_container_step_view_model,
)


APPROVED_SHAPES = ("cuboid", "cylinder", "bottle", "pillow_bag")
ASYMMETRIC_PRODUCT = (180.0, 120.0, 80.0)


def _scene_coordinates(scene):
    return [
        tuple(item[key] for key in ("x", "y", "z", "dx", "dy", "dz"))
        for item in scene["products"]
    ]


class ProductShapeStateTests(SimpleTestCase):
    def test_approved_and_invalid_values_normalize(self):
        for value in APPROVED_SHAPES:
            self.assertEqual(normalize_product_shape(value), value)

        for value in (None, "", "   ", "sphere", object()):
            self.assertEqual(normalize_product_shape(value), "cuboid")

    def test_defaults_serializers_and_forms_share_one_contract(self):
        self.assertEqual(default_container_config()["product_shape"], "cuboid")
        self.assertEqual(default_bag_config()["product_shape"], "cuboid")

        self.assertEqual(
            sanitize_container_config_for_session(
                {"product_shape": " PILLOW_BAG "}
            )["product_shape"],
            "pillow_bag",
        )
        self.assertEqual(
            sanitize_bag_config_for_session({"product_shape": "invalid"})[
                "product_shape"
            ],
            "cuboid",
        )
        self.assertEqual(
            tuple(ContainerSelectionMode1Form.base_fields["product_shape"].choices),
            PRODUCT_SHAPE_CHOICES,
        )
        self.assertEqual(
            tuple(BagSelectionForm.base_fields["product_shape"].choices),
            PRODUCT_SHAPE_CHOICES,
        )

    def test_raw_requests_and_workflow_names_are_normalized_and_prefixed(self):
        factory = RequestFactory()
        container_request = factory.post("/", {"product_shape": "not-approved"})
        bag_request = factory.post("/", {"product_shape": "BOTTLE"})

        self.assertEqual(
            _read_raw_container_config(container_request)["product_shape"],
            "cuboid",
        )
        self.assertEqual(
            _read_raw_bag_config(bag_request)["product_shape"],
            "bottle",
        )

        container_ui = _build_shared_container_ui_contract(prefix="7")
        bag_ui = _build_shared_bag_ui_contract(prefix="8")
        self.assertEqual(container_ui["names"]["product_shape"], "product_shape_7")
        self.assertEqual(container_ui["ids"]["product_shape"], "id_product_shape_7")
        self.assertEqual(bag_ui["names"]["product_shape"], "product_shape_8")
        self.assertEqual(bag_ui["ids"]["product_shape"], "id_product_shape_8")
        self.assertEqual(
            container_ui["ids"]["product_unit_viewer"],
            "containerProductUnitViewer_7",
        )
        self.assertEqual(
            container_ui["ids"]["product_unit_scene"],
            "containerProductUnitScene_7",
        )
        self.assertEqual(
            bag_ui["ids"]["product_unit_viewer"],
            "bagProductUnitViewer_8",
        )
        self.assertEqual(
            bag_ui["ids"]["product_unit_scene"],
            "bagProductUnitScene_8",
        )
        self.assertTrue(
            set(container_ui["ids"].values()).isdisjoint(
                set(bag_ui["ids"].values())
            )
        )

    def test_session_contracts_are_json_safe_primitives(self):
        container = sanitize_container_config_for_session(
            {"product_shape": "cylinder"}
        )
        bag = sanitize_bag_config_for_session({"product_shape": "bottle"})
        self.assertEqual(json.loads(json.dumps(container))["product_shape"], "cylinder")
        self.assertEqual(json.loads(json.dumps(bag))["product_shape"], "bottle")


class ProductOrientationTests(SimpleTestCase):
    def test_all_named_axis_orders_map_to_indexes_zero_through_five(self):
        self.assertEqual(
            [
                orientation_index_from_axis_order(axis_order)
                for axis_order in ORIENTATION_AXIS_ORDERS
            ],
            list(range(6)),
        )

    def test_dimension_matching_uses_authoritative_orientation_order(self):
        oriented_dimensions = (
            (180.0, 120.0, 80.0),
            (180.0, 80.0, 120.0),
            (120.0, 180.0, 80.0),
            (120.0, 80.0, 180.0),
            (80.0, 120.0, 180.0),
            (80.0, 180.0, 120.0),
        )
        allowed = allowed_product_orientations(
            ASYMMETRIC_PRODUCT, 1, 1, 1
        )
        self.assertEqual(
            [
                orientation_index_from_dimensions(
                    ASYMMETRIC_PRODUCT,
                    dimensions,
                    allowed_orientations=allowed,
                )
                for dimensions in oriented_dimensions
            ],
            list(range(6)),
        )

    def test_bag_axis_mapping_uses_names_for_ambiguous_dimensions(self):
        self.assertEqual(
            orientation_index_from_axis_order(
                (
                    "product_height",
                    "product_length",
                    "product_width",
                )
            ),
            5,
        )


class ProductShapeSceneTests(SimpleTestCase):
    def test_product_unit_scene_uses_canonical_dimensions_and_orientation(self):
        scene = build_product_unit_scene(
            (180, "120.5", 80.25),
            "bottle",
        )
        self.assertEqual(
            scene,
            {
                "productShape": "bottle",
                "productDefinition": {
                    "length": 180.0,
                    "width": 120.5,
                    "height": 80.25,
                },
                "orientationIndex": 0,
                "unit": "mm",
                "showBoundingBox": True,
            },
        )
        json.dumps(scene)

    def test_product_unit_scene_rejects_invalid_dimensions(self):
        for product in (
            None,
            (),
            (1, 2),
            (1, 2, 3, 4),
            (0, 2, 3),
            (-1, 2, 3),
            (float("nan"), 2, 3),
            (float("inf"), 2, 3),
            ("invalid", 2, 3),
        ):
            self.assertIsNone(build_product_unit_scene(product, "cuboid"))

    def test_product_unit_scene_normalizes_invalid_shape_to_cuboid(self):
        scene = build_product_unit_scene(ASYMMETRIC_PRODUCT, "sphere")
        self.assertEqual(scene["productShape"], "cuboid")
        self.assertFalse(scene["showBoundingBox"])

    def test_manual_and_catalogue_dimensions_build_equivalent_scenes(self):
        manual_scene = build_product_unit_scene(
            ASYMMETRIC_PRODUCT,
            "pillow_bag",
        )
        catalogue_product = SimpleNamespace(
            product_length=180,
            product_width=120,
            product_height=80,
        )
        catalogue_scene = build_product_unit_scene(
            (
                catalogue_product.product_length,
                catalogue_product.product_width,
                catalogue_product.product_height,
            ),
            "pillow_bag",
        )
        self.assertEqual(catalogue_scene, manual_scene)

    def test_manual_and_catalogue_services_build_equivalent_scenes(self):
        manual_form = SimpleNamespace(cleaned_data={
            "mode": "single",
            "action": "refresh",
            "product_source": "manual",
            "product_l": 180,
            "product_w": 120,
            "product_h": 80,
            "product_weight": None,
            "desired_qty": 1,
            "product_shape": "bottle",
            "r1": True,
            "r2": True,
            "r3": True,
            "container_source": "manual",
        })
        catalogue_form = SimpleNamespace(cleaned_data={
            **manual_form.cleaned_data,
            "product_source": "catalogue",
        })
        catalogue_product = SimpleNamespace(
            product_length=180,
            product_width=120,
            product_height=80,
            desired_qty=1,
            rotation_1=True,
            rotation_2=True,
            rotation_3=True,
        )
        manual_container = analyze_container_form(
            form=manual_form,
            config={},
            materials=[],
        )
        catalogue_container = analyze_container_form(
            form=catalogue_form,
            config={},
            selected_product=catalogue_product,
            materials=[],
        )
        self.assertEqual(
            manual_container["product_unit_scene"],
            catalogue_container["product_unit_scene"],
        )

        bag_base = {
            "mode": "single",
            "product_l": 180,
            "product_w": 120,
            "product_h": 80,
            "desired_qty": 1,
            "product_shape": "bottle",
            "bag_source": "manual",
        }
        manual_bag = analyze_bag_config(
            {**bag_base, "product_source": "manual"},
            action="refresh",
            materials=[],
        )
        catalogue_bag = analyze_bag_config(
            {
                **bag_base,
                "product_source": "catalogue",
                "product_l": "",
                "product_w": "",
                "product_h": "",
            },
            action="refresh",
            selected_product=catalogue_product,
            materials=[],
        )
        self.assertEqual(
            manual_bag["product_unit_scene"],
            catalogue_bag["product_unit_scene"],
        )

    def test_scene_decoration_uses_original_dimensions_and_fallback(self):
        scene = {"products": []}
        self.assertIs(
            decorate_product_scene(
                scene,
                product_shape="not-approved",
                product=ASYMMETRIC_PRODUCT,
            ),
            scene,
        )
        self.assertEqual(scene["productShape"], "cuboid")
        self.assertEqual(
            scene["productDefinition"],
            {"length": 180.0, "width": 120.0, "height": 80.0},
        )
        json.dumps(scene)

    def test_container_single_items_have_individual_orientation_metadata(self):
        with tempfile.TemporaryDirectory() as media_root:
            result = run_mode1_and_render(
                ASYMMETRIC_PRODUCT,
                (600.0, 400.0, 320.0),
                1,
                1,
                1,
                media_root,
                render_style="clean",
            )

        self.assertNotIn("productShape", result.threejs_scene)
        self.assertNotIn("productDefinition", result.threejs_scene)
        allowed = allowed_product_orientations(
            ASYMMETRIC_PRODUCT, 1, 1, 1
        )
        for item in result.threejs_scene["products"]:
            expected = orientation_index_from_dimensions(
                ASYMMETRIC_PRODUCT,
                (item["dx"], item["dy"], item["dz"]),
                allowed_orientations=allowed,
            )
            self.assertEqual(item["orientationIndex"], expected)

    def test_bag_single_items_use_named_body_axis_orientation(self):
        product = (180.0, 120.0, 40.0)
        max_info = compute_max_quantity_for_bag(
            product[0], product[1], product[2], 450.0, 330.0
        )
        result = run_bag_mode1_and_render(
            product=product,
            selected_bag=(450.0, 330.0),
            desired_qty=max_info["max_quantity"],
            solutions=max_info["solutions"],
            media_root="",
            selected_required_bag=(
                max_info["best"]["req_len"],
                max_info["best"]["req_w"],
            ),
        )
        self.assertNotIn("productShape", result.threejs_scene)
        self.assertNotIn("productDefinition", result.threejs_scene)
        self.assertTrue(result.threejs_scene["products"])
        self.assertEqual(
            {item["orientationIndex"] for item in result.threejs_scene["products"]},
            {5},
        )

    def test_multi_product_engine_calls_can_omit_shape_orientation_data(self):
        with tempfile.TemporaryDirectory() as media_root:
            container_result = run_mode1_and_render(
                ASYMMETRIC_PRODUCT,
                (600.0, 400.0, 320.0),
                1,
                1,
                1,
                media_root,
                draw_limit=2,
                render_style="clean",
                include_product_orientation_metadata=False,
            )

        max_info = compute_max_quantity_for_bag(
            180.0, 120.0, 40.0, 450.0, 330.0
        )
        bag_result = run_bag_mode1_and_render(
            product=(180.0, 120.0, 40.0),
            selected_bag=(450.0, 330.0),
            desired_qty=max_info["max_quantity"],
            solutions=max_info["solutions"],
            media_root="",
            draw_limit=2,
            selected_required_bag=(
                max_info["best"]["req_len"],
                max_info["best"]["req_w"],
            ),
            include_product_orientation_metadata=False,
        )

        for scene in (
            container_result.threejs_scene,
            bag_result.threejs_scene,
        ):
            self.assertNotIn("productShape", scene)
            self.assertNotIn("productDefinition", scene)
            self.assertTrue(scene["products"])
            self.assertTrue(
                all("orientationIndex" not in item for item in scene["products"])
            )

    def test_design_products_inherit_candidate_orientation(self):
        container_design = build_container_design_candidates(
            ASYMMETRIC_PRODUCT, 7, 1, 1, 1
        )
        bag_design = build_bag_design_candidates(
            ASYMMETRIC_PRODUCT[0],
            ASYMMETRIC_PRODUCT[1],
            ASYMMETRIC_PRODUCT[2],
            7,
        )

        for candidate in container_design["candidates"]:
            self.assertEqual(
                {
                    item["orientationIndex"]
                    for item in candidate["render_data"]["products"]
                },
                {candidate["orientation_index"]},
            )
        for candidate in bag_design["candidates"]:
            self.assertEqual(
                {
                    item["orientationIndex"]
                    for item in candidate["render_data"]["products"]
                },
                {candidate["orientation_index"]},
            )

    def test_selected_design_scenes_are_decorated_by_services(self):
        container_data = {
            "mode": "design",
            "action": "run_design",
            "product_source": "manual",
            "product_l": "180",
            "product_w": "120",
            "product_h": "80",
            "desired_qty": "7",
            "product_shape": "bottle",
            "r1": "on",
            "r2": "on",
            "r3": "on",
            "container_source": "manual",
        }
        container_form = ContainerSelectionMode1Form(container_data)
        self.assertTrue(container_form.is_valid(), container_form.errors)
        container_analysis = analyze_container_form(
            form=container_form,
            config=container_data,
            materials=[],
        )

        bag_analysis = analyze_bag_config(
            {
                "mode": "design",
                "action": "run_design",
                "product_source": "manual",
                "product_l": "180",
                "product_w": "120",
                "product_h": "80",
                "desired_qty": "7",
                "product_shape": "pillow_bag",
                "bag_source": "manual",
            },
            action="run_design",
            materials=[],
        )

        self.assertEqual(container_analysis["threejs_scene"]["productShape"], "bottle")
        self.assertEqual(bag_analysis["threejs_scene"]["productShape"], "pillow_bag")
        self.assertEqual(
            container_analysis["threejs_scene"]["productDefinition"],
            {"length": 180.0, "width": 120.0, "height": 80.0},
        )
        self.assertEqual(
            bag_analysis["threejs_scene"]["productDefinition"],
            {"length": 180.0, "width": 120.0, "height": 80.0},
        )
        self.assertEqual(
            container_analysis["product_unit_scene"]["productDefinition"],
            {"length": 180.0, "width": 120.0, "height": 80.0},
        )
        self.assertEqual(container_analysis["product_unit_scene"]["orientationIndex"], 0)
        self.assertEqual(
            bag_analysis["product_unit_scene"]["productDefinition"],
            {"length": 180.0, "width": 120.0, "height": 80.0},
        )
        self.assertEqual(bag_analysis["product_unit_scene"]["orientationIndex"], 0)


class ProductUnitWorkflowTests(SimpleTestCase):
    @patch("packagingapp.views.full_packaging.get_container_selected_product", return_value=None)
    @patch("packagingapp.views.full_packaging.get_container_selected_material", return_value=None)
    @patch("packagingapp.views.full_packaging.get_container_products_for_catalogue", return_value=[])
    @patch("packagingapp.views.full_packaging.get_container_materials_for_catalogue", return_value=[])
    @patch("packagingapp.views.full_packaging.get_container_packaging_catalogues", return_value=[])
    @patch("packagingapp.views.full_packaging.get_container_product_catalogues", return_value=[])
    def test_container_step_restores_json_safe_product_unit_scene(self, *_mocks):
        scene = build_product_unit_scene(ASYMMETRIC_PRODUCT, "cylinder")
        step = _new_container_step()
        step["product_unit_scene"] = scene
        _prepare_container_step_view_model(step, 2)
        self.assertEqual(step["product_unit_scene"], scene)
        self.assertEqual(
            step["container_ui"]["ids"]["product_unit_viewer"],
            "containerProductUnitViewer_2",
        )
        json.dumps(step["product_unit_scene"])

    @patch("packagingapp.views.full_packaging.get_bag_selected_product", return_value=None)
    @patch("packagingapp.views.full_packaging.get_bag_selected_material", return_value=None)
    @patch("packagingapp.views.full_packaging.get_bag_products_for_catalogue", return_value=[])
    @patch("packagingapp.views.full_packaging.get_bag_materials_for_catalogue", return_value=[])
    def test_bag_step_restores_json_safe_product_unit_scene(self, *_mocks):
        step = _new_bag_step()
        step["config"].update({
            "product_l": 180,
            "product_w": 120,
            "product_h": 80,
            "product_shape": "bottle",
        })
        _prepare_bag_step_view_model(step, 3)
        self.assertEqual(
            step["product_unit_scene"],
            build_product_unit_scene(ASYMMETRIC_PRODUCT, "bottle"),
        )
        self.assertEqual(
            step["bag_ui"]["ids"]["product_unit_viewer"],
            "bagProductUnitViewer_3",
        )
        json.dumps(step["product_unit_scene"])


class ProductShapeCalculationRegressionTests(SimpleTestCase):
    def _container_analysis(self, product_shape, media_root):
        data = {
            "mode": "single",
            "action": "run_single",
            "product_source": "manual",
            "product_l": "180",
            "product_w": "120",
            "product_h": "80",
            "product_weight": "450",
            "desired_qty": "24",
            "product_shape": product_shape,
            "r1": "on",
            "r2": "on",
            "r3": "on",
            "container_source": "manual",
            "box_l": "600",
            "box_w": "400",
            "box_h": "320",
            "box_weight": "950",
            "box_max_payload": "20000",
        }
        form = ContainerSelectionMode1Form(data)
        self.assertTrue(form.is_valid(), form.errors)
        return analyze_container_form(
            form=form,
            config=data,
            materials=[],
            media_root=media_root,
        )

    def test_container_shape_changes_only_visual_metadata(self):
        results = {}
        with tempfile.TemporaryDirectory() as media_root:
            for product_shape in APPROVED_SHAPES:
                results[product_shape] = self._container_analysis(
                    product_shape, media_root
                )

        reference = results["cuboid"]
        reference_result = reference["result"]
        reference_placements = [
            (*placement.origin, *placement.dimensions)
            for placement in reference_result.placements
        ]
        reference_scene_coordinates = _scene_coordinates(
            reference_result.threejs_scene
        )
        reference_report = {
            key: reference["analysis_report"][key]
            for key in (
                "requested_qty",
                "max_quantity",
                "volumetric_efficiency_current_pct",
                "net_weight",
                "total_weight_current",
                "payload_usage_pct",
            )
        }

        for product_shape, analysis in results.items():
            result = analysis["result"]
            self.assertEqual(result.max_quantity, reference_result.max_quantity)
            self.assertEqual(
                [
                    (*placement.origin, *placement.dimensions)
                    for placement in result.placements
                ],
                reference_placements,
            )
            self.assertEqual(
                _scene_coordinates(result.threejs_scene),
                reference_scene_coordinates,
            )
            self.assertEqual(
                {
                    key: analysis["analysis_report"][key]
                    for key in reference_report
                },
                reference_report,
            )
            self.assertEqual(result.threejs_scene["productShape"], product_shape)
            self.assertEqual(
                result.threejs_scene["productDefinition"],
                {"length": 180.0, "width": 120.0, "height": 80.0},
            )
            self.assertEqual(analysis["product_unit_scene"]["productShape"], product_shape)
            self.assertEqual(analysis["product_unit_scene"]["orientationIndex"], 0)
            if product_shape == "cuboid":
                self.assertTrue(analysis["product_base_image_url"])
            else:
                self.assertIsNone(analysis["product_base_image_url"])

    def test_bag_shape_changes_only_visual_metadata(self):
        base_config = {
            "mode": "single",
            "action": "run_single",
            "product_source": "manual",
            "product_l": "180",
            "product_w": "120",
            "product_h": "40",
            "product_weight": "250",
            "desired_qty": "4",
            "bag_source": "manual",
            "bag_length": "450",
            "bag_width": "330",
            "bag_weight": "18",
            "bag_max_payload": "5000",
        }
        results = {
            product_shape: analyze_bag_config(
                {**base_config, "product_shape": product_shape},
                action="run_single",
                materials=[],
            )
            for product_shape in APPROVED_SHAPES
        }

        reference = results["cuboid"]
        reference_result = reference["result"]
        reference_scene_coordinates = _scene_coordinates(
            reference_result["threejs_scene"]
        )
        reference_result_values = {
            key: reference_result[key]
            for key in (
                "max_quantity",
                "desired_qty",
                "best_required",
                "usage",
                "usage_pct",
            )
        }
        reference_report = {
            key: reference["analysis_report"][key]
            for key in (
                "current_quantity",
                "max_quantity",
                "bag_usage_current_pct",
                "net_weight",
                "total_weight",
                "payload_usage_pct",
            )
        }

        for product_shape, analysis in results.items():
            result = analysis["result"]
            self.assertEqual(
                {key: result[key] for key in reference_result_values},
                reference_result_values,
            )
            self.assertEqual(
                _scene_coordinates(result["threejs_scene"]),
                reference_scene_coordinates,
            )
            self.assertEqual(
                {
                    key: analysis["analysis_report"][key]
                    for key in reference_report
                },
                reference_report,
            )
            self.assertEqual(result["threejs_scene"]["productShape"], product_shape)
            self.assertEqual(
                result["threejs_scene"]["productDefinition"],
                {"length": 180.0, "width": 120.0, "height": 40.0},
            )
            self.assertEqual(analysis["product_unit_scene"]["productShape"], product_shape)
            self.assertEqual(analysis["product_unit_scene"]["orientationIndex"], 0)

    def test_container_pdf_payload_keeps_base_product_png_path(self):
        data = {
            "mode": "single",
            "action": "run_single",
            "product_source": "manual",
            "product_l": "180",
            "product_w": "120",
            "product_h": "80",
            "product_weight": "450",
            "desired_qty": "24",
            "product_shape": "cuboid",
            "r1": "on",
            "r2": "on",
            "r3": "on",
            "container_source": "manual",
            "box_l": "600",
            "box_w": "400",
            "box_h": "320",
            "box_weight": "950",
            "box_max_payload": "20000",
        }
        form = ContainerSelectionMode1Form(data)
        self.assertTrue(form.is_valid(), form.errors)
        with tempfile.TemporaryDirectory() as media_root:
            analysis = analyze_container_form(
                form=form,
                config=data,
                materials=[],
                media_root=media_root,
            )
        payload = _build_single_export_payload(
            form=form,
            analysis=analysis,
            selected_product=None,
            selected_material=None,
        )
        self.assertTrue(payload["product_base_image_rel_path"])
        self.assertEqual(
            payload["product_base_image_rel_path"],
            analysis["product_base_image_rel_path"],
        )

    def test_optimal_selected_results_include_product_unit_scenes(self):
        container_material = SimpleNamespace(
            id=1,
            part_number="BOX-1",
            part_description="Test box",
            branding="",
            part_length=600,
            part_width=400,
            part_height=320,
            part_volume=None,
            part_weight=950,
            max_payload=20000,
        )
        container_form = SimpleNamespace(cleaned_data={
            "mode": "optimal",
            "action": "select_candidate",
            "product_source": "manual",
            "product_l": 180,
            "product_w": 120,
            "product_h": 80,
            "product_weight": 450,
            "desired_qty": 7,
            "product_shape": "cylinder",
            "r1": True,
            "r2": True,
            "r3": True,
            "container_source": "catalogue",
        })
        with tempfile.TemporaryDirectory() as media_root:
            container = analyze_container_form(
                form=container_form,
                config={"catalogue_id": "1"},
                selected_material=container_material,
                materials=[container_material],
                media_root=media_root,
            )
        self.assertIsNotNone(container["result"])
        self.assertEqual(container["product_unit_scene"]["productShape"], "cylinder")
        self.assertEqual(container["product_unit_scene"]["orientationIndex"], 0)

        bag_material = SimpleNamespace(
            id=2,
            part_number="BAG-1",
            part_description="Test bag",
            branding="",
            part_length=450,
            part_width=330,
            part_weight=18,
            max_payload=5000,
        )
        with tempfile.TemporaryDirectory() as media_root:
            bag = analyze_bag_config(
                {
                    "mode": "optimal",
                    "product_source": "manual",
                    "product_l": 180,
                    "product_w": 120,
                    "product_h": 40,
                    "product_weight": 250,
                    "desired_qty": 4,
                    "product_shape": "bottle",
                    "bag_source": "catalogue",
                    "catalogue_id": "1",
                },
                action="select_candidate",
                selected_material=bag_material,
                materials=[bag_material],
                media_root=media_root,
            )
        self.assertIsNotNone(bag["result"])
        self.assertEqual(bag["product_unit_scene"]["productShape"], "bottle")
        self.assertEqual(bag["product_unit_scene"]["orientationIndex"], 0)


class ProductShapeJavaScriptContractTests(SimpleTestCase):
    def test_viewer_keeps_missing_metadata_on_cuboid_path(self):
        static_root = Path(settings.BASE_DIR) / "static" / "js"
        viewer = (static_root / "container_threejs_viewer.js").read_text(
            encoding="utf-8"
        )
        factory = (static_root / "product_shape_factory.js").read_text(
            encoding="utf-8"
        )

        self.assertIn('productShape !== "cuboid"', viewer)
        self.assertIn("hasValidProductDefinition(sceneData.productDefinition)", viewer)
        self.assertIn("addCuboid(productGroup, item, dims", viewer)
        self.assertIn("createApprovedProductVisual({", viewer)
        self.assertIn(
            './product_shape_factory.js?v=20260731-product-shapes',
            viewer,
        )
        self.assertIn("const segmentsAcross = 28;", factory)
        self.assertIn("const segmentsAlong = 36;", factory)
        self.assertIn("const ribCount = 5;", factory)
        self.assertNotIn("SphereGeometry", factory)
        self.assertNotIn("CapsuleGeometry", factory)

        for relative_path in (
            "packagingapp/templates/bag_selection/partials/"
            "_bag_selection_scripts.html",
            "packagingapp/templates/container_selection_tool/partials/"
            "_container_selection_scripts.html",
        ):
            template = (Path(settings.BASE_DIR) / relative_path).read_text(
                encoding="utf-8"
            )
            self.assertIn(
                "container_threejs_viewer.js' %}"
                "?v=20260731-product-shapes",
                template,
            )

    def test_product_unit_viewer_and_template_use_shared_canvas_contract(self):
        root = Path(settings.BASE_DIR)
        viewer = (root / "static/js/product_unit_threejs_viewer.js").read_text(
            encoding="utf-8"
        )
        partial = (
            root / "packagingapp/templates/shared/_product_unit_threejs_panel.html"
        ).read_text(encoding="utf-8")
        container_result = (
            root
            / "packagingapp/templates/container_selection_tool/partials/"
            "_container_selection_result_section.html"
        ).read_text(encoding="utf-8")

        self.assertIn("scene|json_script:scene_id", partial)
        self.assertIn("data-product-unit-threejs-viewer", partial)
        self.assertIn("data-product-unit-threejs-reset", partial)
        for restriction, dimension in (
            ("R1", "Length"),
            ("R2", "Width"),
            ("R3", "Height"),
        ):
            self.assertIn(
                f'data-product-unit-threejs-orientation="{restriction}"',
                partial,
            )
            self.assertIn(
                f'aria-label="View {restriction} — {dimension} vertical"',
                partial,
            )
        self.assertIn("createApprovedProductVisual", viewer)
        self.assertIn("createApprovedProductMaterials", viewer)
        self.assertIn("normalizeProductShape", viewer)
        self.assertIn("orientationQuaternion", viewer)
        self.assertIn(
            'R1: Object.freeze({ verticalDimension: "length", orientationIndex: 3 })',
            viewer,
        )
        self.assertIn(
            'R2: Object.freeze({ verticalDimension: "width", orientationIndex: 5 })',
            viewer,
        )
        self.assertIn(
            'R3: Object.freeze({ verticalDimension: "height", orientationIndex: 0 })',
            viewer,
        )
        self.assertIn("root.quaternion.copy(orientationQuaternion", viewer)
        self.assertIn("THREE.Sprite", viewer)
        self.assertIn("THREE.CanvasTexture", viewer)
        self.assertIn("THREE.EdgesGeometry", viewer)
        self.assertNotIn("WireframeGeometry", viewer)
        self.assertNotIn("requestAnimationFrame(animate", viewer)
        self.assertNotIn("product_base_image_url", container_result)

        for relative_path in (
            "packagingapp/templates/bag_selection/partials/_bag_selection_scripts.html",
            "packagingapp/templates/container_selection_tool/partials/"
            "_container_selection_scripts.html",
        ):
            scripts = (root / relative_path).read_text(encoding="utf-8")
            self.assertIn(
                "product_unit_threejs_viewer.js' %}"
                "?v=20260807-orientation-views",
                scripts,
            )

    def test_container_and_bag_product_unit_partials_render_orientation_views(self):
        scene = build_product_unit_scene(ASYMMETRIC_PRODUCT, "cuboid")
        cases = (
            (
                "container_selection_tool/partials/"
                "_container_selection_design_result.html",
                {
                    "container_ui": {
                        "ids": {
                            "threejs_scene": "containerScene",
                            "threejs_viewer": "containerViewer",
                            "product_unit_scene": "containerProductScene",
                            "product_unit_viewer": "containerProductViewer",
                        },
                        "prefix": "",
                    },
                    "result": {
                        "container_length": 200,
                        "container_width": 140,
                        "container_height": 100,
                    },
                },
            ),
            (
                "bag_selection/partials/_bag_selection_design_result.html",
                {
                    "bag_ui": {
                        "ids": {
                            "threejs_scene": "bagScene",
                            "threejs_viewer": "bagViewer",
                            "product_unit_scene": "bagProductScene",
                            "product_unit_viewer": "bagProductViewer",
                        },
                        "prefix": "",
                    },
                    "result": {
                        "bag_width": 220,
                        "bag_length": 320,
                        "bundle_length": 180,
                        "bundle_width": 120,
                        "bundle_height": 80,
                    },
                    "analysis_report": {"shape_score_display": "100%"},
                },
            ),
        )

        for template_name, context in cases:
            with self.subTest(template=template_name):
                html = render_to_string(
                    template_name,
                    {
                        **context,
                        "mode": "workflow",
                        "threejs_scene": None,
                        "product_unit_scene": scene,
                    },
                )
                self.assertIn("Base product unit", html)
                self.assertEqual(
                    html.count("data-product-unit-threejs-orientation="),
                    3,
                )
                for restriction in ("R1", "R2", "R3"):
                    self.assertIn(
                        f'data-product-unit-threejs-orientation="{restriction}"',
                        html,
                    )
