# Frontend theme and component rules

## Source of truth

The frontend foundation is:

- Django templates;
- Bootstrap;
- `base.html`;
- `static/css/app_theme.css`;
- shared tool wrappers and partials.

The exact CSS tokens and classes in the current branch take priority.

## Approved visual direction

KolliPack uses a clean, modern, customer-facing engineering theme with KolliLabs/KolliPack green branding, restrained neutral backgrounds, rounded cards, readable tables, and strong hierarchy.

Preferred component families historically include:

- `app-page`;
- `app-hero`;
- `app-card`;
- `tool-*` structures;
- `app-table`;
- standard Bootstrap grid/utilities;
- shared wrapper-specific classes.

## Reference tool pattern

Container Selection became the launch-ready reference, followed by Bag, Palletization, and Transport polish. Multi-product Container Selection and Multi-product Bag Selection must visually track their corresponding standalone tools rather than retain older result cards or graphics. New tools should generally provide:

1. compact page header/hero;
2. collapsible “How to use this tool” instructions;
3. clear source choice: manual or catalogue;
4. product/base-unit section;
5. packaging or transport-unit section;
6. primary calculate/analyse action;
7. result cards with key KPIs;
8. clean visualization;
9. detailed analysis and report export;
10. responsive behaviour.

## Forms

- Align labels and controls.
- Keep repeated inputs compact.
- Put units in labels or suffixes.
- Explain optional payload, tare, tolerance, overhang, stack height, and restrictions.
- Preserve user-entered values after validation errors.
- Do not make the user scroll to find the result after every small action.

## Tables and selection

- Catalogue rows can be selectable without a redundant Select button.
- Include product/packaging image thumbnails where available.
- Clearly show part number, description, dimensions, relevant weight/payload, and type.
- Selection must work by keyboard as well as mouse when row-click behaviour is used.

## Result cards

Result cards should distinguish:

- maximum quantity or requested quantity achieved;
- dimensions and orientation;
- utilization metrics with explicit meaning;
- weight/payload feasibility;
- warnings and assumptions;
- selected state.

Avoid vague labels such as “Efficiency” without defining the denominator.

## What not to do

- Do not replace all of `app_theme.css` to solve one page.
- Do not create an isolated `cs-*` or tool-only visual system when shared app classes already solve the need.
- Do not force three columns at widths where the app sidebar leaves insufficient space.
- Do not claim a CSS fix is “guaranteed” without loading the actual template and stylesheet path.
- Do not leave debug borders, axes, or temporary copy in production UI.
