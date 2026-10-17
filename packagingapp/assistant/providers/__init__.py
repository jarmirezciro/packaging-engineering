"""Explicit allow-listed assistant provider registration."""

from __future__ import annotations

from .fake import FakeAssistantProvider
from .openai import OpenAIAssistantProvider


DEFAULT_ASSISTANT_PROVIDER = "fake"
SUPPORTED_ASSISTANT_PROVIDERS = frozenset({"fake", "openai"})


class UnknownAssistantProvider(ValueError):
    """Raised when configuration names a provider outside the allow-list."""


def get_assistant_provider(name: str = DEFAULT_ASSISTANT_PROVIDER):
    if name == "fake":
        return FakeAssistantProvider()
    if name == "openai":
        return OpenAIAssistantProvider()
    raise UnknownAssistantProvider("Unsupported assistant provider.")


__all__ = [
    "DEFAULT_ASSISTANT_PROVIDER",
    "SUPPORTED_ASSISTANT_PROVIDERS",
    "UnknownAssistantProvider",
    "get_assistant_provider",
]
