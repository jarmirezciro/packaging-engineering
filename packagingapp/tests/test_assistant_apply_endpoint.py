import json
import time
from copy import deepcopy
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from packagingapp.assistant.actions import PROPOSE_INPUT_CHANGES
from packagingapp.assistant.contracts import ASSISTANT_RESPONSE_SCHEMA_VERSION
from packagingapp.assistant.proposal_tokens import issue_reviewed_proposal_token
from packagingapp.assistant.workflow import ASSISTANT_STEP_REF_KEY, ensure_workflow_step_refs
from packagingapp.models import PackagingMaterial, Product, UserSubscription
from packagingapp.tools.container.state import default_container_config
from packagingapp.tools.container.assistant_actions import CONTAINER_PROPOSAL_FIELDS
from packagingapp.views.full_packaging import SESSION_KEY, _new_container_step


def manual_state(**overrides):
    state = default_container_config()
    state.update(
        {
            "mode": "single",
            "action": "refresh",
            "product_source": "manual",
            "product_l": "180",
            "product_w": "120",
            "product_h": "80",
            "product_weight": "450",
            "desired_qty": "12",
            "product_shape": "cuboid",
            "r1": True,
            "r2": True,
            "r3": True,
            "container_source": "manual",
            "box_l": "600",
            "box_w": "400",
            "box_h": "300",
            "box_thickness_mm": "4",
            "box_weight": "900",
            "box_max_payload": "20000",
        }
    )
    state.update(overrides)
    return state


@override_settings(MEDIA_URL="/media/")
class AssistantApplyEndpointTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="assistant-apply-user")
        UserSubscription.objects.create(
            user=self.user,
            plan=UserSubscription.Plan.PLUS,
        )
        self.client.force_login(self.user)
        self.ask_url = reverse("assistant_ask")
        self.apply_url = reverse("assistant_apply_proposal")

    def _preview(
        self,
        changes,
        *,
        state=None,
        surface="standalone",
        step_ref=None,
        client=None,
    ):
        state = manual_state() if state is None else state

        def proposal(**kwargs):
            context = kwargs["tool_context"]
            return {
                "schema_version": ASSISTANT_RESPONSE_SCHEMA_VERSION,
                "type": PROPOSE_INPUT_CHANGES,
                "state_fingerprint": context["tool"]["state_fingerprint"],
                "changes": changes,
                "summary": "Provider wording is not Apply authority.",
            }

        payload = {
            "tool": "container_selection",
            "surface": surface,
            "state": state,
            "message": "Review these explicit Container input changes.",
        }
        if surface == "workflow":
            payload["step_ref"] = step_ref
        with patch("packagingapp.assistant.views.ask_external", side_effect=proposal):
            response = (client or self.client).post(
                self.ask_url,
                data=json.dumps(payload),
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 200)
        return response.json()["response"]

    def _apply(self, token, state, *, step_ref=None, client=None, extra=None):
        payload = {"proposal_token": token, "state": state}
        if step_ref is not None:
            payload["step_ref"] = step_ref
        if extra:
            payload.update(extra)
        return (client or self.client).post(
            self.apply_url,
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_valid_preview_gets_token_and_standalone_apply_updates_inputs_only(self):
        state = manual_state()
        before_session = deepcopy(dict(self.client.session))
        preview = self._preview(
            [{"field": "product.dimensions.length", "value": 32, "unit": "cm"}],
            state=state,
        )

        self.assertTrue(preview["can_apply"])
        self.assertIn("proposal_token", preview)
        self.assertNotIn("Provider wording", json.dumps(preview))

        with patch("packagingapp.assistant.views.ask_external") as provider, patch(
            "packagingapp.assistant.views.retrieve_knowledge_context"
        ) as knowledge, patch(
            "packagingapp.assistant.service.evaluate_external_provider_gate"
        ) as external_gate, patch(
            "packagingapp.tools.container.service.run_mode1_and_render"
        ) as selection_engine, patch(
            "packagingapp.tools.container.service.compute_max_quantity_only"
        ) as capacity_engine, patch(
            "packagingapp.tools.container.service.build_container_design_candidates"
        ) as design_engine, patch(
            "packagingapp.utils.package_design_arrangements.build_canonical_design_arrangements"
        ) as arrangements:
            response = self._apply(preview["proposal_token"], state)

        self.assertEqual(response.status_code, 200)
        applied = response.json()["response"]
        self.assertEqual(applied["type"], "applied")
        self.assertEqual(
            applied["fields"],
            [{
                "field": "product.dimensions.length",
                "field_key": "product_l",
                "value": 320.0,
                "unit": "mm",
            }],
        )
        self.assertEqual(applied["calculation_status"], "ready")
        self.assertIn("Run the tool", applied["message"])
        self.assertEqual(dict(self.client.session), before_session)
        provider.assert_not_called()
        knowledge.assert_not_called()
        external_gate.assert_not_called()
        selection_engine.assert_not_called()
        capacity_engine.assert_not_called()
        design_engine.assert_not_called()
        arrangements.assert_not_called()

    def test_multi_field_and_rotation_apply_are_atomic_and_canonical(self):
        state = manual_state()
        preview = self._preview(
            [
                {"field": "product.dimensions.length", "value": 320, "unit": "mm"},
                {"field": "product.dimensions.width", "value": 18, "unit": "cm"},
                {"field": "request.desired_quantity", "value": 24, "unit": "pcs"},
                {
                    "field": "product.allowed_vertical_axes",
                    "value": ["length", "height"],
                    "unit": "none",
                },
            ],
            state=state,
        )

        response = self._apply(preview["proposal_token"], state)

        self.assertEqual(response.status_code, 200)
        fields = response.json()["response"]["fields"]
        self.assertEqual(
            {row["field_key"]: row["value"] for row in fields},
            {
                "product_l": 320.0,
                "product_w": 180.0,
                "desired_qty": 24,
                "r1": True,
                "r2": False,
                "r3": True,
            },
        )

    def test_stale_and_replayed_proposals_change_nothing(self):
        state = manual_state()
        preview = self._preview(
            [{"field": "product.dimensions.length", "value": 320, "unit": "mm"}],
            state=state,
        )
        changed = {**state, "product_w": "121"}

        stale = self._apply(preview["proposal_token"], changed)
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(stale.json()["error"]["code"], "stale_proposal")

        first = self._apply(preview["proposal_token"], state)
        self.assertEqual(first.status_code, 200)
        applied_state = {**state, "product_l": "320"}
        replay = self._apply(preview["proposal_token"], applied_state)
        self.assertEqual(replay.status_code, 409)
        self.assertEqual(replay.json()["error"]["code"], "stale_proposal")

    def test_bad_signature_expiry_and_cross_user_binding_are_rejected(self):
        state = manual_state()
        preview = self._preview(
            [{"field": "product.dimensions.length", "value": 320, "unit": "mm"}],
            state=state,
        )
        token = preview["proposal_token"]
        tampered = token[:-1] + ("a" if token[-1] != "a" else "b")
        bad = self._apply(tampered, state)
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(bad.json()["error"]["code"], "invalid_proposal")

        future = time.time() + 601
        with patch("django.core.signing.time.time", return_value=future):
            expired = self._apply(token, state)
        self.assertEqual(expired.status_code, 410)
        self.assertEqual(expired.json()["error"]["code"], "expired")
        self.assertEqual(
            expired.json()["error"]["message"],
            "This proposal has expired. Ask KolliPack Assistant again to create a new proposal.",
        )

        User = get_user_model()
        other = User.objects.create_user(username="assistant-apply-other")
        UserSubscription.objects.create(user=other, plan=UserSubscription.Plan.PLUS)
        other_client = Client()
        other_client.force_login(other)
        denied = self._apply(token, state, client=other_client)
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(denied.json()["error"]["code"], "unauthorized")

    def test_incomplete_valid_preview_can_apply_but_invalid_preview_has_no_token(self):
        partial = default_container_config()
        valid = self._preview(
            [{"field": "product.dimensions.length", "value": 320, "unit": "mm"}],
            state=partial,
        )
        self.assertTrue(valid["can_apply"])
        self.assertEqual(
            valid["resulting_state"]["calculation_status"], "incomplete"
        )
        applied = self._apply(valid["proposal_token"], partial)
        self.assertEqual(applied.status_code, 200)
        self.assertEqual(
            applied.json()["response"]["calculation_status"], "incomplete"
        )

        invalid = self._preview(
            [{"field": "product.dimensions.length", "value": -1, "unit": "mm"}],
            state=manual_state(),
        )
        self.assertFalse(invalid["can_apply"])
        self.assertFalse(invalid["valid"])
        self.assertNotIn("proposal_token", invalid)
        forged = issue_reviewed_proposal_token(
            user_identifier=self.user.pk,
            tool="container_selection",
            surface="standalone",
            state_fingerprint=invalid["state_fingerprint"],
            changes=[{
                "field": "product.dimensions.length",
                "value": -1,
                "unit": "mm",
            }],
            allowed_fields=set(CONTAINER_PROPOSAL_FIELDS),
        )
        forged_response = self._apply(forged, manual_state())
        self.assertEqual(forged_response.status_code, 422)
        self.assertEqual(
            forged_response.json()["error"]["code"], "invalid_state"
        )

    def test_source_change_and_browser_authority_fields_are_rejected(self):
        state = manual_state()
        preview = self._preview(
            [{"field": "product.dimensions.length", "value": 320, "unit": "mm"}],
            state=state,
        )
        catalogue_state = {
            **state,
            "product_source": "catalogue",
            "product_catalogue_id": "999",
            "selected_product_id": "999",
        }
        source_changed = self._apply(preview["proposal_token"], catalogue_state)
        self.assertEqual(source_changed.status_code, 409)
        self.assertEqual(source_changed.json()["error"]["code"], "stale_proposal")

        for extra in (
            {"changes": [{"field": "product_l", "value": 999}]},
            {"state_fingerprint": "sha256:" + "0" * 64},
            {"selector": "#product_l"},
        ):
            with self.subTest(extra=extra):
                rejected = self._apply(
                    preview["proposal_token"], state, extra=extra
                )
                self.assertEqual(rejected.status_code, 400)
                self.assertEqual(
                    rejected.json()["error"]["code"], "invalid_request_schema"
                )

    def test_entitlement_csrf_and_size_gates_run_before_apply(self):
        state = manual_state()
        preview = self._preview(
            [{"field": "product.dimensions.length", "value": 320, "unit": "mm"}],
            state=state,
        )

        subscription = UserSubscription.objects.get(user=self.user)
        subscription.plan = UserSubscription.Plan.FREE
        subscription.save(update_fields=["plan"])
        forbidden = self._apply(preview["proposal_token"], state)
        self.assertEqual(forbidden.status_code, 403)
        self.assertEqual(forbidden.json()["error"]["code"], "assistant_not_entitled")

        subscription.plan = UserSubscription.Plan.PLUS
        subscription.save(update_fields=["plan"])
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        missing_csrf = self._apply(
            preview["proposal_token"], state, client=csrf_client
        )
        self.assertEqual(missing_csrf.status_code, 403)

        oversized = self.client.post(
            self.apply_url,
            data=json.dumps({
                "proposal_token": "x" * (16 * 1024),
                "state": state,
            }),
            content_type="application/json",
        )
        self.assertEqual(oversized.status_code, 413)
        self.assertEqual(
            oversized.json()["error"]["code"], "assistant_request_too_large"
        )

    def test_apply_does_not_write_catalogues(self):
        state = manual_state()
        preview = self._preview(
            [{"field": "container.thickness", "value": 5, "unit": "mm"}],
            state=state,
        )
        before = (Product.objects.count(), PackagingMaterial.objects.count())

        response = self._apply(preview["proposal_token"], state)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            (Product.objects.count(), PackagingMaterial.objects.count()), before
        )


@override_settings(MEDIA_URL="/media/")
class AssistantWorkflowApplyTests(AssistantApplyEndpointTests):
    def _install_workflow(self, *, steps=2):
        workflow_steps = []
        for _index in range(steps):
            step = _new_container_step()
            step["config"] = manual_state()
            workflow_steps.append(step)
        workflow = {"steps": workflow_steps, "show_add_bar_after": None}
        ensure_workflow_step_refs(workflow)
        session = self.client.session
        session[SESSION_KEY] = workflow
        session.save()
        return workflow

    def test_workflow_apply_updates_only_bound_config_and_preserves_results(self):
        workflow = self._install_workflow(steps=2)
        step = workflow["steps"][0]
        step_ref = step[ASSISTANT_STEP_REF_KEY]
        step["result"] = {"kind": "container", "max_quantity": 10}
        step["pending_result"] = {"length": 608, "width": 408, "height": 316}
        step["selected"] = {"length": 608, "width": 408, "height": 316}
        downstream_before = deepcopy(workflow["steps"][1])
        session = self.client.session
        session[SESSION_KEY] = workflow
        session.save()

        preview = self._preview(
            [{"field": "product.dimensions.length", "value": 320, "unit": "mm"}],
            state=manual_state(),
            surface="workflow",
            step_ref=step_ref,
        )
        before_current = deepcopy(self.client.session[SESSION_KEY]["steps"][0])

        response = self._apply(
            preview["proposal_token"],
            manual_state(),
            step_ref=step_ref,
        )

        self.assertEqual(response.status_code, 200)
        after = self.client.session[SESSION_KEY]
        self.assertEqual(after["steps"][0]["config"]["product_l"], "320")
        for key in (
            "result",
            "pending_result",
            "selected",
            "assistant_result_snapshot",
        ):
            self.assertEqual(after["steps"][0].get(key), before_current.get(key))
        self.assertEqual(after["steps"][1], downstream_before)

    def test_workflow_step_mismatch_and_cross_session_reference_are_denied(self):
        workflow = self._install_workflow(steps=2)
        first_ref = workflow["steps"][0][ASSISTANT_STEP_REF_KEY]
        second_ref = workflow["steps"][1][ASSISTANT_STEP_REF_KEY]
        preview = self._preview(
            [{"field": "container.internal_dimensions.length", "value": 700, "unit": "mm"}],
            state=manual_state(),
            surface="workflow",
            step_ref=first_ref,
        )
        before = deepcopy(self.client.session[SESSION_KEY])

        mismatch = self._apply(
            preview["proposal_token"],
            manual_state(),
            step_ref=second_ref,
        )
        self.assertEqual(mismatch.status_code, 400)
        self.assertEqual(mismatch.json()["error"]["code"], "invalid_proposal")
        self.assertEqual(self.client.session[SESSION_KEY], before)

        other_client = Client()
        other_client.force_login(self.user)
        cross_session = self._apply(
            preview["proposal_token"],
            manual_state(),
            step_ref=first_ref,
            client=other_client,
        )
        self.assertEqual(cross_session.status_code, 404)
        self.assertEqual(cross_session.json()["error"]["code"], "workflow_step_not_found")

    def test_inherited_product_preview_cannot_issue_apply_token(self):
        workflow = self._install_workflow(steps=2)
        second_ref = workflow["steps"][1][ASSISTANT_STEP_REF_KEY]

        preview = self._preview(
            [{"field": "product.dimensions.width", "value": 200, "unit": "mm"}],
            state=manual_state(),
            surface="workflow",
            step_ref=second_ref,
        )

        self.assertFalse(preview["can_apply"])
        self.assertNotIn("proposal_token", preview)
        self.assertEqual(preview["changes"][0]["status"], "not_editable")
        forged = issue_reviewed_proposal_token(
            user_identifier=self.user.pk,
            tool="container_selection",
            surface="workflow",
            state_fingerprint=preview["state_fingerprint"],
            changes=[{
                "field": "product.dimensions.width",
                "value": 200,
                "unit": "mm",
            }],
            allowed_fields=set(CONTAINER_PROPOSAL_FIELDS),
            step_ref=second_ref,
        )
        denied = self._apply(
            forged,
            manual_state(),
            step_ref=second_ref,
        )
        self.assertEqual(denied.status_code, 422)
        self.assertEqual(denied.json()["error"]["code"], "not_editable")
