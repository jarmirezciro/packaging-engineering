from packagingapp.entitlements import (
    BATCH_EXCEL_EXPORT,
    PDF_REPORTS,
    PRIVATE_CATALOGUES,
    catalogue_image_limit_bytes,
    effective_plan,
    expert_support_hours,
    has_feature,
    plan_display_name,
)


def subscription_context(request):
    user = request.user
    return {
        "effective_plan_code": effective_plan(user),
        "effective_plan_display": plan_display_name(user),
        "can_manage_private_catalogues": has_feature(user, PRIVATE_CATALOGUES),
        "can_export_pdf": has_feature(user, PDF_REPORTS),
        "can_export_batch_excel": has_feature(user, BATCH_EXCEL_EXPORT),
        "catalogue_image_limit_bytes": catalogue_image_limit_bytes(user),
        "expert_support_hours": expert_support_hours(user),
    }
