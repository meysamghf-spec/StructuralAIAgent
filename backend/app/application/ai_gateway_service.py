"""Provider-agnostic AI Gateway."""

from __future__ import annotations

from app.application.exceptions import AIProviderNotFoundError, AIModelNotSupportedError
from app.domain.contracts.ai_provider import AIProvider
from app.domain.models.ai_gateway import AICompletionRequest, AICompletionResponse, AIProviderKind


class AIGatewayService:
    def __init__(self, *, providers: dict[AIProviderKind, AIProvider]) -> None:
        self._providers = providers

    def complete(
        self,
        request: AICompletionRequest,
        *,
        provider_kind: AIProviderKind | None = None,
    ) -> AICompletionResponse:
        provider = self._select_provider(request.model, provider_kind)
        return provider.complete(request)

    def list_providers(self) -> list[str]:
        return sorted(kind.value for kind in self._providers)

    def _select_provider(
        self,
        model: str,
        provider_kind: AIProviderKind | None,
    ) -> AIProvider:
        if provider_kind is not None:
            provider = self._providers.get(provider_kind)
            if provider is None:
                raise AIProviderNotFoundError(provider=provider_kind.value)
            if not provider.supports_model(model):
                raise AIModelNotSupportedError(model=model, provider=provider_kind.value)
            return provider

        ranked = sorted(
            self._providers.items(),
            key=lambda item: 1 if item[0] == AIProviderKind.STUB else 0,
        )
        for _kind, provider in ranked:
            if provider.supports_model(model):
                return provider

        raise AIModelNotSupportedError(model=model, provider="any")
