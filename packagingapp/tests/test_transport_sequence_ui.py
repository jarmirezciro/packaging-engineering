import json
import re

from django.test import TestCase
from django.urls import reverse

from packagingapp.tools.transport.modes import (
    FRONT_TO_BACK_INFILL_MODE,
    FRONT_TO_BACK_MODE,
    SPACE_EVENLY_INFILL_MODE,
    SPACE_EVENLY_MODE,
)


MODES = (
    SPACE_EVENLY_MODE,
    FRONT_TO_BACK_MODE,
    SPACE_EVENLY_INFILL_MODE,
    FRONT_TO_BACK_INFILL_MODE,
)


def transport_post(mode, *, workflow=False):
    data = {
        "container_source": "manual",
        "container_l": "500",
        "container_w": "300",
        "container_h": "200",
        "item_name[]": ["A", "B"],
        "item_length[]": ["100", "100"],
        "item_width[]": ["100", "100"],
        "item_height[]": ["100", "100"],
        "item_qty[]": ["1", "1"],
        "item_weight[]": ["0", "0"],
        "item_sequence[]": ["2", "3"],
        "item_r1[]": ["0", "0"],
        "item_r2[]": ["0", "0"],
        "item_r3[]": ["1", "1"],
        "item_stackable[]": ["1", "1"],
    }
    if workflow:
        data.update(
            action="run_step",
            index="0",
            step_action_0="run_analysis",
            container_source_0="manual",
            packing_mode_0=mode,
            container_l_0="500",
            container_w_0="300",
            container_h_0="200",
        )
    else:
        data.update(action="run_analysis", packing_mode=mode)
    return data


def rendered_sequence_inputs(response):
    fields = re.findall(
        r'<input[^>]*name="item_sequence\[\]"[^>]*>',
        response.content.decode(),
    )
    # The shared Add row <template> contains one more input after the live rows.
    return fields[:-1]


class TransportSequenceUiTests(TestCase):
    def assert_rendered_sequences(self, response, expected, *, locked):
        locked_modes = re.search(
            r'data-transport-sequence-locked-modes="([^"]*)"',
            response.content.decode(),
        )
        self.assertIsNotNone(locked_modes)
        self.assertCountEqual(
            locked_modes[1].split(), (SPACE_EVENLY_MODE, SPACE_EVENLY_INFILL_MODE)
        )
        fields = rendered_sequence_inputs(response)
        self.assertEqual(len(fields), len(expected))
        for field, sequence in zip(fields, expected):
            self.assertIn(f'value="{sequence}"', field)
            self.assertEqual(" readonly" in field, locked)
            self.assertEqual(' aria-readonly="true"' in field, locked)

    def test_standalone_and_public_submission_rerender_all_modes(self):
        for url_name in ("container_tool", "transport_container_calculator"):
            for mode in MODES:
                with self.subTest(surface=url_name, mode=mode):
                    response = self.client.post(
                        reverse(url_name), transport_post(mode)
                    )
                    self.assertEqual(response.status_code, 200)
                    self.assertIsNotNone(response.context["result"])
                    locked = mode in (SPACE_EVENLY_MODE, SPACE_EVENLY_INFILL_MODE)
                    expected = [1, 1] if locked else [2, 3]
                    self.assertEqual(
                        [int(row["sequence"]) for row in response.context["product_rows"]],
                        expected,
                    )
                    self.assert_rendered_sequences(response, expected, locked=locked)

    def test_packaging_flow_submission_rerender_all_modes(self):
        url = reverse("full_packaging_mode")
        self.client.post(
            url,
            {"action": "add_step", "after_index": "start", "step_type": "transport"},
        )
        for mode in MODES:
            with self.subTest(mode=mode):
                response = self.client.post(url, transport_post(mode, workflow=True))
                self.assertEqual(response.status_code, 302)
                workflow = self.client.session["full_packaging_mode_session"]
                json.dumps(workflow)
                step = workflow["steps"][0]
                self.assertEqual(step["config"]["packing_mode"], mode)
                locked = mode in (SPACE_EVENLY_MODE, SPACE_EVENLY_INFILL_MODE)
                expected = [1, 1] if locked else [2, 3]
                self.assertEqual(
                    [int(row["sequence"]) for row in step["config"]["product_rows"]],
                    expected,
                )
                rendered = self.client.get(url)
                self.assertEqual(rendered.status_code, 200)
                self.assert_rendered_sequences(rendered, expected, locked=locked)
