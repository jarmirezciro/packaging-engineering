# Shared tool change checklist

## Before coding

- [ ] Current branch and Git status checked
- [ ] Current repository paths inspected
- [ ] Tool engine/service/presenter mapped
- [ ] Standalone view/template mapped
- [ ] Packaging Flow adapter/wrapper mapped
- [ ] Multi-product Container consumer mapped or N/A
- [ ] Multi-product Bag consumer mapped or N/A
- [ ] SEO/public consumer mapped or N/A
- [ ] PDF/image/report path mapped or N/A
- [ ] Catalogue/manual source flow mapped
- [ ] Reproduction fixture recorded
- [ ] Acceptance criteria written

## During implementation

- [ ] Smallest coherent change
- [ ] No duplicate calculation logic
- [ ] Prefix-safe IDs/JS
- [ ] Session data primitives only
- [ ] Original units and dimension labels preserved
- [ ] Existing theme/shared components reused
- [ ] No unrelated global CSS rewrite
- [ ] No production/deployment action

## Verification

- [ ] Domain tests
- [ ] Serializer/session tests
- [ ] Standalone request/manual check
- [ ] Packaging Flow check
- [ ] Multi-product Container check or N/A
- [ ] Multi-product Bag check or N/A
- [ ] Repeated same-type Flow steps check
- [ ] SEO demo/default separation check or N/A
- [ ] Selected result/PDF agreement
- [ ] Image/3D clean mode check
- [ ] Page-position/focus check
- [ ] Final diff reviewed

## Completion

- [ ] All required layers completed; no “next file still required” gap
- [ ] Documentation updated for changed rules/contracts
- [ ] Final report includes files, tests, consumer matrix, and risks
