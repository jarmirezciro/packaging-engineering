from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class PublicStaticSitemap(Sitemap):
    protocol = "https"

    _pages = {
        "company_home": {"changefreq": "monthly", "priority": 1.0},
        "blog_list": {"changefreq": "weekly", "priority": 0.8},
        "palletization_calculator": {"changefreq": "monthly", "priority": 0.9},
        "bag_selection_calculator": {"changefreq": "monthly", "priority": 0.9},
        "container_selection_calculator": {"changefreq": "monthly", "priority": 0.9},
        "transport_container_calculator": {"changefreq": "monthly", "priority": 0.9},
    }

    def items(self):
        return list(self._pages)

    def location(self, item):
        return reverse(item)

    def changefreq(self, item):
        return self._pages[item]["changefreq"]

    def priority(self, item):
        return self._pages[item]["priority"]
