import asyncio
import json
import re
from collections.abc import AsyncIterator, Callable
from typing import Any, Protocol

import httpx

from ..schemas import SourceRecord

GROUNDING_INSTRUCTIONS = (
    "You are Heritage, a document-grounded assistant. Answer only from the "
    "provided sources. Do not use outside knowledge. Format the answer in clear "
    "GitHub-flavored Markdown and choose the structure that makes the information "
    "easiest to understand. Use concise prose for a simple direct answer; bullets "
    "for an unordered set; a numbered list for ordered steps or sequences; a compact "
    "table for comparisons, schedules, or several items that share the same "
    "attributes; and short descriptive headings only when the answer has distinct "
    "sections. Do not force a table or headings when a short answer or list is "
    "clearer. Use bold sparingly for short labels, never entire paragraphs, and do "
    "not wrap the answer in a code fence. Cite every factual sentence, bullet or "
    "numbered item, and factual table row with one or more source markers exactly "
    "like [S1], placed immediately after the supported content. When a citation "
    "ends a sentence, put it immediately before the punctuation with no space "
    "between the marker and punctuation, like `supported content [S1].` Use normal "
    "ASCII square brackets, not decorative citation brackets. Use only source IDs "
    "that appear in the context. If the sources do not contain the answer, say exactly "
    '"I couldn\'t find reliable support for this in the indexed documents." '
    "Do not add a citation to that no-support sentence. Be concise but complete."
)

TITLE_INSTRUCTIONS = (
    "Create a concise title for a document-search conversation. Use 3 to 7 words. "
    "Return only the title in plain text, without quotes, markdown, a trailing "
    "period, or an answer to the query."
)

QUERY_EXPANSION_INSTRUCTIONS = (
    "Rewrite the document-search question as up to three short, complementary "
    "search queries. Preserve names, dates, grades, and quoted phrases. Return "
    "only the queries, one per line, without numbering or explanation."
)

RETRYABLE_STATUSES = {429, 500, 502, 503, 504}


class ProviderError(RuntimeError):
    pass


class AnswerProvider(Protocol):
    model: str

    async def stream_answer(
        self,
        question: str,
        sources: list[SourceRecord],
        source_text: dict[int, str],
        model: str,
    ) -> AsyncIterator[str]: ...

    async def generate_title(self, first_query: str, model: str) -> str: ...

    async def expand_queries(self, question: str, model: str) -> list[str]: ...


def grounded_input(
    question: str,
    sources: list[SourceRecord],
    source_text: dict[int, str],
) -> str:
    context = "\n\n".join(
        (
            f'<source id="S{source.id}" document="{source.document}" '
            f'location="{source.page_label}">\n'
            f"{source_text[source.id]}\n"
            "</source>"
        )
        for source in sources
    )
    return f"<context>\n{context}\n</context>\n\nQuestion: {question}"


async def stream_sse(
    *,
    provider: str,
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    parse_delta: Callable[[str], str | None],
) -> AsyncIterator[str]:
    emitted = False
    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(90.0)) as client:
                async with client.stream(
                    "POST",
                    url,
                    headers=headers,
                    json=payload,
                ) as response:
                    if response.status_code >= 400:
                        body = (await response.aread()).decode("utf-8", errors="replace")
                        if response.status_code in RETRYABLE_STATUSES and attempt == 0:
                            await asyncio.sleep(0.35)
                            continue
                        raise provider_error(provider, response.status_code, body)
                    async for line in response.aiter_lines():
                        delta = parse_delta(line)
                        if delta:
                            emitted = True
                            yield delta
                    return
        except ProviderError:
            raise
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            if attempt == 0 and not emitted:
                await asyncio.sleep(0.35)
                continue
            raise ProviderError(
                f"{provider} could not be reached. Check the connection and try again."
            ) from exc


async def post_json(
    *,
    provider: str,
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
) -> dict[str, Any]:
    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(45.0)) as client:
                response = await client.post(url, headers=headers, json=payload)
            if response.status_code >= 400:
                if response.status_code in RETRYABLE_STATUSES and attempt == 0:
                    await asyncio.sleep(0.35)
                    continue
                raise provider_error(provider, response.status_code, response.text)
            return response.json()
        except ProviderError:
            raise
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            if attempt == 0:
                await asyncio.sleep(0.35)
                continue
            raise ProviderError(
                f"{provider} could not be reached. Check the connection and try again."
            ) from exc
    raise ProviderError(f"{provider} request could not be completed.")


async def check_api_key(
    *,
    provider: str,
    api_key: str | None,
    url: str,
    headers: dict[str, str],
) -> dict[str, Any]:
    if not api_key:
        return {
            "configured": False,
            "available": False,
            "message": "API key not configured",
        }
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(8.0)) as client:
            response = await client.get(url, headers=headers)
        if response.status_code < 400:
            model_ids = _model_ids(response.json())
            return {
                "configured": True,
                "available": True,
                "message": "Ready",
                "model_ids": model_ids,
            }
        error = provider_error(provider, response.status_code, response.text)
        return {
            "configured": True,
            "available": False,
            "message": str(error),
        }
    except (httpx.TimeoutException, httpx.TransportError):
        return {
            "configured": True,
            "available": False,
            "message": f"{provider} health check could not connect",
        }


def provider_error(provider: str, status_code: int, body: str) -> ProviderError:
    code = ""
    try:
        parsed = json.loads(body)
        error = parsed.get("error", {})
        code = str(error.get("code") or error.get("status") or "")
        details = error.get("details") or []
        reasons = " ".join(str(detail.get("reason", "")) for detail in details)
        code = f"{code} {reasons}".strip()
    except (json.JSONDecodeError, AttributeError):
        pass
    lowered = code.lower()
    if status_code in {401, 403} or "api_key_invalid" in lowered or "invalid_api_key" in lowered:
        return ProviderError(f"{provider} rejected the API key or model permission.")
    if status_code == 429:
        return ProviderError(f"{provider} rate limit or quota was reached. Try again later.")
    if status_code in {500, 502, 503, 504}:
        return ProviderError(f"{provider} is temporarily unavailable. Try again shortly.")
    return ProviderError(f"{provider} request failed ({status_code}).")


def _model_ids(payload: dict[str, Any]) -> list[str]:
    items = payload.get("data") or payload.get("models") or []
    model_ids: list[str] = []
    for item in items:
        model_id = item.get("id") or item.get("baseModelId") or item.get("name")
        if not model_id:
            continue
        normalized = str(model_id).removeprefix("models/")
        if normalized not in model_ids:
            model_ids.append(normalized)
    return model_ids


def clean_title(value: str) -> str:
    title = re.sub(r"<think>.*?</think>", "", value, flags=re.DOTALL | re.IGNORECASE)
    title = title.strip().splitlines()[0] if title.strip() else ""
    title = re.sub(r"^[\"'`*_#\s]+|[\"'`*_.#\s]+$", "", title)
    title = re.sub(r"\s+", " ", title)
    return title[:72].rstrip()


def parse_query_lines(value: str, original: str) -> list[str]:
    queries: list[str] = []
    for line in value.splitlines():
        cleaned = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", line).strip()
        cleaned = cleaned.strip("\"'`")
        if cleaned and cleaned.casefold() != original.casefold() and cleaned not in queries:
            queries.append(cleaned[:240])
        if len(queries) == 3:
            break
    return queries


def openai_output_text(payload: dict[str, Any]) -> str:
    parts: list[str] = []
    for item in payload.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text" and content.get("text"):
                parts.append(str(content["text"]))
    return "".join(parts).strip()


def gemini_output_text(payload: dict[str, Any]) -> str:
    parts: list[str] = []
    for candidate in payload.get("candidates", []):
        for part in candidate.get("content", {}).get("parts", []):
            if part.get("text"):
                parts.append(str(part["text"]))
    return "".join(parts).strip()
