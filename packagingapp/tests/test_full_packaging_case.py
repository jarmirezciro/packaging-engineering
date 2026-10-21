from django.test import TestCase
from django.urls import reverse


class FullPackagingCaseTests(TestCase):
    def test_think_beyond_the_box_case_loads_and_remains_json_safe(self):
        case_url = reverse("full_packaging_case", args=["think-beyond-the-box"])
        for query in ("", "?reset=1"):
            with self.subTest(query=query):
                response = self.client.get(case_url + query, follow=True)

                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    response.context["case_preset"]["slug"],
                    "think-beyond-the-box",
                )
                self.assertEqual(
                    [step["type"] for step in response.context["steps"]],
                    ["container", "pallet", "transport"],
                )

        session = self.client.session
        workflow = session["full_packaging_mode_session_case_think-beyond-the-box"]
        self.assertEqual(
            [step["type"] for step in workflow["steps"]],
            ["container", "pallet", "transport"],
        )
