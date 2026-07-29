import json
import re
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from .confidence import evaluate_confidence, sanitize_answer
from .database import Database
from .providers.groq import GroqProvider
from .retrieval import RetrievalService
from .schemas import AnsweredFrom, AnswerPayload, ChatRequest, SourceRecord

NO_SUPPORT_ANSWER = "I couldn't find reliable support for this in the indexed documents."


class ChatService:
    def __init__(
        self,
        retrieval: RetrievalService,
        provider: GroqProvider,
        database: Database,
    ):
        self.retrieval = retrieval
        self.provider = provider
        self.database = database

    async def stream(self, request: ChatRequest) -> AsyncIterator[str]:
        message_id = f"msg_{uuid.uuid4().hex}"
        selected_model = request.model or self.provider.model
        now = datetime.now(UTC).isoformat()

        if request.chat_id:
            chat = self.database.get_chat(request.chat_id)
            if not chat:
                yield _sse("error", {"message": "Conversation not found."})
                return
            chat_id = request.chat_id
        else:
            chat_id = f"chat_{uuid.uuid4().hex}"
            try:
                title = await self.provider.generate_title(
                    request.message,
                    selected_model,
                )
            except Exception:
                title = _fallback_title(request.message)
            chat = self.database.create_chat(chat_id, title, now)
            yield _sse("chat.created", chat)

        user_message_id = f"msg_{uuid.uuid4().hex}"
        self.database.save_user_message(
            message_id=user_message_id,
            chat_id=chat_id,
            content=request.message,
            model=selected_model,
            retrieval_mode=request.retrieval_mode,
            created_at=now,
        )
        yield _sse(
            "message.started",
            {
                "message_id": message_id,
                "chat_id": chat_id,
                "model": selected_model,
                "retrieval_mode": request.retrieval_mode,
            },
        )

        result = self.retrieval.retrieve_with_mode(
            request.message,
            request.retrieval_mode,
        )
        yield _sse(
            "retrieval.completed",
            {
                "source_count": len(result.sources),
                "documents": sorted({source.document for source in result.sources}),
            },
        )

        if not result.sufficient:
            raw_answer = NO_SUPPORT_ANSWER
            yield _sse("answer.delta", {"text": raw_answer})
        else:
            source_text = {
                source.id: result.context_rows[source.id - 1]["text"] for source in result.sources
            }
            parts: list[str] = []
            try:
                async for delta in self.provider.stream_answer(
                    request.message,
                    result.sources,
                    source_text,
                    selected_model,
                ):
                    parts.append(delta)
                    yield _sse("answer.delta", {"text": delta})
            except Exception as exc:
                yield _sse("error", {"message": str(exc)})
                return
            raw_answer = "".join(parts).strip() or NO_SUPPORT_ANSWER

        sanitized, cited_numbers = sanitize_answer(raw_answer, len(result.sources))
        cited_sources = [source for source in result.sources if source.id in set(cited_numbers)]
        if not cited_sources:
            sanitized = NO_SUPPORT_ANSWER

        confidence = evaluate_confidence(raw_answer, cited_sources, result.sources)
        answered_from = _answered_from(cited_sources)
        payload = AnswerPayload(
            answer=sanitized,
            answered_from=answered_from,
            citations=cited_sources,
            confidence=confidence,
            model=selected_model,
            retrieval_mode=request.retrieval_mode,
        )
        self.database.save_message_snapshot(
            message_id=message_id,
            chat_id=chat_id,
            content=payload.answer,
            model=payload.model,
            retrieval_mode=payload.retrieval_mode,
            citations=[source.model_dump() for source in payload.citations],
            confidence=payload.confidence.model_dump(),
            status=payload.status,
            created_at=datetime.now(UTC).isoformat(),
        )
        yield _sse(
            "answer.completed",
            {"message_id": message_id, "chat_id": chat_id, **payload.model_dump()},
        )


def _answered_from(sources: list[SourceRecord]) -> list[AnsweredFrom]:
    grouped: dict[tuple[str, str], set[str]] = {}
    for source in sources:
        key = (source.document_id, source.document)
        grouped.setdefault(key, set()).add(source.page_label)
    return [
        AnsweredFrom(
            document_id=document_id,
            document=document,
            pages=", ".join(sorted(pages, key=_natural_page_key)),
        )
        for (document_id, document), pages in grouped.items()
    ]


def _natural_page_key(label: str) -> tuple[int, int]:
    match = re.search(r"\d+", label)
    return (0 if match else 1, int(match.group()) if match else 0)


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _fallback_title(question: str) -> str:
    words = re.sub(r"\s+", " ", question).strip().rstrip("?.!").split()
    title = " ".join(words[:7])
    if len(words) > 7:
        title += "…"
    return title or "New conversation"
