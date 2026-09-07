# Pricing and entitlements

## Founding plans

KolliPack uses a Free / Plus / Premium commercial model. Free is the complete calculation and optimization product, not a demo: calculation tools, Packaging Flow, 3D visualization, batch analyses, previews, and public platform catalogues remain available without calculation quotas.

- **Free — $0:** interactive calculations and public catalogue use. No private catalogue management, PDF reports, AI entitlement, or batch-result Excel export.
- **Plus — $99/year Founding Price:** PDF reports, private Product and Packaging Catalogue management, catalogue Excel operations, AI entitlement, 100 MiB of optimized private catalogue images, and 1 Expert Support Hour/year.
- **Premium — $299/year Founding Price:** everything in Plus, 1 GiB of catalogue images, Excel result export from Multi-product Container and Multi-product Bag, and 5 Expert Support Hours/year.

Payment processing is not implemented in Phase 1. `UserSubscription` records are assigned manually in Django Admin. Missing, inactive, future, or expired paid subscriptions resolve to Free at request time. Staff and superusers bypass commercial restrictions.

## Architecture contract

`packagingapp/entitlements.py` is the authoritative commercial-access layer. Views and templates must use its feature constants and helpers rather than comparing subscription fields directly. `packagingapp/access.py` remains authoritative for catalogue visibility and ownership.

An owned private catalogue remains visible and usable as a calculation source after downgrade, but becomes read-only. Public platform catalogue browsing and selection always remain Free.

Paid export checks must run before snapshot capture, temporary-file work, ranking/workbook construction, or PDF generation. Catalogue images use the shared catalogue-media service for real-image validation, EXIF correction, bounded resizing, WebP encoding, per-image limits, safe ZIP ingestion, and final-byte quota enforcement. Technical drawings are excluded from the image quota.
