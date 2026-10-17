from django.test import SimpleTestCase

from packagingapp.assistant.public_contracts import (
    MAX_PUBLIC_KNOWLEDGE_SECTION_CHARS,
    MAX_PUBLIC_KNOWLEDGE_SECTIONS,
    MAX_PUBLIC_KNOWLEDGE_TEXT_CHARS,
)
from packagingapp.assistant.public_knowledge import (
    PUBLIC_KNOWLEDGE_REGISTRY,
    PUBLIC_KNOWLEDGE_SOURCE_PATHS,
    retrieve_public_knowledge_context,
)


class PublicExpertKnowledgeTests(SimpleTestCase):
    def test_registry_is_separate_section_level_and_excludes_internal_sources(self):
        self.assertGreater(len(PUBLIC_KNOWLEDGE_REGISTRY), 1)
        self.assertEqual(
            PUBLIC_KNOWLEDGE_SOURCE_PATHS,
            frozenset(source.path for source in PUBLIC_KNOWLEDGE_REGISTRY),
        )
        self.assertTrue(all(source.include_headings for source in PUBLIC_KNOWLEDGE_REGISTRY))
        excluded_fragments = (
            "ai_assistant",
            "deployment",
            "maintenance",
            "known-issues",
            "testing",
            "benchmarks",
            "transport-container-engine",
        )
        for path in PUBLIC_KNOWLEDGE_SOURCE_PATHS:
            with self.subTest(path=path):
                self.assertFalse(any(fragment in path for fragment in excluded_fragments))

    def test_global_tool_and_company_questions_retrieve_curated_public_sections(self):
        company = retrieve_public_knowledge_context(
            "What is KolliPack?", knowledge_scope="global"
        )
        tools = retrieve_public_knowledge_context(
            "What tools does KolliPack provide?", knowledge_scope="global"
        )
        self.assertEqual(company["status"], "available")
        self.assertEqual(tools["status"], "available")
        self.assertEqual(
            company["sections"][0]["ref"],
            "product/public-kollipack-knowledge#kollilabs-and-kollipack",
        )
        self.assertEqual(
            tools["sections"][0]["ref"],
            "product/public-kollipack-knowledge#available-kollipack-tools",
        )

    def test_scope_biases_ambiguous_question_but_does_not_block_cross_tool(self):
        scoped = retrieve_public_knowledge_context(
            "How does this tool work?", knowledge_scope="container_selection"
        )
        cross_tool = retrieve_public_knowledge_context(
            "What is sealing margin?", knowledge_scope="container_selection"
        )
        comparison = retrieve_public_knowledge_context(
            "Container Selection vs Bag Selection", knowledge_scope="container_selection"
        )
        self.assertTrue(scoped["sections"][0]["ref"].startswith("domain/container-selection"))
        self.assertTrue(cross_tool["sections"][0]["ref"].startswith("domain/bag-selection"))
        refs = [section["ref"] for section in comparison["sections"]]
        self.assertTrue(any(ref.startswith("domain/container-selection") for ref in refs))
        self.assertTrue(any(ref.startswith("domain/bag-selection") for ref in refs))

    def test_tool_overview_questions_prefer_the_reviewed_purpose_heading(self):
        cases = (
            ("What does Palletization do?", "global", "domain/palletization-logic#purpose"),
            (
                "How does Transport Container loading work?",
                "transport",
                "domain/transport-selection-logic#purpose",
            ),
            (
                "What does the Corrugated Material & Strength tool do?",
                "global",
                "domain/corrugated-material-strength#purpose",
            ),
        )
        for question, scope, expected_ref in cases:
            with self.subTest(question=question):
                context = retrieve_public_knowledge_context(
                    question, knowledge_scope=scope
                )
                self.assertEqual(context["sections"][0]["ref"], expected_ref)

    def test_unsupported_question_is_no_match_and_context_is_bounded(self):
        unsupported = retrieve_public_knowledge_context(
            "What adhesive should I use?", knowledge_scope="global"
        )
        self.assertEqual(unsupported["status"], "no_match")
        self.assertEqual(unsupported["sections"], [])

        context = retrieve_public_knowledge_context(
            "Explain Container Selection modes, cubicity, assumptions, rotations, and dimensions.",
            knowledge_scope="container_selection",
        )
        self.assertLessEqual(len(context["sections"]), MAX_PUBLIC_KNOWLEDGE_SECTIONS)
        self.assertTrue(
            all(len(section["text"]) <= MAX_PUBLIC_KNOWLEDGE_SECTION_CHARS for section in context["sections"])
        )
        self.assertLessEqual(
            sum(len(section["text"]) for section in context["sections"]),
            MAX_PUBLIC_KNOWLEDGE_TEXT_CHARS,
        )
        self.assertTrue(all("source" not in section for section in context["sections"]))
