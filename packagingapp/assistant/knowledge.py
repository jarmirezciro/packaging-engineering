"""Bounded, deterministic retrieval over approved KolliPack documentation.

Knowledge Context is deliberately separate from Tool Context.  It describes
stable KolliPack concepts and tool behaviour; it never represents a user's
current calculation state and never invokes an engineering engine.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from pathlib import Path
import re
from threading import RLock
from typing import Any, Iterable, TypedDict

from django.conf import settings


logger = logging.getLogger(__name__)

KNOWLEDGE_CONTEXT_SCHEMA_VERSION = "1.0"
KNOWLEDGE_STATUS_AVAILABLE = "available"
KNOWLEDGE_STATUS_NO_MATCH = "no_match"
KNOWLEDGE_STATUS_UNAVAILABLE = "unavailable"
KNOWLEDGE_STATUSES = frozenset(
    {
        KNOWLEDGE_STATUS_AVAILABLE,
        KNOWLEDGE_STATUS_NO_MATCH,
        KNOWLEDGE_STATUS_UNAVAILABLE,
    }
)

MAX_KNOWLEDGE_SECTIONS = 6
MAX_KNOWLEDGE_SECTION_CHARS = 2_500
MAX_KNOWLEDGE_TEXT_CHARS = 12_000
MAX_KNOWLEDGE_CONTEXT_BYTES = 20 * 1024
MAX_KNOWLEDGE_REF_LENGTH = 200
MAX_KNOWLEDGE_SOURCE_LENGTH = 180
MAX_KNOWLEDGE_TITLE_LENGTH = 180
MAX_HEADING_PATH_ITEMS = 8

_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_FENCE = re.compile(r"^\s*(```|~~~)")
_WORD = re.compile(r"[a-z0-9]+")
_WHITESPACE = re.compile(r"\s+")
_NON_SLUG = re.compile(r"[^a-z0-9]+")


class KnowledgeSection(TypedDict):
    ref: str
    source: str
    title: str
    heading_path: list[str]
    authority: str
    confidence: list[str]
    text: str


class KnowledgeContext(TypedDict):
    schema_version: str
    status: str
    sections: list[KnowledgeSection]


class KnowledgeContextValidationError(ValueError):
    """Raised when application-selected knowledge violates its strict contract."""


@dataclass(frozen=True)
class KnowledgeSource:
    path: str
    tool_tags: tuple[str, ...] = ()

    @property
    def semantic_id(self) -> str:
        value = self.path.removeprefix("docs/")
        return value.removesuffix(".md")


@dataclass(frozen=True)
class ParsedKnowledgeSection:
    ref: str
    source: str
    title: str
    heading_path: tuple[str, ...]
    authority: str
    confidence: tuple[str, ...]
    text: str
    tool_tags: tuple[str, ...]


# This tuple is the complete Session 8.5A corpus.  New Markdown files do not
# enter provider-eligible knowledge unless they are explicitly added here.
APPROVED_KNOWLEDGE_SOURCES = (
    KnowledgeSource(
        "docs/product/terminology.md",
        ("container_selection", "bag_selection", "palletization", "transport_container"),
    ),
    KnowledgeSource("docs/product/product-vision.md"),
    KnowledgeSource("docs/domain/general-packaging-rules.md"),
    KnowledgeSource("docs/domain/container-selection-logic.md", ("container_selection",)),
    KnowledgeSource("docs/domain/bag-selection-logic.md", ("bag_selection",)),
    KnowledgeSource("docs/domain/palletization-logic.md", ("palletization",)),
    KnowledgeSource("docs/domain/transport-container-engine.md", ("transport_container",)),
    KnowledgeSource("docs/domain/transport-selection-logic.md", ("transport_container",)),
    KnowledgeSource("docs/architecture/packaging-flow.md", ("packaging_flow",)),
    KnowledgeSource("docs/features/three-d-rendering-and-reports.md"),
)
APPROVED_KNOWLEDGE_SOURCE_PATHS = frozenset(
    source.path for source in APPROVED_KNOWLEDGE_SOURCES
)

TOOL_ALIASES = {
    "transport_container": (
        "transport container",
        "transport loading",
        "transport selection",
        "transport",
        "balanced spread",
        "progressive fill",
        "space evenly",
        "front to back",
        "product block",
        "dgfe",
        "frontier efficiency",
        "deferred gravity frontier envelope",
    ),
    "container_selection": (
        "container selection",
        "box selection",
        "container design",
        "box design",
        "container",
        "box",
    ),
    "bag_selection": ("bag selection", "bag design", "bag"),
    "palletization": ("palletization", "palletisation", "pallet"),
    "packaging_flow": ("packaging flow",),
}

# Distinctive documented terms may identify a tool even when the user asks
# from another surface without naming that tool.  These are routing aliases,
# not semantic expansion: every answer still comes from the approved corpus.
TOOL_CONCEPT_HINTS = (
    ("sealing margin", "bag_selection"),
    ("sealing space", "bag_selection"),
    ("lay flat", "bag_selection"),
    ("p1", "palletization"),
    ("p2", "palletization"),
    ("brick pattern", "palletization"),
    ("pinwheel", "palletization"),
    ("mosaic", "palletization"),
    ("inherited input", "packaging_flow"),
    ("pending and selected", "packaging_flow"),
)

# These short terms have different meanings in multiple tools.  With no tool
# named, the active tool owns the interpretation.  This prevents raw keyword
# frequency from leaking, for example, Transport frontier efficiency into a
# Container question or a Product Block into a Palletization question.
AMBIGUOUS_CONCEPT_TOOLS = (
    ("design mode", ("container_selection", "bag_selection")),
    ("design", ("container_selection", "bag_selection")),
    (
        "efficiency",
        ("container_selection", "palletization", "transport_container"),
    ),
    ("cubicity", ("container_selection", "bag_selection")),
    ("additional capacity", ("container_selection", "bag_selection")),
    (
        "restriction",
        (
            "container_selection",
            "bag_selection",
            "palletization",
            "transport_container",
        ),
    ),
    ("block", ("palletization", "transport_container")),
)

_TERMINOLOGY_HEADING_TO_TOOL = {
    "container selection": "container_selection",
    "bag selection": "bag_selection",
    "palletization": "palletization",
    "transport loading": "transport_container",
}

_AUTHORITY_MARKERS = (
    ("repository verification required", "repository_verification_required"),
    ("current implementation note", "current_implementation_note"),
    ("intended rule", "intended_rule"),
    ("established", "established"),
)

_DEFINITION_PREFIXES = (
    "what is ",
    "what are ",
    "what does ",
    "meaning of ",
    "explain ",
    "how does ",
    "how do ",
)
_STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "about",
        "can",
        "could",
        "does",
        "do",
        "did",
        "for",
        "from",
        "how",
        "i",
        "in",
        "is",
        "input",
        "kollipack",
        "mean",
        "meaning",
        "my",
        "of",
        "on",
        "result",
        "state",
        "the",
        "this",
        "these",
        "please",
        "should",
        "tell",
        "tool",
        "to",
        "use",
        "using",
        "we",
        "what",
        "which",
        "with",
        "would",
        "why",
        "work",
        "works",
    }
)

_cache_lock = RLock()
_source_cache: dict[str, tuple[tuple[int, int], tuple[ParsedKnowledgeSection, ...]]] = {}


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _clean_heading(value: str) -> str:
    cleaned = value.strip().strip("#").strip()
    cleaned = re.sub(r"[`*_]", "", cleaned)
    cleaned = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", cleaned)
    return _WHITESPACE.sub(" ", cleaned)[:MAX_KNOWLEDGE_TITLE_LENGTH]


def _slug(value: str) -> str:
    normalized = _NON_SLUG.sub("-", value.lower()).strip("-")
    return (normalized or "section")[:96]


def _markdown_blocks(text: str) -> list[str]:
    blocks: list[str] = []
    current: list[str] = []
    fence_marker = ""
    for line in text.splitlines():
        fence = _FENCE.match(line)
        if fence:
            marker = fence.group(1)
            if not fence_marker:
                fence_marker = marker
            elif fence_marker == marker:
                fence_marker = ""
            current.append(line)
            continue
        if not fence_marker and not line.strip():
            if current:
                blocks.append("\n".join(current).strip())
                current = []
            continue
        current.append(line)
    if current:
        blocks.append("\n".join(current).strip())
    return [block for block in blocks if block]


def _split_oversized_block(block: str, limit: int) -> list[str]:
    if len(block) <= limit:
        return [block]
    pieces: list[str] = []
    remaining = block
    while len(remaining) > limit:
        cut = remaining.rfind("\n", 0, limit + 1)
        if cut < limit // 2:
            cut = remaining.rfind(" ", 0, limit + 1)
        if cut < limit // 2:
            cut = limit
        pieces.append(remaining[:cut].rstrip())
        remaining = remaining[cut:].lstrip()
    if remaining:
        pieces.append(remaining)
    return pieces


def _split_section_text(text: str) -> list[str]:
    blocks: list[str] = []
    for block in _markdown_blocks(text):
        blocks.extend(_split_oversized_block(block, MAX_KNOWLEDGE_SECTION_CHARS))

    chunks: list[str] = []
    current = ""
    for block in blocks:
        candidate = block if not current else f"{current}\n\n{block}"
        if len(candidate) <= MAX_KNOWLEDGE_SECTION_CHARS:
            current = candidate
            continue
        if current:
            chunks.append(current)
        current = block
    if current:
        chunks.append(current)
    return chunks


def _confidence_labels(heading_path: Iterable[str], text: str) -> tuple[str, ...]:
    haystack = "\n".join((*heading_path, text)).lower()
    return tuple(
        label for marker, label in _AUTHORITY_MARKERS if marker in haystack
    )


def parse_markdown_sections(
    markdown: str,
    source: KnowledgeSource,
) -> tuple[ParsedKnowledgeSection, ...]:
    """Parse heading-owned Markdown bodies into deterministic bounded chunks."""
    if not isinstance(markdown, str):
        raise KnowledgeContextValidationError("Knowledge source must be text.")

    sections: list[ParsedKnowledgeSection] = []
    heading_stack: list[str] = []
    current_path: tuple[str, ...] = ()
    current_title = "Overview"
    current_lines: list[str] = []
    anchor_counts: dict[str, int] = {}
    fence_marker = ""

    def flush() -> None:
        nonlocal current_lines
        body = "\n".join(current_lines).strip()
        current_lines = []
        if not body:
            return
        title = current_title[:MAX_KNOWLEDGE_TITLE_LENGTH]
        path = current_path or (title,)
        anchor = _slug(title)
        anchor_counts[anchor] = anchor_counts.get(anchor, 0) + 1
        if anchor_counts[anchor] > 1:
            anchor = f"{anchor}-{anchor_counts[anchor]}"
        base_ref = f"{source.semantic_id}#{anchor}"
        chunks = _split_section_text(body)
        confidence = _confidence_labels(path, body)
        for index, chunk in enumerate(chunks, start=1):
            ref = base_ref if len(chunks) == 1 else f"{base_ref}:{index}"
            sections.append(
                ParsedKnowledgeSection(
                    ref=ref[:MAX_KNOWLEDGE_REF_LENGTH],
                    source=source.path,
                    title=title,
                    heading_path=path[:MAX_HEADING_PATH_ITEMS],
                    authority="approved",
                    confidence=confidence,
                    text=chunk,
                    tool_tags=source.tool_tags,
                )
            )

    for line in markdown.splitlines():
        fence = _FENCE.match(line)
        if fence:
            marker = fence.group(1)
            if not fence_marker:
                fence_marker = marker
            elif fence_marker == marker:
                fence_marker = ""
            current_lines.append(line)
            continue

        heading = None if fence_marker else _HEADING.match(line)
        if not heading:
            current_lines.append(line)
            continue

        flush()
        level = len(heading.group(1))
        title = _clean_heading(heading.group(2))
        heading_stack[:] = heading_stack[: level - 1]
        while len(heading_stack) < level - 1:
            heading_stack.append("Untitled")
        heading_stack.append(title)
        current_path = tuple(heading_stack)
        current_title = title

    flush()
    return tuple(sections)


def _load_approved_sections(
    *,
    repository_root: Path | None = None,
    sources: tuple[KnowledgeSource, ...] = APPROVED_KNOWLEDGE_SOURCES,
) -> tuple[ParsedKnowledgeSection, ...]:
    root = (repository_root or _repository_root()).resolve()
    loaded: list[ParsedKnowledgeSection] = []
    for source in sources:
        if source.path not in APPROVED_KNOWLEDGE_SOURCE_PATHS and sources is APPROVED_KNOWLEDGE_SOURCES:
            raise KnowledgeContextValidationError("Knowledge source is not approved.")
        candidate = (root / source.path).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise KnowledgeContextValidationError(
                "Knowledge source leaves the repository root."
            ) from exc
        stat = candidate.stat()
        fingerprint = (stat.st_mtime_ns, stat.st_size)
        cache_key = str(candidate)
        with _cache_lock:
            cached = _source_cache.get(cache_key)
        if cached is None or cached[0] != fingerprint:
            markdown = candidate.read_text(encoding="utf-8-sig")
            parsed = parse_markdown_sections(markdown, source)
            with _cache_lock:
                _source_cache[cache_key] = (fingerprint, parsed)
        else:
            parsed = cached[1]
        loaded.extend(parsed)
    return tuple(loaded)


def clear_knowledge_cache() -> None:
    """Clear only the process-local parsed-document cache (primarily for tests)."""
    with _cache_lock:
        _source_cache.clear()


def _normalized_text(value: str) -> str:
    return " ".join(_WORD.findall(value.lower()))


def _stem(token: str) -> str:
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 4 and token.endswith("s"):
        return token[:-1]
    return token


def _tokens(value: str) -> tuple[str, ...]:
    return tuple(_stem(token) for token in _WORD.findall(value.lower()))


def _definition_question(question: str) -> bool:
    normalized = _normalized_text(question)
    return any(normalized.startswith(prefix.strip()) for prefix in _DEFINITION_PREFIXES)


def _concept_phrase(question: str) -> str:
    normalized = _normalized_text(question)
    for prefix in _DEFINITION_PREFIXES:
        clean_prefix = prefix.strip()
        if normalized.startswith(clean_prefix + " "):
            normalized = normalized[len(clean_prefix) + 1 :]
            break
    normalized = re.sub(r"\b(work|works|mean|means|do)\b$", "", normalized).strip()
    return normalized


def _explicit_tools(question: str) -> tuple[str, ...]:
    normalized = _normalized_text(question)
    matches: list[tuple[int, int, str]] = []
    for tool, aliases in TOOL_ALIASES.items():
        for alias in aliases:
            match = re.search(rf"\b{re.escape(alias)}\b", normalized)
            if match:
                matches.append((match.start(), -len(alias), tool))
                break
    matches.sort()
    ordered: list[str] = []
    for _position, _length, tool in matches:
        if tool not in ordered:
            ordered.append(tool)
    # "transport container" must not simultaneously route through the generic
    # Container Selection meaning of container.
    if "transport_container" in ordered and "container_selection" in ordered:
        has_selection_phrase = any(
            phrase in normalized
            for phrase in ("container selection", "box selection", "container design", "box design")
        )
        if not has_selection_phrase:
            ordered.remove("container_selection")
    return tuple(ordered)


def _section_tool_tags(section: ParsedKnowledgeSection) -> tuple[str, ...]:
    """Return heading-specific tags for mixed-tool terminology sections."""
    if section.source != "docs/product/terminology.md":
        return section.tool_tags
    for heading in reversed(section.heading_path):
        tool = _TERMINOLOGY_HEADING_TO_TOOL.get(_normalized_text(heading))
        if tool:
            return (tool,)
    return ()


def _query_tool_scope(
    question: str,
    *,
    active_tool: str,
) -> tuple[tuple[str, ...], bool, bool]:
    explicit_tools = _explicit_tools(question)
    if explicit_tools:
        return explicit_tools, True, True

    normalized = _normalized_text(question)
    hinted: list[str] = []
    for phrase, tool in TOOL_CONCEPT_HINTS:
        if re.search(rf"\b{re.escape(phrase)}\b", normalized) and tool not in hinted:
            hinted.append(tool)
    if hinted:
        return tuple(hinted), True, False

    for phrase, owners in AMBIGUOUS_CONCEPT_TOOLS:
        if re.search(rf"\b{re.escape(phrase)}\b", normalized):
            if active_tool in owners:
                return (active_tool,), True, False
            # Keep the active-tool boundary even when that tool has no matching
            # definition.  The result should then be no_match, not a definition
            # borrowed from whichever other tool has more keyword occurrences.
            return ("__no_match__",), True, False
    return (), False, False


def _score_section(
    section: ParsedKnowledgeSection,
    *,
    question: str,
    active_tool: str,
    scoped_tools: tuple[str, ...],
    tool_scope_applied: bool,
    explicit_tool_named: bool,
    definition_question: bool,
) -> int | None:
    normalized_question = _normalized_text(question)
    concept = _concept_phrase(question)
    query_tokens = tuple(
        token for token in _tokens(concept) if token not in _STOP_WORDS
    )
    heading_text = _normalized_text(" ".join(section.heading_path))
    title_text = _normalized_text(section.title)
    body_text = _normalized_text(section.text)
    heading_tokens = set(_tokens(heading_text))
    title_tokens = set(_tokens(title_text))
    body_tokens = set(_tokens(body_text))

    section_tools = _section_tool_tags(section)
    if tool_scope_applied and not set(section_tools).intersection(scoped_tools):
        if section_tools or section.source not in {
            "docs/product/terminology.md",
            "docs/product/product-vision.md",
            "docs/domain/general-packaging-rules.md",
        }:
            return None

    score = 0
    lexical_matches = 0
    strong_lexical_match = False
    if concept and len(concept) >= 3:
        if concept in title_text:
            score += 80
            lexical_matches += 1
            strong_lexical_match = True
        elif concept in heading_text:
            score += 60
            lexical_matches += 1
            strong_lexical_match = True
        elif concept in body_text:
            score += 24
            lexical_matches += 1
            strong_lexical_match = True

    for token in dict.fromkeys(query_tokens):
        if token in title_tokens:
            score += 30
            lexical_matches += 1
            strong_lexical_match = True
        elif token in heading_tokens:
            score += 14
            lexical_matches += 1
            strong_lexical_match = True
        elif token in body_tokens:
            score += 5
            lexical_matches += 1

    matching_tools = set(section_tools).intersection(scoped_tools)
    if matching_tools:
        score += 35 * len(matching_tools)
    elif active_tool in section_tools and (
        not scoped_tools or active_tool in scoped_tools
    ):
        score += 6

    title_lower = section.title.lower()
    generic_active_tool_question = (
        not query_tokens
        and not scoped_tools
        and active_tool in section_tools
        and "tool" in normalized_question
    )
    if (
        definition_question
        and section.source == "docs/product/terminology.md"
        and concept
        and (concept in title_text or concept in heading_text)
    ):
        score += 16
    if definition_question and title_lower in {"purpose", "glossary"}:
        if generic_active_tool_question or (explicit_tool_named and matching_tools):
            score += 10
    if (
        "design" in query_tokens
        and title_lower == "design mode"
        and not {"efficiency", "cubicity", "additional"}.intersection(query_tokens)
    ):
        if matching_tools or active_tool in section_tools:
            score += 55
    if normalized_question.startswith("why ") and title_lower in {
        "conceptual calculation flow",
        "ranking",
        "ranking and tie-breaking",
    }:
        if matching_tools or active_tool in section_tools:
            score += 35
    comparison_question = any(
        phrase in normalized_question
        for phrase in (" vs ", " versus ", "different from", "difference between", "compare ")
    )
    if comparison_question and title_lower == "purpose" and matching_tools:
        score += 70
    if generic_active_tool_question and title_lower == "purpose":
        score += 40

    if lexical_matches == 0 and not generic_active_tool_question and (
        not matching_tools or not explicit_tool_named
    ):
        return None
    if (
        not strong_lexical_match
        and lexical_matches < 2
        and not explicit_tool_named
        and not generic_active_tool_question
    ):
        return None
    return score if score >= 8 else None


def _rank_sections(
    sections: tuple[ParsedKnowledgeSection, ...],
    *,
    question: str,
    active_tool: str,
) -> list[ParsedKnowledgeSection]:
    scoped_tools, tool_scope_applied, explicit_tool_named = _query_tool_scope(
        question,
        active_tool=active_tool,
    )
    if scoped_tools == ("__no_match__",):
        return []
    definition_question = _definition_question(question)
    scored: list[tuple[int, str, ParsedKnowledgeSection]] = []
    for section in sections:
        score = _score_section(
            section,
            question=question,
            active_tool=active_tool,
            scoped_tools=scoped_tools,
            tool_scope_applied=tool_scope_applied,
            explicit_tool_named=explicit_tool_named,
            definition_question=definition_question,
        )
        if score is not None:
            scored.append((score, section.ref, section))
    scored.sort(key=lambda item: (-item[0], item[1]))
    if scored:
        relative_floor = max(8, scored[0][0] * 3 // 10)
        scored = [item for item in scored if item[0] >= relative_floor]

    selected: list[ParsedKnowledgeSection] = []
    selected_refs: set[str] = set()
    if len(scoped_tools) > 1:
        for tool in scoped_tools:
            match = next(
                (
                    section
                    for _score, _ref, section in scored
                    if _section_tool_tags(section) == (tool,)
                    and section.ref not in selected_refs
                ),
                None,
            )
            if match is None:
                match = next(
                    (
                        section
                        for _score, _ref, section in scored
                        if tool in _section_tool_tags(section)
                        and section.ref not in selected_refs
                    ),
                    None,
                )
            if match is not None:
                selected.append(match)
                selected_refs.add(match.ref)

    for _score, _ref, section in scored:
        if len(selected) >= MAX_KNOWLEDGE_SECTIONS:
            break
        if section.ref in selected_refs:
            continue
        selected.append(section)
        selected_refs.add(section.ref)
    return selected


def _truncate_at_boundary(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    if limit <= 0:
        return ""
    cut = text.rfind("\n\n", 0, limit + 1)
    if cut < limit // 2:
        cut = text.rfind("\n", 0, limit + 1)
    if cut < limit // 2:
        cut = text.rfind(" ", 0, limit + 1)
    if cut < limit // 2:
        cut = limit
    return text[:cut].rstrip()


def _as_context(sections: list[ParsedKnowledgeSection]) -> KnowledgeContext:
    bounded: list[KnowledgeSection] = []
    remaining = MAX_KNOWLEDGE_TEXT_CHARS
    for section in sections[:MAX_KNOWLEDGE_SECTIONS]:
        text = _truncate_at_boundary(section.text, remaining)
        if not text:
            break
        bounded.append(
            {
                "ref": section.ref,
                "source": section.source,
                "title": section.title,
                "heading_path": list(section.heading_path),
                "authority": section.authority,
                "confidence": list(section.confidence),
                "text": text,
            }
        )
        remaining -= len(text)
    context: KnowledgeContext = {
        "schema_version": KNOWLEDGE_CONTEXT_SCHEMA_VERSION,
        "status": (
            KNOWLEDGE_STATUS_AVAILABLE if bounded else KNOWLEDGE_STATUS_NO_MATCH
        ),
        "sections": bounded,
    }
    return validate_knowledge_context(context)


def empty_knowledge_context(*, unavailable: bool = False) -> KnowledgeContext:
    context: KnowledgeContext = {
        "schema_version": KNOWLEDGE_CONTEXT_SCHEMA_VERSION,
        "status": (
            KNOWLEDGE_STATUS_UNAVAILABLE if unavailable else KNOWLEDGE_STATUS_NO_MATCH
        ),
        "sections": [],
    }
    return validate_knowledge_context(context)


def retrieve_knowledge_context(
    question: str,
    *,
    active_tool: str,
    repository_root: Path | None = None,
    sources: tuple[KnowledgeSource, ...] = APPROVED_KNOWLEDGE_SOURCES,
) -> KnowledgeContext:
    """Return bounded approved documentation for one current question."""
    try:
        if not isinstance(question, str) or not question.strip():
            return empty_knowledge_context()
        sections = _load_approved_sections(
            repository_root=repository_root,
            sources=sources,
        )
        ranked = _rank_sections(
            sections,
            question=question,
            active_tool=active_tool,
        )
        return _as_context(ranked)
    except Exception:
        logger.warning(
            "Assistant knowledge retrieval failed safely.",
            extra={"assistant_knowledge_outcome": KNOWLEDGE_STATUS_UNAVAILABLE},
        )
        return empty_knowledge_context(unavailable=True)


def validate_knowledge_context(context: Any) -> KnowledgeContext:
    if not isinstance(context, dict) or set(context) != {
        "schema_version",
        "status",
        "sections",
    }:
        raise KnowledgeContextValidationError(
            "Knowledge Context fields do not match schema."
        )
    if context.get("schema_version") != KNOWLEDGE_CONTEXT_SCHEMA_VERSION:
        raise KnowledgeContextValidationError("Unsupported Knowledge Context version.")
    if context.get("status") not in KNOWLEDGE_STATUSES:
        raise KnowledgeContextValidationError("Unsupported Knowledge Context status.")
    sections = context.get("sections")
    if not isinstance(sections, list) or len(sections) > MAX_KNOWLEDGE_SECTIONS:
        raise KnowledgeContextValidationError("Knowledge sections exceed the limit.")
    if context["status"] != KNOWLEDGE_STATUS_AVAILABLE and sections:
        raise KnowledgeContextValidationError(
            "Unavailable or unmatched knowledge cannot contain sections."
        )
    if context["status"] == KNOWLEDGE_STATUS_AVAILABLE and not sections:
        raise KnowledgeContextValidationError(
            "Available knowledge requires at least one section."
        )

    total_text = 0
    for section in sections:
        if not isinstance(section, dict) or set(section) != {
            "ref",
            "source",
            "title",
            "heading_path",
            "authority",
            "confidence",
            "text",
        }:
            raise KnowledgeContextValidationError(
                "Knowledge section fields do not match schema."
            )
        ref = section.get("ref")
        source = section.get("source")
        title = section.get("title")
        text = section.get("text")
        heading_path = section.get("heading_path")
        confidence = section.get("confidence")
        if not isinstance(ref, str) or not ref or len(ref) > MAX_KNOWLEDGE_REF_LENGTH:
            raise KnowledgeContextValidationError("Knowledge ref is invalid.")
        if "\\" in ref or ref.startswith("/") or ".." in ref.split("/"):
            raise KnowledgeContextValidationError("Knowledge ref is unsafe.")
        if (
            not isinstance(source, str)
            or source not in APPROVED_KNOWLEDGE_SOURCE_PATHS
            or len(source) > MAX_KNOWLEDGE_SOURCE_LENGTH
        ):
            raise KnowledgeContextValidationError("Knowledge source is not approved.")
        if Path(source).is_absolute() or ".." in Path(source).parts:
            raise KnowledgeContextValidationError("Knowledge source path is unsafe.")
        if not isinstance(title, str) or not title or len(title) > MAX_KNOWLEDGE_TITLE_LENGTH:
            raise KnowledgeContextValidationError("Knowledge title is invalid.")
        if (
            not isinstance(heading_path, list)
            or not heading_path
            or len(heading_path) > MAX_HEADING_PATH_ITEMS
            or not all(
                isinstance(item, str)
                and item
                and len(item) <= MAX_KNOWLEDGE_TITLE_LENGTH
                for item in heading_path
            )
        ):
            raise KnowledgeContextValidationError("Knowledge heading path is invalid.")
        if section.get("authority") != "approved":
            raise KnowledgeContextValidationError("Knowledge authority is invalid.")
        if (
            not isinstance(confidence, list)
            or len(confidence) > len(_AUTHORITY_MARKERS)
            or not all(
                item in {label for _marker, label in _AUTHORITY_MARKERS}
                for item in confidence
            )
        ):
            raise KnowledgeContextValidationError("Knowledge confidence is invalid.")
        if (
            not isinstance(text, str)
            or not text
            or len(text) > MAX_KNOWLEDGE_SECTION_CHARS
        ):
            raise KnowledgeContextValidationError("Knowledge text is invalid.")
        for value in (ref, source, title, *heading_path, text):
            if any(
                ord(character) < 32 and character not in "\n\r\t"
                for character in value
            ):
                raise KnowledgeContextValidationError(
                    "Knowledge Context contains unsupported control characters."
                )
        total_text += len(text)

    if total_text > MAX_KNOWLEDGE_TEXT_CHARS:
        raise KnowledgeContextValidationError("Knowledge text exceeds the total limit.")
    encoded = json.dumps(
        context,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    if len(encoded) > MAX_KNOWLEDGE_CONTEXT_BYTES:
        raise KnowledgeContextValidationError("Knowledge Context is too large.")
    return context


def canonical_knowledge_json(context: KnowledgeContext) -> str:
    validated = validate_knowledge_context(context)
    return json.dumps(
        validated,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def knowledge_trace(context: KnowledgeContext) -> list[dict[str, Any]]:
    validate_knowledge_context(context)
    return [
        {
            "ref": section["ref"],
            "title": section["title"],
            "heading_path": list(section["heading_path"]),
        }
        for section in context["sections"]
    ]


def knowledge_trace_enabled() -> bool:
    value = getattr(settings, "AI_ASSISTANT_KNOWLEDGE_TRACE_ENABLED", False)
    if isinstance(value, str):
        value = value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(settings.DEBUG and value is True)


__all__ = [
    "APPROVED_KNOWLEDGE_SOURCES",
    "KNOWLEDGE_CONTEXT_SCHEMA_VERSION",
    "KnowledgeContext",
    "KnowledgeContextValidationError",
    "KnowledgeSource",
    "MAX_KNOWLEDGE_SECTIONS",
    "MAX_KNOWLEDGE_SECTION_CHARS",
    "MAX_KNOWLEDGE_TEXT_CHARS",
    "canonical_knowledge_json",
    "clear_knowledge_cache",
    "empty_knowledge_context",
    "knowledge_trace",
    "knowledge_trace_enabled",
    "parse_markdown_sections",
    "retrieve_knowledge_context",
    "validate_knowledge_context",
]
