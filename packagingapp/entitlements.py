from __future__ import annotations

from functools import wraps
from urllib.parse import urlencode

from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone

from packagingapp.models import UserSubscription


PRIVATE_CATALOGUES = "private_catalogues"
PDF_REPORTS = "pdf_reports"
BATCH_EXCEL_EXPORT = "batch_excel_export"
AI_ASSISTANT = "ai_assistant"

PLUS_IMAGE_LIMIT_BYTES = 100 * 1024 * 1024
PREMIUM_IMAGE_LIMIT_BYTES = 1024 * 1024 * 1024

PLAN_FEATURES = {
    UserSubscription.Plan.FREE: frozenset(),
    UserSubscription.Plan.PLUS: frozenset(
        {PRIVATE_CATALOGUES, PDF_REPORTS, AI_ASSISTANT}
    ),
    UserSubscription.Plan.PREMIUM: frozenset(
        {PRIVATE_CATALOGUES, PDF_REPORTS, BATCH_EXCEL_EXPORT, AI_ASSISTANT}
    ),
}

FEATURE_MESSAGES = {
    PRIVATE_CATALOGUES: "Private Product and Packaging Catalogues are included in Plus and Premium.",
    PDF_REPORTS: "PDF reports are included in Plus and Premium.",
    BATCH_EXCEL_EXPORT: "Excel result export for the Multi-product Box/Container and Bag batch tools is a Premium feature.",
    AI_ASSISTANT: "KolliPack AI is included in Plus and Premium.",
}


def _is_staff_bypass(user) -> bool:
    return bool(
        getattr(user, "is_authenticated", False)
        and (getattr(user, "is_staff", False) or getattr(user, "is_superuser", False))
    )


def effective_plan(user) -> str:
    if _is_staff_bypass(user):
        return UserSubscription.Plan.PREMIUM
    if not getattr(user, "is_authenticated", False):
        return UserSubscription.Plan.FREE

    subscription = getattr(user, "subscription", None)
    if subscription is None or subscription.plan == UserSubscription.Plan.FREE:
        return UserSubscription.Plan.FREE

    now = timezone.now()
    if subscription.status != UserSubscription.Status.ACTIVE:
        return UserSubscription.Plan.FREE
    if subscription.starts_at and subscription.starts_at > now:
        return UserSubscription.Plan.FREE
    if subscription.current_period_end is not None and subscription.current_period_end <= now:
        return UserSubscription.Plan.FREE
    return subscription.plan


def has_feature(user, feature: str) -> bool:
    if _is_staff_bypass(user):
        return True
    return feature in PLAN_FEATURES.get(effective_plan(user), frozenset())


def catalogue_image_limit_bytes(user) -> int | None:
    if _is_staff_bypass(user):
        return None
    plan = effective_plan(user)
    if plan == UserSubscription.Plan.PLUS:
        return PLUS_IMAGE_LIMIT_BYTES
    if plan == UserSubscription.Plan.PREMIUM:
        return PREMIUM_IMAGE_LIMIT_BYTES
    return 0


def expert_support_hours(user) -> int:
    if _is_staff_bypass(user):
        return 0
    plan = effective_plan(user)
    if plan == UserSubscription.Plan.PLUS:
        return 1
    if plan == UserSubscription.Plan.PREMIUM:
        return 5
    return 0


def plan_display_name(user) -> str:
    if _is_staff_bypass(user):
        return "Premium"
    return UserSubscription.Plan(effective_plan(user)).label


def pricing_url(feature_query: str | None = None) -> str:
    url = reverse("pricing")
    if feature_query:
        return f"{url}?{urlencode({'feature': feature_query})}"
    return url


def feature_required(
    feature: str,
    feature_query: str,
    *,
    redirect_to_pricing: bool = False,
    json_response: bool = False,
):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if has_feature(request.user, feature):
                return view_func(request, *args, **kwargs)

            message = FEATURE_MESSAGES[feature]
            upgrade_url = pricing_url(feature_query)
            if json_response:
                return JsonResponse(
                    {"ok": False, "error": message, "pricing_url": upgrade_url},
                    status=403,
                )
            if redirect_to_pricing:
                messages.info(request, message)
                return redirect(upgrade_url)
            return HttpResponse(message, status=403, content_type="text/plain")

        return wrapped

    return decorator
