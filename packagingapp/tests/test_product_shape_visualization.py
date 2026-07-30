import json
import tempfile
from pathlib import Path

from django.conf import settings
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
    _build_shared_container_ui_contract,
    _read_raw_container_config,
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
        self.assertIn("const segmentsAcross = 28;", factory)
        self.assertIn("const segmentsAlong = 36;", factory)
        self.assertIn("const ribCount = 5;", factory)
        self.assertNotIn("SphereGeometry", factory)
        self.assertNotIn("CapsuleGeometry", factory)
