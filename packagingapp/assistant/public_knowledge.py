"""Reviewed, bounded retrieval for anonymous Public Expert requests."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
import re
from threading import RLock
from typing import Any

from .knowledge import KnowledgeSource, ParsedKnowledgeSection, parse_markdown_sections
from .public_contracts import (
    MAX_PUBLIC_KNOWLEDGE_SECTION_CHARS,
    MAX_PUBLIC_KNOWLEDGE_SECTIONS,
    MAX_PUBLIC_KNOWLEDGE_TEXT_CHARS,
    PUBLIC_KNOWLEDGE_CONTEXT_SCHEMA_VERSION,
    PublicKnowledgeContext,
    empty_public_knowledge_context,
    validate_public_knowledge_context,
)


logger = logging.getLogger(__name__)

_WORD = re.compile(r"[a-z0-9]+")
_cache_lock = RLock()
_public_source_cache: dict[
    str,
    tuple[tuple[int, int], tuple[ParsedKnowledgeSection, ...]],
] = {}

_PUBLIC_STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "can",
        "does",
        "do",
        "for",
        "from",
        "how",
        "i",
        "in",
        "is",
        "it",
        "mean",
        "my",
        "of",
        "on",
        "please",
        "should",
        "the",
        "this",
        "to",
        "use",
        "what",
        "which",
        "with",
        "work",
        "works",
    }
)

PUBLIC_SCOPE_ALIASES = {
    "container_selection": (
        "container selection",
        "box selection",
        "box size",
        "container design",
        "design mode",
        "r1",
        "r2",
        "r3",
        "cubicity",
    ),
    "bag_selection": (
        "bag selection",
        "bag size",
        "lay flat",
        "sealing margin",
        "sealing space",
    ),
    "palletization": (
        "palletization",
        "palletisation",
        "pallet",
        "p1",
        "p2",
        "pinwheel",
        "brick pattern",
    ),
    "transport": (
        "transport container",
        "container loading",
        "transport loading",
        "trailer",
        "balanced spread",
        "progressive fill",
        "space evenly",
        "front to back",
    ),
    "corrugated": (
        "corrugated",
        "fefco",
        "mckee",
        "ect",
        "bct",
    ),
    "packaging_flow": ("packaging flow", "full packaging"),
}


@dataclass(frozen=True)
class PublicKnowledgeSource:
    path: str
    include_headings: tuple[str, ...]
    tool_tags: tuple[str, ...] = ()


# Every heading below was reviewed for anonymous disclosure. Files or headings
# not listed here are never eligible for the Public Expert provider payload.
PUBLIC_KNOWLEDGE_REGISTRY = (
    PublicKnowledgeSource(
        "docs/product/public-kollipack-knowledge.md",
        (
            "KolliLabs and KolliPack",
            "Available KolliPack tools",
            "Choosing a tool",
            "Public Expert boundary",
        ),
    ),
    PublicKnowledgeSource(
        "docs/product/company-context.md",
        ("Identity", "Why KolliLabs exists", "Offer structure", "Voice"),
    ),
    PublicKnowledgeSource(
        "docs/product/product-vision.md",
        ("Product vision", "Product principles", "Public-site separation"),
    ),
    PublicKnowledgeSource(
        "docs/product/terminology.md",
        (
            "General",
            "Dimensions",
            "Container selection",
            "Bag selection",
            "Palletization",
            "Transport loading",
        ),
    ),
    PublicKnowledgeSource(
        "docs/domain/container-selection-logic.md",
        (
            "Purpose",
            "R1, R2, and R3",
            "Modes",
            "Single mode",
            "Optimal mode",
            "Assumptions",
            "Internal and external carton dimensions",
            "Design quantity and additional capacity",
            "Cubicity",
            "Design efficiency",
        ),
        ("container_selection",),
    ),
    PublicKnowledgeSource(
        "docs/domain/bag-selection-logic.md",
        ("Purpose", "Established behaviour", "Assumptions"),
        ("bag_selection",),
    ),
    PublicKnowledgeSource(
        "docs/domain/palletization-logic.md",
        (
            "Purpose",
            "Inputs",
            "Block pattern",
            "Brick pattern",
            "P1 and P2",
            "Layer count and height",
            "Pallet payload",
            "Bottom-carton load",
            "Column and interlock",
        ),
        ("palletization",),
    ),
    PublicKnowledgeSource(
        "docs/domain/corrugated-material-strength.md",
        (
            "Purpose",
            "Scope and boundaries",
            "External dimensions and pallet basis",
            "Practical compression capacity",
            "FEFCO 0201 geometry",
            "Strength calculation",
            "CO₂ screening",
            "Known limitations and future extensions",
        ),
        ("corrugated",),
    ),
    PublicKnowledgeSource(
        "docs/domain/transport-selection-logic.md",
        (
            "Purpose",
            "Transport unit",
            "Product/load rows",
            "How Balanced Spread behaves for users",
            "How Progressive Fill behaves for users",
            "Weight and payload",
            "Results, metrics, and presentation",
            "Doors, access, and physical validation",
            "Business use and Packaging Flow role",
            "User-facing interpretation",
        ),
        ("transport",),
    ),
    PublicKnowledgeSource(
        "docs/architecture/packaging-flow.md",
        ("Purpose", "Upstream inheritance", "Inherited input"),
        ("packaging_flow",),
    ),
    PublicKnowledgeSource(
        "docs/features/public-site-blog-and-seo.md",
        ("Site roles", "SEO calculator architecture", "SEO content rules"),
    ),
)

PUBLIC_KNOWLEDGE_SOURCE_PATHS = frozenset(
    source.path for source in PUBLIC_KNOWLEDGE_REGISTRY
)


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_public_sections(
    *,
    repository_root: Path | None = None,
    registry: tuple[PublicKnowledgeSource, ...] = PUBLIC_KNOWLEDGE_REGISTRY,
) -> tuple[ParsedKnowledgeSection, ...]:
    root = (repository_root or _repository_root()).resolve()
    loaded: list[ParsedKnowledgeSection] = []
    for public_source in registry:
        if registry is PUBLIC_KNOWLEDGE_REGISTRY and public_source.path not in PUBLIC_KNOWLEDGE_SOURCE_PATHS:
            raise ValueError("Public knowledge source is not approved.")
        candidate = (root / public_source.path).resolve()
        candidate.relative_to(root)
        stat = candidate.stat()
        fingerprint = (stat.st_mtime_ns, stat.st_size)
        cache_key = f"{candidate}|{public_source.tool_tags!r}"
        with _cache_lock:
            cached = _public_source_cache.get(cache_key)
        if cached is None or cached[0] != fingerprint:
            parsed = parse_markdown_sections(
                candidate.read_text(encoding="utf-8-sig"),
                KnowledgeSource(public_source.path, public_source.tool_tags),
            )
            with _cache_lock:
                _public_source_cache[cache_key] = (fingerprint, parsed)
        else:
            parsed = cached[1]
        approved_headings = frozenset(public_source.include_headings)
        loaded.extend(section for section in parsed if section.title in approved_headings)
    return tuple(loaded)


def clear_public_knowledge_cache() -> None:
    with _cache_lock:
        _public_source_cache.clear()


def _normalized(value: str) -> str:
    return " ".join(_WORD.findall(value.lower()))


def _stem(token: str) -> str:
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 4 and token.endswith("s"):
        return token[:-1]
    return token


def _tokens(value: str) -> tuple[str, ...]:
    return tuple(_stem(token) for token in _WORD.findall(value.lower()))


def _explicit_scopes(question: str) -> tuple[str, ...]:
    normalized = _normalized(question)
    matches: list[tuple[int, str]] = []
    for scope, aliases in PUBLIC_SCOPE_ALIASES.items():
        for alias in aliases:
            match = re.search(rf"\b{re.escape(alias)}\b", normalized)
            if match:
                matches.append((match.start(), scope))
                break
    matches.sort()
    result: list[str] = []
    for _position, scope in matches:
        if scope not in result:
            result.append(scope)
    if "transport" in result and "container_selection" in result:
        if not any(
            phrase in normalized
            for phrase in ("container selection", "box selection", "box size", "container design")
        ):
            result.remove("container_selection")
    return tuple(result)


def _score_section(
    section: ParsedKnowledgeSection,
    *,
    question: str,
    knowledge_scope: str,
    explicit_scopes: tuple[str, ...],
) -> int | None:
    normalized_question = _normalized(question)
    query_tokens = {
        token for token in _tokens(normalized_question) if token not in _PUBLIC_STOP_WORDS
    }
    if "tool" in normalized_question or "calculator" in normalized_question:
        query_tokens.update({"tool", "calculator", "available", "choosing"})
    if "this tool" in normalized_question and knowledge_scope != "global":
        query_tokens.update(_tokens(knowledge_scope.replace("_", " ")))

    heading = _normalized(" ".join(section.heading_path))
    title = _normalized(section.title)
    body = _normalized(section.text)
    heading_tokens = set(_tokens(heading))
    body_tokens = set(_tokens(body))
    section_tags = set(section.tool_tags)

    score = 0
    lexical_matches = 0
    for token in query_tokens:
        if token in heading_tokens:
            score += 20
            lexical_matches += 1
        elif token in body_tokens:
            score += 4
            lexical_matches += 1
    for phrase in PUBLIC_SCOPE_ALIASES.get(knowledge_scope, ()):
        if phrase in normalized_question and phrase in f"{heading} {body}":
            score += 32

    if knowledge_scope != "global" and knowledge_scope in section_tags:
        score += 26
    if not section_tags and knowledge_scope == "global":
        score += 8
    if explicit_scopes:
        matching = section_tags.intersection(explicit_scopes)
        if matching:
            score += 65 * len(matching)
        elif section_tags:
            score -= 35

    comparison = any(
        phrase in normalized_question
        for phrase in (" vs ", " versus ", "difference", "different from", "compare")
    )
    purpose_question = (
        normalized_question.startswith("what does ")
        or normalized_question.startswith("what is ")
        or normalized_question.startswith("how does ")
    )
    if purpose_question and section.title == "Purpose" and section_tags.intersection(
        explicit_scopes
    ):
        score += 70
    if comparison and section.title == "Purpose" and section_tags.intersection(explicit_scopes):
        score += 45
    if section.title == "Choosing a tool" and any(
        word in normalized_question for word in ("which tool", "what tool")
    ):
        score += 90
    if section.title == "Available KolliPack tools" and any(
        word in normalized_question for word in ("available", "tools", "provide")
    ):
        score += 90
    if section.title == "KolliLabs and KolliPack" and (
        "kollilabs" in normalized_question or "what is kollipack" in normalized_question
    ):
        score += 90
    if "this tool" in normalized_question and knowledge_scope in section_tags and title == "purpose":
        score += 70

    if lexical_matches == 0 and score < 40:
        return None
    return score if score >= 8 else None


def _rank_public_sections(
    sections: tuple[ParsedKnowledgeSection, ...],
    *,
    question: str,
    knowledge_scope: str,
) -> list[ParsedKnowledgeSection]:
    explicit_scopes = _explicit_scopes(question)
    scored: list[tuple[int, str, ParsedKnowledgeSection]] = []
    for section in sections:
        score = _score_section(
            section,
            question=question,
            knowledge_scope=knowledge_scope,
            explicit_scopes=explicit_scopes,
        )
        if score is not None:
            scored.append((score, section.ref, section))
    scored.sort(key=lambda item: (-item[0], item[1]))

    selected: list[ParsedKnowledgeSection] = []
    selected_refs: set[str] = set()
    if len(explicit_scopes) > 1:
        for scope in explicit_scopes:
            match = next(
                (
                    section
                    for _score, _ref, section in scored
                    if scope in section.tool_tags and section.ref not in selected_refs
                ),
                None,
            )
            if match is not None:
                selected.append(match)
                selected_refs.add(match.ref)
    for _score, _ref, section in scored:
        if len(selected) >= MAX_PUBLIC_KNOWLEDGE_SECTIONS:
            break
        if section.ref not in selected_refs:
            selected.append(section)
            selected_refs.add(section.ref)
    return selected


def _truncate_at_boundary(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text.rfind("\n\n", 0, limit + 1)
    if cut < limit // 2:
        cut = text.rfind("\n", 0, limit + 1)
    if cut < limit // 2:
        cut = text.rfind(" ", 0, limit + 1)
    if cut < limit // 2:
        cut = limit
    return text[:cut].rstrip()


def _as_public_context(sections: list[ParsedKnowledgeSection]) -> PublicKnowledgeContext:
    bounded = []
    remaining = MAX_PUBLIC_KNOWLEDGE_TEXT_CHARS
    for section in sections[:MAX_PUBLIC_KNOWLEDGE_SECTIONS]:
        text = _truncate_at_boundary(
            section.text,
            min(MAX_PUBLIC_KNOWLEDGE_SECTION_CHARS, remaining),
        )
        if not text:
            break
        bounded.append(
            {
                "ref": section.ref,
                "title": section.title,
                "heading_path": list(section.heading_path),
                "text": text,
            }
        )
        remaining -= len(text)
    context: PublicKnowledgeContext = {
        "schema_version": PUBLIC_KNOWLEDGE_CONTEXT_SCHEMA_VERSION,
        "status": "available" if bounded else "no_match",
        "sections": bounded,
    }
    return validate_public_knowledge_context(context)


def retrieve_public_knowledge_context(
    question: str,
    *,
    knowledge_scope: str,
    repository_root: Path | None = None,
    registry: tuple[PublicKnowledgeSource, ...] = PUBLIC_KNOWLEDGE_REGISTRY,
) -> PublicKnowledgeContext:
    try:
        if not isinstance(question, str) or not question.strip():
            return empty_public_knowledge_context()
        sections = _load_public_sections(
            repository_root=repository_root,
            registry=registry,
        )
        return _as_public_context(
            _rank_public_sections(
                sections,
                question=question,
                knowledge_scope=knowledge_scope,
            )
        )
    except Exception:
        logger.warning(
            "Public Expert knowledge retrieval failed safely.",
            extra={"public_expert_knowledge_outcome": "unavailable"},
        )
        return empty_public_knowledge_context(unavailable=True)


def public_knowledge_trace(context: PublicKnowledgeContext) -> list[dict[str, Any]]:
    validate_public_knowledge_context(context)
    return [
        {
            "ref": section["ref"],
            "title": section["title"],
            "heading_path": list(section["heading_path"]),
        }
        for section in context["sections"]
    ]


__all__ = [
    "PUBLIC_KNOWLEDGE_REGISTRY",
    "PUBLIC_KNOWLEDGE_SOURCE_PATHS",
    "PublicKnowledgeSource",
    "clear_public_knowledge_cache",
    "public_knowledge_trace",
    "retrieve_public_knowledge_context",
]
