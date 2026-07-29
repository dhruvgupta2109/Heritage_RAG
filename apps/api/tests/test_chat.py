import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.chat import NO_SUPPORT_ANSWER, ChatService
from app.database import Database
from app.retrieval import RetrievalResult
from app.schemas import ChatRequest, SourceRecord


class FakeRetrieval:
    def __init__(self, result: RetrievalResult):
        self.result = result
        self.mode = None

    def retrieve_with_mode(self, _: str, mode: str) -> RetrievalResult:
        self.mode = mode
        return self.result


class FakeProvider:
    model = "test-model"

    def __init__(self, answer: str):
        self.answer = answer
        self.selected_model = None
        self.title_queries: list[str] = []

    async def stream_answer(self, *args: object):
        self.selected_model = args[3]
        for token in self.answer.split(" "):
            yield f"{token} "

    async def generate_title(self, query: str, _: str) -> str:
        self.title_queries.append(query)
        return "Experiential Learning Components"


def source() -> SourceRecord:
    return SourceRecord(
        id=1,
        chunk_id="chunk-1",
        document_id="document-1",
        document="Experiential Learning",
        file_name="experiential.pdf",
        page_start=1,
        page_end=1,
        snippet="Experience, reflection, dialogue, and understanding.",
        relevance=0.95,
    )


def parse_sse(events: list[str], event_name: str) -> dict:
    event = next(item for item in events if item.startswith(f"event: {event_name}\n"))
    data_line = next(line for line in event.splitlines() if line.startswith("data: "))
    return json.loads(data_line[6:])


@pytest.mark.asyncio
async def test_grounded_answer_keeps_valid_page_citation(tmp_path: Path) -> None:
    evidence = source()
    retrieval = FakeRetrieval(
        RetrievalResult(
            sources=[evidence],
            context_rows=[{"text": evidence.snippet}],
            sufficient=True,
        )
    )
    database = Database(tmp_path / "heritage.db")
    database.initialize()
    provider = FakeProvider("The four components are listed on the page. [S1]")
    service = ChatService(
        retrieval=retrieval,  # type: ignore[arg-type]
        provider=provider,  # type: ignore[arg-type]
        database=database,
    )

    events = [
        event
        async for event in service.stream(
            ChatRequest(
                message="Question",
                model="openai/gpt-oss-20b",
                retrieval_mode="deep",
            )
        )
    ]
    completed = parse_sse(events, "answer.completed")
    created = parse_sse(events, "chat.created")

    assert retrieval.mode == "deep"
    assert provider.selected_model == "openai/gpt-oss-20b"
    assert provider.title_queries == ["Question"]
    assert created["title"] == "Experiential Learning Components"
    assert completed["chat_id"] == created["id"]
    assert completed["model"] == "openai/gpt-oss-20b"
    assert completed["retrieval_mode"] == "deep"
    assert completed["answer"].endswith("[1]")
    assert completed["answered_from"] == [
        {
            "document_id": "document-1",
            "document": "Experiential Learning",
            "pages": "Page 1",
        }
    ]
    assert completed["citations"][0]["page_start"] == 1
    assert completed["confidence"]["level"] in {"high", "very_high"}
    saved_chat = database.get_chat(created["id"])
    assert saved_chat is not None
    assert [message["role"] for message in saved_chat["messages"]] == [
        "user",
        "assistant",
    ]
    assert saved_chat["messages"][1]["answered_from"][0]["pages"] == "Page 1"


@pytest.mark.asyncio
async def test_uncited_provider_answer_becomes_no_support(tmp_path: Path) -> None:
    evidence = source()
    retrieval = FakeRetrieval(
        RetrievalResult(
            sources=[evidence],
            context_rows=[{"text": evidence.snippet}],
            sufficient=True,
        )
    )
    database = Database(tmp_path / "heritage.db")
    database.initialize()
    service = ChatService(
        retrieval=retrieval,  # type: ignore[arg-type]
        provider=FakeProvider("This answer has no source marker."),  # type: ignore[arg-type]
        database=database,
    )

    events = [event async for event in service.stream(ChatRequest(message="Question"))]
    completed = parse_sse(events, "answer.completed")

    assert completed["answer"] == NO_SUPPORT_ANSWER
    assert completed["answered_from"] == []
    assert completed["citations"] == []
    assert completed["confidence"]["level"] == "very_low"


def test_chat_request_rejects_an_unknown_model() -> None:
    with pytest.raises(ValidationError):
        ChatRequest(message="Question", model="not-a-groq-model")


@pytest.mark.asyncio
async def test_existing_chat_is_reused_without_regenerating_title(tmp_path: Path) -> None:
    evidence = source()
    retrieval = FakeRetrieval(
        RetrievalResult(
            sources=[evidence],
            context_rows=[{"text": evidence.snippet}],
            sufficient=True,
        )
    )
    database = Database(tmp_path / "heritage.db")
    database.initialize()
    provider = FakeProvider("A grounded answer. [S1]")
    service = ChatService(
        retrieval=retrieval,  # type: ignore[arg-type]
        provider=provider,  # type: ignore[arg-type]
        database=database,
    )

    first_events = [event async for event in service.stream(ChatRequest(message="First question"))]
    chat_id = parse_sse(first_events, "chat.created")["id"]
    second_events = [
        event
        async for event in service.stream(
            ChatRequest(message="Follow-up question", chat_id=chat_id)
        )
    ]

    assert not any(event.startswith("event: chat.created\n") for event in second_events)
    assert provider.title_queries == ["First question"]
    saved_chat = database.get_chat(chat_id)
    assert saved_chat is not None
    assert saved_chat["title"] == "Experiential Learning Components"
    assert saved_chat["message_count"] == 4
    assert [message["content"] for message in saved_chat["messages"][::2]] == [
        "First question",
        "Follow-up question",
    ]
