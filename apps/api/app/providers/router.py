import asyncio
import time
from collections.abc import AsyncIterator
from typing import Any

from ..config import MODEL_CATALOG
from ..schemas import SourceRecord
from .base import ProviderError
from .gemini import GeminiProvider
from .groq import GroqProvider
from .openai import OpenAIProvider


class ProviderRouter:
    def __init__(
        self,
        *,
        groq: GroqProvider,
        openai: OpenAIProvider,
        gemini: GeminiProvider,
        default_model: str,
    ):
        self.providers = {
            "groq": groq,
            "openai": openai,
            "gemini": gemini,
        }
        self.model = default_model
        self._models = {str(model["id"]): model for model in MODEL_CATALOG}
        self._health_cache: dict[str, dict[str, Any]] | None = None
        self._health_checked_at = 0.0

    async def stream_answer(
        self,
        question: str,
        sources: list[SourceRecord],
        source_text: dict[int, str],
        model: str,
    ) -> AsyncIterator[str]:
        provider = self.provider_for_model(model)
        async for delta in provider.stream_answer(question, sources, source_text, model):
            yield delta

    async def generate_title(self, first_query: str, model: str) -> str:
        return await self.provider_for_model(model).generate_title(first_query, model)

    async def expand_queries(self, question: str, model: str) -> list[str]:
        return await self.provider_for_model(model).expand_queries(question, model)

    async def health(self, *, refresh: bool = False) -> list[dict[str, Any]]:
        now = time.monotonic()
        if not refresh and self._health_cache is not None and now - self._health_checked_at < 60:
            statuses = self._health_cache
        else:
            keys = list(self.providers)
            results = await asyncio.gather(
                *(self.providers[key].health() for key in keys),
            )
            statuses = dict(zip(keys, results, strict=True))
            self._health_cache = statuses
            self._health_checked_at = now
        return [
            {
                "id": key,
                "label": self.providers[key].name,
                "configured": statuses[key]["configured"],
                "available": statuses[key]["available"],
                "message": statuses[key]["message"],
            }
            for key in self.providers
        ]

    def models_with_status(self) -> list[dict[str, Any]]:
        statuses = self._health_cache or {}
        models: list[dict[str, Any]] = []
        for model in MODEL_CATALOG:
            provider_status = statuses.get(
                str(model["provider"]),
                {
                    "available": False,
                    "message": "Provider status has not been checked",
                    "model_ids": [],
                },
            )
            model_ids = provider_status.get("model_ids", [])
            provider_available = bool(provider_status["available"])
            model_available = provider_available and (not model_ids or model["id"] in model_ids)
            models.append(
                {
                    **model,
                    "available": model_available,
                    "status": (
                        provider_status["message"]
                        if model_available or not provider_available
                        else "Model is not available for this API key"
                    ),
                }
            )
        return models

    def provider_for_model(self, model: str):
        metadata = self._models.get(model)
        if not metadata:
            raise ProviderError("The selected model is not supported.")
        return self.providers[str(metadata["provider"])]
