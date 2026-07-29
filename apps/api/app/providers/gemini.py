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
    gemini_output_text,
    grounded_input,
    parse_query_lines,
    post_json,
    stream_sse,
)

GEMINI_API_ROOT = "https://generativelanguage.googleapis.com/v1beta"


class GeminiProvider:
    name = "Gemini"

    def __init__(self, api_key: str | None):
        self.api_key = api_key

    @property
    def headers(self) -> dict[str, str]:
        return {
            "x-goog-api-key": self.api_key or "",
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
        payload = self._payload(
            GROUNDING_INSTRUCTIONS,
            grounded_input(question, sources, source_text),
            max_output_tokens=1_200,
        )

        def parse_delta(line: str) -> str | None:
            if not line.startswith("data: "):
                return None
            event = json.loads(line[6:])
            block_reason = event.get("promptFeedback", {}).get("blockReason")
            if block_reason:
                raise ProviderError("Gemini blocked this request before answering.")
            return gemini_output_text(event) or None

        async for delta in stream_sse(
            provider=self.name,
            url=f"{GEMINI_API_ROOT}/models/{model}:streamGenerateContent?alt=sse",
            headers=self.headers,
            payload=payload,
            parse_delta=parse_delta,
        ):
            yield delta

    async def generate_title(self, first_query: str, model: str) -> str:
        self._require_key()
        response = await post_json(
            provider=self.name,
            url=f"{GEMINI_API_ROOT}/models/{model}:generateContent",
            headers=self.headers,
            payload=self._payload(TITLE_INSTRUCTIONS, first_query, max_output_tokens=120),
        )
        title = clean_title(gemini_output_text(response))
        if not title:
            raise ProviderError("Gemini returned an empty conversation title.")
        return title

    async def expand_queries(self, question: str, model: str) -> list[str]:
        self._require_key()
        response = await post_json(
            provider=self.name,
            url=f"{GEMINI_API_ROOT}/models/{model}:generateContent",
            headers=self.headers,
            payload=self._payload(
                QUERY_EXPANSION_INSTRUCTIONS,
                question,
                max_output_tokens=220,
            ),
        )
        return parse_query_lines(gemini_output_text(response), question)

    async def health(self) -> dict:
        return await check_api_key(
            provider=self.name,
            api_key=self.api_key,
            url=f"{GEMINI_API_ROOT}/models?pageSize=1000",
            headers=self.headers,
        )

    @staticmethod
    def _payload(
        instructions: str,
        user_text: str,
        *,
        max_output_tokens: int,
    ) -> dict:
        return {
            "systemInstruction": {"parts": [{"text": instructions}]},
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": user_text}],
                }
            ],
            "generationConfig": {"maxOutputTokens": max_output_tokens},
        }

    def _require_key(self) -> None:
        if not self.api_key:
            raise ProviderError("GEMINI_API_KEY is missing. Add it to .env and restart the app.")
