import json
from pathlib import Path
from typing import Any

from .chat import NO_SUPPORT_ANSWER
from .confidence import SOURCE_MARKER, evaluate_confidence, sanitize_answer
from .retrieval import RetrievalService
from .schemas import EvidenceState, RetrievalMode, SourceRecord


def load_evaluation_cases(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("Evaluation file must contain a non-empty cases list.")
    return cases


def evaluate_retrieval(
    retrieval: RetrievalService,
    cases: list[dict[str, Any]],
    mode: RetrievalMode,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for case in cases:
        result = retrieval.retrieve_with_mode(str(case["question"]), mode)
        expected = case.get("expected_sources", [])
        matched_rank = _matched_rank(result.context_rows, expected)
        answerable = bool(case["answerable"])
        passed = matched_rank is not None if answerable else None
        results.append(
            {
                "id": case["id"],
                "passed": passed,
                "scored": answerable,
                "answerable": answerable,
                "matched_rank": matched_rank,
                "retrieved": [
                    {
                        "file_name": source.file_name,
                        "page": source.page_start,
                        "relevance": source.relevance,
                    }
                    for source in result.sources
                ],
            }
        )

    answerable_results = [item for item in results if item["answerable"]]
    no_answer_results = [item for item in results if not item["answerable"]]
    passed_count = sum(bool(item["passed"]) for item in answerable_results)
    return {
        "mode": mode,
        "case_count": len(results),
        "scored_case_count": len(answerable_results),
        "no_answer_case_count": len(no_answer_results),
        "passed": passed_count,
        "pass_rate": round(passed_count / max(1, len(answerable_results)), 3),
        "answerable_hit_rate": round(
            sum(bool(item["passed"]) for item in answerable_results)
            / max(1, len(answerable_results)),
            3,
        ),
        "no_answer_note": (
            "No-answer cases require generation/citation evaluation and are not "
            "scored by retrieval hit rate."
        ),
        "failures": [item for item in answerable_results if not item["passed"]],
        "results": results,
    }


def evaluate_answer_cases(cases: list[dict[str, Any]]) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    citation_correct = 0
    grounded_correct = 0
    confidence_correct = 0
    no_answer_correct = 0
    no_answer_count = 0

    for case in cases:
        sources = [
            SourceRecord.model_validate(source)
            for source in case.get("retrieved_sources", [])
        ]
        raw_answer = str(case["answer"])
        sanitized, cited_numbers = sanitize_answer(raw_answer, len(sources))
        cited = [source for source in sources if source.id in cited_numbers]
        state = str(case["evidence_state"])
        confidence = evaluate_confidence(
            raw_answer,
            cited,
            sources,
            evidence_state=state,  # type: ignore[arg-type]
        )
        raw_markers = [int(marker) for marker in SOURCE_MARKER.findall(raw_answer)]
        valid_markers = [marker for marker in raw_markers if 1 <= marker <= len(sources)]
        citations_pass = bool(valid_markers) and len(valid_markers) == len(raw_markers)
        expected_documents = set(case.get("expected_documents", []))
        if expected_documents:
            citations_pass = citations_pass and expected_documents.issubset(
                {source.file_name for source in cited}
            )

        expected_terms = [str(term).casefold() for term in case.get("expected_terms", [])]
        term_recall = (
            sum(term in sanitized.casefold() for term in expected_terms)
            / max(1, len(expected_terms))
        )
        absent = state == "absent"
        if absent:
            no_answer_count += 1
            no_answer_pass = (
                sanitized == NO_SUPPORT_ANSWER
                and not cited
                and confidence.level == "very_low"
            )
            no_answer_correct += int(no_answer_pass)
            citations_pass = not cited and not raw_markers
            grounded_pass = no_answer_pass
        else:
            no_answer_pass = None
            grounded_pass = citations_pass and term_recall >= float(
                case.get("minimum_term_recall", 1.0)
            )

        allowed_levels = set(case.get("expected_confidence_levels", []))
        confidence_pass = confidence.level in allowed_levels
        citation_correct += int(citations_pass)
        grounded_correct += int(grounded_pass)
        confidence_correct += int(confidence_pass)
        results.append(
            {
                "id": case["id"],
                "evidence_state": state,
                "citations_pass": citations_pass,
                "grounded_pass": grounded_pass,
                "confidence_pass": confidence_pass,
                "no_answer_pass": no_answer_pass,
                "term_recall": round(term_recall, 3),
                "confidence": confidence.model_dump(),
            }
        )

    count = len(results)
    return {
        "case_count": count,
        "evidence_states": sorted({item["evidence_state"] for item in results}),
        "citation_precision": round(citation_correct / max(1, count), 3),
        "answer_groundedness": round(grounded_correct / max(1, count), 3),
        "confidence_accuracy": round(confidence_correct / max(1, count), 3),
        "no_answer_accuracy": round(no_answer_correct / max(1, no_answer_count), 3),
        "passed": all(
            item["citations_pass"]
            and item["grounded_pass"]
            and item["confidence_pass"]
            for item in results
        ),
        "failures": [
            item
            for item in results
            if not (
                item["citations_pass"]
                and item["grounded_pass"]
                and item["confidence_pass"]
            )
        ],
        "results": results,
    }


def add_evidence_labels(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    labeled: list[dict[str, Any]] = []
    for case in cases:
        category = str(case.get("category", "direct"))
        state: EvidenceState = "absent" if not case.get("answerable") else "direct"
        if category == "partial":
            state = "partial"
        elif category == "conflicting":
            state = "conflicting"
        labeled.append({**case, "evidence_state": state})
    return labeled


def _matched_rank(
    rows: list[dict],
    expected_sources: list[dict[str, Any]],
) -> int | None:
    for rank, row in enumerate(rows, start=1):
        for expected in expected_sources:
            if row.get("file_name") != expected.get("file_name"):
                continue
            expected_pages = set(expected.get("pages", []))
            if not expected_pages or row.get("page_start") in expected_pages:
                return rank
    return None
