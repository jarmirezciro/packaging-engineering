from django.conf import settings
from django.test import TestCase
from django.urls import reverse


class AppSidebarShellTests(TestCase):
    def test_representative_application_pages_use_one_shared_sidebar_shell(self):
        url_names = (
            "container_selection_mode1",
            "bag_selection_mode1",
            "multi_product_container_selection",
            "multi_product_bag_selection",
            "palletization_mode1",
            "container_tool",
            "full_packaging_mode",
            "corrugated_material_strength",
        )

        for url_name in url_names:
            with self.subTest(url_name=url_name):
                response = self.client.get(reverse(url_name))

                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'id="appShell"', count=1)
                self.assertContains(response, 'id="appSidebar"', count=1)
                self.assertContains(response, 'id="appSidebarToggle"', count=1)
                self.assertContains(response, 'id="appMobileMenuButton"', count=1)
                self.assertContains(response, 'id="appSidebarClose"', count=1)
                self.assertContains(response, 'id="appSidebarBackdrop"', count=1)
                self.assertContains(response, "js/app_sidebar.js", count=1)
                self.assertContains(response, 'class="app-nav-link active"', count=1)

    def test_sidebar_shell_exposes_persistence_and_accessibility_contract(self):
        response = self.client.get(reverse("container_selection_mode1"))

        self.assertContains(response, "kollipackSidebarCollapsed")
        self.assertContains(response, 'aria-label="Application navigation"')
        self.assertContains(response, 'aria-label="Collapse navigation"')
        self.assertContains(response, 'aria-label="Open navigation"')
        self.assertContains(response, 'aria-label="Close navigation"')
        self.assertContains(response, "@media (min-width: 992px)")
        self.assertContains(response, "@media (max-width: 991px)")
        self.assertContains(response, "prefers-reduced-motion")

    def test_shared_workspace_and_packaging_flow_are_not_width_capped(self):
        tool_response = self.client.get(reverse("container_selection_mode1"))
        flow_response = self.client.get(reverse("full_packaging_mode"))
        theme_css = (settings.BASE_DIR / "static" / "css" / "app_theme.css").read_text(
            encoding="utf-8"
        )
        sidebar_js = (settings.BASE_DIR / "static" / "js" / "app_sidebar.js").read_text(
            encoding="utf-8"
        )

        self.assertContains(tool_response, ".app-content-wrap {")
        self.assertContains(tool_response, "width: 100%;")
        self.assertContains(tool_response, "min-width: 0;")
        self.assertNotContains(tool_response, "max-width: 1400px")
        self.assertContains(flow_response, ".fp-page{display:grid;gap:1rem;width:100%;min-width:0;}")
        self.assertNotContains(flow_response, "max-width:1220px")
        self.assertIn(".app-page > *", theme_css)
        self.assertIn("min-width: 0;", theme_css)
        self.assertContains(
            tool_response,
            "padding-right: var(--app-drawer-scrollbar-gutter, 0px);",
        )
        self.assertIn("--app-drawer-scrollbar-gutter", sidebar_js)
        self.assertIn('removeProperty("--app-drawer-scrollbar-gutter")', sidebar_js)

    def test_public_blog_keeps_its_separate_readable_layout(self):
        response = self.client.get(reverse("blog_list"))
        theme_css = (settings.BASE_DIR / "static" / "css" / "app_theme.css").read_text(
            encoding="utf-8"
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "marketing/blog_list.html")
        self.assertTemplateUsed(response, "marketing_base.html")
        self.assertNotContains(response, 'id="appSidebar"')
        self.assertIn(".marketing-page {\n    max-width: 1220px;", theme_css)
        self.assertIn(".blog-article {\n    max-width: 980px;", theme_css)
