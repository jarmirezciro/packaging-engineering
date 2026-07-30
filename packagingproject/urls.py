"""Root URL configuration for the Packaging Engineering application."""

from django.conf import settings
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path, re_path
from django.views.static import serve as serve_media

from packagingapp.sitemaps import PublicStaticSitemap
from packagingapp.views.marketing import robots_txt


urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("sitemap.xml", sitemap, {"sitemaps": {"public": PublicStaticSitemap}}, name="sitemap"),
    path("robots.txt", robots_txt, name="robots_txt"),
    path("", include("packagingapp.urls")),
]

# The application creates runtime engineering images and stores uploaded
# catalogue files under MEDIA_ROOT. During the Railway soft launch, serve those
# files from the same Django service and a persistent Railway Volume.
#
# This is intentionally controlled by SERVE_MEDIA_FILES so it can be disabled
# later when media is moved to object storage or a dedicated media service.
if settings.SERVE_MEDIA_FILES:
    urlpatterns += [
        re_path(
            r"^media/(?P<path>.*)$",
            serve_media,
            {"document_root": settings.MEDIA_ROOT},
        ),
    ]
