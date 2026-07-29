import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def lexical_overlap(query: str, text: str) -> float:
    query_tokens = Counter(TOKEN_PATTERN.findall(query.lower()))
    if not query_tokens:
        return 0.0
    text_tokens = Counter(TOKEN_PATTERN.findall(text.lower()))
    matched = sum(min(count, text_tokens[token]) for token, count in query_tokens.items())
    return min(1.0, matched / max(1, sum(query_tokens.values())))


class VectorStore:
    def __init__(self, path: Path, collection_name: str):
        self.client = chromadb.PersistentClient(path=str(path))
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=DefaultEmbeddingFunction(),
            metadata={"hnsw:space": "cosine"},
        )

    @property
    def count(self) -> int:
        return self.collection.count()

    def upsert(self, chunks: list[dict[str, Any]]) -> None:
        if not chunks:
            return
        self.collection.upsert(
            ids=[chunk["chunk_id"] for chunk in chunks],
            documents=[chunk["text"] for chunk in chunks],
            metadatas=[self._chroma_metadata(chunk) for chunk in chunks],
        )

    def delete_document(self, document_id: str) -> None:
        self.collection.delete(where={"document_id": document_id})

    def query(
        self,
        question: str,
        candidate_k: int,
        top_k: int,
        lexical_weight: float = 0.18,
    ) -> list[dict[str, Any]]:
        available = self.count
        if available == 0:
            return []
        result = self.collection.query(
            query_texts=[question],
            n_results=min(candidate_k, available),
            include=["documents", "metadatas", "distances"],
        )
        rows: list[dict[str, Any]] = []
        ids = result["ids"][0]
        documents = result["documents"][0]
        metadatas = result["metadatas"][0]
        distances = result["distances"][0]
        for chunk_id, text, metadata, distance in zip(
            ids, documents, metadatas, distances, strict=True
        ):
            vector_similarity = max(0.0, min(1.0, 1.0 - float(distance)))
            lexical_similarity = lexical_overlap(question, text)
            relevance = max(
                0.0,
                min(
                    1.0,
                    (vector_similarity * (1 - lexical_weight))
                    + (lexical_similarity * lexical_weight),
                ),
            )
            rows.append(
                {
                    "chunk_id": chunk_id,
                    "text": text,
                    "relevance": relevance,
                    **metadata,
                }
            )
        rows.sort(key=lambda row: row["relevance"], reverse=True)
        return rows[:top_k]

    @staticmethod
    def _chroma_metadata(chunk: dict[str, Any]) -> dict[str, str | int | float | bool]:
        metadata: dict[str, str | int | float | bool] = {
            "document_id": chunk["document_id"],
            "file_name": chunk["file_name"],
            "title": chunk["title"],
            "relative_path": chunk["relative_path"],
            "section": chunk.get("section") or "",
            "content_hash": chunk["content_hash"],
        }
        if chunk.get("page_start") is not None:
            metadata["page_start"] = int(chunk["page_start"])
            metadata["page_end"] = int(chunk.get("page_end") or chunk["page_start"])
        return metadata


def clamp_score(value: float) -> float:
    if not math.isfinite(value):
        return 0.0
    return max(0.0, min(1.0, value))
