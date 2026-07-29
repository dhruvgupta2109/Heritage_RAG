import re
from dataclasses import dataclass

from .schemas import RetrievalMode, SourceRecord
from .vector_store import VectorStore

RETRIEVAL_PROFILES = {
    "quick": {
        "candidate_k": 3,
        "top_k": 3,
        "lexical_weight": 0.0,
        "minimum_relevance": 0.32,
    },
    "medium": {
        "candidate_k": 14,
        "top_k": 7,
        "lexical_weight": 0.18,
        "minimum_relevance": 0.28,
    },
    "deep": {
        "candidate_k": 24,
        "top_k": 15,
        "lexical_weight": 0.25,
        "minimum_relevance": 0.24,
    },
}


@dataclass
class RetrievalResult:
    sources: list[SourceRecord]
    context_rows: list[dict]
    sufficient: bool


class RetrievalService:
    def __init__(
        self,
        vector_store: VectorStore,
        candidate_k: int,
        top_k: int,
        minimum_relevance: float,
    ):
        self.vector_store = vector_store
        self.candidate_k = candidate_k
        self.top_k = top_k
        self.minimum_relevance = minimum_relevance

    def retrieve(self, question: str) -> RetrievalResult:
        return self.retrieve_with_mode(question, "medium")

    def retrieve_with_mode(
        self,
        question: str,
        mode: RetrievalMode,
    ) -> RetrievalResult:
        profile = RETRIEVAL_PROFILES[mode]
        rows = self.vector_store.query(
            question,
            candidate_k=int(profile["candidate_k"]),
            top_k=int(profile["top_k"]),
            lexical_weight=float(profile["lexical_weight"]),
        )
        minimum_relevance = float(profile["minimum_relevance"])
        relevant = [row for row in rows if row["relevance"] >= minimum_relevance]
        sources = [
            SourceRecord(
                id=index,
                chunk_id=row["chunk_id"],
                document_id=str(row["document_id"]),
                document=str(row["title"]),
                file_name=str(row["file_name"]),
                page_start=_optional_int(row.get("page_start")),
                page_end=_optional_int(row.get("page_end")),
                section=str(row.get("section") or "") or None,
                snippet=_snippet(row["text"], question),
                relevance=round(float(row["relevance"]), 4),
            )
            for index, row in enumerate(relevant, start=1)
        ]
        return RetrievalResult(
            sources=sources,
            context_rows=relevant,
            sufficient=bool(sources),
        )


def _optional_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def _snippet(text: str, query: str, length: int = 320) -> str:
    if len(text) <= length:
        return text

    words = re.findall(r"[a-z0-9]+", query.lower())
    lowered = text.lower()
    match_position: int | None = None
    for window_size in range(min(5, len(words)), 1, -1):
        for start in range(0, len(words) - window_size + 1):
            phrase = " ".join(words[start : start + window_size])
            position = lowered.find(phrase)
            if position >= 0:
                match_position = position
                break
        if match_position is not None:
            break

    if match_position is None:
        distinctive = sorted(
            {word for word in words if len(word) >= 4},
            key=lambda word: (lowered.count(word) or 10_000, -len(word)),
        )
        for word in distinctive:
            position = lowered.find(word)
            if position >= 0:
                match_position = position
                break

    start = max(0, (match_position or 0) - 75)
    end = min(len(text), start + length)
    if start > 0:
        start = text.find(" ", start) + 1
    if end < len(text):
        end = text.rfind(" ", start, end)
    snippet = text[start:end].strip()
    return f"{'…' if start else ''}{snippet}{'…' if end < len(text) else ''}"
