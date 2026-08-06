from __future__ import annotations

import json

from django.conf import settings
from django.contrib import messages
from django.core.mail import send_mail
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.templatetags.static import static
from django.utils import timezone

from packagingapp.forms import ContactForm
from packagingapp.services.blog_repository import get_published_article, get_published_articles

AUTHOR_PROFILE = {
    "name": "Alejandro Ramírez",
    "role": "Founder of KolliLabs · Chemical Engineer Msc.",
    "image": "img/alejandro-ramirez.jpg",
    "bio": (
        "Alejandro Ramírez is a Chemical Engineer and digitalization specialist based in Gothenburg, Sweden. "
        "He builds KolliPack from his experience in the field of logisctis and packaging to make packaging decisions more visual, systematic, and data-driven."
    ),
}


ARTICLE_TYPES = {
    "demo_case_study": {
        "label": "Demo case study",
        "short_label": "Case study",
        "icon": "bi-bar-chart-line",
        "description": "Reproducible packaging calculations that compare practical alternatives and support a specific decision.",
    },
    "engineering_deep_dive": {
        "label": "Engineering deep dive",
        "short_label": "Nerd article",
        "icon": "bi-cpu",
        "description": "Technical articles with algorithms, geometry, calculations, and detailed packaging logic.",
    },
    "business_case": {
        "label": "Business case",
        "short_label": "Business article",
        "icon": "bi-briefcase",
        "description": "Management-friendly articles about cost, savings, CO₂, process improvement, and business decisions.",
    },
    "practical_guide": {
        "label": "Practical guide",
        "short_label": "How-to guide",
        "icon": "bi-compass",
        "description": "Step-by-step articles that help packaging and logistics teams apply a method in daily work.",
    },
    "kollipack_update": {
        "label": "KolliPack update",
        "short_label": "Product update",
        "icon": "bi-stars",
        "description": "Posts about KolliPack features, workflows, releases, and examples from the app.",
    },
    "sustainability": {
        "label": "Sustainability",
        "short_label": "Sustainability",
        "icon": "bi-leaf",
        "description": "Articles about material reduction, transport efficiency, emissions, and environmental impact.",
    },
}


def _prepare_blog_post(post: dict) -> dict:
    prepared = dict(post)
    article_type_key = prepared.get("article_type") or "practical_guide"
    article_type_meta = ARTICLE_TYPES.get(article_type_key, ARTICLE_TYPES["practical_guide"])
    prepared["article_type"] = article_type_key
    prepared["article_type_meta"] = article_type_meta
    prepared["author"] = AUTHOR_PROFILE
    return prepared


def _prepared_blog_posts() -> list[dict]:
    return [_prepare_blog_post(post) for post in get_published_articles()]


def _blog_post_by_slug(slug: str) -> dict:
    post = get_published_article(slug)
    if post is None:
        raise Http404("Blog article not found")
    return _prepare_blog_post(post)


def _absolute_url(request, view_name: str, *, kwargs: dict | None = None) -> str:
    return request.build_absolute_uri(reverse(view_name, kwargs=kwargs))


def robots_txt(request):
    sitemap_url = request.build_absolute_uri(reverse("sitemap"))
    content = "\n".join([
        "User-agent: *",
        "Allow: /",
        f"Sitemap: {sitemap_url}",
        "",
    ])
    return HttpResponse(content, content_type="text/plain; charset=utf-8")


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

            return redirect("company_home")

    return render(
        request,
        "marketing/about.html",
        {
            "contact_form": contact_form,
            "latest_posts": _prepared_blog_posts()[:3],
            "generated_year": timezone.now().year,
        },
    )


def blog_list(request):
    return render(
        request,
        "marketing/blog_list.html",
        {
            "posts": _prepared_blog_posts(),
            "article_types": ARTICLE_TYPES.values(),
            "canonical_url": _absolute_url(request, "blog_list"),
        },
    )


def _article_schema_json(request, post: dict) -> str:
    image_path = post.get("featured_image")
    image_url = request.build_absolute_uri(static(image_path)) if image_path else None
    canonical_url = _absolute_url(request, "blog_detail", kwargs={"slug": post.get("slug", "")})

    schema = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": post.get("title", ""),
        "description": post.get("description") or post.get("subtitle", ""),
        "author": {"@type": "Person", "name": post.get("author", AUTHOR_PROFILE).get("name", AUTHOR_PROFILE["name"])},
        "publisher": {"@type": "Organization", "name": "KolliLabs"},
        "articleSection": post.get("category", ""),
        "about": post.get("article_type_meta", {}).get("label", "Packaging engineering"),
        "datePublished": post.get("published_at", ""),
        "dateModified": post.get("updated_at") or post.get("published_at", ""),
        "mainEntityOfPage": canonical_url,
    }
    if image_url:
        schema["image"] = [image_url]

    return json.dumps(schema, ensure_ascii=False)


def blog_detail(request, slug: str):
    post = _blog_post_by_slug(slug)
    canonical_url = _absolute_url(request, "blog_detail", kwargs={"slug": post["slug"]})
    post["article_schema_json"] = _article_schema_json(request, post)
    return render(
        request,
        "marketing/blog_detail.html",
        {
            "post": post,
            "canonical_url": canonical_url,
        },
    )
