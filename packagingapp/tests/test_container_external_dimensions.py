import json
from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import SimpleTestCase

from packagingapp.forms import ContainerSelectionMode1Form
from packagingapp.tools.container.dimensions import (
    DEFAULT_BOX_THICKNESS_MM,
    EXTERNAL_DIMENSION_SOURCE_CATALOGUE,
    EXTERNAL_DIMENSION_SOURCE_CATALOGUE_THICKNESS,
    EXTERNAL_DIMENSION_SOURCE_DEFAULT_THICKNESS,
    EXTERNAL_DIMENSION_SOURCE_PROVIDED_THICKNESS,
    resolve_external_carton_dimensions,
)
from packagingapp.tools.container.serializers import sanitize_container_config_for_session
from packagingapp.tools.container.service import (
    analyze_container_capacity,
    build_container_analysis_report,
    resolve_container_dimension_contract,
)
from packagingapp.tools.full_packaging.chain_optimizer import build_design_candidate_payload
from packagingapp.views.full_packaging import (
    _apply_payload_to_config,
    _build_container_non_design_workflow_payload,
)


def manual_form(*, thickness="", mode="single", desired_qty="2"):
    data = {
        "mode": mode,
        "action": "run_design" if mode == "design" else "run_single",
        "product_source": "manual",
        "product_l": "100",
        "product_w": "80",
        "product_h": "50",
        "desired_qty": desired_qty,
        "r1": "on",
        "r2": "on",
        "r3": "on",
        "container_source": "manual",
        "box_l": "600",
        "box_w": "400",
        "box_h": "300",
        "box_thickness_mm": thickness,
    }
    form = ContainerSelectionMode1Form(data)
    return form, data


class ExternalCartonDimensionResolverTests(SimpleTestCase):
    def test_default_and_known_thickness_contracts(self):
        assumed = resolve_external_carton_dimensions(600, 400, 300)
        self.assertEqual(DEFAULT_BOX_THICKNESS_MM, 4.0)
        self.assertEqual(
            (assumed["external_length"], assumed["external_width"], assumed["external_height"]),
            (608.0, 408.0, 316.0),
        )
        self.assertEqual(assumed["box_thickness_mm"], 4.0)
        self.assertTrue(assumed["box_thickness_assumed"])
        self.assertEqual(assumed["external_dimension_source"], EXTERNAL_DIMENSION_SOURCE_DEFAULT_THICKNESS)

        provided = resolve_external_carton_dimensions(600, 400, 300, thickness_mm=5)
        self.assertEqual(
            (provided["external_length"], provided["external_width"], provided["external_height"]),
            (610.0, 410.0, 320.0),
        )
        self.assertFalse(provided["box_thickness_assumed"])
        self.assertEqual(provided["external_dimension_source"], EXTERNAL_DIMENSION_SOURCE_PROVIDED_THICKNESS)
        json.dumps(provided)

    def test_complete_catalogue_external_dimensions_win_and_incomplete_triplet_never_hybrids(self):
        explicit = resolve_external_carton_dimensions(
            600, 400, 300,
            external_length=609, external_width=409, external_height=309,
            thickness_mm=12,
            thickness_source=EXTERNAL_DIMENSION_SOURCE_CATALOGUE_THICKNESS,
        )
        self.assertEqual(
            (explicit["external_length"], explicit["external_width"], explicit["external_height"]),
            (609.0, 409.0, 309.0),
        )
        self.assertEqual(explicit["external_dimension_source"], EXTERNAL_DIMENSION_SOURCE_CATALOGUE)

        incomplete = resolve_external_carton_dimensions(
            600, 400, 300,
            external_length=999, external_width=None, external_height=None,
            thickness_mm=3,
            thickness_source=EXTERNAL_DIMENSION_SOURCE_CATALOGUE_THICKNESS,
        )
        self.assertEqual(
            (incomplete["external_length"], incomplete["external_width"], incomplete["external_height"]),
            (606.0, 406.0, 312.0),
        )
        self.assertEqual(incomplete["external_dimension_source"], EXTERNAL_DIMENSION_SOURCE_CATALOGUE_THICKNESS)

    def test_invalid_user_thickness_is_a_form_error(self):
        for value in ("0", "-1", "not-a-number"):
            with self.subTest(value=value):
                form, _data = manual_form(thickness=value)
                self.assertFalse(form.is_valid())
                self.assertIn("box_thickness_mm", form.errors)


class ContainerDimensionContractTests(SimpleTestCase):
    def test_manual_analysis_report_and_detailed_analysis_assumption(self):
        form, _data = manual_form(thickness="")
        self.assertTrue(form.is_valid(), form.errors)
        report = build_container_analysis_report(
            form=form,
            result=SimpleNamespace(max_quantity=10),
            product=(100, 80, 50),
            container=(600, 400, 300),
            desired_qty=2,
            product_source="manual",
        )
        self.assertEqual((report["external_length"], report["external_width"], report["external_height"]), (608.0, 408.0, 316.0))
        self.assertTrue(report["box_thickness_assumed"])

        html = render_to_string(
            "container_selection_tool/partials/_container_selection_result_section.html",
            {
                "result": SimpleNamespace(max_quantity=10),
                "analysis_report": report,
                "mode": "workflow",
                "current_mode": "single",
                "container_ui": {"prefix": "0", "ids": {}},
                "pending_result": None,
            },
        )
        self.assertIn("Internal dimensions", html)
        self.assertIn("External dimensions", html)
        self.assertIn("assumed 4 mm box thickness", html)

        provided_form, _provided_data = manual_form(thickness="5")
        self.assertTrue(provided_form.is_valid(), provided_form.errors)
        provided_report = build_container_analysis_report(
            form=provided_form,
            result=SimpleNamespace(max_quantity=10),
            product=(100, 80, 50),
            container=(600, 400, 300),
            desired_qty=2,
            product_source="manual",
        )
        provided_html = render_to_string(
            "container_selection_tool/partials/_container_selection_result_section.html",
            {
                "result": SimpleNamespace(max_quantity=10),
                "analysis_report": provided_report,
                "mode": "workflow",
                "current_mode": "single",
                "container_ui": {"prefix": "0", "ids": {}},
                "pending_result": None,
            },
        )
        self.assertEqual(
            (provided_report["external_length"], provided_report["external_width"], provided_report["external_height"]),
            (610.0, 410.0, 320.0),
        )
        self.assertNotIn("assumed 4 mm box thickness", provided_html)

    def test_catalogue_precedence_uses_external_then_thickness_then_default(self):
        form, _data = manual_form()
        self.assertTrue(form.is_valid(), form.errors)
        form.cleaned_data["container_source"] = "catalogue"

        fixtures = [
            ((609, 409, 309), 3, (609.0, 409.0, 309.0), False),
            ((None, None, None), 3, (606.0, 406.0, 312.0), False),
            ((None, None, None), None, (608.0, 408.0, 316.0), True),
        ]
        for external, thickness, expected, assumed in fixtures:
            with self.subTest(external=external, thickness=thickness):
                material = SimpleNamespace(
                    external_length=external[0],
                    external_width=external[1],
                    external_height=external[2],
                    box_thickness_mm=thickness,
                )
                contract = resolve_container_dimension_contract(
                    form, (600, 400, 300), "catalogue", material
                )
                self.assertEqual(
                    (contract["external_length"], contract["external_width"], contract["external_height"]),
                    expected,
                )
                self.assertEqual(contract["box_thickness_assumed"], assumed)

    def test_design_ranking_and_internal_capacity_do_not_change_with_thickness(self):
        analyses = []
        for thickness in ("", "5"):
            form, data = manual_form(thickness=thickness, mode="design", desired_qty="7")
            self.assertTrue(form.is_valid(), form.errors)
            analyses.append(analyze_container_capacity(form, data))

        blank, thick = analyses
        self.assertEqual(
            [
                (row["candidate_id"], row["rank"], row["container_length"], row["container_width"], row["container_height"], row["design_quantity"])
                for row in blank["design_candidates"]
            ],
            [
                (row["candidate_id"], row["rank"], row["container_length"], row["container_width"], row["container_height"], row["design_quantity"])
                for row in thick["design_candidates"]
            ],
        )
        self.assertEqual(
            thick["result"]["external_length"],
            thick["result"]["container_length"] + 10,
        )

        capacities = []
        for thickness in ("", "5"):
            form, data = manual_form(thickness=thickness)
            self.assertTrue(form.is_valid(), form.errors)
            capacities.append(analyze_container_capacity(form, data)["result"]["max_quantity"])
        self.assertEqual(capacities[0], capacities[1])

    def test_workflow_payload_uses_external_dimensions_and_old_config_defaults(self):
        old_config = {"box_l": "600", "box_w": "400", "box_h": "300"}
        sanitized = sanitize_container_config_for_session(old_config)
        self.assertEqual(sanitized["box_thickness_mm"], "")
        payload = _build_container_non_design_workflow_payload(
            sanitized, 12, None, None, None
        )
        self.assertEqual((payload["length"], payload["width"], payload["height"]), (608.0, 408.0, 316.0))
        self.assertEqual((payload["internal_length"], payload["internal_width"], payload["internal_height"]), (600.0, 400.0, 300.0))
        self.assertTrue(payload["box_thickness_assumed"])

        pallet_config = _apply_payload_to_config({}, "pallet", payload)
        self.assertEqual(
            (pallet_config["box_l"], pallet_config["box_w"], pallet_config["box_h"]),
            (608.0, 408.0, 316.0),
        )

    def test_design_selected_and_optimizer_paths_share_external_payload_builder(self):
        candidate = {
            "candidate_id": "candidate",
            "design_quantity": 6,
            "desired_quantity": 6,
            "additional_capacity": 0,
            "container_length": 600,
            "container_width": 400,
            "container_height": 300,
            "box_thickness_mm": 5,
            "box_thickness_assumed": False,
        }
        normal = build_design_candidate_payload("container", candidate)
        optimizer = build_design_candidate_payload("container", candidate)
        self.assertEqual(normal, optimizer)
        self.assertEqual((normal["length"], normal["width"], normal["height"]), (610.0, 410.0, 320.0))
        self.assertEqual((normal["internal_length"], normal["internal_width"], normal["internal_height"]), (600.0, 400.0, 300.0))

        candidate.pop("box_thickness_mm")
        candidate.pop("box_thickness_assumed")
        assumed = build_design_candidate_payload("container", candidate)
        self.assertEqual((assumed["length"], assumed["width"], assumed["height"]), (608.0, 408.0, 316.0))
        self.assertTrue(assumed["box_thickness_assumed"])
