from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
import re

from django.conf import settings
from markdown import markdown

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 fallback
    import tomli as tomllib


ARTICLE_DIRECTORY = Path(settings.BASE_DIR) / "packagingapp" / "content" / "blog" / "articles"
_FRONT_MATTER = re.compile(r"\A\+\+\+\s*\n(?P<meta>.*?)\n\+\+\+\s*\n?(?P<body>.*)\Z", re.DOTALL)


class BlogContentError(ValueError):
    """Raised when an article file is malformed."""


def _as_text(value: object) -> object:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _estimated_read_time(body: str) -> str:
    words = len(re.findall(r"\b\w+\b", body))
    minutes = max(1, round(words / 220))
    return f"{minutes} min read"


def _load_article(path: Path) -> dict:
    source = path.read_text(encoding="utf-8")
    match = _FRONT_MATTER.match(source)
    if not match:
        raise BlogContentError(f"Missing TOML front matter in {path}")

    metadata = tomllib.loads(match.group("meta"))
    body = match.group("body").strip()

    slug = str(metadata.get("slug", "")).strip()
    if not slug:
        raise BlogContentError(f"Missing slug in {path}")
    if path.stem != slug:
        raise BlogContentError(f"Filename and slug differ in {path}")

    article = {key: _as_text(value) for key, value in metadata.items()}
    static_prefix = str(settings.STATIC_URL).rstrip("/") + "/"
    rendered_source = body.replace("static://", static_prefix)

    article["content_html"] = markdown(
        rendered_source,
        extensions=["extra", "sane_lists", "md_in_html"],
        output_format="html5",
    )
    article["summary"] = article.get("summary") or article.get("excerpt", "")
    article["description"] = article.get("description") or article.get("meta_description") or article.get("subtitle", "")
    article["featured_image"] = article.get("featured_image") or article.get("thumbnail", "")
    article["read_time"] = article.get("read_time") or _estimated_read_time(body)
    article["flow_steps"] = article.get("flow_steps") or []
    article["takeaways"] = article.get("takeaways") or []
    return article


def get_published_articles() -> list[dict]:
    if not ARTICLE_DIRECTORY.exists():
        return []

    articles = [
        _load_article(path)
        for path in ARTICLE_DIRECTORY.glob("*.md")
    ]
    published = [article for article in articles if article.get("status", "published") == "published"]
    return sorted(
        published,
        key=lambda article: (
            int(article.get("display_order", 9999)),
            str(article.get("published_at", "")),
        ),
    )


def get_published_article(slug: str) -> dict | None:
    path = ARTICLE_DIRECTORY / f"{slug}.md"
    if not path.is_file():
        return None

    article = _load_article(path)
    if article.get("status", "published") != "published":
        return None
    return article
