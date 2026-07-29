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
    openai_output_text,
    parse_query_lines,
    post_json,
    stream_sse,
)

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
OPENAI_MODELS_URL = "https://api.openai.com/v1/models"


class OpenAIProvider:
    name = "OpenAI"

    def __init__(self, api_key: str | None):
        self.api_key = api_key

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
        model: str,
    ) -> AsyncIterator[str]:
        self._require_key()
        payload = {
            "model": model,
            "instructions": GROUNDING_INSTRUCTIONS,
            "input": grounded_input(question, sources, source_text),
            "reasoning": {"effort": "low"},
            "text": {"verbosity": "medium"},
            "max_output_tokens": 1_200,
            "store": False,
            "stream": True,
        }

        def parse_delta(line: str) -> str | None:
            if not line.startswith("data: "):
                return None
            data = line[6:]
            if data == "[DONE]":
                return None
            event = json.loads(data)
            if event.get("type") == "response.output_text.delta":
                return str(event.get("delta") or "")
            if event.get("type") == "error":
                raise ProviderError("OpenAI could not complete the response.")
            return None

        async for delta in stream_sse(
            provider=self.name,
            url=OPENAI_RESPONSES_URL,
            headers=self.headers,
            payload=payload,
            parse_delta=parse_delta,
        ):
            yield delta

    async def generate_title(self, first_query: str, model: str) -> str:
        self._require_key()
        response = await post_json(
            provider=self.name,
            url=OPENAI_RESPONSES_URL,
            headers=self.headers,
            payload={
                "model": model,
                "instructions": TITLE_INSTRUCTIONS,
                "input": first_query,
                "reasoning": {"effort": "none"},
                "text": {"verbosity": "low"},
                "max_output_tokens": 120,
                "store": False,
            },
        )
        title = clean_title(openai_output_text(response))
        if not title:
            raise ProviderError("OpenAI returned an empty conversation title.")
        return title

    async def expand_queries(self, question: str, model: str) -> list[str]:
        self._require_key()
        response = await post_json(
            provider=self.name,
            url=OPENAI_RESPONSES_URL,
            headers=self.headers,
            payload={
                "model": model,
                "instructions": QUERY_EXPANSION_INSTRUCTIONS,
                "input": question,
                "reasoning": {"effort": "low"},
                "text": {"verbosity": "low"},
                "max_output_tokens": 220,
                "store": False,
            },
        )
        return parse_query_lines(openai_output_text(response), question)

    async def health(self) -> dict:
        return await check_api_key(
            provider=self.name,
            api_key=self.api_key,
            url=OPENAI_MODELS_URL,
            headers=self.headers,
        )

    def _require_key(self) -> None:
        if not self.api_key:
            raise ProviderError("OPENAI_API_KEY is missing. Add it to .env and restart the app.")
