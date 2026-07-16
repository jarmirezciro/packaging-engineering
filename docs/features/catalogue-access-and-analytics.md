# Catalogue, access, and analytics

## Product and packaging catalogues

Catalogues are shared data sources for standalone tools and Packaging Flow.

Important behaviours:

- manual and catalogue source modes;
- searchable/filterable rows;
- product/packaging images;
- dimensions, weight, type, branding/material fields as relevant;
- row selection without redundant buttons;
- add/edit/delete permissions;
- selected catalogue objects converted to primitives before session storage.

Historical `PackagingMaterial` fields included:

```text
part_number
part_description
packaging_type
branding
packaging_materials
part_length
part_width
part_height
part_volume
picture
```

Verify current models before relying on this list.

## Access management

- Superuser/admin creation and Railway administration are deployment operations and require explicit user intent.
- UI permissions should be enforced server-side, not only hidden in templates.
- Catalogue editing forms should reuse the app’s modern input style.
- Do not expose private admin data on public SEO pages.

## First-party analytics direction

The preferred analytics approach avoids third-party tracking services.

GDPR-safer design discussed:

- server-side Django events;
- no analytics cookies/local storage/fingerprinting;
- no raw IP storage;
- daily rotating salted anonymous identifiers or session-key fallback;
- page-view and calculator/conversion events;
- bot and health-check filtering;
- private admin dashboard;
- aggregated reporting;
- automatic deletion of detailed events after approximately 30–90 days, with 90 days discussed as a practical target;
- privacy-policy explanation and legitimate-interest assessment.

This is a design direction, not legal advice. Verify the implemented data model and retention job before making compliance claims.

## Shared event taxonomy

Prefer explicit events such as:

```text
page_view
calculator_started
calculation_completed
result_selected
pdf_exported
catalogue_item_selected
kollipack_cta_clicked
```

Do not store full free-text inputs or personally identifying catalogue data unless necessary and documented.
