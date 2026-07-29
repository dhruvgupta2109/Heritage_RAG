import json
from pathlib import Path
from typing import Any

from .retrieval import RetrievalService
from .schemas import RetrievalMode


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
