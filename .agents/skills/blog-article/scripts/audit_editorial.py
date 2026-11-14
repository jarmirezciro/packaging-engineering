#!/usr/bin/env python3
"""Read-only editorial checks for KolliLabs articles."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
from hashlib import sha256
from html.parser import HTMLParser
from importlib import import_module
import json
from pathlib import Path
import re
import sys
from urllib.parse import parse_qs, unquote, urlsplit

if __name__ == "__main__":
    sys.dont_write_bytecode = True

import validate_article


REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
STATIC_PREFIX = "/static/"
SITE_HOSTS = {"kollilabs.com", "www.kollilabs.com"}
FIGURE_NUMBER = re.compile(r"\b(?:Figure|Fig\.?)\s+(\d+)\b", re.IGNORECASE)
CASE_ID = re.compile(r"[a-z0-9]+(?:[-_][a-z0-9]+)*")
FLOW_CASE = re.compile(r"/full-packaging/case/([^/]+)/")
TABLE_SEPARATOR = re.compile(r"^[ \t]*(?=[^\n]*\|)\|?[ \t]*:?-{3,}:?(?:[ \t]*\|[ \t]*:?-{3,}:?)*[ \t]*\|?[ \t]*$", re.MULTILINE)
HEADER_UNIT = re.compile(r"\((mm|cm|m|in|ft|g|kg|lb|%)\)\s*$", re.IGNORECASE)
CELL_UNIT = re.compile(r"^[-+]?\d[\d.,]*\s*(mm|cm|m|in|ft|g|kg|lb|%)$", re.IGNORECASE)

# Public and standalone views that consume named presets. The getters own the
# case keys, including aliases. Other routes need an integration check.
CASE_ROUTES = {
    "/free-box-size-calculator/": "container",
    "/container-selection/mode1/": "container",
    "/free-palletization-calculator/": "palletization",
    "/palletization/mode1/": "palletization",
    "/free-container-loading-calculator/": "transport",
    "/container-tool/": "transport",
    "/bag-selection/": "bag",
    "/bag-selection/mode1/": "bag",
}
CASE_GETTERS = {
    "container": "get_container_selection_case_preset",
    "palletization": "get_palletization_case_preset",
    "transport": "get_transport_container_case_preset",
    "bag": "get_bag_selection_case_preset",
    "full_packaging": "get_case_preset",
}


@dataclass
class Finding:
    rule: str
    kind: str
    status: str
    message: str


@dataclass
class Figure:
    line: int
    editorial: bool
    decorative: bool
    caption: list[str] = field(default_factory=list)


@dataclass
class Table:
    line: int
    rows: list[list[tuple[str, str]]] = field(default_factory=list)
    simple_columns: bool = True


class RenderedArticle(HTMLParser):
    """Collect just the elements needed from the production HTML fragment."""

    def __init__(self, html: str):
        super().__init__()
        self.images = []
        self.links = []
        self.figures: list[Figure] = []
        self.tables: list[Table] = []
        self.text = []
        self.figure = None
        self.in_caption = False
        self.ignored = []
        self.table_stack: list[Table] = []
        self.cell = None
        self.cell_text = []
        self.feed(html)
        self.close()

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        line = self.getpos()[0]
        if tag in {"pre", "code", "script", "style"}:
            self.ignored.append(tag)
        if self.ignored:
            return
        if tag in {"p", "div", "section", "br", "li"}:
            self.text.append("\n")
        if tag == "a" and attrs.get("href"):
            self.links.append(attrs["href"])
        if tag == "img":
            self.images.append((line, attrs))
        if tag == "figure":
            editorial = "blog-figure" in (attrs.get("class") or "").split()
            decorative = attrs.get("role") in {"presentation", "none"} or attrs.get("aria-hidden") == "true"
            self.figure = Figure(line, editorial, decorative)
            self.figures.append(self.figure)
        if tag == "figcaption":
            self.in_caption = True
        if tag == "table":
            table = Table(line)
            self.tables.append(table)
            self.table_stack.append(table)
        if self.table_stack and tag == "tr":
            self.table_stack[-1].rows.append([])
        if self.table_stack and tag in {"td", "th"}:
            self.cell = tag
            self.cell_text = []
            if attrs.get("colspan", "1") != "1" or attrs.get("rowspan", "1") != "1":
                self.table_stack[-1].simple_columns = False

    def handle_endtag(self, tag):
        if self.ignored:
            if tag == self.ignored[-1]:
                self.ignored.pop()
            return
        if tag in {"p", "div", "section", "li"}:
            self.text.append("\n")
        if tag == "figcaption":
            self.in_caption = False
        if tag == "figure":
            self.figure = None
        if self.table_stack and tag in {"td", "th"} and self.cell:
            table = self.table_stack[-1]
            if not table.rows:
                table.rows.append([])
            table.rows[-1].append((self.cell, "".join(self.cell_text).strip()))
            self.cell = None
        if tag == "table" and self.table_stack:
            self.table_stack.pop()

    def handle_data(self, data):
        if self.cell and not any(tag in self.ignored for tag in ("pre", "script", "style")):
            self.cell_text.append(data)
        if self.ignored:
            return
        if self.in_caption:
            if self.figure is not None:
                self.figure.caption.append(data)
        else:
            self.text.append(data)


def render_article(path: Path) -> tuple[str, str]:
    from django.conf import settings

    if not settings.configured:
        settings.configure(BASE_DIR=REPO_ROOT, STATIC_URL=STATIC_PREFIX)
    from packagingapp.services.blog_repository import _load_article

    return _load_article(path)["content_html"], str(settings.STATIC_URL).rstrip("/") + "/"


def parsed_url(value):
    try:
        return urlsplit(value)
    except ValueError:
        return None


def static_path(value: str, static_root: Path) -> tuple[str, Path]:
    decoded = unquote(value)
    parts = decoded.split("/")
    if any(not part or part.endswith(".") for part in parts) or re.search(r'[\\:\x00-\x20?#<>"|*]', decoded):
        raise ValueError(f"Unsafe static-relative path: {value!r}")
    path = static_root.joinpath(*parts).resolve()
    if not path.is_relative_to(static_root.resolve()):
        raise ValueError(f"Asset leaves the static directory: {value!r}")
    return decoded, path


def check_assets(metadata, page, static_root, prefix, validator_errors, findings):
    starting_count = len(findings)
    candidates = [
        (field, metadata[field])
        for field in ("thumbnail", "featured_image", "og_image", "hero_image")
        if field in metadata
    ]
    for field, image_field in (("thumbnail_alt", "thumbnail"), ("hero_image_alt", "hero_image")):
        alt = metadata.get(field)
        if image_field in metadata and (not isinstance(alt, str) or not alt.strip()):
            findings.append(Finding("ASSETS", "automated", "FAIL", f"{field} is empty or missing."))
    for line, attrs in page.images:
        source = attrs.get("src") or ""
        location = f"Image on rendered line {line}"
        if attrs.get("alt") is None:
            findings.append(Finding("ASSETS", "automated", "FAIL", f"{location} has no alt attribute."))
        url = parsed_url(source)
        if url and url.scheme in {"http", "https"} and url.hostname and url.hostname not in SITE_HOSTS:
            findings.append(Finding("ASSETS", "review", "REVIEW_REQUIRED", f"Check external image access and use rights: {source}"))
        elif url and url.scheme in {"", "http", "https"} and url.path.startswith(prefix) and (
            not url.netloc or url.hostname in SITE_HOSTS
        ):
            candidates.append(("body image", url.path[len(prefix):]))
        else:
            findings.append(Finding("ASSETS", "automated", "FAIL", f"{location} needs a valid static source: {source!r}"))

    references = set()
    for label, value in candidates:
        if not isinstance(value, str):
            findings.append(Finding("ASSETS", "automated", "FAIL", f"{label} must be a static-relative path."))
            continue
        try:
            relative, path = static_path(value, static_root)
            references.add(relative)
            if not path.is_file() and f"{label} asset does not exist: {value}" not in validator_errors:
                findings.append(Finding("ASSETS", "automated", "FAIL", f"{label} asset does not exist: {value}"))
        except (OSError, ValueError) as exc:
            findings.append(Finding("ASSETS", "automated", "FAIL", f"{label}: {exc}"))
    if not any(f.kind == "automated" for f in findings[starting_count:]) and not any(
        "asset" in error for error in validator_errors
    ):
        findings.append(Finding("ASSETS", "automated", "PASS", "Local image paths and required alt attributes checked."))
    return references


def check_tables(page, findings):
    rule = "EDR-07"
    text = "".join(page.text)
    leaks = TABLE_SEPARATOR.findall(text)
    if leaks:
        findings.append(Finding(rule, "automated", "FAIL", f"{len(leaks)} raw Markdown table separator(s) survived production rendering."))
    for table in page.tables:
        headers = [row for row in table.rows if any(tag == "th" for tag, _ in row)]
        data = [row for row in table.rows if row and all(tag == "td" for tag, _ in row)]
        if not any(value for row in headers for tag, value in row if tag == "th"):
            findings.append(Finding(rule, "automated", "FAIL", f"Table on rendered line {table.line} has no labeled headers."))
        if table.simple_columns and len(headers) == 1 and all(tag == "th" for tag, _ in headers[0]):
            for row in data:
                for (_, heading), (_, cell) in zip(headers[0], row):
                    expected = HEADER_UNIT.search(heading)
                    actual = CELL_UNIT.fullmatch(cell)
                    if expected and actual and expected[1].lower() != actual[1].lower():
                        findings.append(Finding(rule, "automated", "WARNING", f"Table on rendered line {table.line}: {cell!r} conflicts with unit in {heading!r}."))
    if not any(f.rule == rule and f.kind == "automated" for f in findings):
        status = "PASS" if page.tables else "NOT_APPLICABLE"
        findings.append(Finding(rule, "automated", status, f"Rendered tables found: {len(page.tables)}."))
    if page.tables or leaks:
        findings.append(Finding(rule, "visual", "REVIEW_REQUIRED", "Inspect rendered table styling, unit context and narrow-width readability."))


def check_figures(page, findings):
    rule = "EDR-08"
    captions = [(figure, "".join(figure.caption).strip()) for figure in page.figures if not figure.decorative]
    references = {int(number) for number in FIGURE_NUMBER.findall("".join(page.text))}
    numbered = references or any(FIGURE_NUMBER.match(caption) for _, caption in captions)
    series = [(figure, caption) for figure, caption in captions if figure.editorial or (numbered and caption)]
    if not series and not references:
        findings.append(Finding(rule, "automated", "NOT_APPLICABLE", "No numbered or blog-figure series detected."))
        return
    numbers = []
    for figure, caption in series:
        number = FIGURE_NUMBER.match(caption)
        if number:
            numbers.append(int(number[1]))
        else:
            findings.append(Finding(rule, "automated", "FAIL", f"Editorial figure on rendered line {figure.line} needs a numbered caption."))
    if numbers != list(range(1, len(numbers) + 1)):
        findings.append(Finding(rule, "automated", "FAIL", f"Caption numbers must run from 1 in order without duplicates or gaps. Found {numbers}."))
    unresolved = sorted(references - set(numbers))
    if unresolved:
        findings.append(Finding(rule, "automated", "FAIL", f"Prose references figure number(s) with no matching caption: {unresolved}."))
    if not any(f.rule == rule for f in findings):
        findings.append(Finding(rule, "automated", "PASS", "Caption order and explicit prose references agree in rendered HTML."))
    findings.append(Finding(rule, "visual", "REVIEW_REQUIRED", "Compare caption numbers with labels printed in the artwork and check caption meaning."))


def case_link(value):
    """Return (tool, preset), or None for URLs without an identifiable case."""
    if not isinstance(value, str) or re.search(r"\s|\\", value):
        raise ValueError(f"Invalid case URL: {value!r}")
    url = parsed_url(value)
    if url is None:
        raise ValueError(f"Invalid case URL: {value!r}")
    query = parse_qs(url.query, keep_blank_values=True)
    flow = FLOW_CASE.fullmatch(url.path)
    if "case" not in query and not url.path.startswith("/full-packaging/case/"):
        return None
    if (
        not url.path.startswith("/")
        or (url.scheme and (url.scheme != "https" or not url.netloc))
        or (url.netloc and url.netloc not in SITE_HOSTS)
    ):
        raise ValueError(f"Case URL must target a KolliLabs route: {value!r}")
    cases = query.get("case", [])
    if flow and not cases:
        slug = flow[1]
    elif len(cases) == 1 and not url.path.startswith("/full-packaging/case/"):
        slug = cases[0]
    else:
        raise ValueError(f"Case URL must identify exactly one case: {value!r}")
    if not CASE_ID.fullmatch(slug):
        raise ValueError(f"Invalid case identifier in {value!r}")
    return ("full_packaging" if flow else CASE_ROUTES.get(url.path), slug)


def check_cases(metadata, page, require_case, findings):
    rule = "EDR-11"
    cta = metadata.get("cta")
    cta_url = cta.get("url", "") if isinstance(cta, dict) else ""
    required = require_case or metadata.get("article_type") == "demo_case_study"
    try:
        cta_case = case_link(cta_url)
    except ValueError as exc:
        findings.append(Finding(rule, "automated", "FAIL", str(exc)))
        cta_case = None
    body_cases = set()
    for url in dict.fromkeys(page.links):
        parsed = parsed_url(url)
        if not parsed or (parsed.netloc and parsed.netloc not in SITE_HOSTS):
            continue
        try:
            destination = case_link(url)
        except ValueError as exc:
            if re.search(r"[?&]case(?:[=&]|$)|/full-packaging/case/", url):
                findings.append(Finding(rule, "automated", "FAIL", str(exc)))
            continue
        if destination:
            body_cases.add(destination)
    destinations = body_cases | ({cta_case} if cta_case else set())
    if (required or destinations) and not cta_case:
        findings.append(Finding(rule, "automated", "FAIL", "Front-matter CTA must identify an article-specific case."))
    if len(destinations) > 1:
        findings.append(Finding(rule, "automated", "WARNING", "Multiple case destinations. Check that the body and CTA describe the same primary case and label alternatives."))
    if cta_case and cta_case not in body_cases:
        findings.append(Finding(rule, "automated", "WARNING", "The article body has no matching case link for the front-matter CTA."))
    for tool, slug in sorted(destinations, key=str):
        if tool is None:
            findings.append(Finding(rule, "automated", "WARNING", f"No static preset lookup is mapped for the route used by {slug!r}."))
            continue
        presets = import_module(f"packagingapp.tools.{tool}.case_presets")
        preset = getattr(presets, CASE_GETTERS[tool])(slug)
        if preset is None:
            findings.append(Finding(rule, "automated", "FAIL", f"No {tool} preset named {slug!r}."))
        else:
            findings.append(Finding(rule, "automated", "PASS", f"Found {tool} preset {slug!r} in the repository."))
    if destinations:
        findings.append(Finding(rule, "review", "REVIEW_REQUIRED", "Open the actual tool in future integration QA and verify prefilled values, case scope and CTA behavior."))
    elif not any(f.rule == rule for f in findings):
        findings.append(Finding(rule, "automated", "NOT_APPLICABLE", "No named case or demo CTA requirement detected. Use --require-case for a benchmark intended to be runnable."))


def check_evidence(path, metadata, page, comparative, findings):
    rule = "EDR-10"
    notes = REPO_ROOT / "docs" / "blog" / f"research-notes-{path.stem}.md"
    external = []
    for link in dict.fromkeys(page.links):
        url = parsed_url(link)
        if url and url.scheme in {"https", "http"} and url.hostname and url.hostname not in SITE_HOSTS:
            external.append(link)
    # The editorial profile is independent of article_type. An explicit option
    # covers comparisons whose title does not signal a benchmark.
    title = str(metadata.get("title") or "")
    comparative = comparative or bool(re.search(r"\b(?:benchmark|vs\.?|versus)\b", title, re.IGNORECASE))
    if not (comparative or external or notes.is_file()):
        findings.append(Finding(rule, "automated", "NOT_APPLICABLE", "No external links, research ledger or comparison signal detected. Use --comparative when external results are discussed."))
        return
    if notes.is_file():
        findings.append(Finding(rule, "automated", "PASS", f"Local evidence record available: {notes.relative_to(REPO_ROOT).as_posix()}. Local record presence does not establish a source archive."))
    if external:
        findings.append(Finding(rule, "automated", "WARNING", f"{len(external)} external link(s) present. Source archival was not verified."))
    if not external and not notes.is_file():
        findings.append(Finding(rule, "automated", "FAIL", "Comparison has no external source links or matching research notes."))
    findings.append(Finding(rule, "review", "REVIEW_REQUIRED", "Verify claim-to-source mapping, archive and reuse status, reported versus reproduced values, numeric units and engineering scope."))


def asset_hash(path):
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_approvals(slug, thumbnail, references, static_root, approval_record, findings):
    # Production's tracked editorial fixture pins reviewed thumbnail bytes.
    # It is an asset baseline only, independent of visual QA and publication.
    from packagingapp.tests.test_blog_editorial_metadata import APPROVED_THUMBNAIL_HASHES

    rule = "EDR-12"
    baselines = {
        path: checksum for path, checksum in APPROVED_THUMBNAIL_HASHES.items()
        if path.startswith(f"img/blog/{slug}/")
    }
    if baselines and approval_record is None and thumbnail not in baselines:
        findings.append(Finding(rule, "automated", "FAIL", "Selected thumbnail differs from the tracked production approval path. Supply a trusted approval record for an authorized replacement."))
    if approval_record is not None:
        try:
            record = json.loads(approval_record.read_text(encoding="utf-8"))
            approved = record.get("assets") if isinstance(record, dict) else None
            if not isinstance(approved, dict) or not approved or record.get("article_slug") != slug:
                raise ValueError("Expected the article_slug and a non-empty assets mapping.")
            for path, checksum in approved.items():
                static_path(path, static_root)
                if not isinstance(checksum, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", checksum):
                    raise ValueError(f"Invalid SHA-256 for {path!r}.")
            baselines = approved
        except (OSError, ValueError) as exc:
            findings.append(Finding(rule, "automated", "FAIL", f"Cannot read supplied approval baseline: {exc}"))
            return
    if not baselines:
        findings.append(Finding(rule, "review", "REVIEW_REQUIRED", "No verified approval baseline available for hash preservation."))
        return
    for relative, checksum in baselines.items():
        try:
            _, asset = static_path(relative, static_root)
            if relative not in references:
                raise ValueError("approved path is no longer referenced")
            if asset_hash(asset) != checksum.lower():
                raise ValueError("SHA-256 differs from approval baseline")
        except (OSError, ValueError) as exc:
            findings.append(Finding(rule, "automated", "FAIL", f"{relative}: {exc}"))
        else:
            source = "supplied approval record" if approval_record else "production thumbnail baseline"
            findings.append(Finding(rule, "automated", "PASS", f"{relative} matches the {source}."))
    if references - baselines.keys():
        findings.append(Finding(rule, "review", "REVIEW_REQUIRED", "Asset references outside the byte baseline still require preservation and approval review."))


def check_thumbnail(path, thumbnail_report, findings):
    rule = "EDR-09"
    if thumbnail_report is not None:
        try:
            report = json.loads(thumbnail_report.read_text(encoding="utf-8"))
            if not isinstance(report, dict) or not isinstance(report.get("file"), dict) or not isinstance(report.get("layout"), dict):
                raise ValueError("Expected a validation report from the thumbnail workflow.")
            if asset_hash(path) != report["file"].get("sha256"):
                raise ValueError("Thumbnail bytes differ from the supplied validation report.")
            from thumbnail_workflow import validate_rendered_thumbnail

            validation = validate_rendered_thumbnail(path, report)
            for message in validation["hard_failures"]:
                findings.append(Finding(rule, "automated", "FAIL", message))
            for message in validation["warnings"]:
                findings.append(Finding(rule, "automated", "WARNING", message))
            if validation["hard_status"] == "pass":
                findings.append(Finding(rule, "automated", "PASS", "Existing thumbnail workflow checks passed for the supplied report."))
        except (OSError, ValueError, TypeError, IndexError) as exc:
            findings.append(Finding(rule, "automated", "FAIL", f"Cannot validate thumbnail report: {exc}"))
    findings.append(Finding(rule, "visual", "REVIEW_REQUIRED", "Use the thumbnail workflow and inspect the thumbnail at full and card size. Confirm owner approval separately."))


def audit(path, *, comparative=False, require_case=False, approval_record=None, thumbnail_report=None):
    findings = []
    try:
        existing_errors = validate_article.validate(path)
    except (TypeError, UnicodeError, OSError, ValueError) as exc:
        existing_errors = [str(exc)]
    for error in existing_errors:
        findings.append(Finding("SCHEMA", "automated", "FAIL", error))
    if not existing_errors:
        findings.append(Finding("SCHEMA", "automated", "PASS", "Existing article validator passed."))

    for rule, message in (
        ("EDR-01", "Review the opening with the Fresh-Eyes Business Reader."),
        ("EDR-02", "Review terminology, caveats and reader-facing language with the Fresh-Eyes Business Reader."),
        ("EDR-03", "Review the progression from setup to results and engineering implications."),
        ("EDR-04", "Inspect actual geometry and labels against the verified source inputs and results."),
        ("EDR-05", "Review physical context and in-scope stages using Packaging Scenario Setup."),
        ("EDR-06", "Review screenshot fidelity and composition with the Visual Editorial Critic where applicable."),
    ):
        findings.append(Finding(rule, "editorial" if rule < "EDR-04" else "visual", "REVIEW_REQUIRED", message))

    try:
        metadata, _ = validate_article.parse_article(path)
        html, prefix = render_article(path)
    except (ImportError, OSError, TypeError, ValueError) as exc:
        for rule in ("ASSETS", *(f"EDR-{i:02d}" for i in range(7, 13))):
            findings.append(Finding(rule, "automated", "REVIEW_REQUIRED", f"Production rendering unavailable: {exc}"))
        return findings

    page = RenderedArticle(html)
    static_root = REPO_ROOT / "static"
    references = check_assets(metadata, page, static_root, prefix, existing_errors, findings)
    check_tables(page, findings)
    check_figures(page, findings)
    check_evidence(path, metadata, page, comparative, findings)
    check_cases(metadata, page, require_case, findings)
    check_approvals(path.stem, metadata.get("thumbnail"), references, static_root, approval_record, findings)
    try:
        _, thumbnail = static_path(str(metadata.get("thumbnail", "")), static_root)
    except (OSError, ValueError):
        findings.append(Finding("EDR-09", "visual", "REVIEW_REQUIRED", "Resolve the thumbnail reference before running thumbnail QA."))
    else:
        check_thumbnail(thumbnail, thumbnail_report, findings)
    return findings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("article", type=Path)
    parser.add_argument("--json", action="store_true", help="Print machine-readable findings.")
    parser.add_argument("--comparative", action="store_true", help="Check external comparison evidence regardless of title or metadata.")
    parser.add_argument("--require-case", action="store_true", help="Require a named case for a runnable benchmark.")
    parser.add_argument("--approval-record", type=Path, help="Trusted JSON approval record for this article.")
    parser.add_argument("--thumbnail-report", type=Path, help="Validation JSON from the existing thumbnail workflow.")
    args = parser.parse_args()
    findings = audit(
        args.article, comparative=args.comparative, require_case=args.require_case,
        approval_record=args.approval_record, thumbnail_report=args.thumbnail_report,
    )
    automated = [finding for finding in findings if finding.kind == "automated"]
    failed = any(finding.status == "FAIL" for finding in automated)
    automated_status = (
        "FAIL" if failed else
        "REVIEW_REQUIRED" if any(f.status == "REVIEW_REQUIRED" for f in automated) else
        "WARNING" if any(f.status == "WARNING" for f in automated) else "PASS"
    )
    if args.json:
        print(json.dumps({
            "article": str(args.article),
            "automated_validation": automated_status,
            "editorial_and_visual_review": "REVIEW_REQUIRED",
            "publication_readiness": "BLOCKED" if failed else "REVIEW_REQUIRED",
            "findings": [asdict(f) for f in findings],
        }, indent=2))
    else:
        print(f"Editorial QA: {args.article}")
        for finding in sorted(findings, key=lambda item: item.rule):
            print(f"{finding.rule} {finding.kind} {finding.status}: {finding.message}")
        print(f"Automated validation: {automated_status}")
        print("Editorial, visual and evidence gates: review required. Publication readiness has not been established.")
    return int(failed or automated_status == "REVIEW_REQUIRED")


if __name__ == "__main__":
    raise SystemExit(main())
