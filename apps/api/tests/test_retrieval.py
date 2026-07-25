from app.retrieval import RETRIEVAL_PROFILES, RetrievalService, _snippet


class CapturingVectorStore:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def query(
        self,
        question: str,
        candidate_k: int,
        top_k: int,
        lexical_weight: float,
    ) -> list[dict]:
        self.calls.append(
            {
                "question": question,
                "candidate_k": candidate_k,
                "top_k": top_k,
                "lexical_weight": lexical_weight,
            }
        )
        return []


def test_snippet_centers_the_matching_query_phrase() -> None:
    prefix = "Background material. " * 40
    text = (
        f"{prefix}The approach has four components: experience, reflection, "
        "dialogue, and understanding. Additional material follows."
    )

    snippet = _snippet(
        text,
        "What are the four components of experiential learning?",
        length=180,
    )

    assert snippet.startswith("…")
    assert "four components" in snippet
    assert "experience, reflection, dialogue, and understanding" in snippet


def test_retrieval_modes_use_different_depths() -> None:
    vector_store = CapturingVectorStore()
    service = RetrievalService(
        vector_store=vector_store,  # type: ignore[arg-type]
        candidate_k=14,
        top_k=7,
        minimum_relevance=0.28,
    )

    service.retrieve_with_mode("Question", "quick")
    service.retrieve_with_mode("Question", "medium")
    result = service.retrieve_with_mode(
        "Question",
        "deep",
        ["Question details", "Question source"],
    )

    assert [call["top_k"] for call in vector_store.calls] == [3, 7, 24, 24, 24]
    assert [call["lexical_weight"] for call in vector_store.calls] == [
        0.0,
        0.18,
        0.0,
        0.0,
        0.0,
    ]
    assert result.query_count == 3
    assert result.strategy == "full_rerank"
    assert RETRIEVAL_PROFILES["deep"]["top_k"] == 12
