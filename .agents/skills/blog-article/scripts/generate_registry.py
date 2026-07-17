#!/usr/bin/env python3
from __future__ import annotations

import argparse
try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 compatibility
    import tomli as tomllib
from pathlib import Path
from typing import Any


def parse_metadata(path: Path) -> dict[str, Any]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "+++":
        raise ValueError(f"{path}: missing opening +++")
    end = next(i for i, line in enumerate(lines[1:], 1) if line.strip() == "+++")
    return tomllib.loads("\n".join(lines[1:end]))


def cell(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) or "—"
    return str(value) if value not in (None, "") else "—"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the KolliLabs blog article registry.")
    parser.add_argument(
        "--articles-dir",
        type=Path,
        default=Path("packagingapp/content/blog/articles"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/blog/article-registry.md"),
    )
    args = parser.parse_args()

    rows = []
    seen = set()
    for path in sorted(args.articles_dir.glob("*.md")):
        metadata = parse_metadata(path)
        slug = str(metadata.get("slug", ""))
        if slug in seen:
            raise ValueError(f"Duplicate slug: {slug}")
        seen.add(slug)
        rows.append(metadata)

    rows.sort(key=lambda item: (str(item.get("published_at", "")), str(item.get("slug", ""))), reverse=True)
    lines = [
        "<!-- GENERATED FILE: do not edit manually. -->",
        "",
        "# KolliLabs Blog Article Registry",
        "",
        "| Slug | Title | Status | Type | Primary keyword | Published | Updated | Related tools |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for item in rows:
        lines.append(
            "| {slug} | {title} | {status} | {article_type} | {primary_keyword} | "
            "{published_at} | {updated_at} | {related_tools} |".format(
                **{key: cell(item.get(key)) for key in (
                    "slug", "title", "status", "article_type", "primary_keyword",
                    "published_at", "updated_at", "related_tools"
                )}
            )
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {args.output} with {len(rows)} article(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
