"""Server-owned Public Expert page scopes and suggested questions."""

from __future__ import annotations

from .public_contracts import MAX_PUBLIC_USER_MESSAGE_LENGTH
from .public_policy import public_expert_feature_enabled


PUBLIC_EXPERT_PAGE_SCOPES = {
    "company_home": "global",
    "about": "global",
    "home": "global",
    "blog_list": "global",
    "blog_detail": "global",
    "container_selection_calculator": "container_selection",
    "bag_selection_calculator": "bag_selection",
    "palletization_calculator": "palletization",
    "transport_container_calculator": "transport",
}

PUBLIC_EXPERT_SUGGESTIONS = {
    "global": (
        "What does KolliPack do?",
        "Which tool should I use?",
        "How does Palletization work?",
        "Container Selection vs Bag Selection",
    ),
    "container_selection": (
        "How does this tool work?",
        "What is Design Mode?",
        "What do R1, R2 and R3 mean?",
        "What is cubicity?",
    ),
    "bag_selection": (
        "How does this tool work?",
        "What is sealing margin?",
        "How is Bag Selection different from Container Selection?",
    ),
    "palletization": (
        "How does this tool work?",
        "What do P1 and P2 mean?",
        "What is a Block pattern?",
        "What does interlock mean?",
    ),
    "transport": (
        "How does this tool work?",
        "What does Space Evenly do?",
        "What is payload utilization?",
        "What loading limits should I check?",
    ),
}


def public_expert_template_context(request) -> dict:
    resolver_match = getattr(request, "resolver_match", None)
    url_name = getattr(resolver_match, "url_name", None)
    scope = PUBLIC_EXPERT_PAGE_SCOPES.get(url_name)
    enabled = bool(scope and public_expert_feature_enabled())
    return {
        "public_expert_ui_enabled": enabled,
        "public_expert_scope": scope if enabled else "",
        "public_expert_surface": (
            "public_site" if enabled and scope == "global" else "public_tool"
        ),
        "public_expert_suggestions": (
            PUBLIC_EXPERT_SUGGESTIONS.get(scope, ()) if enabled else ()
        ),
        "public_expert_message_limit": MAX_PUBLIC_USER_MESSAGE_LENGTH,
    }


__all__ = [
    "PUBLIC_EXPERT_PAGE_SCOPES",
    "PUBLIC_EXPERT_SUGGESTIONS",
    "public_expert_template_context",
]
