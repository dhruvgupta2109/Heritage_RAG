import re

from .schemas import (
    ConfidenceFactors,
    ConfidenceLevel,
    ConfidenceResult,
    SourceRecord,
)

SENTENCE_PATTERN = re.compile(r"(?<=[.!?])\s+|\n+")
SOURCE_MARKER = re.compile(r"(?:\[|【)\s*S(\d+)\s*(?:\]|】)", re.IGNORECASE)
THINK_BLOCK = re.compile(r"<think>.*?</think>\s*", re.IGNORECASE | re.DOTALL)

LABELS: dict[ConfidenceLevel, str] = {
    "very_high": "Very high confidence",
    "high": "High confidence",
    "medium": "Medium confidence",
    "low": "Low confidence",
    "very_low": "Very low confidence",
}


def cited_source_numbers(answer: str, valid_count: int) -> list[int]:
    answer = THINK_BLOCK.sub("", answer)
    return sorted(
        {int(match) for match in SOURCE_MARKER.findall(answer) if 1 <= int(match) <= valid_count}
    )


def sanitize_answer(answer: str, valid_count: int) -> tuple[str, list[int]]:
    answer = THINK_BLOCK.sub("", answer)
    cited = cited_source_numbers(answer, valid_count)
    valid = set(cited)

    def replace_marker(match: re.Match[str]) -> str:
        source_id = int(match.group(1))
        return f"[{source_id}]" if source_id in valid else ""

    cleaned = SOURCE_MARKER.sub(replace_marker, answer).strip()
    return cleaned, cited


def evaluate_confidence(
    raw_answer: str,
    cited_sources: list[SourceRecord],
    retrieved_sources: list[SourceRecord],
) -> ConfidenceResult:
    raw_answer = THINK_BLOCK.sub("", raw_answer)
    sentences = [
        sentence.strip() for sentence in SENTENCE_PATTERN.split(raw_answer) if sentence.strip()
    ]
    cited_sentences = sum(bool(SOURCE_MARKER.search(sentence)) for sentence in sentences)
    citation_coverage = cited_sentences / max(1, len(sentences))
    if cited_sources:
        # A final marker can support one coherent paragraph or numbered list.
        citation_coverage = max(citation_coverage, 0.74)

    retrieval_strength = (
        sum(source.relevance for source in cited_sources) / len(cited_sources)
        if cited_sources
        else 0.0
    )
    distinct_locations = {
        (source.document_id, source.page_start, source.page_end) for source in cited_sources
    }
    source_agreement = (
        min(1.0, 0.82 + (0.09 * (len(distinct_locations) - 1))) if cited_sources else 0.0
    )
    location_quality = (
        sum(source.page_start is not None for source in cited_sources) / len(cited_sources)
        if cited_sources
        else 0.0
    )
    factors = ConfidenceFactors(
        citation_coverage=round(citation_coverage, 3),
        retrieval_strength=round(retrieval_strength, 3),
        source_agreement=round(source_agreement, 3),
        location_quality=round(location_quality, 3),
    )

    if not retrieved_sources or not cited_sources:
        score = min(20, round(retrieval_strength * 20))
        return _result(
            score,
            "The answer is not backed by a valid citation from the indexed documents.",
            factors,
        )

    weighted = (
        (citation_coverage * 0.34)
        + (retrieval_strength * 0.34)
        + (source_agreement * 0.14)
        + (location_quality * 0.18)
    )
    score = round(weighted * 100)
    return _result(score, _rationale(score, factors), factors)


def _result(
    score: int,
    rationale: str,
    factors: ConfidenceFactors,
) -> ConfidenceResult:
    score = max(0, min(100, score))
    level = level_for_score(score)
    return ConfidenceResult(
        score=score,
        level=level,
        label=LABELS[level],
        rationale=rationale,
        factors=factors,
    )


def level_for_score(score: int) -> ConfidenceLevel:
    if score >= 90:
        return "very_high"
    if score >= 75:
        return "high"
    if score >= 55:
        return "medium"
    if score >= 30:
        return "low"
    return "very_low"


def _rationale(score: int, factors: ConfidenceFactors) -> str:
    if score >= 90:
        return "The answer is directly and completely supported by clearly located passages."
    if score >= 75:
        return "The answer has strong support from relevant, clearly located passages."
    if score >= 55:
        return "The documents provide useful but incomplete or indirect support."
    if score >= 30:
        return "The documents provide only partial or weak support; check the cited pages."
    if factors.location_quality < 1:
        return "The available evidence is weak or lacks a reliable source location."
    return "Reliable support for this answer was not found in the indexed documents."
