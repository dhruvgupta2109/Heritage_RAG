import json
import re
from collections.abc import AsyncIterator

import httpx

from ..schemas import SourceRecord

GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"


class GroqProvider:
    def __init__(self, api_key: str | None, model: str):
        self.api_key = api_key
        self.model = model

    async def stream_answer(
        self,
        question: str,
        sources: list[SourceRecord],
        source_text: dict[int, str],
        model: str | None = None,
    ) -> AsyncIterator[str]:
        if not self.api_key:
            raise RuntimeError(
                "GROQ_API_KEY is missing. Add it to the project .env file and restart."
            )

        context = "\n\n".join(
            (
                f'<source id="S{source.id}" document="{source.document}" '
                f'location="{source.page_label}">\n'
                f"{source_text[source.id]}\n"
                "</source>"
            )
            for source in sources
        )
        system = (
            "You are Heritage, a document-grounded assistant. Answer only from the "
            "provided sources. Do not use outside knowledge. Cite every factual sentence "
            "and every numbered item with one or more source markers exactly like [S1]. "
            "Use normal ASCII square brackets, not decorative citation brackets. Use only "
            "source IDs that appear in the context. If the sources do not contain the "
            "answer, say exactly "
            '"I couldn\'t find reliable support for this in the indexed documents." '
            "Do not add a citation to that no-support sentence. Be concise but complete."
        )
        payload = {
            "model": model or self.model,
            "messages": [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": f"<context>\n{context}\n</context>\n\nQuestion: {question}",
                },
            ],
            "temperature": 0.1,
            "max_completion_tokens": 900,
            "stream": True,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=httpx.Timeout(90.0)) as client:
            async with client.stream(
                "POST", GROQ_CHAT_URL, headers=headers, json=payload
            ) as response:
                if response.status_code >= 400:
                    body = (await response.aread()).decode("utf-8", errors="replace")
                    raise RuntimeError(_safe_error(response.status_code, body))
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    event = json.loads(data)
                    delta = event.get("choices", [{}])[0].get("delta", {}).get("content")
                    if delta:
                        yield delta

    async def generate_title(
        self,
        first_query: str,
        model: str | None = None,
    ) -> str:
        if not self.api_key:
            raise RuntimeError(
                "GROQ_API_KEY is missing. Add it to the project .env file and restart."
            )

        payload = {
            "model": model or self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Create a concise title for a document-search conversation. "
                        "Use 3 to 7 words. Return only the title in plain text, without "
                        "quotes, markdown, a trailing period, or an answer to the query."
                    ),
                },
                {"role": "user", "content": first_query},
            ],
            "temperature": 0.1,
            "max_completion_tokens": 80,
            "reasoning_effort": "low",
            "reasoning_format": "hidden",
            "stream": False,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
            response = await client.post(
                GROQ_CHAT_URL,
                headers=headers,
                json=payload,
            )
        if response.status_code >= 400:
            raise RuntimeError(_safe_error(response.status_code, response.text))
        content = response.json().get("choices", [{}])[0].get("message", {}).get("content", "")
        title = _clean_title(content)
        if not title:
            raise RuntimeError("Groq returned an empty conversation title.")
        return title


def _safe_error(status_code: int, body: str) -> str:
    try:
        parsed = json.loads(body)
        message = parsed.get("error", {}).get("message")
    except json.JSONDecodeError:
        message = None
    if status_code in {401, 403}:
        return "Groq rejected the configured API key or model permission."
    if status_code == 429:
        return "Groq rate limit reached. Wait briefly and try again."
    return f"Groq request failed ({status_code}): {message or 'Unknown provider error'}"


def _clean_title(value: str) -> str:
    title = re.sub(r"<think>.*?</think>", "", value, flags=re.DOTALL | re.IGNORECASE)
    title = title.strip().splitlines()[0] if title.strip() else ""
    title = re.sub(r"^[\"'`*_#\s]+|[\"'`*_.#\s]+$", "", title)
    title = re.sub(r"\s+", " ", title)
    return title[:72].rstrip()
