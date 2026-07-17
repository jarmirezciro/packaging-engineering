# Blog Architecture

## Stable public surface

The blog is part of the existing Django `packagingapp` application.

Expected public routes:

- `/blog/`
- `/blog/<slug>/`

The existing first article must remain available at:

- `/blog/box-selection-3d-bin-packing-problem/`

## Source of truth

One Markdown file per article:

```text
packagingapp/content/blog/articles/<slug>.md
```

Production images:

```text
static/img/blog/<slug>/
```

The article filename and front-matter slug must match.

## Runtime flow

```text
Markdown + TOML front matter
        ↓
blog_repository.py
        ↓
marketing.py views
        ↓
existing blog list/detail templates
```

`marketing.py` contains view logic only. It must not contain article bodies or article metadata.

## Static references in article bodies

Use:

```text
static://img/blog/<slug>/<filename>.webp
```

The repository converts `static://` to the configured Django `STATIC_URL`.

Example:

```markdown
![Six box orientations](static://img/blog/example/six-orientations.webp)
```

## Article assets

Use semantic filenames:

```text
six-box-orientations.webp
pallet-utilization-comparison.webp
box-selection-thumbnail.webp
```

Avoid names such as `image1.png`, `final-final.png`, or generated opaque identifiers.

## Registry

`docs/blog/article-registry.md` is generated from front matter. It must not be manually edited as a second content database.

## Brand assets

Use the existing canonical official KolliLabs/KolliPack logo and the real brand color source in the repository. Record the discovered canonical paths here during implementation:

```text
Official logo: <fill from repository>
Brand green source: <fill from repository CSS/settings>
```

Do not redraw the logo with an image model.
