import math
import re
from collections import Counter
from dataclasses import dataclass

from .schemas import RetrievalMode, SourceRecord
from .vector_store import TOKEN_PATTERN, VectorStore, lexical_overlap

RETRIEVAL_PROFILES = {
    "quick": {
        "candidate_k": 3,
        "top_k": 3,
        "lexical_weight": 0.0,
        "minimum_relevance": 0.32,
        "strategy": "vector",
    },
    "medium": {
        "candidate_k": 14,
        "top_k": 7,
        "lexical_weight": 0.18,
        "minimum_relevance": 0.28,
        "strategy": "hybrid",
    },
    "deep": {
        "candidate_k": 24,
        "top_k": 15,
        "lexical_weight": 0.0,
        "minimum_relevance": 0.24,
        "strategy": "full_rerank",
    },
}


@dataclass
class RetrievalResult:
    sources: list[SourceRecord]
    context_rows: list[dict]
    sufficient: bool
    query_count: int = 1
    strategy: str = "hybrid"


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
        expanded_queries: list[str] | None = None,
    ) -> RetrievalResult:
        profile = RETRIEVAL_PROFILES[mode]
        if mode == "deep":
            queries = _unique_queries(question, expanded_queries or [])
            rows = self._deep_rows(
                question=question,
                queries=queries,
                candidate_k=int(profile["candidate_k"]),
                top_k=int(profile["top_k"]),
            )
        else:
            queries = [question]
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
            query_count=len(queries),
            strategy=str(profile["strategy"]),
        )

    def _deep_rows(
        self,
        *,
        question: str,
        queries: list[str],
        candidate_k: int,
        top_k: int,
    ) -> list[dict]:
        merged: dict[str, dict] = {}
        reciprocal_ranks: Counter[str] = Counter()
        query_hits: Counter[str] = Counter()
        for query in queries:
            rows = self.vector_store.query(
                query,
                candidate_k=candidate_k,
                top_k=candidate_k,
                lexical_weight=0.0,
            )
            for rank, row in enumerate(rows, start=1):
                chunk_id = str(row["chunk_id"])
                reciprocal_ranks[chunk_id] += 1 / (60 + rank)
                query_hits[chunk_id] += 1
                if chunk_id not in merged:
                    merged[chunk_id] = dict(row)
                else:
                    merged[chunk_id]["relevance"] = max(
                        float(merged[chunk_id]["relevance"]),
                        float(row["relevance"]),
                    )

        candidates = list(merged.values())
        bm25 = _bm25_scores(question, candidates)
        maximum_rrf = max(1 / 61, len(queries) / 61)
        for row in candidates:
            chunk_id = str(row["chunk_id"])
            semantic = float(row["relevance"])
            exact_overlap = lexical_overlap(question, str(row["text"]))
            fused_rank = min(1.0, reciprocal_ranks[chunk_id] / maximum_rrf)
            coverage = query_hits[chunk_id] / max(1, len(queries))
            row["relevance"] = min(
                1.0,
                (semantic * 0.46)
                + (bm25.get(chunk_id, 0.0) * 0.25)
                + (exact_overlap * 0.14)
                + (fused_rank * 0.10)
                + (coverage * 0.05),
            )
        candidates.sort(key=lambda row: float(row["relevance"]), reverse=True)
        return candidates[:top_k]


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


def _unique_queries(question: str, expanded: list[str]) -> list[str]:
    queries = [question]
    seen = {question.casefold().strip()}
    for query in expanded:
        normalized = query.casefold().strip()
        if normalized and normalized not in seen:
            queries.append(query.strip())
            seen.add(normalized)
        if len(queries) == 4:
            break
    return queries


def _bm25_scores(query: str, rows: list[dict]) -> dict[str, float]:
    query_terms = TOKEN_PATTERN.findall(query.lower())
    if not query_terms or not rows:
        return {}
    tokenized = [TOKEN_PATTERN.findall(str(row["text"]).lower()) for row in rows]
    average_length = sum(len(tokens) for tokens in tokenized) / max(1, len(tokenized))
    document_frequency = Counter(
        term for terms in tokenized for term in set(terms) if term in query_terms
    )
    scores: dict[str, float] = {}
    total_documents = len(rows)
    for row, terms in zip(rows, tokenized, strict=True):
        frequencies = Counter(terms)
        score = 0.0
        for term in query_terms:
            frequency = frequencies[term]
            if not frequency:
                continue
            frequency_docs = document_frequency[term]
            inverse_frequency = max(
                0.0,
                math.log(1 + ((total_documents - frequency_docs + 0.5) / (frequency_docs + 0.5))),
            )
            length_adjustment = 1.5 * (1 - 0.75 + (0.75 * len(terms) / max(1.0, average_length)))
            score += inverse_frequency * ((frequency * 2.5) / (frequency + length_adjustment))
        scores[str(row["chunk_id"])] = score
    maximum = max(scores.values(), default=0.0)
    if maximum <= 0:
        return {key: 0.0 for key in scores}
    return {key: value / maximum for key, value in scores.items()}
