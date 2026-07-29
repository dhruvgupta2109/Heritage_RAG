from app.confidence import evaluate_confidence, level_for_score, sanitize_answer
from app.schemas import SourceRecord


def source(source_id: int = 1, relevance: float = 0.9) -> SourceRecord:
    return SourceRecord(
        id=source_id,
        chunk_id=f"chunk-{source_id}",
        document_id="document-1",
        document="Experiential Learning",
        file_name="experiential.pdf",
        page_start=1,
        page_end=1,
        snippet="Evidence",
        relevance=relevance,
    )


def test_confidence_level_boundaries() -> None:
    assert level_for_score(100) == "very_high"
    assert level_for_score(90) == "very_high"
    assert level_for_score(89) == "high"
    assert level_for_score(75) == "high"
    assert level_for_score(74) == "medium"
    assert level_for_score(55) == "medium"
    assert level_for_score(54) == "low"
    assert level_for_score(30) == "low"
    assert level_for_score(29) == "very_low"
    assert level_for_score(0) == "very_low"


def test_invalid_citation_is_removed() -> None:
    cleaned, cited = sanitize_answer("Supported [S1]. Invented [S9].", valid_count=1)
    assert cleaned == "Supported [1]. Invented ."
    assert cited == [1]


def test_decorative_provider_citation_is_normalized() -> None:
    cleaned, cited = sanitize_answer("Supported by the page【S1】.", valid_count=1)
    assert cleaned == "Supported by the page[1]."
    assert cited == [1]


def test_hidden_reasoning_block_is_removed() -> None:
    cleaned, cited = sanitize_answer(
        "<think>Private reasoning.</think>\nFinal answer [S1].",
        valid_count=1,
    )
    assert cleaned == "Final answer [1]."
    assert cited == [1]


def test_no_valid_citation_is_very_low() -> None:
    evidence = source()
    result = evaluate_confidence(
        raw_answer="An answer without a citation.",
        cited_sources=[],
        retrieved_sources=[evidence],
    )
    assert result.level == "very_low"
    assert result.score <= 29


def test_strong_cited_answer_is_high_or_better() -> None:
    evidence = source(relevance=0.95)
    result = evaluate_confidence(
        raw_answer="The answer is directly stated in the source. [S1]",
        cited_sources=[evidence],
        retrieved_sources=[evidence],
    )
    assert result.level in {"high", "very_high"}
