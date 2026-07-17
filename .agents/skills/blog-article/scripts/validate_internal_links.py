#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
import tomllib
from pathlib import Path

MARKDOWN_LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+[\"'][^\"']*[\"'])?\)")
HTML_LINK_RE = re.compile(r"(?:href|src)=[\"']([^\"']+)[\"']")
BLOG_LINK_RE = re.compile(r"^/blog/([a-z0-9-]+)/?$")
STATIC_TOKEN_PREFIX = "static://"


def parse(path: Path):
    lines = path.read_text(encoding="utf-8").splitlines()
    end = next(i for i, line in enumerate(lines[1:], 1) if line.strip() == "+++")
    metadata = tomllib.loads("\n".join(lines[1:end]))
    body = "\n".join(lines[end + 1 :])
    return metadata, body


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate internal blog and static links in article Markdown files.")
    parser.add_argument("--articles-dir", type=Path, default=Path("packagingapp/content/blog/articles"))
    parser.add_argument("--static-root", type=Path, default=Path("static"))
    args = parser.parse_args()

    parsed = []
    slugs = set()
    for path in sorted(args.articles_dir.glob("*.md")):
        metadata, body = parse(path)
        parsed.append((path, metadata, body))
        slugs.add(str(metadata.get("slug", "")))

    errors: list[str] = []
    for path, metadata, body in parsed:
        links = MARKDOWN_LINK_RE.findall(body) + HTML_LINK_RE.findall(body)
        for link in links:
            if link.startswith(STATIC_TOKEN_PREFIX):
                relative = link[len(STATIC_TOKEN_PREFIX):].split("#", 1)[0].split("?", 1)[0]
                if not (args.static_root / relative).is_file():
                    errors.append(f"{path}: missing static asset: {relative}")
                continue

            match = BLOG_LINK_RE.match(link)
            if match and match.group(1) not in slugs:
                errors.append(f"{path}: unknown blog slug in link: {match.group(1)}")

        for related in metadata.get("related_articles", []):
            if related not in slugs:
                errors.append(f"{path}: unknown related article slug: {related}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(f"Validated links in {len(parsed)} article(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
