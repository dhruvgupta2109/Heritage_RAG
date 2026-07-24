import re

from .schemas import (
    ConfidenceFactors,
    ConfidenceLevel,
    ConfidenceResult,
    EvidenceState,
    SourceRecord,
)

SENTENCE_PATTERN = re.compile(r"(?<=[.!?])\s+|\n+")
SOURCE_MARKER = re.compile(r"(?:\[|【)\s*S(\d+)\s*(?:\]|】)", re.IGNORECASE)
THINK_BLOCK = re.compile(r"<think>.*?</think>\s*", re.IGNORECASE | re.DOTALL)
CITATION_PUNCTUATION_GAP = re.compile(r"(\[\d+])\s+([,.;:!?])")
PARTIAL_SUPPORT_PATTERN = re.compile(
    r"\b(?:not specified|not provided|not stated|does not specify|"
    r"couldn['’]t find|could not find|only partially|partial support)\b",
    re.IGNORECASE,
)
CONFLICT_PATTERN = re.compile(
    r"\b(?:conflict(?:s|ing|ed)?|contradict(?:s|ing|ed|ory)?|"
    r"disagree(?:s|ment)?|inconsistent|different accounts?)\b",
    re.IGNORECASE,
)

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

    cleaned = SOURCE_MARKER.sub(replace_marker, answer)
    cleaned = CITATION_PUNCTUATION_GAP.sub(r"\1\2", cleaned).strip()
    return cleaned, cited


def evaluate_confidence(
    raw_answer: str,
    cited_sources: list[SourceRecord],
    retrieved_sources: list[SourceRecord],
    evidence_state: EvidenceState | None = None,
) -> ConfidenceResult:
    raw_answer = THINK_BLOCK.sub("", raw_answer)
    state = evidence_state or infer_evidence_state(
        raw_answer,
        cited_sources,
        retrieved_sources,
    )
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
    if state == "conflicting":
        source_agreement = min(source_agreement, 0.35)
    location_quality = (
        sum(source.page_start is not None for source in cited_sources) / len(cited_sources)
        if cited_sources
        else 0.0
    )
    completeness = {
        "direct": 1.0,
        "partial": 0.58,
        "conflicting": 0.62,
        "absent": 0.0,
    }[state]
    factors = ConfidenceFactors(
        citation_coverage=round(citation_coverage, 3),
        retrieval_strength=round(retrieval_strength, 3),
        source_agreement=round(source_agreement, 3),
        location_quality=round(location_quality, 3),
        completeness=completeness,
        contradiction=1.0 if state == "conflicting" else 0.0,
    )

    if state == "absent" or not retrieved_sources or not cited_sources:
        score = min(20, round(retrieval_strength * 20))
        return _result(
            score,
            "The answer is not backed by a valid citation from the indexed documents.",
            factors,
        )

    weighted = (
        (citation_coverage * 0.28)
        + (retrieval_strength * 0.28)
        + (source_agreement * 0.14)
        + (location_quality * 0.14)
        + (completeness * 0.16)
    )
    score = round(weighted * 100)
    if state == "partial":
        score = min(score, 74)
    elif state == "conflicting":
        score = min(score, 54)
    return _result(score, _rationale(score, factors, state), factors)


def infer_evidence_state(
    raw_answer: str,
    cited_sources: list[SourceRecord],
    retrieved_sources: list[SourceRecord],
) -> EvidenceState:
    if not retrieved_sources or not cited_sources:
        return "absent"
    if CONFLICT_PATTERN.search(raw_answer):
        return "conflicting"
    if PARTIAL_SUPPORT_PATTERN.search(raw_answer):
        return "partial"
    return "direct"


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


def _rationale(
    score: int,
    factors: ConfidenceFactors,
    evidence_state: EvidenceState,
) -> str:
    if evidence_state == "conflicting":
        return "The cited documents conflict; compare the cited pages before relying on the answer."
    if evidence_state == "partial":
        return "The documents support only part of the answer; the missing detail is not stated."
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
