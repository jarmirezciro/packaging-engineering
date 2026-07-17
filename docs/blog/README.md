# KolliLabs Blog Content

The blog uses one Markdown file per article:

```text
packagingapp/content/blog/articles/<slug>.md
```

The public URL remains:

```text
/blog/<slug>/
```

`packagingapp/services/blog_repository.py` loads and validates the files. The existing list and detail templates remain in use.

## Article source of truth

After the one-time migration, do not add article dictionaries to `packagingapp/views/marketing.py`. New and refreshed articles must be created through the repository skill at:

```text
.agents/skills/blog-article/SKILL.md
```

## Validation

```powershell
python manage.py validate_blog_content
python manage.py test packagingapp.tests.test_blog_repository
python manage.py check
```

The one-time migration preserves the complete legacy article context inside each Markdown file. This allows the current templates to continue using existing fields while future articles move toward the normalized schema.
