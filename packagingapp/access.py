from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import Http404

from .models import PackagingCatalogue, ProductCatalogue


LOGIN_REQUIRED_MESSAGE = "Please sign in to create or manage private catalogues."


def user_can_manage_private_catalogues(user):
    return bool(getattr(user, "is_authenticated", False))


def can_manage_packaging_catalogue(user, catalogue):
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
        return True
    return catalogue.owner_id == user.id


def can_manage_product_catalogue(user, catalogue):
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
        return True
    return catalogue.owner_id == user.id


def visible_packaging_catalogues(user):
    qs = PackagingCatalogue.objects.filter(is_public=True)
    if getattr(user, "is_authenticated", False):
        qs = PackagingCatalogue.objects.filter(Q(is_public=True) | Q(owner=user))
    return qs.distinct().order_by("name")


def visible_product_catalogues(user):
    qs = ProductCatalogue.objects.filter(is_public=True)
    if getattr(user, "is_authenticated", False):
        qs = ProductCatalogue.objects.filter(Q(is_public=True) | Q(owner=user))
    return qs.distinct().order_by("name")


def manageable_packaging_catalogues(user):
    if not getattr(user, "is_authenticated", False):
        return PackagingCatalogue.objects.none()
    if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
        return PackagingCatalogue.objects.all().order_by("name")
    return PackagingCatalogue.objects.filter(owner=user).order_by("name")


def manageable_product_catalogues(user):
    if not getattr(user, "is_authenticated", False):
        return ProductCatalogue.objects.none()
    if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
        return ProductCatalogue.objects.all().order_by("name")
    return ProductCatalogue.objects.filter(owner=user).order_by("name")


def get_visible_packaging_catalogue_or_404(user, pk):
    catalogue = visible_packaging_catalogues(user).filter(pk=pk).first()
    if catalogue is None:
        raise Http404("Packaging catalogue not found.")
    return catalogue


def get_visible_product_catalogue_or_404(user, pk):
    catalogue = visible_product_catalogues(user).filter(pk=pk).first()
    if catalogue is None:
        raise Http404("Product catalogue not found.")
    return catalogue


def get_manageable_packaging_catalogue_or_404(user, pk):
    catalogue = manageable_packaging_catalogues(user).filter(pk=pk).first()
    if catalogue is None:
        raise Http404("Packaging catalogue not found.")
    return catalogue


def get_manageable_product_catalogue_or_404(user, pk):
    catalogue = manageable_product_catalogues(user).filter(pk=pk).first()
    if catalogue is None:
        raise Http404("Product catalogue not found.")
    return catalogue
