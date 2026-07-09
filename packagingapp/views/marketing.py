from __future__ import annotations

import json

from django.conf import settings
from django.contrib import messages
from django.core.mail import send_mail
from django.http import Http404
from django.shortcuts import redirect, render
from django.templatetags.static import static
from django.utils import timezone

from packagingapp.forms import ContactForm

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
    return [_prepare_blog_post(post) for post in BLOG_POSTS]


BLOG_POSTS = [
    {
        "slug": "box-selection-3d-bin-packing-problem",
        "article_type": "engineering_deep_dive",
        "title": "Why Choosing the Right Box Is a 3D Bin Packing Problem",
        "subtitle": (
            "A practical explanation of why box selection is more than checking if a product fits, "
            "and how KolliPack uses packing logic to optimize box space and catalogue decisions."
        ),
        "description": (
            "Learn why choosing the right box is more complex than it looks, how 3D bin packing affects "
            "packaging cost and transport efficiency, and how KolliPack helps companies optimize packaging decisions."
        ),
        "category": "Packaging optimization",
        "read_time": "9 min read",
        "published_at": "2026-07-09",
        "hero_icon": "bi-box-seam",
        "featured_image": "img/blog/box-selection-3d-bin-packing-problem/blog1_thumbnail_kollipack_box_selection.png",
        "summary": (
            "Box selection is a 3D packing problem with many possible product orientations and leftover-space combinations. "
            "KolliPack helps evaluate these alternatives faster and more consistently than manual checks."
        ),
        "flow_steps": [
            {"icon": "bi-box-seam", "label": "Product"},
            {"icon": "bi-grid-3x3-gap", "label": "Base ways"},
            {"icon": "bi-bounding-box", "label": "Mosaic zones"},
            {"icon": "bi-check2-circle", "label": "Better decision"},
        ],
        "sections": [
            {
                "heading": "Why a simple box decision becomes an optimization problem",
                "paragraphs": [
                    (
                        "Manufacturing and logistics operations need boxes, containers, and other packaging materials to transport "
                        "finished and semi-finished goods. Most companies therefore work with a standard packaging assortment: a catalogue "
                        "of boxes, pallets, bags, and containers that are already approved, purchased, and available in the supply chain."
                    ),
                    (
                        "At first, choosing a box may sound like a simple task. A product has dimensions, the box has dimensions, and the "
                        "packaging engineer only needs to check whether the product fits. In reality, the problem is much more complex."
                    ),
                    (
                        "A single product can often be placed inside a box in several different orientations. When multiple pieces must be "
                        "packed together, the number of possible combinations grows very quickly. This is why box selection is closely related "
                        "to the 3D bin packing problem: the challenge of fitting three-dimensional items into a container in the most efficient way possible."
                    ),
                    (
                        "For one fixed box and one fixed product the solution space is not literally infinite, but in practical packaging work it can feel almost endless. "
                        "Different orientations, layers, leftover spaces, box dimensions, weights, and quantity requirements create a large search problem. "
                        "This is exactly the type of problem that should not depend only on manual checks or intuition. It is better to let KolliPack calculate "
                        "the alternatives faster, more consistently, and more accurately."
                    ),
                ],
            },
            {
                "heading": "Why box selection matters",
                "paragraphs": [
                    (
                        "Operations and customers often require products to be shipped in specific multiples. For example, a customer may need products "
                        "delivered in quantities of 2, 4, 8, 10, 20, or 50 pieces per shipping unit."
                    ),
                    (
                        "To satisfy this requirement, a company usually has two options: select a box from the existing standard packaging assortment, "
                        "or source and validate a new custom box. The first option is usually preferred because it avoids new purchasing activities, new inventory, "
                        "and additional complexity. However, selecting the wrong box from the standard assortment can create unnecessary costs."
                    ),
                ],
                "bullets": [
                    "Higher packaging material cost.",
                    "More empty space inside the package.",
                    "Lower transport efficiency.",
                    "More pallets, trucks, or containers needed.",
                    "Higher CO₂ emissions.",
                    "Increased risk of damage if the product is not properly supported.",
                    "More complexity in warehouse and inventory management.",
                ],
                "note": (
                    "For many companies, the best solution is not to create more packaging materials, but to use the existing packaging catalogue more intelligently."
                ),
            },
            {
                "heading": "The hidden complexity of packing a product in a box",
                "paragraphs": [
                    (
                        "The challenge is that 'does it fit?' is not enough. A packaging decision should also consider product orientations, quantity, weight, "
                        "internal box dimensions, empty space, material utilization, product fragility, and the impact on palletization and transport."
                    ),
                    (
                        "For example, a product may fit in a box when placed lengthwise, but the same product may allow more pieces if rotated. Another orientation "
                        "may improve space utilization but be unacceptable because the product cannot be stacked or tilted in that direction."
                    ),
                    (
                        "This is where packaging engineering becomes more than a manual check. It becomes an optimization problem."
                    ),
                ],
            },
            {
                "heading": "A simple example: six base ways of packing",
                "paragraphs": [
                    (
                        "Let us take a simple case: a product of 130 × 70 × 30 mm packed into a box of 500 × 300 × 200 mm. "
                        "A human approach may start by checking the six basic axis-aligned orientations of the product inside the box. These are the simple uniform "
                        "packing alternatives, where every product is placed in the same orientation."
                    ),
                    (
                        "This is a reasonable starting point. It shows the most obvious ways to place the product in the box. In this example, the best uniform-orientation "
                        "result fits 84 products. However, this is still only the beginning of the problem."
                    ),
                ],
                "figures": [
                    {
                        "src": "img/blog/box-selection-3d-bin-packing-problem/figure_1_six_uniform_base_ways.png",
                        "alt": "Six uniform 3D packing layouts for a product inside a box",
                        "caption": "Figure 1. The six uniform base orientations are a useful starting point, but they do not explore the full leftover-space opportunity."
                    },
                ],
            },
            {
                "heading": "KolliPack goes beyond the obvious packing patterns",
                "paragraphs": [
                    (
                        "After checking the six base orientations, KolliPack can continue the search by analyzing unused space inside the box. In simple terms, "
                        "the algorithm does not stop when one uniform packing block is created. It can also evaluate the leftover rectangular zones around the main filled block. "
                        "These zones can then be tested with different product orientations."
                    ),
                    (
                        "This creates a rectangular-subbox mosaic layout. The box can be divided into practical zones such as a main filled block, side leftover zones, "
                        "and a top leftover zone. Each zone can use a different product orientation."
                    ),
                    (
                        "This approach is controlled and explainable. It is not random. KolliPack evaluates structured alternatives that are relevant for packaging engineering and box selection."
                    ),
                ],
                "figures": [
                    {
                        "src": "img/blog/box-selection-3d-bin-packing-problem/figure_2b_rectangular_subbox_family_all_base_mosaics.png",
                        "alt": "Rectangular subbox mosaic family generated from the six base packing orientations",
                        "caption": "Figure 2. From each base orientation, KolliPack can evaluate rectangular leftover zones and test additional product rotations."
                    },
                    {
                        "src": "img/blog/box-selection-3d-bin-packing-problem/figure_2_developed_mosaic_layout.png",
                        "alt": "Developed mosaic layout with a main block and leftover zones",
                        "caption": "Figure 3. A developed mosaic layout can use the box space better than a single uniform orientation."
                    },
                ],
            },
            {
                "heading": "The goal is not always to pack more products",
                "paragraphs": [
                    (
                        "In this example, the optimized layout allows more products to fit in the same box. That is a powerful result, but it is not the only use case. "
                        "In real business, the requirement is often not 'pack as many as possible.' The requirement may be to pack exactly 4, 10, 20, or 50 pieces per carton."
                    ),
                    (
                        "This is where the same optimization logic becomes even more useful. If the business has a predefined quantity per carton, KolliPack can use the company packaging "
                        "catalogue to search for the box that suits that quantity best. Instead of asking only, 'How many products fit in this box?', the company can ask a better question."
                    ),
                ],
                "quote": "For this required quantity, which box from our catalogue gives the best packaging solution?",
            },
            {
                "heading": "Best uniform packing versus KolliPack optimization",
                "paragraphs": [
                    (
                        "The difference between basic manual reasoning and algorithmic optimization can be shown clearly. In the studied case, the best uniform packing fits 84 products, "
                        "while the KolliPack-style mosaic layout fits 102 products."
                    ),
                    (
                        "This does not mean that every product will always produce this type of improvement. Some products and boxes are already geometrically efficient. Others have much more hidden potential. "
                        "The important point is that the algorithm explores the alternatives systematically. It can find when a better solution exists, and it can also confirm when the current solution is already good."
                    ),
                ],
                "figures": [
                    {
                        "src": "img/blog/box-selection-3d-bin-packing-problem/figure_3_best_uniform_vs_kollipack.png",
                        "alt": "Best uniform packing compared with KolliPack optimized mosaic result",
                        "caption": "Figure 4. In this example, the KolliPack-style mosaic result improves box capacity from 84 to 102 products."
                    },
                ],
                "table": {
                    "headers": ["Method", "Quantity"],
                    "rows": [
                        ["Best uniform packing", "84 products"],
                        ["KolliPack optimized mosaic layout", "102 products"],
                        ["Improvement", "+18 products"],
                        ["Improvement percentage", "+21.4%"],
                    ],
                },
            },
            {
                "heading": "Why many companies lose money in packaging selection",
                "paragraphs": [
                    (
                        "In many companies, the process for selecting packaging materials is not well established or properly documented. Decisions may rely on old Excel files, individual experience, "
                        "local habits, or packaging rules that nobody fully owns anymore. The result is often an accumulation of small inefficiencies."
                    ),
                    (
                        "One product may have slightly too much empty space. Another may use a box that is too strong or too large. Another may require a custom box even though a better standard option "
                        "already exists in the catalogue. Individually, each case may look small. Over thousands of products and shipments, the cost impact can become significant."
                    ),
                    (
                        "This is one of the reasons why packaging optimization has strong savings potential. Better packaging decisions can reduce material cost, improve transport efficiency, simplify catalogues, "
                        "and support sustainability targets."
                    ),
                ],
            },
            {
                "heading": "How KolliPack helps with box and container selection",
                "paragraphs": [
                    (
                        "KolliPack is designed to help companies make better packaging decisions using structured data and optimization logic. The Container Selection Tool analyzes product dimensions, weight, "
                        "allowed orientations, required quantities, and available packaging options. It can calculate how many products fit inside a container and compare different alternatives from the packaging catalogue."
                    ),
                    (
                        "Instead of manually checking one box at a time, KolliPack can evaluate several packaging alternatives and identify which option gives the best fit for the business requirement."
                    ),
                ],
                "bullets": [
                    "Which standard box should be used for this product?",
                    "How many pieces fit in each box?",
                    "Which product orientation gives the best utilization?",
                    "Is the current packaging oversized?",
                    "Could another box from the catalogue reduce empty space?",
                    "Is a custom box really needed?",
                    "What is the best alternative for a given shipping multiple?",
                    "Which catalogue box is best for a predefined quantity per carton?",
                ],
                "note": "The packaging catalogue becomes more than a list of available boxes. It becomes a decision-making system.",
            },
            {
                "heading": "A practical cost-saving project",
                "paragraphs": [
                    (
                        "One practical project that companies can run with KolliPack is to compare their current packaging decisions against the optimized alternatives suggested by the tool. "
                        "Many packaging inefficiencies are not visible until the data is analyzed systematically."
                    ),
                ],
                "bullets": [
                    "Export a list of products and their current packaging.",
                    "Load the company packaging catalogue into KolliPack.",
                    "Define the business quantity required per carton.",
                    "Run the Container Selection Tool for each product and quantity requirement.",
                    "Compare the current packaging against the best suggested alternatives.",
                    "Identify oversized boxes, inefficient packing patterns, and unnecessary custom packaging.",
                    "Prioritize the products with the highest savings potential.",
                ],
                "note": "Even small improvements in box selection can create value when they are repeated across many products, shipments, warehouses, and markets.",
            },
            {
                "heading": "Packaging optimization also supports sustainability",
                "paragraphs": [
                    (
                        "A better box selection process is not only about cost. Oversized packaging usually means more paper, more empty space, and less efficient transportation. Empty space is transported "
                        "through the supply chain as if it were product, consuming pallet positions, warehouse space, truck capacity, and container volume."
                    ),
                    (
                        "By improving material utilization, companies can reduce unnecessary packaging material and improve transport efficiency. This can contribute to lower CO₂ emissions and better environmental performance. "
                        "As environmental compliance and sustainability reporting become more important, packaging optimization is becoming a practical way to connect cost reduction with environmental responsibility."
                    ),
                ],
            },
            {
                "heading": "Conclusion",
                "paragraphs": [
                    (
                        "Choosing the right box is more complex than it looks. What may appear to be a simple packaging decision is often a 3D bin packing problem involving dimensions, orientations, quantities, weights, "
                        "catalogue availability, cost, and transport efficiency."
                    ),
                    (
                        "KolliPack helps make this process more structured, visual, and data-driven. By using advanced packing logic together with a user-friendly packaging catalogue setup, companies can identify better "
                        "packaging alternatives, reduce empty space, lower material consumption, and improve transport efficiency."
                    ),
                    (
                        "In the example studied, KolliPack finds a better layout that increases the number of products in the same box. In other business cases, the same logic can be used to find the best catalogue box "
                        "for a predefined quantity per carton. This is the real value of packaging optimization: not only packing more, but making better packaging decisions."
                    ),
                    (
                        "In upcoming articles, we will explore how packaging geometry affects material utilization, how product orientation influences the result, and how to define the right input data for better packaging optimization in KolliPack."
                    ),
                ],
            },
        ],
        "takeaways": [
            "Box selection is a 3D optimization problem, not only a fit check.",
            "The six uniform product orientations are only the first level of reasoning.",
            "KolliPack can analyze leftover rectangular zones to improve space utilization.",
            "The same logic can find the best catalogue box for a predefined quantity per carton.",
            "Better box selection can reduce material cost, empty space, transport waste, and CO₂ impact.",
        ],
    },
    {
        "slug": "why-packaging-flow-matters",
        "article_type": "business_case",
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
        "article_type": "business_case",
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
        "article_type": "practical_guide",
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
            return _prepare_blog_post(post)
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
        },
    )


def _article_schema_json(request, post: dict) -> str:
    image_path = post.get("featured_image")
    image_url = request.build_absolute_uri(static(image_path)) if image_path else None

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
        "mainEntityOfPage": request.build_absolute_uri(),
    }
    if image_url:
        schema["image"] = [image_url]

    return json.dumps(schema, ensure_ascii=False)


def blog_detail(request, slug: str):
    post = _blog_post_by_slug(slug)
    post["article_schema_json"] = _article_schema_json(request, post)
    return render(request, "marketing/blog_detail.html", {"post": post})
