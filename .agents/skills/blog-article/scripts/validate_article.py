#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 compatibility
    import tomli as tomllib
from datetime import date, datetime
from pathlib import Path
from typing import Any

ARTICLE_TYPES = {
    "demo_case_study",
    "engineering_deep_dive",
    "business_case",
    "practical_guide",
    "kollipack_update",
    "sustainability",
}
REQUIRED_FIELDS = {
    "schema_version",
    "status",
    "title",
    "slug",
    "excerpt",
    "seo_title",
    "meta_description",
    "article_type",
    "author",
    "published_at",
    "updated_at",
    "thumbnail",
    "thumbnail_alt",
    "primary_keyword",
}
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def parse_article(path: Path) -> tuple[dict[str, Any], str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "+++":
        raise ValueError("missing opening +++ front-matter delimiter")
    try:
        end = next(i for i, line in enumerate(lines[1:], 1) if line.strip() == "+++")
    except StopIteration as exc:
        raise ValueError("missing closing +++ front-matter delimiter") from exc
    metadata = tomllib.loads("\n".join(lines[1:end]))
    return metadata, "\n".join(lines[end + 1 :]).strip()


def as_date(value: Any, field: str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise ValueError(f"{field} must be a date")


def validate(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        metadata, body = parse_article(path)
    except (OSError, ValueError, tomllib.TOMLDecodeError) as exc:
        return [str(exc)]

    missing = sorted(REQUIRED_FIELDS - metadata.keys())
    if missing:
        errors.append(f"missing fields: {', '.join(missing)}")

    slug = str(metadata.get("slug", ""))
    if slug and not SLUG_RE.fullmatch(slug):
        errors.append("slug must use lowercase kebab-case")
    if slug and path.stem != slug:
        errors.append(f"filename must be {slug}.md")

    if metadata.get("status") not in {"draft", "published"}:
        errors.append("status must be draft or published")
    if metadata.get("article_type") not in ARTICLE_TYPES:
        errors.append(f"article_type must be one of {sorted(ARTICLE_TYPES)}")
    if metadata.get("schema_version") != 1:
        errors.append("schema_version must be 1")

    try:
        published = as_date(metadata.get("published_at"), "published_at")
        updated = as_date(metadata.get("updated_at"), "updated_at")
        if updated < published:
            errors.append("updated_at cannot be earlier than published_at")
    except (TypeError, ValueError) as exc:
        errors.append(str(exc))

    if not body:
        errors.append("article body is empty")
    if len(str(metadata.get("meta_description", ""))) > 170:
        errors.append("meta_description exceeds 170 characters")
    if len(str(metadata.get("seo_title", ""))) > 70:
        errors.append("seo_title exceeds 70 characters")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a KolliLabs Markdown article.")
    parser.add_argument("article", type=Path, help="Path to the article Markdown file")
    args = parser.parse_args()

    errors = validate(args.article)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(f"Valid article: {args.article}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
