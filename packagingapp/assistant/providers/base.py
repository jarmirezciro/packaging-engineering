"""Provider-neutral boundary for text-only read-only assistant generation."""

from __future__ import annotations

from typing import Any, Protocol

from ..contracts import ToolContext
from ..knowledge import KnowledgeContext
from ..prompts import AssistantInstructions


class AssistantProviderError(RuntimeError):
    """Base exception for normalized provider-adapter failures."""


class AssistantProviderTimeout(AssistantProviderError):
    """The provider did not complete within its configured invocation bound."""


class AssistantProviderUnavailable(AssistantProviderError):
    """The provider could not produce a candidate response."""


class AssistantProviderAuthenticationError(AssistantProviderUnavailable):
    """The provider rejected its server-side credential."""


class AssistantProviderPermissionError(AssistantProviderUnavailable):
    """The configured provider project cannot use the requested resource."""


class AssistantProviderRateLimitError(AssistantProviderUnavailable):
    """The provider rejected the request because of a provider-side limit."""


class AssistantProviderConnectionError(AssistantProviderUnavailable):
    """The provider could not be reached."""


class AssistantProviderServerError(AssistantProviderUnavailable):
    """The provider failed while processing the request."""


class AssistantProviderRefusal(AssistantProviderUnavailable):
    """The provider returned a safety refusal instead of structured output."""


class AssistantProviderInvalidResponse(AssistantProviderError):
    """The provider response was incomplete, empty, or structurally unsafe."""


class AssistantProviderResponseTooLarge(AssistantProviderInvalidResponse):
    """The provider response exceeded KolliPack's application-owned limit."""


class AssistantProvider(Protocol):
    provider_id: str

    def generate(
        self,
        *,
        message: str,
        tool_context: ToolContext,
        instructions: AssistantInstructions,
        timeout_seconds: float,
        knowledge_context: KnowledgeContext | None = None,
    ) -> Any:
        """Return an untrusted response candidate for application validation."""
