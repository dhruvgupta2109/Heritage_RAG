import json
from collections.abc import AsyncIterator

from ..schemas import SourceRecord
from .base import (
    GROUNDING_INSTRUCTIONS,
    QUERY_EXPANSION_INSTRUCTIONS,
    TITLE_INSTRUCTIONS,
    ProviderError,
    check_api_key,
    clean_title,
    grounded_input,
    parse_query_lines,
    post_json,
    stream_sse,
)

GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODELS_URL = "https://api.groq.com/openai/v1/models"


class GroqProvider:
    name = "Groq"

    def __init__(self, api_key: str | None, model: str):
        self.api_key = api_key
        self.model = model

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key or ''}",
            "Content-Type": "application/json",
        }

    async def stream_answer(
        self,
        question: str,
        sources: list[SourceRecord],
        source_text: dict[int, str],
        model: str | None = None,
    ) -> AsyncIterator[str]:
        self._require_key()
        payload = {
            "model": model or self.model,
            "messages": [
                {"role": "system", "content": GROUNDING_INSTRUCTIONS},
                {
                    "role": "user",
                    "content": grounded_input(question, sources, source_text),
                },
            ],
            "temperature": 0.1,
            "max_completion_tokens": 900,
            "stream": True,
        }

        def parse_delta(line: str) -> str | None:
            if not line.startswith("data: "):
                return None
            data = line[6:]
            if data == "[DONE]":
                return None
            event = json.loads(data)
            return event.get("choices", [{}])[0].get("delta", {}).get("content")

        async for delta in stream_sse(
            provider=self.name,
            url=GROQ_CHAT_URL,
            headers=self.headers,
            payload=payload,
            parse_delta=parse_delta,
        ):
            yield delta

    async def generate_title(
        self,
        first_query: str,
        model: str | None = None,
    ) -> str:
        self._require_key()
        response = await post_json(
            provider=self.name,
            url=GROQ_CHAT_URL,
            headers=self.headers,
            payload={
                "model": model or self.model,
                "messages": [
                    {"role": "system", "content": TITLE_INSTRUCTIONS},
                    {"role": "user", "content": first_query},
                ],
                "temperature": 0.1,
                "max_completion_tokens": 80,
                "reasoning_effort": "low",
                "reasoning_format": "hidden",
                "stream": False,
            },
        )
        content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
        title = clean_title(content)
        if not title:
            raise ProviderError("Groq returned an empty conversation title.")
        return title

    async def expand_queries(self, question: str, model: str | None = None) -> list[str]:
        self._require_key()
        response = await post_json(
            provider=self.name,
            url=GROQ_CHAT_URL,
            headers=self.headers,
            payload={
                "model": model or self.model,
                "messages": [
                    {"role": "system", "content": QUERY_EXPANSION_INSTRUCTIONS},
                    {"role": "user", "content": question},
                ],
                "temperature": 0.1,
                "max_completion_tokens": 180,
                "reasoning_effort": "low",
                "reasoning_format": "hidden",
                "stream": False,
            },
        )
        content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
        return parse_query_lines(content, question)

    async def health(self) -> dict:
        return await check_api_key(
            provider=self.name,
            api_key=self.api_key,
            url=GROQ_MODELS_URL,
            headers=self.headers,
        )

    def _require_key(self) -> None:
        if not self.api_key:
            raise ProviderError("GROQ_API_KEY is missing. Add it to .env and restart the app.")


_clean_title = clean_title
