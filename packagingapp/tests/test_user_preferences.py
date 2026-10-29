from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.contrib.sessions.backends.db import SessionStore

from packagingapp.catalogue_units import catalogue_units_from_request
from packagingapp.forms import UserPreferencesForm
from packagingapp.models import UserPreferences
from packagingapp.user_preferences import (
    LEGACY_UNIT_DEFAULTS,
    apply_user_unit_defaults,
    unit_defaults_for_user,
)
from packagingapp.views.bag_selection import _read_raw_bag_config
from packagingapp.views.container_selection import _read_raw_container_config
from packagingapp.views.full_packaging import (
    _new_bag_step,
    _new_container_step,
    _new_pallet_step,
    _new_transport_step,
)
from packagingapp.views.palletization import _read_raw_palletization_config


User = get_user_model()


class UserPreferenceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="unit-preferences",
            password="password-123",
        )

    def set_preferences(self, **values):
        return UserPreferences.objects.create(user=self.user, **values)

    def test_missing_preferences_keep_legacy_defaults(self):
        self.assertEqual(unit_defaults_for_user(self.user), LEGACY_UNIT_DEFAULTS)
        self.assertEqual(unit_defaults_for_user(None), LEGACY_UNIT_DEFAULTS)

    def test_settings_page_saves_the_three_centralized_choices(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("user_settings"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Units &amp; Display")

        response = self.client.post(
            reverse("user_settings"),
            {
                "default_length_unit": "in",
                "default_small_mass_unit": "lb",
                "default_large_mass_unit": "lb",
            },
        )
        self.assertRedirects(response, reverse("user_settings"))
        preferences = UserPreferences.objects.get(user=self.user)
        self.assertEqual(preferences.default_length_unit, "in")
        self.assertEqual(preferences.default_small_mass_unit, "lb")
        self.assertEqual(preferences.default_large_mass_unit, "lb")

    def test_invalid_units_are_rejected(self):
        form = UserPreferencesForm(
            data={
                "default_length_unit": "yd",
                "default_small_mass_unit": "g",
                "default_large_mass_unit": "stone",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("default_length_unit", form.errors)
        self.assertIn("default_large_mass_unit", form.errors)

    def test_invalid_persisted_values_fall_back_without_breaking_tools(self):
        self.set_preferences(
            default_length_unit="yd",
            default_small_mass_unit="g",
            default_large_mass_unit="stone",
        )
        self.assertEqual(
            unit_defaults_for_user(self.user),
            {"length": "mm", "small_mass": "g", "large_mass": "kg"},
        )

    def test_new_standalone_configs_use_account_defaults(self):
        self.set_preferences(
            default_length_unit="in",
            default_small_mass_unit="lb",
            default_large_mass_unit="lb",
        )
        factory = RequestFactory()
        request = factory.get("/")
        request.user = self.user

        container = _read_raw_container_config(
            request,
            user=self.user,
            initialize_user_units=True,
        )
        bag = _read_raw_bag_config(
            request,
            user=self.user,
            initialize_user_units=True,
        )
        pallet = _read_raw_palletization_config(
            request,
            user=self.user,
            initialize_user_units=True,
        )
        self.assertEqual(container["product_dimension_unit"], "in")
        self.assertEqual(container["container_mass_unit"], "lb")
        self.assertEqual(bag["bag_dimension_unit"], "in")
        self.assertEqual(bag["bag_mass_unit"], "lb")
        self.assertEqual(pallet["pallet_dimension_unit"], "in")
        self.assertEqual(pallet["mass_unit"], "lb")

    def test_signed_in_tool_gets_account_defaults_in_rendered_selectors(self):
        self.set_preferences(
            default_length_unit="in",
            default_small_mass_unit="lb",
            default_large_mass_unit="lb",
        )
        self.client.force_login(self.user)
        for url_name in (
            "container_selection_mode1",
            "bag_selection_mode1",
            "palletization_mode1",
            "container_tool",
            "corrugated_material_strength",
        ):
            with self.subTest(url_name=url_name):
                response = self.client.get(reverse(url_name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'value="in"')
                self.assertContains(response, 'value="lb"')

    def test_explicit_local_state_wins_and_does_not_mutate_preferences(self):
        self.set_preferences(
            default_length_unit="in",
            default_small_mass_unit="lb",
            default_large_mass_unit="lb",
        )
        config = {
            "product_dimension_unit": "cm",
            "container_dimension_unit": "cm",
            "product_mass_unit": "g",
            "container_mass_unit": "g",
        }
        apply_user_unit_defaults(config, self.user, "container")
        self.assertEqual(config["product_dimension_unit"], "cm")
        self.assertEqual(config["container_mass_unit"], "g")
        self.assertEqual(UserPreferences.objects.get(user=self.user).default_length_unit, "in")

    def test_new_full_packaging_steps_use_defaults_but_legacy_steps_do_not_change(self):
        self.set_preferences(
            default_length_unit="in",
            default_small_mass_unit="lb",
            default_large_mass_unit="lb",
        )
        self.assertEqual(_new_container_step(self.user)["config"]["product_dimension_unit"], "in")
        self.assertEqual(_new_bag_step(self.user)["config"]["bag_mass_unit"], "lb")
        self.assertEqual(_new_pallet_step(self.user)["config"]["mass_unit"], "lb")
        transport = _new_transport_step(self.user)["config"]
        self.assertEqual(transport["transport_dimension_unit"], "in")
        self.assertEqual(transport["transport_mass_unit"], "lb")
        self.assertEqual(_new_container_step()["config"]["product_dimension_unit"], "mm")

    def test_catalogue_uses_user_defaults_then_preserves_local_session_override(self):
        self.set_preferences(
            default_length_unit="in",
            default_small_mass_unit="lb",
            default_large_mass_unit="lb",
        )
        request = RequestFactory().get("/catalogues/")
        request.user = self.user
        request.session = SessionStore()
        units, error = catalogue_units_from_request(request)
        self.assertIsNone(error)
        self.assertEqual(units, {"length": "in", "mass": "lb"})

        request.session["catalogue_length_unit"] = "cm"
        request.session["catalogue_mass_unit"] = "oz"
        units, error = catalogue_units_from_request(request)
        self.assertIsNone(error)
        self.assertEqual(units, {"length": "cm", "mass": "oz"})
