from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase

from packagingapp.forms import ContainerSelectionMode1Form
from packagingapp.tools.bag.service import build_bag_analysis_report
from packagingapp.tools.container.service import build_container_analysis_report
from packagingapp.tools.palletization.service import (
    analyze_palletization_capacity,
    build_effective_palletization_config,
)
from packagingapp.tools.palletization.presenter import build_pallet_ui_contract
from packagingapp.tools.palletization.state import default_palletization_config
from packagingapp.tools.transport.modes import DEFAULT_TRANSPORT_PACKING_MODE
from packagingapp.tools.transport.service import build_container_from_config
from packagingapp.units import (
    UnsupportedUnitError,
    convert_length,
    convert_mass,
)
from packagingapp.views.full_packaging import (
    _enrich_package_payload_weight,
    _hydrate_pallet_catalogue_values,
    _resolve_packaging_weight_kg,
    _resolve_product_weight_kg,
    _transport_rows_from_selected,
)


def _catalogue_product(weight_kg):
    return SimpleNamespace(
        weight=Decimal(weight_kg),
        product_length=Decimal("100"),
        product_width=Decimal("80"),
        product_height=Decimal("60"),
        desired_qty=1,
        rotation_1=True,
        rotation_2=True,
        rotation_3=True,
    )


def _catalogue_material(weight_kg, packaging_type="BOX"):
    return SimpleNamespace(
        part_weight=Decimal(weight_kg),
        part_length=Decimal("400"),
        part_width=Decimal("300"),
        part_height=Decimal("250"),
        external_length=Decimal("400"),
        external_width=Decimal("300"),
        external_height=Decimal("250"),
        box_thickness_mm=None,
        packaging_type=packaging_type,
    )


class UnitConversionTests(SimpleTestCase):
    def test_exact_known_length_conversions(self):
        self.assertEqual(convert_length(Decimal("25.4"), "mm", "in"), Decimal("1"))
        self.assertEqual(convert_length(Decimal("304.8"), "mm", "ft"), Decimal("1"))
        self.assertEqual(convert_length(Decimal("1000"), "mm", "m"), Decimal("1"))
        self.assertEqual(convert_length(Decimal("10"), "mm", "cm"), Decimal("1"))

    def test_exact_known_mass_conversions(self):
        self.assertEqual(convert_mass(Decimal("1000"), "g", "kg"), Decimal("1"))
        self.assertEqual(convert_mass(Decimal("1000000"), "g", "t"), Decimal("1"))
        self.assertEqual(convert_mass(Decimal("453.59237"), "g", "lb"), Decimal("1"))
        self.assertEqual(convert_mass(Decimal("28.349523125"), "g", "oz"), Decimal("1"))

    def test_round_trips_preserve_decimal_values(self):
        length = Decimal("1234.56789")
        mass = Decimal("9876.54321")
        self.assertLess(
            abs(convert_length(convert_length(length, "mm", "ft"), "ft", "mm") - length),
            Decimal("1e-20"),
        )
        self.assertLess(
            abs(convert_mass(convert_mass(mass, "g", "lb"), "lb", "g") - mass),
            Decimal("1e-20"),
        )

    def test_float_round_trip_is_stable_without_conversion_rounding(self):
        value = 123.456789
        converted = convert_mass(value, "kg", "lb")
        self.assertAlmostEqual(convert_mass(converted, "lb", "kg"), value, places=12)

    def test_unsupported_and_non_numeric_values_are_rejected(self):
        with self.assertRaises(UnsupportedUnitError):
            convert_mass(1, "ton", "kg")
        with self.assertRaises(TypeError):
            convert_length("25.4", "mm", "in")
        with self.assertRaises(ValueError):
            convert_mass(float("inf"), "g", "kg")


class CatalogueBoundaryContractTests(SimpleTestCase):
    def _container_form(self):
        form = ContainerSelectionMode1Form(data={
            "mode": "single",
            "product_source": "catalogue",
            "product_l": "100",
            "product_w": "80",
            "product_h": "60",
            "desired_qty": "1",
            "r1": "on",
            "r2": "on",
            "r3": "on",
            "container_source": "catalogue",
            "box_l": "400",
            "box_w": "300",
            "box_h": "250",
        })
        self.assertTrue(form.is_valid(), form.errors.as_json())
        return form

    def test_product_catalogue_kg_becomes_grams_for_container(self):
        report = build_container_analysis_report(
            form=self._container_form(),
            result=SimpleNamespace(max_quantity=8),
            product=(100, 80, 60),
            container=(400, 300, 250),
            desired_qty=1,
            product_source="catalogue",
            selected_product=_catalogue_product("1.250"),
            selected_material=_catalogue_material("0.450"),
        )
        self.assertEqual(report["product_weight"], 1250.0)
        self.assertEqual(report["container_tare"], 450.0)

    def test_product_and_packaging_catalogue_kg_become_grams_for_bag(self):
        report = build_bag_analysis_report(
            config={"product_source": "catalogue", "bag_source": "catalogue"},
            result={
                "desired_qty": 1,
                "max_quantity": 1,
                "fits": True,
                "bag_len": 450,
                "bag_w": 330,
                "best_required": (400, 300),
                "usage": 0.8,
            },
            product=(100, 80, 60),
            quantity=1,
            selected_product=_catalogue_product("1.250"),
            selected_material=_catalogue_material("0.450", packaging_type="BAG"),
        )
        self.assertEqual(report["product_weight"], 1250.0)
        self.assertEqual(report["bag_weight"], 450.0)

    def test_packaging_catalogue_kg_becomes_grams_for_palletization(self):
        config = self._pallet_config(box_source="catalogue", box_weight="")
        built = build_effective_palletization_config(
            config,
            selected_box_material=_catalogue_material("0.450"),
        )
        self.assertTrue(built["ok"], built["messages"])
        self.assertEqual(built["effective_config"]["box_weight"], 450.0)

    def test_manual_and_catalogue_carton_weights_are_physically_equivalent(self):
        manual = analyze_palletization_capacity(
            self._pallet_config(box_source="manual", box_weight=450),
        )
        catalogue = analyze_palletization_capacity(
            self._pallet_config(box_source="catalogue", box_weight=""),
            selected_box_material=_catalogue_material("0.450"),
        )
        self.assertTrue(manual["ok"], manual["messages"])
        self.assertTrue(catalogue["ok"], catalogue["messages"])
        manual_weight_results = [
            (row["feasible_weight"], row["max_bottom_load_g"], row["weight_limit_g"])
            for row in manual["raw_results"]
        ]
        catalogue_weight_results = [
            (row["feasible_weight"], row["max_bottom_load_g"], row["weight_limit_g"])
            for row in catalogue["raw_results"]
        ]
        self.assertEqual(catalogue_weight_results, manual_weight_results)

    def test_transport_catalogue_tare_remains_kilograms(self):
        container, messages = build_container_from_config(
            {
                "container_source": "catalogue",
                "max_weight": 26500,
                "tare_weight": "",
                "packing_mode": DEFAULT_TRANSPORT_PACKING_MODE,
            },
            selected_material=_catalogue_material("2200", packaging_type="CONTAINER"),
        )
        self.assertEqual(messages, [])
        self.assertEqual(container["tare_weight"], 2200.0)

    def test_full_packaging_uses_kg_as_authoritative_mass(self):
        product = _catalogue_product("0.250")
        packaging = _catalogue_material("0.100")
        product_weight_kg = _resolve_product_weight_kg(
            {"product_source": "catalogue"}, product
        )
        packaging_weight_kg = _resolve_packaging_weight_kg(
            {"container_source": "catalogue"},
            "box_weight",
            packaging,
            source_key="container_source",
        )
        payload = _enrich_package_payload_weight(
            {"label": "Box", "length": 400, "width": 300, "height": 250, "units_per_parent": 8},
            product_weight_kg=product_weight_kg,
            packaging_weight_kg=packaging_weight_kg,
        )
        self.assertEqual(payload["weight_kg"], 2.1)
        self.assertEqual(payload["weight_g"], 2100.0)
        self.assertEqual(_transport_rows_from_selected(payload)[0]["weight"], 2.1)

    def test_full_packaging_manual_weight_ignores_stale_catalogue_selection(self):
        packaging_weight_kg = _resolve_packaging_weight_kg(
            {"container_source": "manual", "box_weight": 100},
            "box_weight",
            _catalogue_material("9.999"),
            source_key="container_source",
        )
        self.assertEqual(packaging_weight_kg, 0.1)

    @staticmethod
    def _pallet_config(*, box_source, box_weight):
        return {
            "box_source": box_source,
            "box_l": 400,
            "box_w": 300,
            "box_h": 250,
            "box_weight": box_weight,
            "max_weight_on_bottom_box": 1000,
            "pallet_source": "manual",
            "pallet_l": 1200,
            "pallet_w": 800,
            "pallet_height": 144,
            "max_stack_height": 1000,
            "max_width_stickout": 0,
            "max_length_stickout": 0,
        }


class PalletizationResultCompatibilityTests(SimpleTestCase):
    def test_correct_gram_keys_and_legacy_aliases_share_the_same_values(self):
        analysis = analyze_palletization_capacity({
            "box_source": "manual",
            "box_l": 400,
            "box_w": 300,
            "box_h": 250,
            "box_weight": 450,
            "max_weight_on_bottom_box": 1000,
            "pallet_source": "manual",
            "pallet_l": 1200,
            "pallet_w": 800,
            "pallet_height": 144,
            "max_stack_height": 1000,
            "max_width_stickout": 0,
            "max_length_stickout": 0,
        })
        self.assertTrue(analysis["ok"], analysis["messages"])
        row = analysis["raw_results"][0]
        self.assertEqual(row["max_bottom_load_g"], row["max_bottom_load_kg"])
        self.assertEqual(row["avg_bottom_load_g"], row["avg_bottom_load_kg"])
        self.assertEqual(row["weight_limit_g"], row["weight_limit_kg"])


class PalletizationManualUnitBoundaryTests(SimpleTestCase):
    @staticmethod
    def _config():
        return {
            "box_source": "manual",
            "box_l": 400,
            "box_w": 300,
            "box_h": 250,
            "box_weight": 453.59237,
            "max_weight_on_bottom_box": 1000,
            "pallet_source": "manual",
            "pallet_l": 1200,
            "pallet_w": 800,
            "pallet_height": 150,
            "max_stack_height": 1000,
            "max_width_stickout": 0,
            "max_length_stickout": 0,
        }

    @staticmethod
    def _result_signature(analysis):
        return [
            (
                row["pattern"],
                row["stacking"],
                row["total_boxes"],
                row["layers"],
                row["feasible_weight"],
            )
            for row in analysis["raw_results"]
        ]

    def test_length_units_normalize_to_the_same_palletization_inputs(self):
        metric = analyze_palletization_capacity(self._config())
        self.assertTrue(metric["ok"], metric["messages"])

        equivalent_inputs = {
            "cm": {"box_l": 40, "box_w": 30, "box_h": 25},
            "m": {"box_l": 0.4, "box_w": 0.3, "box_h": 0.25},
            "in": {
                "box_l": 15.74803149606299,
                "box_w": 11.81102362204724,
                "box_h": 9.84251968503937,
            },
            "ft": {
                "box_l": 1.312335958005249,
                "box_w": 0.984251968503937,
                "box_h": 0.820209973753281,
            },
        }

        for unit, values in equivalent_inputs.items():
            config = self._config()
            config.update(values)
            config["box_dimension_unit"] = unit
            result = analyze_palletization_capacity(config)
            self.assertTrue(result["ok"], result["messages"])
            for key in ("box_l", "box_w", "box_h"):
                self.assertAlmostEqual(
                    result["effective_config"][key],
                    metric["effective_config"][key],
                    places=7,
                )
            self.assertEqual(self._result_signature(result), self._result_signature(metric))

    def test_pallet_layout_units_normalize_height_and_constraints(self):
        config = self._config()
        config.update({
            "pallet_dimension_unit": "ft",
            "pallet_l": 3.937007874015748,
            "pallet_w": 2.6246719160104985,
            "pallet_height": 0.4921259842519685,
            "max_stack_height": 3.280839895013123,
            "max_width_stickout": 0,
            "max_length_stickout": 0,
        })
        result = analyze_palletization_capacity(config)
        self.assertTrue(result["ok"], result["messages"])
        self.assertAlmostEqual(result["effective_config"]["pallet_l"], 1200, places=7)
        self.assertAlmostEqual(result["effective_config"]["pallet_w"], 800, places=7)
        self.assertAlmostEqual(result["effective_config"]["pallet_height"], 150, places=7)
        self.assertAlmostEqual(result["effective_config"]["max_stack_height"], 1000, places=7)

    def test_metric_and_imperial_pallet_layouts_have_equivalent_results(self):
        metric = self._config()
        metric.update({
            "pallet_height": 150,
            "max_stack_height": 1000,
            "max_width_stickout": 0,
            "max_length_stickout": 0,
        })
        imperial = dict(metric)
        imperial.update({
            "pallet_dimension_unit": "in",
            "pallet_l": convert_length(1200, "mm", "in"),
            "pallet_w": convert_length(800, "mm", "in"),
            "pallet_height": convert_length(150, "mm", "in"),
            "max_stack_height": convert_length(1000, "mm", "in"),
            "max_width_stickout": "",
            "max_length_stickout": "",
        })

        metric_result = analyze_palletization_capacity(metric)
        imperial_result = analyze_palletization_capacity(imperial)

        self.assertTrue(metric_result["ok"], metric_result["messages"])
        self.assertTrue(imperial_result["ok"], imperial_result["messages"])
        self.assertEqual(
            self._result_signature(imperial_result),
            self._result_signature(metric_result),
        )

    def test_mass_units_normalize_weight_and_limit(self):
        metric = analyze_palletization_capacity(self._config())
        config = self._config()
        config.update({
            "mass_unit": "lb",
            "box_weight": 1,
            "max_weight_on_bottom_box": 2.2046226218487757,
        })
        imperial = analyze_palletization_capacity(config)
        self.assertTrue(imperial["ok"], imperial["messages"])
        self.assertAlmostEqual(imperial["effective_config"]["box_weight"], 453.59237, places=7)
        self.assertAlmostEqual(
            imperial["effective_config"]["max_weight_on_bottom_box"],
            1000,
            places=7,
        )
        self.assertEqual(self._result_signature(imperial), self._result_signature(metric))

    def test_supported_ounce_kilogram_and_tonne_values_are_converted(self):
        for unit, value, expected in (
            ("oz", 1, 28.349523125),
            ("kg", 1, 1000),
            ("t", 1, 1000000),
        ):
            config = self._config()
            config.update({"mass_unit": unit, "box_weight": value})
            built = build_effective_palletization_config(config)
            self.assertTrue(built["ok"], built["messages"])
            self.assertAlmostEqual(built["effective_config"]["box_weight"], expected, places=7)

    def test_invalid_units_fail_without_metric_fallback(self):
        config = self._config()
        config["box_dimension_unit"] = "yard"
        result = build_effective_palletization_config(config)
        self.assertFalse(result["ok"])
        self.assertTrue(any("Unsupported carton dimension unit" in item for item in result["messages"]))

        config = self._config()
        config["mass_unit"] = "banana"
        result = build_effective_palletization_config(config)
        self.assertFalse(result["ok"])
        self.assertTrue(any("Unsupported mass unit" in item for item in result["messages"]))

    def test_legacy_metric_config_without_unit_metadata_remains_valid(self):
        result = build_effective_palletization_config(self._config())
        self.assertTrue(result["ok"], result["messages"])
        self.assertEqual(result["effective_config"]["box_l"], 400.0)
        self.assertEqual(result["effective_config"]["box_weight"], 453.59237)

    def test_blank_optional_overhangs_normalize_to_zero_mm(self):
        config = self._config()
        config.update({
            "pallet_dimension_unit": "in",
            "pallet_height": convert_length(150, "mm", "in"),
            "max_stack_height": convert_length(1000, "mm", "in"),
            "max_width_stickout": "",
            "max_length_stickout": "",
        })

        built = build_effective_palletization_config(config)

        self.assertTrue(built["ok"], built["messages"])
        self.assertEqual(built["effective_config"]["max_width_stickout"], 0.0)
        self.assertEqual(built["effective_config"]["max_length_stickout"], 0.0)

    def test_blank_optional_mass_fields_remain_none(self):
        config = self._config()
        config.update({
            "box_weight": "",
            "max_weight_on_bottom_box": "",
            "max_width_stickout": "",
            "max_length_stickout": "",
        })

        result = analyze_palletization_capacity(config)

        self.assertTrue(result["ok"], result["messages"])
        self.assertIsNone(result["effective_config"]["box_weight"])
        self.assertIsNone(result["effective_config"]["max_weight_on_bottom_box"])

    def test_blank_max_stack_height_remains_required(self):
        config = self._config()
        config["max_stack_height"] = ""

        built = build_effective_palletization_config(config)

        self.assertFalse(built["ok"])
        self.assertIn("Please enter max stack height.", built["messages"])

    def test_catalogue_pallet_dimensions_remain_authoritative(self):
        material = SimpleNamespace(
            external_length=Decimal("1200"),
            external_width=Decimal("800"),
            external_height=Decimal("144"),
            part_length=Decimal("1200"),
            part_width=Decimal("800"),
            part_height=Decimal("144"),
            part_weight=Decimal("25"),
        )
        config = self._config()
        config.update({
            "pallet_source": "catalogue",
            "pallet_dimension_unit": "in",
            "pallet_l": "999",
            "pallet_w": "888",
            "pallet_height": "777",
            "max_stack_height": 50,
            "max_width_stickout": "",
            "max_length_stickout": "",
        })

        built = build_effective_palletization_config(
            config,
            selected_pallet_material=material,
        )

        self.assertTrue(built["ok"], built["messages"])
        self.assertEqual(built["effective_config"]["pallet_l"], 1200.0)
        self.assertEqual(built["effective_config"]["pallet_w"], 800.0)
        self.assertEqual(built["effective_config"]["pallet_height"], 144.0)

    def test_catalogue_pallet_hydration_preserves_local_display_unit_and_constraints(self):
        material = SimpleNamespace(
            external_length=Decimal("1200"),
            external_width=Decimal("800"),
            external_height=Decimal("144"),
            part_length=Decimal("1200"),
            part_width=Decimal("800"),
            part_height=Decimal("144"),
        )
        for display_unit, expected_dimensions in (
            ("in", (1200 / 25.4, 800 / 25.4, 144 / 25.4)),
            ("cm", (120, 80, 14.4)),
        ):
            with self.subTest(display_unit=display_unit):
                hydrated = _hydrate_pallet_catalogue_values(
                    {
                        "pallet_source": "catalogue",
                        "pallet_dimension_unit": display_unit,
                        "pallet_l": "999",
                        "pallet_w": "888",
                        "pallet_height": "777",
                        "max_stack_height": 50,
                        "max_width_stickout": "",
                        "max_length_stickout": "",
                    },
                    selected_pallet_material=material,
                )

                self.assertEqual(hydrated["pallet_dimension_unit"], display_unit)
                self.assertEqual(hydrated["max_stack_height"], 50)
                self.assertEqual(hydrated["max_width_stickout"], "")
                self.assertEqual(hydrated["max_length_stickout"], "")
                for key, expected in zip(
                    ("pallet_l", "pallet_w", "pallet_height"),
                    expected_dimensions,
                ):
                    self.assertAlmostEqual(hydrated[key], expected, places=10)

                rehydrated = _hydrate_pallet_catalogue_values(
                    hydrated,
                    selected_pallet_material=material,
                )
                self.assertEqual(rehydrated, hydrated)

    def test_catalogue_weight_ignores_manual_mass_unit(self):
        config = self._config()
        config.update({"box_source": "catalogue", "mass_unit": "lb", "box_weight": ""})
        built = build_effective_palletization_config(
            config,
            selected_box_material=_catalogue_material("0.450"),
        )
        self.assertTrue(built["ok"], built["messages"])
        self.assertEqual(built["effective_config"]["box_weight"], 450.0)

    def test_shared_ui_contract_and_state_expose_three_reusable_groups(self):
        contract = build_pallet_ui_contract(prefix="2")
        state = default_palletization_config()
        self.assertEqual(
            set(contract["unit_selectors"]),
            {"box_dimensions", "pallet_dimensions", "mass"},
        )
        self.assertEqual(state["box_dimension_unit"], "mm")
        self.assertEqual(state["pallet_dimension_unit"], "mm")
        self.assertEqual(state["mass_unit"], "g")
        self.assertEqual(contract["names"]["box_dimension_unit"], "box_dimension_unit_2")
