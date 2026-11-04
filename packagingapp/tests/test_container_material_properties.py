"""Finished-carton provenance, independent overrides and incomplete Flow mass."""

import inspect
import json
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase
from django.urls import reverse
from openpyxl import Workbook, load_workbook

from packagingapp.forms import PackagingMaterialForm
from packagingapp.models import CorrugatedBoardConstruction, PackagingCatalogue, PackagingMaterial
from packagingapp.services.excel_import import REQUIRED_COLUMNS, import_packaging_excel
from packagingapp.tests.test_container_carton_tare import container_form, report_for
from packagingapp.tools.container.carton_tare import calculate_rsc_carton_tare
from packagingapp.tools.container.corrugated_material import gsm_to_lb_msf
from packagingapp.tools.container.serializers import sanitize_container_config_for_session
from packagingapp.tools.container.service import analyze_container_form, apply_catalogue_choices
from packagingapp.tools.container import export as container_export
from packagingapp.tools.full_packaging.chain_optimizer import build_design_candidate_payload
from packagingapp.views import full_packaging as flow
from packagingapp.views.container_selection import _build_shared_container_ui_contract, _read_raw_container_config
from packagingapp.views.container_selection import _build_single_export_payload, _build_design_export_payload
from packagingapp.views.packaging_catalogue import export_catalogue_excel


class ContainerMaterialPropertyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.board = CorrugatedBoardConstruction.objects.get(code="FEFCO_C_175_140_175")
        cls.catalogue = PackagingCatalogue.objects.create(name="Finished carton provenance")

    def sku(self, **values):
        defaults = dict(
            catalogue=self.catalogue, part_number="SKU", part_description="Test carton",
            packaging_type="BOX", branding="Brand1", packaging_materials="Corrugated",
            part_length=600, part_width=400, part_height=300,
        )
        defaults.update(values)
        return PackagingMaterial.objects.create(**defaults)

    def form(self, **values):
        form = container_form(
            corrugated_material_id=self.board.code,
            box_thickness_user_override="", grammage_user_override="", **values,
        )
        apply_catalogue_choices(form, [self.catalogue], [], [self.board])
        self.assertTrue(form.is_valid(), form.errors)
        return form

    def report(self, **values):
        return report_for(self.form(**values), selected_board=self.board)

    def test_new_design_has_catalogue_reference_defaults_and_one_input_per_property(self):
        response = self.client.get(reverse("container_selection_mode1"), {"mode": "design"})
        self.assertEqual(response.status_code, 200)
        config = response.context["container_config"]
        self.assertEqual(config["corrugated_material_id"], self.board.code)
        self.assertEqual(float(config["box_thickness_mm"]), 4.08)
        self.assertEqual(float(config["combined_grammage_g_m2"]), 560.2)
        self.assertContains(response, 'name="box_thickness_mm"', count=1)
        self.assertContains(response, 'name="combined_grammage_g_m2"', count=1)
        self.assertNotContains(response, "Box thickness")

    def test_leaving_design_restores_disabled_source_radio_state(self):
        data = dict(container_form(action="refresh").data)
        data.pop("container_source")
        response = self.client.post(reverse("container_selection_mode1"), data)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("container_source", response.context["form"].errors)
        self.assertEqual(response.context["form"].cleaned_data["container_source"], "manual")

    def test_independent_overrides_reset_and_reference_precision(self):
        automatic = self.report(box_thickness_mm="0.161", combined_grammage_g_m2="114.7", container_dimension_unit="in")
        self.assertEqual(automatic["caliper_mm"], 4.08)
        self.assertEqual(automatic["combined_grammage_g_m2"], 560.2)
        caliper_form = self.form(box_thickness_mm="5")
        caliper_form.cleaned_data["box_thickness_user_override"] = "1"
        caliper_form.data["box_thickness_user_override"] = "1"
        caliper = report_for(caliper_form, selected_board=self.board)
        self.assertEqual(caliper["caliper_mm"], 5)
        self.assertEqual(caliper["combined_grammage_g_m2"], 560.2)
        grammage_form = self.form(combined_grammage_g_m2="700")
        grammage_form.cleaned_data["grammage_user_override"] = "1"
        grammage_form.data["grammage_user_override"] = "1"
        grammage = report_for(grammage_form, selected_board=self.board)
        self.assertEqual(grammage["caliper_mm"], 4.08)
        self.assertEqual(grammage["combined_grammage_g_m2"], 700)
        self.assertEqual(caliper["carton_tare_g"], automatic["carton_tare_g"])
        self.assertGreater(grammage["carton_tare_g"], automatic["carton_tare_g"])
        # Explicit reset flags discard even stale posted override values.
        reset = self.report(box_thickness_mm="5", combined_grammage_g_m2="700")
        self.assertEqual(reset["caliper_mm"], 4.08)
        self.assertEqual(reset["combined_grammage_g_m2"], 560.2)

    def test_board_change_updates_each_non_overridden_property(self):
        other = SimpleNamespace(pk=99, name="Other board", caliper_mm=2.3, combined_grammage_g_m2=420)
        form = self.form(box_thickness_mm="5", combined_grammage_g_m2="700")
        automatic = report_for(form, selected_board=other)
        self.assertEqual((automatic["caliper_mm"], automatic["combined_grammage_g_m2"]), (2.3, 420))
        form.data["box_thickness_user_override"] = "1"
        form.cleaned_data["box_thickness_user_override"] = "1"
        overridden = report_for(form, selected_board=other)
        self.assertEqual((overridden["caliper_mm"], overridden["combined_grammage_g_m2"]), (5, 420))

    def test_catalogue_owns_properties_and_requires_confirmed_geometry(self):
        form = self.form(container_source="catalogue", box_weight="999", box_thickness_mm="9", combined_grammage_g_m2="999")
        for values, expected_source in (
            ({}, "unavailable"),
            ({"box_thickness_mm": 3}, "unavailable"),
            ({"box_thickness_mm": 3, "combined_grammage_g_m2": 400}, "unavailable"),
            ({"box_thickness_mm": 3, "combined_grammage_g_m2": 400, "carton_style": "0201"}, "estimated_material"),
            ({"corrugated_construction": self.board, "carton_style": "0201"}, "estimated_material"),
            ({"part_weight": 0.75, "combined_grammage_g_m2": 400, "carton_style": "0201"}, "catalogue"),
        ):
            with self.subTest(values=values):
                sku = self.sku(part_number=str(len(PackagingMaterial.objects.all())), **values)
                report = report_for(form, selected_board=self.board, selected_material=sku)
                self.assertEqual(report["carton_tare_source"], expected_source)
                if expected_source == "unavailable":
                    self.assertIsNone(report["carton_tare_g"])
                    self.assertIsNone(report["gross_carton_weight_g"])
                elif expected_source == "catalogue":
                    self.assertEqual(report["carton_tare_g"], 750)
                else:
                    gsm = values.get("combined_grammage_g_m2", 560.2)
                    self.assertAlmostEqual(report["carton_tare_g"], float(calculate_rsc_carton_tare(600, 400, 300, gsm).finished_box_weight_g), places=3)
                json.dumps(report)

    def test_sku_properties_override_associated_board_and_external_dimensions_win(self):
        sku = self.sku(corrugated_construction=self.board, box_thickness_mm=3, combined_grammage_g_m2=420,
                       external_length=621, external_width=422, external_height=323)
        report = report_for(self.form(container_source="catalogue"), selected_material=sku, selected_board=self.board)
        self.assertEqual((report["caliper_mm"], report["combined_grammage_g_m2"]), (3, 420))
        self.assertEqual(report["caliper_source"], "catalogue")
        self.assertEqual(report["grammage_source"], "catalogue")
        self.assertEqual((report["external_length"], report["external_width"], report["external_height"]), (621, 422, 323))

    def test_non_box_never_uses_rsc_geometry_even_with_board_and_style(self):
        for kind in ("CRATE", "CONTAINER", "TRAILER"):
            sku = self.sku(part_number=kind, packaging_type=kind, corrugated_construction=self.board, carton_style="0201")
            report = report_for(self.form(container_source="catalogue"), selected_material=sku)
            self.assertIsNone(report["carton_tare_g"])

    def test_top5_properties_and_selection_refresh_are_candidate_specific(self):
        first = self.sku(part_number="FIRST", corrugated_construction=self.board, carton_style="0201")
        second = self.sku(part_number="SECOND", box_thickness_mm=2, combined_grammage_g_m2=300, carton_style="0201")
        form = self.form(mode="optimal", action="select_candidate", catalogue_id=str(self.catalogue.pk), box_weight="999")
        config = dict(form.data)
        rendered = SimpleNamespace(max_quantity=12, threejs_scene={}, image_rel_path="")
        with patch("packagingapp.tools.container.service.run_mode1_and_render", return_value=rendered), patch("packagingapp.tools.container.service.render_product_base_unit", return_value=""):
            for selected, expected_gsm in ((first, 560.2), (second, 300), (first, 560.2)):
                analysis = analyze_container_form(form, config, selected_material=selected, materials=[first, second])
                self.assertTrue(analysis["ok"], analysis["messages"])
                report = analysis["analysis_report"]
                self.assertEqual(report["combined_grammage_g_m2"], expected_gsm)
                self.assertEqual(report["carton_tare_source"], "estimated_material")
                self.assertEqual([row["combined_grammage_g_m2"] for row in analysis["top5"]], [560.2, 300])
                self.assertEqual(report["gross_carton_weight_g"], round(500 + report["carton_tare_g"], 3))

    def test_contents_only_summary_and_detail_have_no_redundant_weight_card(self):
        report = report_for(container_form())
        html = render_to_string("container_selection_tool/partials/_container_selection_result_section.html", {
            "result": SimpleNamespace(max_quantity=12), "analysis_report": report,
        })
        self.assertIn("Contents weight", html)
        self.assertIn("Carton tare unavailable", html)
        self.assertNotIn("<strong>Carton weight</strong>", html)
        self.assertEqual(html.count("Empty carton tare"), 1)
        self.assertIsNone(report["gross_carton_weight_g"])

    def test_workflow_preserves_incomplete_weight_through_downstream_adapters(self):
        report = report_for(container_form())
        cfg = dict(container_form().data)
        payload = flow._build_container_non_design_workflow_payload(cfg, 12, None, None, None, report)
        self.assertEqual(payload["weight_status"], "net_only")
        self.assertEqual(payload["net_content_weight_g"], 1200)
        self.assertNotIn("weight_kg", payload)
        inherited = flow._apply_payload_to_config({"box_weight": 999}, "pallet", payload)
        self.assertEqual(inherited["box_weight"], "")
        transport_rows = flow._transport_rows_from_selected(payload)
        self.assertEqual(transport_rows[0]["weight"], "")
        selected = {"total_boxes": 12, "actual_pallet_load_g": 0}
        with patch.object(flow, "build_pallet_pending_result", return_value={"weight_kg": 0}):
            pallet = flow._build_pallet_workflow_payload({}, selected, SimpleNamespace(part_weight=20), payload)
        self.assertNotIn("weight_kg", pallet)
        self.assertEqual(pallet["weight_status"], "unknown")
        step = {"result": {"summary": {"gross_weight": 0, "utilization_weight_pct": 0}, "display": {"gross_weight": "0 kg"}}}
        flow._mark_incomplete_transport_weight(step, pallet)
        self.assertIsNone(step["result"]["summary"]["gross_weight"])
        self.assertIn("Unavailable", step["result"]["display"]["gross_weight"])
        design = build_design_candidate_payload("container", {
            "design_quantity": 5, "net_content_weight": 500,
            "container_length": 600, "container_width": 400, "container_height": 300,
        })
        self.assertEqual(design["weight_status"], "net_only")
        self.assertNotIn("weight_kg", design)
        json.dumps([payload, pallet, design, transport_rows])

    def test_metric_and_imperial_manual_grammage_are_equivalent(self):
        metric = container_form(combined_grammage_g_m2="700.1234567", grammage_user_override="1")
        imperial = container_form(combined_grammage_g_m2=str(gsm_to_lb_msf("700.1234567")), grammage_user_override="1", container_dimension_unit="in")
        first, second = report_for(metric), report_for(imperial)
        self.assertEqual(first["combined_grammage_g_m2"], 700.1234567)
        self.assertEqual(first["carton_tare_g"], second["carton_tare_g"])
        self.assertEqual(first["combined_grammage_g_m2"], second["combined_grammage_g_m2"])
        self.assertIn("lb/MSF", second["grammage_display"])

    def test_state_roundtrip_and_prefix_names_preserve_independent_flags(self):
        config = sanitize_container_config_for_session({"box_thickness_mm": "5"})
        self.assertEqual(config["box_thickness_user_override"], "1")
        self.assertEqual(config["grammage_user_override"], "")
        config.update(combined_grammage_g_m2="700", grammage_user_override="1")
        for prefix in ("", "2", "3"):
            ui = _build_shared_container_ui_contract(prefix)
            suffix = "_" + prefix if prefix else ""
            self.assertEqual(ui["names"]["combined_grammage_g_m2"], "combined_grammage_g_m2" + suffix)
        # The normalized Flow form and standalone request both retain the fields.
        normalized = flow._normalized_container_post(config)
        self.assertEqual(normalized["combined_grammage_g_m2"], "700")
        request = RequestFactory().post("/", config)
        standalone = _read_raw_container_config(request)
        self.assertEqual(standalone["grammage_user_override"], "1")
        self.assertEqual(standalone["combined_grammage_g_m2"], "700")
        json.dumps(sanitize_container_config_for_session(config))

    def test_catalogue_form_and_excel_roundtrip_with_legacy_columns(self):
        values = dict(part_number="FORM", part_description="Form carton", packaging_type="BOX", branding="Brand1",
                      packaging_materials="Corrugated", part_length=600, part_width=400, part_height=300,
                      corrugated_construction=self.board.pk, combined_grammage_g_m2=420, carton_style="0201")
        form = PackagingMaterialForm(values)
        self.assertTrue(form.is_valid(), form.errors)
        material = form.save(commit=False)
        material.catalogue = self.catalogue
        material.save()
        request = RequestFactory().get("/")
        request.user = None
        with patch("packagingapp.views.packaging_catalogue.get_manageable_packaging_catalogue_or_404", return_value=self.catalogue):
            response = inspect.unwrap(export_catalogue_excel)(request, self.catalogue.pk)
        workbook = load_workbook(BytesIO(response.content))
        headers = [cell.value for cell in workbook.active[1]]
        self.assertIn("corrugated_construction_code", headers)
        self.assertEqual(import_packaging_excel(BytesIO(response.content), self.catalogue), (0, 1))
        material.refresh_from_db()
        self.assertEqual(material.corrugated_construction_id, self.board.pk)
        self.assertEqual(float(material.combined_grammage_g_m2), 420)
        self.assertEqual(material.carton_style, "0201")

        # Older spreadsheets omit all optional columns without clearing SKU data.
        wb = Workbook()
        wb.active.append(REQUIRED_COLUMNS)
        wb.active.append([values.get(key) for key in REQUIRED_COLUMNS])
        stream = BytesIO()
        wb.save(stream)
        stream.seek(0)
        import_packaging_excel(stream, self.catalogue)
        material.refresh_from_db()
        self.assertEqual(material.corrugated_construction_id, self.board.pk)
        self.assertEqual(material.carton_style, "0201")

    def test_workflow_post_get_and_reset_use_the_shared_material_contract(self):
        url = reverse("full_packaging_mode")
        self.client.post(url, {"action": "add_step", "step_type": "container"})
        data = dict(container_form(mode="design", action="run_design", corrugated_material_id=self.board.code,
                                  box_thickness_mm="5", combined_grammage_g_m2="700",
                                  box_thickness_user_override="1", grammage_user_override="1").data)
        posted = {f"{key}_0": value for key, value in data.items()}
        posted.update(action="run_step", index="0", step_action_0="run_design")
        response = self.client.post(url, posted, follow=True)
        self.assertEqual(response.status_code, 200)
        step = self.client.session["full_packaging_mode_session"]["steps"][0]
        self.assertEqual(step["config"]["combined_grammage_g_m2"], "700")
        self.assertEqual(step["analysis_report"]["caliper_mm"], 5)
        self.assertEqual(step["analysis_report"]["combined_grammage_g_m2"], 700)
        self.assertContains(response, 'name="combined_grammage_g_m2_0"', count=1)
        posted.update(box_thickness_user_override_0="", grammage_user_override_0="")
        self.client.post(url, posted, follow=True)
        step = self.client.session["full_packaging_mode_session"]["steps"][0]
        self.assertEqual(step["analysis_report"]["caliper_mm"], 4.08)
        self.assertEqual(step["analysis_report"]["combined_grammage_g_m2"], 560.2)
        json.dumps(step)

    def test_pdf_material_values_provenance_and_missing_gross_are_shared(self):
        for unit in ("mm", "in"):
            form = self.form(container_dimension_unit=unit)
            report = report_for(form, selected_board=self.board)
            analysis = {"analysis_report": report, "result": SimpleNamespace(image_rel_path="")}
            payload = _build_single_export_payload(form=form, analysis=analysis, selected_product=None, selected_material=None)
            with patch.object(container_export, "_key_value_table", wraps=container_export._key_value_table) as tables:
                pdf = container_export.build_container_selection_pdf(payload)
            self.assertTrue(pdf.getvalue().startswith(b"%PDF"))
            rows = dict(tables.call_args_list[-1].args[0])
            self.assertEqual(rows["Grammage"], report["grammage_display"])
            self.assertEqual(rows["Caliper source"], report["caliper_source_display"])
            self.assertEqual(rows["Tare source"], "Estimated from corrugated material")
            self.assertIn("lb/MSF" if unit == "in" else "g/m²", rows["Grammage"])
        form = container_form()
        report = report_for(form)
        payload = _build_single_export_payload(form=form, analysis={"analysis_report": report, "result": SimpleNamespace(image_rel_path="")}, selected_product=None, selected_material=None)
        with patch.object(container_export, "_metric_cards", wraps=container_export._metric_cards) as metrics:
            container_export.build_container_selection_pdf(payload)
        self.assertIn(("Contents weight", report["net_weight_display"]), metrics.call_args.args[0])
        self.assertIsNone(report["gross_carton_weight_g"])
        design_form = self.form(mode="design", action="run_design")
        analysis = analyze_container_form(design_form, dict(design_form.data))
        payload = _build_design_export_payload(form=design_form, analysis=analysis, selected_product=None)
        self.assertTrue(container_export.build_container_selection_pdf(payload).getvalue().startswith(b"%PDF"))
