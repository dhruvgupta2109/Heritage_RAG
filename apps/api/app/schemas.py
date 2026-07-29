from typing import Literal

from pydantic import BaseModel, Field
from pydantic.functional_validators import field_validator

from .config import MODEL_IDS

ConfidenceLevel = Literal["very_high", "high", "medium", "low", "very_low"]
RetrievalMode = Literal["quick", "medium", "deep"]


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4_000)
    chat_id: str | None = Field(default=None, min_length=1, max_length=100)
    model: str | None = None
    retrieval_mode: RetrievalMode = "medium"

    @field_validator("model")
    @classmethod
    def supported_model(cls, value: str | None) -> str | None:
        if value is not None and value not in MODEL_IDS:
            raise ValueError("Unsupported model")
        return value


class SourceRecord(BaseModel):
    id: int
    chunk_id: str
    document_id: str
    document: str
    file_name: str
    page_start: int | None = None
    page_end: int | None = None
    section: str | None = None
    snippet: str
    relevance: float = Field(ge=0, le=1)

    @property
    def page_label(self) -> str:
        if self.page_start is None:
            return "Page unavailable"
        if self.page_end and self.page_end != self.page_start:
            return f"Pages {self.page_start}–{self.page_end}"
        return f"Page {self.page_start}"


class AnsweredFrom(BaseModel):
    document_id: str
    document: str
    pages: str


class ConfidenceFactors(BaseModel):
    citation_coverage: float = Field(ge=0, le=1)
    retrieval_strength: float = Field(ge=0, le=1)
    source_agreement: float = Field(ge=0, le=1)
    location_quality: float = Field(ge=0, le=1)


class ConfidenceResult(BaseModel):
    score: int = Field(ge=0, le=100)
    level: ConfidenceLevel
    label: str
    rationale: str
    factors: ConfidenceFactors


class AnswerPayload(BaseModel):
    answer: str
    answered_from: list[AnsweredFrom]
    citations: list[SourceRecord]
    confidence: ConfidenceResult
    model: str
    retrieval_mode: RetrievalMode
    status: Literal["completed", "incomplete"] = "completed"


class ChatSummary(BaseModel):
    id: str
    title: str
    pinned: bool = False
    created_at: str
    updated_at: str
    message_count: int


class ChatUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    pinned: bool | None = None

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("Title cannot be empty")
        return cleaned


class ChatMessage(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    content: str
    model: str | None = None
    retrieval_mode: RetrievalMode | None = None
    answered_from: list[AnsweredFrom] = Field(default_factory=list)
    citations: list[SourceRecord] = Field(default_factory=list)
    confidence: ConfidenceResult | None = None
    status: str
    created_at: str


class ChatDetail(ChatSummary):
    messages: list[ChatMessage]


class DocumentRecord(BaseModel):
    id: str
    file_name: str
    title: str
    relative_path: str
    media_type: str
    page_count: int | None
    status: str
    indexed_at: str | None


class IndexResult(BaseModel):
    indexed: list[str]
    skipped: list[str]
    failed: dict[str, str]
    chunk_count: int


class UploadUnlockRequest(BaseModel):
    password: str = Field(min_length=1, max_length=200)


class UploadSessionStatus(BaseModel):
    unlocked: bool
    expires_in_seconds: int | None = None
