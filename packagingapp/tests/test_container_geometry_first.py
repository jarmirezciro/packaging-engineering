"""Geometry-first UI, read-only catalogue overrides, and accepted snapshots."""

import json
from html.parser import HTMLParser
from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, TestCase
from django.urls import reverse

from packagingapp.models import CorrugatedBoardConstruction, PackagingCatalogue, PackagingMaterial, ProductCatalogue, Product
from packagingapp.tools.container import export as pdf_export
from packagingapp.tools.container.carton_tare import attach_carton_weight_metadata
from packagingapp.tools.container.corrugated_material import gsm_to_lb_msf
from packagingapp.tools.container.presenter import build_container_advanced_context
from packagingapp.tools.container.serializers import sanitize_container_config_for_session
from packagingapp.tools.container.service import (
    analyze_container_form, apply_catalogue_choices, build_container_analysis_report,
    build_container_form, get_corrugated_materials,
)
from packagingapp.tools.container.state import default_container_config
from packagingapp.views.container_selection import _build_design_export_payload, _build_single_export_payload, _read_raw_container_config
from packagingapp.views import full_packaging as flow


class FormMarkup(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.nodes = []
        self.feed(html)

    def handle_starttag(self, tag, attributes):
        self.nodes.append((tag, dict(attributes)))


class GeometryFirstContainerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.board = CorrugatedBoardConstruction.objects.get(code="FEFCO_C_175_140_175")
        cls.catalogue = PackagingCatalogue.objects.create(name="Geometry-first cartons")
        cls.product_catalogue = ProductCatalogue.objects.create(name="Geometry-first products")
        cls.product = Product.objects.create(catalogue=cls.product_catalogue, product_id="P1", product_name="Catalogue product",
                                            product_length=100, product_width=80, product_height=50, weight="0.100",
                                            rotation_1=True, rotation_2=True, rotation_3=True)
        cls.product.refresh_from_db()

    def sku(self, **values):
        defaults = dict(catalogue=self.catalogue, part_number="C" + str(PackagingMaterial.objects.count()),
                        part_description="RSC carton", packaging_type="BOX", branding="Brand1", packaging_materials="Corrugated board",
                        part_length=200, part_width=160, part_height=100, carton_style="0201")
        defaults.update(values)
        item = PackagingMaterial.objects.create(**defaults)
        item.refresh_from_db()
        return item

    def config(self, sku=None, product=None, **values):
        config = default_container_config()
        config.update(product_l="100", product_w="80", product_h="50", product_weight="100", desired_qty="5",
                      box_l="200", box_w="160", box_h="100", action="run_single")
        if sku is not None:
            config.update(container_source="catalogue", catalogue_id=str(self.catalogue.pk), container_id=str(sku.pk))
        if product is not None:
            config.update(product_source="catalogue", product_catalogue_id=str(self.product_catalogue.pk), selected_product_id=str(product.pk))
        config.update(values)
        config["container_override_target"] = "catalogue:" + str(sku.pk) if sku is not None and config["mode"] != "design" else "manual"
        config["product_override_target"] = "catalogue:" + str(product.pk) if product is not None else "manual"
        for key, flag in (("box_thickness_mm", "box_thickness_user_override"), ("combined_grammage_g_m2", "grammage_user_override"),
                          ("box_weight", "box_weight_user_override"), ("box_max_payload", "box_max_payload_user_override"),
                          ("product_weight", "product_weight_user_override")):
            if key in values and flag not in values:
                config[flag] = "1"
        return sanitize_container_config_for_session(config)

    def form(self, config, sku=None, product=None):
        request = SimpleNamespace(method="POST", POST=config)
        form = build_container_form(request, config, product, sku)
        apply_catalogue_choices(form, [self.catalogue], [self.product_catalogue], get_corrugated_materials())
        self.assertTrue(form.is_valid(), form.errors)
        return form

    def report(self, config, sku=None, product=None):
        return build_container_analysis_report(form=self.form(config, sku, product), result=SimpleNamespace(max_quantity=8),
            product=(100, 80, 50), container=(200, 160, 100), desired_qty=5,
            product_source=config["product_source"], mode=config["mode"], selected_product=product, selected_material=sku)

    def render_stub(self):
        return patch("packagingapp.tools.container.service.run_mode1_and_render", return_value=SimpleNamespace(max_quantity=8, image_rel_path="", threejs_scene={}))

    def test_new_design_advanced_is_collapsed_with_reference_values_present(self):
        response = self.client.get(reverse("container_selection_mode1"), {"mode": "design"})
        self.assertEqual(response.status_code, 200)
        advanced = response.context["container_advanced"]
        self.assertFalse(advanced["product_open"])
        self.assertFalse(advanced["container_open"])
        self.assertEqual(float(advanced["inputs"]["box_thickness_mm"]), 4.08)
        self.assertEqual(float(advanced["inputs"]["combined_grammage_g_m2"]), 560.2)
        self.assertEqual(advanced["properties"]["grammage_source"], "reference_assumption")
        markup = FormMarkup(response.content.decode())
        panels = [attrs for _, attrs in markup.nodes if "data-tool-advanced-panel" in attrs]
        self.assertEqual(len(panels), 2)
        self.assertTrue(all("hidden" in panel for panel in panels))
        for name in ("product_weight", "product_shape", "box_thickness_mm", "combined_grammage_g_m2", "box_weight", "box_max_payload"):
            nodes = [attrs for _, attrs in markup.nodes if attrs.get("name") == name]
            self.assertEqual(len(nodes), 1, name)
            self.assertNotIn("disabled", nodes[0])
        self.assertNotContains(response, "Reset caliper")
        self.assertNotContains(response, "Reset grammage")

    def test_catalogue_sources_populate_fields_independently(self):
        for values, caliper, gsm in (
            ({"box_thickness_mm": 3.2, "combined_grammage_g_m2": 420, "part_weight": ".350"}, 3.2, 420),
            ({"box_thickness_mm": 3.2}, 3.2, 560.2),
            ({"corrugated_construction": self.board}, 4.08, 560.2),
            ({}, 4.08, 560.2),
        ):
            with self.subTest(values=values):
                sku = self.sku(**values)
                config = self.config(sku)
                form = self.form(config, sku)
                advanced = build_container_advanced_context(config, form, selected_material=sku)
                self.assertEqual(float(advanced["inputs"]["box_thickness_mm"]), caliper)
                self.assertEqual(float(advanced["inputs"]["combined_grammage_g_m2"]), gsm)
                self.assertGreater(float(advanced["inputs"]["box_weight"]), 0)

    def test_reference_assumptions_require_applicable_cartons(self):
        for values in ({"packaging_type": "CRATE", "packaging_materials": "Plastic"},
                       {"packaging_type": "PALLET"}, {"packaging_type": "TRAILER"},
                       {"packaging_type": "CONTAINER"}, {"carton_style": None}, {"packaging_materials": "Plastic"}):
            sku = self.sku(**values)
            report = self.report(self.config(sku), sku)
            self.assertIsNone(report["combined_grammage_g_m2"])
            self.assertIsNone(report["carton_tare_g"])
            self.assertIsNone(report["gross_carton_weight_g"])
        sku = self.sku()
        assumed = self.report(self.config(sku), sku)
        self.assertEqual(assumed["grammage_source"], "reference_assumption")
        self.assertTrue(assumed["carton_tare_assumed_material"])
        self.assertIn("assumed", assumed["carton_tare_source_display"])
        self.assertEqual(assumed["weight_status"], "gross_estimated")

    def test_actual_tare_survives_grammage_override_and_explicit_tare_wins(self):
        sku = self.sku(box_thickness_mm=3.2, combined_grammage_g_m2=420, part_weight=".350")
        initial = self.report(self.config(sku), sku)
        overridden = self.report(self.config(sku, combined_grammage_g_m2="700", box_thickness_mm="5"), sku)
        self.assertEqual(overridden["combined_grammage_g_m2"], 700)
        self.assertEqual(overridden["caliper_mm"], 5)
        self.assertEqual(overridden["carton_tare_g"], 350)
        self.assertEqual(overridden["carton_tare_source"], "catalogue")
        self.assertEqual(overridden["gross_carton_weight_g"], initial["gross_carton_weight_g"])
        manual = self.report(self.config(sku, box_weight="400"), sku)
        self.assertEqual(manual["carton_tare_source"], "manual")
        self.assertEqual(manual["gross_carton_weight_g"], 1200)
        self.assertEqual(manual["effective_specification"]["carton_tare_baseline_g"], 350)
        sku.refresh_from_db()
        self.assertEqual(float(sku.part_weight), .35)
        self.assertEqual(float(sku.combined_grammage_g_m2), 420)
        self.assertEqual(float(sku.box_thickness_mm), 3.2)

    def test_effective_grammage_changes_estimate_and_caliper_changes_only_derived_size(self):
        sku = self.sku(corrugated_construction=self.board)
        baseline = self.report(self.config(sku), sku)
        caliper = self.report(self.config(sku, box_thickness_mm="5"), sku)
        grammage = self.report(self.config(sku, combined_grammage_g_m2="700"), sku)
        self.assertEqual(caliper["carton_tare_g"], baseline["carton_tare_g"])
        self.assertNotEqual(caliper["external_length"], baseline["external_length"])
        self.assertEqual(grammage["external_length"], baseline["external_length"])
        self.assertGreater(grammage["carton_tare_g"], baseline["carton_tare_g"])
        sku.external_length, sku.external_width, sku.external_height = 220, 180, 120
        sku.save()
        explicit = self.report(self.config(sku, box_thickness_mm="10"), sku)
        self.assertEqual((explicit["external_length"], explicit["external_width"], explicit["external_height"]), (220, 180, 120))

    def test_restore_each_property_returns_its_source(self):
        sku = self.sku(box_thickness_mm=3.2, combined_grammage_g_m2=420, part_weight=".350")
        config = self.config(sku, box_thickness_mm="5", combined_grammage_g_m2="700", box_weight="400")
        config["grammage_user_override"] = ""
        report = self.report(config, sku)
        self.assertEqual((report["caliper_mm"], report["combined_grammage_g_m2"], report["carton_tare_g"]), (5, 420, 400))
        config["box_thickness_user_override"] = config["box_weight_user_override"] = ""
        report = self.report(config, sku)
        self.assertEqual((report["caliper_mm"], report["combined_grammage_g_m2"], report["carton_tare_g"]), (3.2, 420, 350))

    def test_top5_scope_prevents_leakage_and_preserves_same_candidate_override(self):
        first = self.sku(part_number="FIRST", combined_grammage_g_m2=400, part_weight=".350")
        second = self.sku(part_number="SECOND", combined_grammage_g_m2=600, part_weight=".250")
        config = self.config(first, mode="optimal", action="select_candidate", combined_grammage_g_m2="700", box_weight="450")
        form = self.form(config, first)
        with self.render_stub(), patch("packagingapp.tools.container.service.render_product_base_unit", return_value=""):
            analysis = analyze_container_form(form, config, selected_material=first, materials=[first, second])
        reports = {row["material"].pk: row for row in analysis["top5"]}
        self.assertEqual(reports[first.pk]["combined_grammage_g_m2"], 700)
        self.assertEqual(reports[first.pk]["carton_tare_g"], 450)
        self.assertEqual(reports[second.pk]["combined_grammage_g_m2"], 600)
        self.assertEqual(reports[second.pk]["carton_tare_g"], 250)
        self.assertEqual(sanitize_container_config_for_session(config)["grammage_user_override"], "1")
        request = RequestFactory().post("/", {**config, "container_id": str(second.pk)})
        switched = _read_raw_container_config(request)
        self.assertEqual(switched["grammage_user_override"], "")
        self.assertEqual(switched["box_weight_user_override"], "")
        self.assertEqual(self.report(switched, second)["combined_grammage_g_m2"], 600)

    def test_product_catalogue_mass_override_is_effective_and_read_only(self):
        sku = self.sku(part_weight=".350")
        config = self.config(sku, self.product, product_weight="200")
        report = self.report(config, sku, self.product)
        self.assertEqual(report["net_weight"], 1600)
        self.assertEqual(report["gross_carton_weight_g"], 1950)
        self.assertEqual(report["product_weight_source"], "manual")
        self.assertEqual(report["effective_specification"]["product_weight_baseline_g"], 100)
        config["product_weight_user_override"] = ""
        self.assertEqual(self.report(config, sku, self.product)["net_weight"], 800)
        self.product.refresh_from_db()
        self.assertEqual(float(self.product.weight), .1)

    def test_metric_imperial_overrides_and_reference_values_keep_canonical_precision(self):
        sku = self.sku()
        config = self.config(sku, container_dimension_unit="in", box_thickness_mm="0.161",
                             box_thickness_user_override="", combined_grammage_g_m2="114.7", grammage_user_override="")
        report = self.report(config, sku)
        self.assertEqual(report["caliper_mm"], 4.08)
        self.assertEqual(report["combined_grammage_g_m2"], 560.2)
        metric = self.report(self.config(sku, combined_grammage_g_m2="700.1234567", box_weight="400"), sku)
        imperial = self.report(self.config(sku, container_dimension_unit="in", combined_grammage_g_m2=str(gsm_to_lb_msf("700.1234567")), box_weight="0.4", container_mass_unit="kg"), sku)
        self.assertEqual(metric["combined_grammage_g_m2"], imperial["combined_grammage_g_m2"])
        self.assertEqual(metric["gross_carton_weight_g"], imperial["gross_carton_weight_g"])
        self.assertIn("lb/MSF", imperial["grammage_display"])

    def test_optional_mass_never_blocks_geometry_and_never_becomes_false_gross(self):
        sku = self.sku(carton_style=None)
        config = self.config(sku, product_weight="", product_weight_user_override="")
        form = self.form(config, sku)
        with self.render_stub(), patch("packagingapp.tools.container.service.render_product_base_unit", return_value=""):
            analysis = analyze_container_form(form, config, selected_material=sku)
        self.assertTrue(analysis["ok"])
        self.assertEqual(analysis["result"].max_quantity, 8)
        self.assertEqual(analysis["analysis_report"]["weight_status"], "unknown")
        known_contents = self.report(self.config(sku), sku)
        self.assertEqual(known_contents["weight_status"], "net_only")
        self.assertIsNone(known_contents["gross_carton_weight_g"])

    def test_analysis_views_never_save_product_or_packaging_records(self):
        sku = self.sku(part_weight=".350", combined_grammage_g_m2=420)
        config = self.config(sku, self.product, product_weight="200", combined_grammage_g_m2="700", box_weight="400")
        with patch.object(PackagingMaterial, "save", side_effect=AssertionError("Catalogue save during analysis")), patch.object(Product, "save", side_effect=AssertionError("Product save during analysis")), self.render_stub(), patch("packagingapp.tools.container.service.render_product_base_unit", return_value=""):
            response = self.client.post(reverse("container_selection_mode1"), config)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["analysis_report"]["gross_carton_weight_g"], 2000)
        self.assertEqual(float(response.context["container_advanced"]["inputs"]["combined_grammage_g_m2"]), 700)

    def test_invalid_advanced_inputs_expand_their_sections_in_both_surfaces(self):
        config = self.config(box_weight="-1", product_weight="-2")
        response = self.client.post(reverse("container_selection_mode1"), config)
        self.assertTrue(response.context["container_advanced"]["product_open"])
        self.assertTrue(response.context["container_advanced"]["container_open"])
        url = reverse("full_packaging_mode")
        self.client.post(url, {"action": "add_step", "step_type": "container"})
        posted = {f"{key}_0": value for key, value in config.items()}
        response = self.client.post(url, {**posted, "action": "run_step", "index": "0"}, follow=True)
        self.assertEqual(response.status_code, 200)
        step = response.context["steps"][0]
        self.assertIn("box_weight", step["container_form"].errors)
        self.assertTrue(step["container_advanced"]["container_open"])
        self.assertTrue(step["container_advanced"]["product_open"])

    def test_accepted_effective_snapshot_propagates_and_edits_clear_downstream(self):
        sku = self.sku(corrugated_construction=self.board, part_weight=".350")
        config = self.config(sku, self.product, box_thickness_mm="5", product_weight="200", box_weight="400")
        step = flow._new_container_step()
        downstream = flow._new_pallet_step()
        steps = [step, downstream]
        posted = {f"{key}_0": value for key, value in config.items()}
        with self.render_stub(), patch("packagingapp.tools.container.service.render_product_base_unit", return_value=""):
            flow._process_container_step(step, steps, 0, posted)
        pending = step["pending_result"]
        self.assertEqual(pending["weight_kg"], 2)
        self.assertEqual(pending["length"], 210)
        self.assertEqual(pending["effective_specification"]["source_packaging_item_id"], str(sku.pk))
        flow._accept_pending_result(step)
        inherited = flow._apply_payload_to_config(downstream["config"], "pallet", step["selected"])
        self.assertEqual(inherited["box_l"], 210)
        self.assertEqual(inherited["box_weight"], 2000)
        carried = flow._carry_effective_container_specification({}, step["selected"])
        self.assertEqual(carried["source_container_item_id"], str(sku.pk))
        self.assertEqual(carried["upstream_packaging_specification"]["carton_tare_g"], 400)
        downstream["selected"] = {"weight_kg": 20}
        posted["box_thickness_mm_0"] = "6"
        with self.render_stub(), patch("packagingapp.tools.container.service.render_product_base_unit", return_value=""):
            flow._process_container_step(step, steps, 0, posted)
        self.assertIsNone(step["selected"])
        self.assertIsNone(downstream["selected"])
        self.assertEqual(step["pending_result"]["length"], 212)
        json.dumps(step["pending_result"])

    def test_pdf_uses_effective_product_and_material_values(self):
        sku = self.sku(part_weight=".350", combined_grammage_g_m2=420)
        config = self.config(sku, self.product, product_weight="200", combined_grammage_g_m2="700")
        form = self.form(config, sku, self.product)
        report = self.report(config, sku, self.product)
        payload = _build_single_export_payload(form=form, analysis={"analysis_report": report, "result": SimpleNamespace(image_rel_path="")}, selected_product=self.product, selected_material=sku)
        self.assertEqual(payload["product"]["weight"], "200 g")
        with patch.object(pdf_export, "_key_value_table", wraps=pdf_export._key_value_table) as tables:
            self.assertTrue(pdf_export.build_container_selection_pdf(payload).getvalue().startswith(b"%PDF"))
        rows = dict(tables.call_args_list[-1].args[0])
        self.assertEqual(rows["Grammage"], "700.0 g/m²")
        self.assertEqual(rows["Tare source"], "Catalogue actual")
        design_config = self.config(product=self.product, mode="design", action="run_design", corrugated_material_id=self.board.code, product_weight="200")
        design_form = self.form(design_config, product=self.product)
        analysis = analyze_container_form(design_form, design_config, selected_product=self.product)
        payload = _build_design_export_payload(form=design_form, analysis=analysis, selected_product=self.product)
        self.assertEqual(payload["product"]["weight"], "200 g")

    def test_payload_override_is_in_the_effective_specification(self):
        sku = self.sku(part_weight=".350")
        report = self.report(self.config(sku, box_max_payload="1000"), sku)
        self.assertEqual(report["payload_capacity"], 1000)
        self.assertEqual(report["effective_specification"]["payload_capacity_g"], 1000)
        self.assertEqual(report["effective_specification"]["payload_capacity_source"], "manual")

    def test_default_design_tare_is_labelled_as_using_assumed_material(self):
        config = self.config(mode="design", action="run_design", corrugated_material_id=self.board.code)
        analysis = analyze_container_form(self.form(config), config)
        self.assertTrue(analysis["analysis_report"]["carton_tare_assumed_material"])
        self.assertIn("assumed material", analysis["analysis_report"]["carton_tare_source_display"])
        config["corrugated_material_user_selected"] = "1"
        analysis = analyze_container_form(self.form(config), config)
        self.assertEqual(analysis["analysis_report"]["grammage_source"], "construction")

    def test_effective_snapshot_retains_upstream_weight_uncertainty(self):
        sku = self.sku(part_weight=".350")
        report = self.report(self.config(sku), sku)
        for upstream_status, expected_status in (("gross_estimated", "gross_estimated"), ("net_only", "net_only")):
            payload = attach_carton_weight_metadata({}, report, upstream={"weight_status": upstream_status})
            self.assertEqual(payload["weight_status"], expected_status)
            self.assertEqual(payload["effective_specification"]["weight_status"], expected_status)
            self.assertEqual(payload["effective_specification"]["gross_carton_weight_g"], payload["gross_carton_weight_g"])
            if upstream_status == "net_only":
                self.assertNotIn("weight_kg", payload)
                self.assertIsNone(payload["effective_specification"]["gross_carton_weight_g"])
        self.assertEqual(report["effective_specification"]["weight_status"], "gross_known")

    def test_accept_action_recalculates_submitted_analysis_overrides(self):
        sku = self.sku(part_weight=".350", combined_grammage_g_m2=420)
        config = self.config(sku, self.product)
        url = reverse("full_packaging_mode")
        self.client.post(url, {"action": "add_step", "step_type": "container"})
        posted = {f"{key}_0": value for key, value in config.items()}
        with self.render_stub(), patch("packagingapp.tools.container.service.render_product_base_unit", return_value=""):
            self.client.post(url, {**posted, "action": "run_step", "index": "0"})
            posted.update(combined_grammage_g_m2_0="700", grammage_user_override_0="1", product_weight_0="200", product_weight_user_override_0="1")
            response = self.client.post(url, {**posted, "action": "use_step_result", "index": "0"})
        self.assertEqual(response.status_code, 302)
        selected = self.client.session["full_packaging_mode_session"]["steps"][0]["selected"]
        self.assertEqual(selected["weight_kg"], 1.95)
        self.assertEqual(selected["effective_specification"]["combined_grammage_g_m2"], 700)
        self.assertEqual(selected["effective_specification"]["source_packaging_item_id"], str(sku.pk))
        sku.refresh_from_db()
        self.assertEqual(float(sku.combined_grammage_g_m2), 420)
