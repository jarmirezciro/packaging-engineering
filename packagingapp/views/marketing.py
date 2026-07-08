from __future__ import annotations

from django.conf import settings
from django.contrib import messages
from django.core.mail import send_mail
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils import timezone

from packagingapp.forms import ContactForm


BLOG_POSTS = [
    {
        "slug": "why-packaging-flow-matters",
        "title": "Why packaging flow matters in KolliPack: from product dimensions to transport loading",
        "subtitle": (
            "A practical look at why packaging decisions should be evaluated as a connected flow, "
            "not as isolated calculations."
        ),
        "category": "Packaging optimization",
        "read_time": "6 min read",
        "published_at": "2026-07-03",
        "hero_icon": "bi-diagram-3",
        "summary": (
            "Container selection, palletization, and transport loading are often optimized separately. "
            "KolliPack is built around the idea that better decisions appear when the whole chain is analyzed together."
        ),
        "sections": [
            {
                "heading": "Packaging decisions are connected",
                "paragraphs": [
                    (
                        "A carton that looks efficient around the product can perform poorly on a pallet. "
                        "A pallet pattern that looks strong can still waste trailer space. A transport layout "
                        "that maximizes volume can exceed payload limits. This is why packaging engineering "
                        "should be treated as a flow."
                    ),
                    (
                        "The practical goal is not only to find a package that fits. The goal is to understand "
                        "how each decision affects the next one: product, bag or carton, pallet, and transport unit."
                    ),
                ],
            },
            {
                "heading": "A useful packaging flow starts with clear inputs",
                "paragraphs": [
                    (
                        "The foundation is simple but important: product dimensions, product weight, required "
                        "quantity, allowed rotations, packaging dimensions, pallet limits, and transport constraints. "
                        "When these inputs are consistent, the engineering discussion becomes faster and easier."
                    ),
                ],
            },
            {
                "heading": "Visualization improves decision communication",
                "paragraphs": [
                    (
                        "A visual result helps teams understand what the calculation means. It is easier to discuss "
                        "a carton fill, a pallet pattern, or a loaded trailer when the result can be seen rather than "
                        "only described in a spreadsheet."
                    ),
                ],
            },
            {
                "heading": "Reports make decisions easier to reuse",
                "paragraphs": [
                    (
                        "Packaging decisions often need to be explained to project managers, logistics teams, suppliers, "
                        "or customers. A simple PDF report with the selected solution, assumptions, utilization, and images "
                        "creates a common reference for the project."
                    ),
                ],
            },
        ],
        "takeaways": [
            "Evaluate packaging as a chain, not as isolated tools.",
            "Use consistent units and clear catalogue data.",
            "Show the decision first, then the engineering details.",
            "Use visualization and PDF reports to communicate results.",
        ],
    },
    {
        "slug": "palletization-affects-transport-cost",
        "title": "How palletization affects transport loading and cost",
        "subtitle": (
            "A practical explanation of why pallet patterns, stack height, and overhang decisions should be reviewed "
            "before transport loading is evaluated."
        ),
        "category": "Palletization",
        "read_time": "5 min read",
        "published_at": "2026-07-03",
        "hero_icon": "bi-grid-3x3-gap",
        "summary": (
            "Palletization is not only about fitting cartons on a pallet. The final stack can strongly affect trailer "
            "fill, payload usage, handling, and how easy the packaging solution is to explain."
        ),
        "sections": [
            {
                "heading": "A good pallet pattern must work beyond the pallet",
                "paragraphs": [
                    (
                        "A pallet pattern can look efficient on the pallet floor but still create problems later in the chain. "
                        "If the stack height is too high, the pallet may not fit in the transport unit. If the pattern creates "
                        "unstable edges, the solution may be difficult to handle. If the pallet dimensions are not aligned with "
                        "the transport unit, floor space can be wasted."
                    ),
                ],
            },
            {
                "heading": "The most important palletization metrics",
                "paragraphs": [
                    (
                        "Useful palletization discussions usually focus on cartons per layer, number of layers, total cartons per "
                        "pallet, pallet floor usage, stack volume usage, gross pallet weight, and overhang. These metrics explain "
                        "both the engineering result and the operational impact."
                    ),
                ],
            },
            {
                "heading": "Transport changes the meaning of an efficient pallet",
                "paragraphs": [
                    (
                        "A pallet that maximizes cartons may still be a poor option if fewer pallets fit in the trailer or if payload "
                        "is reached before volume is used. This is why palletization and transport loading should be reviewed "
                        "together when the decision has logistics impact."
                    ),
                ],
            },
        ],
        "takeaways": [
            "Review palletization together with transport loading when possible.",
            "Use clear language: main layer, alternate layer, pallet floor usage, stack volume usage, and overhang.",
            "Do not optimize only cartons per pallet if it creates downstream transport losses.",
            "A visual pallet report helps project teams understand the selected solution.",
        ],
    },
    {
        "slug": "carton-selection-basics",
        "title": "Carton selection basics: fit, quantity, weight, and documentation",
        "subtitle": (
            "A simple guide to the practical inputs that make carton selection easier to standardize and communicate."
        ),
        "category": "Container selection",
        "read_time": "4 min read",
        "published_at": "2026-07-03",
        "hero_icon": "bi-box-seam",
        "summary": (
            "Carton selection is more than finding a box that fits. A useful decision also considers quantity, orientation, "
            "gross weight, catalogue data, and what happens in palletization."
        ),
        "sections": [
            {
                "heading": "Start with reliable product data",
                "paragraphs": [
                    (
                        "The most common carton selection problems start with inconsistent inputs. Product length, width, height, "
                        "weight, quantity, and allowed rotations should be clear before alternatives are compared."
                    ),
                ],
            },
            {
                "heading": "Use outside dimensions for downstream steps",
                "paragraphs": [
                    (
                        "A carton may have internal and external dimensions. Internal dimensions are useful for product fit. External "
                        "dimensions are usually the correct input for palletization and transport analysis because they describe the "
                        "real physical footprint of the packed carton."
                    ),
                ],
            },
            {
                "heading": "Document the selected decision",
                "paragraphs": [
                    (
                        "A selected carton should be easy to explain: what product was analyzed, which carton was selected, how many "
                        "units fit, the gross carton weight, and whether there are any constraints or warnings."
                    ),
                ],
            },
        ],
        "takeaways": [
            "Separate product fit logic from downstream external-dimension logic.",
            "Quantity and gross weight are essential for the next packaging step.",
            "Good carton decisions should be visual and reportable.",
            "Catalogue quality directly affects engineering quality.",
        ],
    },

]


def _blog_post_by_slug(slug: str) -> dict:
    for post in BLOG_POSTS:
        if post["slug"] == slug:
            return post
    raise Http404("Blog article not found")


def about(request):
    contact_form = ContactForm(request.POST or None)

    if request.method == "POST":
        if contact_form.is_valid():
            cleaned = contact_form.cleaned_data
            recipient = getattr(settings, "CONTACT_EMAIL", "")

            if recipient:
                subject = f"KolliLabs contact: {cleaned['area_of_interest']}"
                body = "\n".join([
                    "New contact form submission",
                    "",
                    f"Name: {cleaned['name']}",
                    f"Email: {cleaned['email']}",
                    f"Company: {cleaned.get('company') or '-'}",
                    f"Area of interest: {cleaned['area_of_interest']}",
                    "",
                    "Message:",
                    cleaned["message"],
                ])

                try:
                    send_mail(
                        subject=subject,
                        message=body,
                        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
                        recipient_list=[recipient],
                        fail_silently=False,
                    )
                    messages.success(
                        request,
                        "Thank you for your message. KolliLabs will get back to you as soon as possible.",
                    )
                except Exception:
                    messages.warning(
                        request,
                        "Your message was validated, but email delivery is not configured correctly yet. "
                        "Please use the LinkedIn contact link for now.",
                    )
            else:
                messages.warning(
                    request,
                    "The contact form is ready, but CONTACT_EMAIL is not configured yet. "
                    "Please use the LinkedIn contact link for now.",
                )

            return redirect("about")

    return render(
        request,
        "marketing/about.html",
        {
            "contact_form": contact_form,
            "latest_posts": BLOG_POSTS[:3],
            "generated_year": timezone.now().year,
        },
    )


def blog_list(request):
    return render(request, "marketing/blog_list.html", {"posts": BLOG_POSTS})


def blog_detail(request, slug: str):
    post = _blog_post_by_slug(slug)
    return render(request, "marketing/blog_detail.html", {"post": post})
