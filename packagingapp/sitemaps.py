from __future__ import annotations

from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from packagingapp.services.blog_repository import get_published_articles


class PublicStaticSitemap(Sitemap):
    protocol = "https"

    _pages = {
        "company_home": {"changefreq": "monthly", "priority": 1.0},
        "blog_list": {"changefreq": "weekly", "priority": 0.8},
        "palletization_calculator": {"changefreq": "weekly", "priority": 0.95},
        "bag_selection_calculator": {"changefreq": "monthly", "priority": 0.9},
        "container_selection_calculator": {"changefreq": "monthly", "priority": 0.9},
        "transport_container_calculator": {"changefreq": "monthly", "priority": 0.9},
    }

    def items(self):
        items: list[tuple[str, str]] = [("static", name) for name in self._pages]
        items.extend(("blog", article["slug"]) for article in get_published_articles())
        return items

    def location(self, item):
        item_type, value = item
        if item_type == "blog":
            return reverse("blog_detail", kwargs={"slug": value})
        return reverse(value)

    def changefreq(self, item):
        item_type, value = item
        if item_type == "blog":
            return "monthly"
        return self._pages[value]["changefreq"]

    def priority(self, item):
        item_type, value = item
        if item_type == "blog":
            return 0.75
        return self._pages[value]["priority"]
