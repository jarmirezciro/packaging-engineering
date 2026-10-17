import json
import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from packagingapp.assistant.contracts import (
    MAX_CONTEXT_BYTES,
    ToolContextValidationError,
    canonical_json,
)
from packagingapp.assistant.views import (
    MAX_ASSISTANT_CONTEXT_REQUEST_BYTES,
    STANDALONE_CONTAINER_RESULT_SESSION_KEY,
)
from packagingapp.assistant.workflow import (
    ASSISTANT_STEP_REF_KEY,
    ensure_workflow_step_refs,
)
from packagingapp.models import (
    PackagingCatalogue,
    PackagingMaterial,
    Product,
    ProductCatalogue,
    UserSubscription,
)
from packagingapp.views.full_packaging import (
    SESSION_KEY,
    _new_bag_step,
    _new_container_step,
)


def ready_state(**overrides):
    state = {
        "mode": "single",
        "action": "refresh",
        "product_source": "manual",
        "product_l": "10",
        "product_w": "8",
        "product_h": "6",
        "product_weight": "25",
        "desired_qty": "4",
        "product_shape": "cuboid",
        "r1": True,
        "r2": True,
        "r3": True,
        "container_source": "manual",
        "box_l": "40",
        "box_w": "30",
        "box_h": "20",
        "box_thickness_mm": "",
        "box_weight": "100",
        "box_max_payload": "1000",
    }
    state.update(overrides)
    return state


def calculation_post(**overrides):
    state = ready_state(action="run_single")
    state.update(overrides)
    post = dict(state)
    for rotation in ("r1", "r2", "r3"):
        if post.pop(rotation):
            post[rotation] = "on"
    return post


@override_settings(MEDIA_URL="/media/")
class AssistantContextEndpointTests(TestCase):
    def setUp(self):
        self.media_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.media_dir.cleanup)
        self.settings_override = override_settings(MEDIA_ROOT=self.media_dir.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)

        User = get_user_model()
        self.entitled = User.objects.create_user(
            username="assistant-plus",
            email="assistant-plus@example.test",
            password="test-password",
        )
        UserSubscription.objects.create(
            user=self.entitled,
            plan=UserSubscription.Plan.PLUS,
        )
        self.unentitled = User.objects.create_user(
            username="assistant-free",
            email="assistant-free@example.test",
            password="test-password",
        )
        self.url = reverse("assistant_context")

    def post_context(self, payload, *, client=None, content_type="application/json"):
        return (client or self.client).post(
            self.url,
            data=json.dumps(payload),
            content_type=content_type,
        )

    def standalone_payload(self, state=None, **extra):
        payload = {
            "tool": "container_selection",
            "surface": "standalone",
            "state": {} if state is None else state,
        }
        payload.update(extra)
        return payload

    def login_entitled(self):
        self.client.force_login(self.entitled)

    def test_authentication_and_entitlement_are_enforced_before_context_work(self):
        anonymous = self.post_context(self.standalone_payload())
        self.assertEqual(anonymous.status_code, 401)
        self.assertEqual(anonymous.json()["error"]["code"], "authentication_required")

        self.client.force_login(self.unentitled)
        denied = self.post_context(
            self.standalone_payload(entitled=True)
        )
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(denied.json()["error"]["code"], "assistant_not_entitled")

        self.login_entitled()
        allowed = self.post_context(self.standalone_payload())
        self.assertEqual(allowed.status_code, 200)
        self.assertTrue(allowed.json()["ok"])

    def test_method_content_type_json_and_request_schema_errors_are_stable(self):
        self.login_entitled()

        wrong_method = self.client.get(self.url)
        self.assertEqual(wrong_method.status_code, 405)
        self.assertEqual(wrong_method["Allow"], "POST")
        self.assertEqual(wrong_method.json()["error"]["code"], "method_not_allowed")

        wrong_type = self.client.post(self.url, data="{}", content_type="text/plain")
        self.assertEqual(wrong_type.status_code, 415)
        self.assertEqual(
            wrong_type.json()["error"]["code"], "unsupported_content_type"
        )

        malformed = self.client.post(
            self.url, data=b'{"tool":', content_type="application/json"
        )
        self.assertEqual(malformed.status_code, 400)
        self.assertEqual(malformed.json()["error"]["code"], "malformed_json")

        unsupported_tool = self.post_context(
            {
                "tool": "arbitrary_python_function",
                "surface": "standalone",
                "state": {},
            }
        )
        self.assertEqual(unsupported_tool.status_code, 400)
        self.assertEqual(
            unsupported_tool.json()["error"]["code"], "unsupported_tool"
        )

        unsupported_surface = self.post_context(
            {
                "tool": "container_selection",
                "surface": "public",
                "state": {},
            }
        )
        self.assertEqual(unsupported_surface.status_code, 400)
        self.assertEqual(
            unsupported_surface.json()["error"]["code"], "unsupported_surface"
        )

        nested_state = self.post_context(
            self.standalone_payload({"product_l": {"value": 10}})
        )
        self.assertEqual(nested_state.status_code, 400)
        self.assertEqual(
            nested_state.json()["error"]["code"], "invalid_current_state"
        )

    def test_standalone_empty_partial_invalid_and_ready_states_do_not_calculate(self):
        self.login_entitled()
        cases = (
            ({}, "empty"),
            ({"product_l": "10"}, "partial"),
            (ready_state(product_l="not-a-number"), "invalid"),
            (ready_state(), "ready"),
        )
        with patch(
            "packagingapp.tools.container.service.run_mode1_and_render"
        ) as render_engine, patch(
            "packagingapp.tools.container.service.compute_max_quantity_only"
        ) as capacity_engine:
            for state, expected in cases:
                with self.subTest(expected=expected):
                    response = self.post_context(self.standalone_payload(state))
                    self.assertEqual(response.status_code, 200)
                    context = response.json()["context"]
                    self.assertEqual(
                        context["tool"]["calculation_status"], expected
                    )
                    self.assertIsNone(context["result"])
            render_engine.assert_not_called()
            capacity_engine.assert_not_called()

        invalid = self.post_context(
            self.standalone_payload(ready_state(product_l="not-a-number"))
        ).json()["context"]
        self.assertEqual(invalid["validation"]["status"], "invalid")
        self.assertIn(
            "product.dimensions.length",
            {error["field"] for error in invalid["validation"]["errors"]},
        )

    def test_normal_calculation_creates_complete_stale_and_recalculated_lifecycle(self):
        self.login_entitled()
        state_a = ready_state()

        calculated_a = self.client.post(
            reverse("container_selection_mode1"), calculation_post()
        )
        self.assertEqual(calculated_a.status_code, 200)
        self.assertIsNotNone(calculated_a.context["result"])
        self.assertIn(
            STANDALONE_CONTAINER_RESULT_SESSION_KEY,
            self.client.session,
        )

        complete_a = self.post_context(self.standalone_payload(state_a)).json()[
            "context"
        ]
        fingerprint_a = complete_a["tool"]["state_fingerprint"]
        self.assertEqual(complete_a["tool"]["calculation_status"], "complete")
        self.assertIsNotNone(complete_a["result"])

        state_b = ready_state(product_l="12")
        stale_b = self.post_context(self.standalone_payload(state_b)).json()[
            "context"
        ]
        self.assertEqual(stale_b["tool"]["calculation_status"], "stale")
        self.assertIsNone(stale_b["result"])
        self.assertEqual(stale_b["alternatives"], [])
        self.assertIn(
            "previous_result_is_stale",
            {warning["code"] for warning in stale_b["warnings"]},
        )

        recalculated_b = self.client.post(
            reverse("container_selection_mode1"),
            calculation_post(product_l="12"),
        )
        self.assertEqual(recalculated_b.status_code, 200)
        complete_b = self.post_context(self.standalone_payload(state_b)).json()[
            "context"
        ]
        self.assertEqual(complete_b["tool"]["calculation_status"], "complete")
        self.assertIsNotNone(complete_b["result"])
        self.assertNotEqual(
            complete_b["tool"]["state_fingerprint"], fingerprint_a
        )

        serialized_snapshot = json.dumps(
            self.client.session[STANDALONE_CONTAINER_RESULT_SESSION_KEY],
            sort_keys=True,
        )
        for forbidden_key in (
            '"placements"',
            '"threejs_scene"',
            '"image_path"',
            '"session_key"',
        ):
            self.assertNotIn(forbidden_key, serialized_snapshot)

    def test_optimal_and_design_calculations_are_returned_from_compact_snapshots(self):
        self.login_entitled()
        packaging = PackagingCatalogue.objects.create(
            name="Endpoint Optimal Packaging", is_public=True
        )
        PackagingMaterial.objects.create(
            catalogue=packaging,
            part_number="OPTIMAL-PRIVATE-LABEL",
            part_description="Endpoint candidate",
            packaging_type="BOX",
            branding="Brand1",
            packaging_materials="Board",
            part_length=40,
            part_width=30,
            part_height=20,
        )

        optimal_state = ready_state(
            mode="optimal",
            action="find_top5",
            catalogue_id=str(packaging.pk),
            container_source="manual",
        )
        optimal_post = calculation_post(
            mode="optimal",
            action="find_top5",
            catalogue_id=str(packaging.pk),
            container_source="manual",
        )
        optimal_calculation = self.client.post(
            reverse("container_selection_mode1"), optimal_post
        )
        self.assertEqual(optimal_calculation.status_code, 200)
        self.assertTrue(optimal_calculation.context["top5"])
        optimal = self.post_context(
            self.standalone_payload(optimal_state)
        ).json()["context"]
        self.assertEqual(optimal["tool"]["calculation_status"], "complete")
        self.assertEqual(optimal["tool"]["mode"], "optimal")
        self.assertEqual(optimal["result"]["kind"], "optimal_search")
        self.assertTrue(optimal["alternatives"])
        self.assertNotIn("OPTIMAL-PRIVATE-LABEL", json.dumps(optimal))

        design_state = ready_state(
            mode="design",
            action="run_design",
            desired_qty="7",
            box_l="",
            box_w="",
            box_h="",
            box_weight="",
            box_max_payload="",
        )
        design_post = calculation_post(
            mode="design",
            action="run_design",
            desired_qty="7",
            box_l="",
            box_w="",
            box_h="",
            box_weight="",
            box_max_payload="",
        )
        design_calculation = self.client.post(
            reverse("container_selection_mode1"), design_post
        )
        self.assertEqual(design_calculation.status_code, 200)
        self.assertIsNotNone(design_calculation.context["result"])
        design = self.post_context(
            self.standalone_payload(design_state)
        ).json()["context"]
        self.assertEqual(design["tool"]["calculation_status"], "complete")
        self.assertEqual(design["tool"]["mode"], "design")
        self.assertEqual(design["result"]["kind"], "design")
        self.assertTrue(design["alternatives"])
        self.assertNotIn('"render_data"', json.dumps(design, sort_keys=True))

    def test_nonsemantic_action_does_not_change_fingerprint(self):
        self.login_entitled()
        first = self.post_context(
            self.standalone_payload(ready_state(action="run_single"))
        ).json()["context"]
        second = self.post_context(
            self.standalone_payload(ready_state(action="future_assistant_button"))
        ).json()["context"]
        self.assertEqual(
            first["tool"]["state_fingerprint"],
            second["tool"]["state_fingerprint"],
        )

    def test_request_and_context_size_failures_are_safe(self):
        self.login_entitled()
        oversized = b"{" + b" " * MAX_ASSISTANT_CONTEXT_REQUEST_BYTES + b"}"
        response = self.client.post(
            self.url, data=oversized, content_type="application/json"
        )
        self.assertEqual(response.status_code, 413)
        self.assertEqual(
            response.json()["error"]["code"], "assistant_request_too_large"
        )

        normal = self.post_context(self.standalone_payload(ready_state()))
        self.assertEqual(normal.status_code, 200)
        encoded = canonical_json(normal.json()["context"]).encode("utf-8")
        self.assertLess(len(encoded), MAX_CONTEXT_BYTES)

        with patch(
            "packagingapp.assistant.views._build_standalone_context",
            side_effect=ToolContextValidationError(
                "Tool Context exceeds the application limit."
            ),
        ):
            too_large = self.post_context(self.standalone_payload())
        self.assertEqual(too_large.status_code, 413)
        self.assertEqual(
            too_large.json()["error"]["code"], "assistant_context_too_large"
        )

    def test_csrf_is_enforced_by_normal_django_middleware(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.entitled)
        page = csrf_client.get(reverse("container_selection_mode1"))
        self.assertEqual(page.status_code, 200)
        token = csrf_client.cookies["csrftoken"].value

        missing = csrf_client.post(
            self.url,
            data=json.dumps(self.standalone_payload()),
            content_type="application/json",
        )
        self.assertEqual(missing.status_code, 403)

        valid = csrf_client.post(
            self.url,
            data=json.dumps(self.standalone_payload()),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(valid.status_code, 200)


class AssistantContextCatalogueVisibilityTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(
            username="catalogue-owner", email="owner@example.test"
        )
        UserSubscription.objects.create(
            user=self.owner, plan=UserSubscription.Plan.PLUS
        )
        self.other = User.objects.create_user(
            username="catalogue-other", email="other@example.test"
        )
        UserSubscription.objects.create(
            user=self.other, plan=UserSubscription.Plan.PLUS
        )
        self.client.force_login(self.owner)
        self.url = reverse("assistant_context")

        self.public_products, self.public_product = self.make_product(
            "Public Products", None, True, "PUBLIC-SECRET", 11, 12, 13
        )
        self.own_products, self.own_product = self.make_product(
            "Owner Products", self.owner, False, "OWNER-SECRET", 21, 22, 23
        )
        self.other_products, self.other_product = self.make_product(
            "Other Products", self.other, False, "OTHER-SECRET", 31, 32, 33
        )
        self.public_packaging, self.public_material = self.make_material(
            "Public Packaging", None, True, "PUBLIC-BOX", 101, 102, 103
        )
        self.own_packaging, self.own_material = self.make_material(
            "Owner Packaging", self.owner, False, "OWNER-BOX", 201, 202, 203
        )
        self.other_packaging, self.other_material = self.make_material(
            "Other Packaging", self.other, False, "OTHER-BOX", 301, 302, 303
        )

    def make_product(self, name, owner, is_public, product_id, length, width, height):
        catalogue = ProductCatalogue.objects.create(
            name=name, owner=owner, is_public=is_public
        )
        product = Product.objects.create(
            catalogue=catalogue,
            product_id=product_id,
            product_name=f"{product_id} confidential name",
            product_length=length,
            product_width=width,
            product_height=height,
            weight=44,
            rotation_1=True,
            rotation_2=False,
            rotation_3=True,
        )
        return catalogue, product

    def make_material(self, name, owner, is_public, part_number, length, width, height):
        catalogue = PackagingCatalogue.objects.create(
            name=name, owner=owner, is_public=is_public
        )
        material = PackagingMaterial.objects.create(
            catalogue=catalogue,
            part_number=part_number,
            part_description=f"{part_number} confidential description",
            packaging_type="BOX",
            branding="Brand1",
            packaging_materials="Confidential board",
            part_length=length,
            part_width=width,
            part_height=height,
            part_weight=2,
        )
        return catalogue, material

    def request_catalogue_context(self, product_catalogue, product, packaging, material):
        state = ready_state(
            product_source="catalogue",
            product_catalogue_id=str(product_catalogue.pk),
            selected_product_id=str(product.pk),
            product_l="999",
            product_w="999",
            product_h="999",
            container_source="catalogue",
            catalogue_id=str(packaging.pk),
            container_id=str(material.pk),
            box_l="999",
            box_w="999",
            box_h="999",
        )
        return self.client.post(
            self.url,
            data=json.dumps(
                {
                    "tool": "container_selection",
                    "surface": "standalone",
                    "state": state,
                }
            ),
            content_type="application/json",
        )

    def test_public_and_owned_catalogue_values_are_rehydrated_authoritatively(self):
        for product_catalogue, product, packaging, material, expected in (
            (
                self.public_products,
                self.public_product,
                self.public_packaging,
                self.public_material,
                (11.0, 101.0),
            ),
            (
                self.own_products,
                self.own_product,
                self.own_packaging,
                self.own_material,
                (21.0, 201.0),
            ),
        ):
            with self.subTest(expected=expected):
                response = self.request_catalogue_context(
                    product_catalogue, product, packaging, material
                )
                self.assertEqual(response.status_code, 200)
                context = response.json()["context"]
                self.assertEqual(
                    context["inputs"]["product"]["dimensions"]["length"]["value"],
                    expected[0],
                )
                self.assertEqual(
                    context["inputs"]["container"]["internal_dimensions"][
                        "length"
                    ]["value"],
                    expected[1],
                )
                self.assertNotIn(
                    "tare_weight", context["inputs"]["container"]
                )

    def test_another_users_private_records_cannot_be_referenced_or_spoofed(self):
        response = self.request_catalogue_context(
            self.other_products,
            self.other_product,
            self.other_packaging,
            self.other_material,
        )
        self.assertEqual(response.status_code, 200)
        context = response.json()["context"]
        self.assertIn(
            context["tool"]["calculation_status"], {"partial", "invalid"}
        )
        self.assertIsNone(
            context["inputs"]["product"]["dimensions"]["length"]["value"]
        )
        self.assertIsNone(
            context["inputs"]["container"]["internal_dimensions"]["length"][
                "value"
            ]
        )
        serialized = json.dumps(response.json(), sort_keys=True)
        for sensitive in (
            "OTHER-SECRET",
            "OTHER-BOX",
            "confidential name",
            "confidential description",
            self.other.username,
            self.other.email,
        ):
            self.assertNotIn(sensitive, serialized)

    def test_actual_endpoint_response_excludes_identity_ids_paths_and_raw_objects(self):
        response = self.request_catalogue_context(
            self.public_products,
            self.public_product,
            self.public_packaging,
            self.public_material,
        )
        serialized = json.dumps(response.json(), sort_keys=True)
        for sensitive in (
            self.owner.username,
            self.owner.email,
            "PUBLIC-SECRET",
            "PUBLIC-BOX",
            "Confidential board",
            "csrf",
            "session_key",
            "media/",
        ):
            self.assertNotIn(sensitive, serialized)
        for forbidden_key in (
            '"user_id"',
            '"owner_id"',
            '"catalogue_id"',
            '"container_id"',
            '"selected_product_id"',
            '"placements"',
            '"threejs_scene"',
        ):
            self.assertNotIn(forbidden_key, serialized)


@override_settings(MEDIA_URL="/media/")
class AssistantContextWorkflowTests(TestCase):
    def setUp(self):
        self.media_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.media_dir.cleanup)
        self.settings_override = override_settings(MEDIA_ROOT=self.media_dir.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)

        User = get_user_model()
        self.user = User.objects.create_user(username="workflow-plus")
        UserSubscription.objects.create(
            user=self.user, plan=UserSubscription.Plan.PLUS
        )
        self.client.force_login(self.user)
        self.url = reverse("assistant_context")
        self.flow_url = reverse("full_packaging_mode")

    def workflow_request(self, step_ref, state=None, *, client=None):
        return (client or self.client).post(
            self.url,
            data=json.dumps(
                {
                    "tool": "container_selection",
                    "surface": "workflow",
                    "step_ref": step_ref,
                    "state": {} if state is None else state,
                }
            ),
            content_type="application/json",
        )

    def add_step(self, step_type="container", after_index="start"):
        response = self.client.post(
            self.flow_url,
            {
                "action": "add_step",
                "step_type": step_type,
                "after_index": after_index,
            },
        )
        self.assertEqual(response.status_code, 302)

    def run_first_container(self):
        response = self.client.post(
            self.flow_url,
            {
                "action": "run_step",
                "index": "0",
                "action_0": "run_single",
                "mode_0": "single",
                "product_source_0": "manual",
                "product_l_0": "10",
                "product_w_0": "8",
                "product_h_0": "6",
                "product_weight_0": "25",
                "desired_qty_0": "4",
                "product_shape_0": "cuboid",
                "r1_0": "on",
                "r2_0": "on",
                "r3_0": "on",
                "container_source_0": "manual",
                "box_l_0": "40",
                "box_w_0": "30",
                "box_h_0": "20",
                "box_weight_0": "100",
                "box_max_payload_0": "1000",
            },
        )
        self.assertEqual(response.status_code, 302)

    def test_explicit_step_binding_pending_selected_and_inherited_state(self):
        self.add_step("container")
        self.run_first_container()
        workflow = self.client.session[SESSION_KEY]
        first = workflow["steps"][0]
        first_ref = first[ASSISTANT_STEP_REF_KEY]
        self.assertIn("assistant_result_snapshot", first)

        pending_response = self.workflow_request(first_ref)
        self.assertEqual(pending_response.status_code, 200)
        pending = pending_response.json()["context"]
        self.assertEqual(pending["tool"]["calculation_status"], "complete")
        self.assertEqual(pending["workflow"]["result_state"], "pending")

        stale = self.workflow_request(first_ref, {"product_l": "12"}).json()[
            "context"
        ]
        self.assertEqual(stale["tool"]["calculation_status"], "stale")
        self.assertIsNone(stale["result"])
        self.assertEqual(stale["alternatives"], [])

        selected_response = self.client.post(
            self.flow_url, {"action": "use_step_result", "index": "0"}
        )
        self.assertEqual(selected_response.status_code, 302)
        selected = self.workflow_request(first_ref).json()["context"]
        self.assertEqual(selected["workflow"]["result_state"], "selected")

        self.add_step("container", after_index="0")
        workflow = self.client.session[SESSION_KEY]
        second_ref = workflow["steps"][1][ASSISTANT_STEP_REF_KEY]
        inherited_response = self.workflow_request(
            second_ref,
            ready_state(product_l="999", product_w="999", product_h="999"),
        )
        self.assertEqual(inherited_response.status_code, 200)
        inherited = inherited_response.json()["context"]
        self.assertEqual(inherited["workflow"]["input_origin"], "inherited")
        self.assertEqual(inherited["workflow"]["step_ordinal"], 2)
        self.assertEqual(
            inherited["inputs"]["product"]["dimensions"]["length"]["value"],
            48.0,
        )
        self.assertFalse(
            inherited["input_definitions"]["product.dimensions.length"][
                "editable"
            ]
        )

    def test_step_attacks_unsupported_types_and_cross_session_refs_fail_safely(self):
        container_step = _new_container_step()
        bag_step = _new_bag_step()
        workflow = {"steps": [container_step, bag_step], "show_add_bar_after": None}
        ensure_workflow_step_refs(workflow)
        session = self.client.session
        session[SESSION_KEY] = workflow
        session.save()

        for invalid_ref in ("-1", "999999", "containerSelectionRoot_0", "../0"):
            with self.subTest(step_ref=invalid_ref):
                response = self.workflow_request(invalid_ref)
                self.assertEqual(response.status_code, 404)
                self.assertEqual(
                    response.json()["error"]["code"], "workflow_step_not_found"
                )

        unsupported = self.workflow_request(bag_step[ASSISTANT_STEP_REF_KEY])
        self.assertEqual(unsupported.status_code, 400)
        self.assertEqual(
            unsupported.json()["error"]["code"], "unsupported_workflow_step"
        )

        other_client = Client()
        other_client.force_login(self.user)
        cross_session = self.workflow_request(
            container_step[ASSISTANT_STEP_REF_KEY], client=other_client
        )
        self.assertEqual(cross_session.status_code, 404)

    def test_only_requested_step_is_returned_and_unrelated_workflow_data_is_private(self):
        current = _new_container_step()
        unrelated = _new_bag_step()
        unrelated["messages"] = ["UNRELATED-WORKFLOW-SECRET"]
        unrelated["selected"] = {"label": "UNRELATED-SELECTED-SECRET"}
        workflow = {"steps": [current, unrelated], "show_add_bar_after": None}
        ensure_workflow_step_refs(workflow)
        session = self.client.session
        session[SESSION_KEY] = workflow
        session.save()

        response = self.workflow_request(current[ASSISTANT_STEP_REF_KEY])
        self.assertEqual(response.status_code, 200)
        serialized = json.dumps(response.json(), sort_keys=True)
        self.assertNotIn("UNRELATED-WORKFLOW-SECRET", serialized)
        self.assertNotIn("UNRELATED-SELECTED-SECRET", serialized)
        self.assertNotIn(current[ASSISTANT_STEP_REF_KEY], serialized)
