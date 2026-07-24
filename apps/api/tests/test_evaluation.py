from pathlib import Path

from app.evaluation import evaluate_answer_cases, load_evaluation_cases


def test_corpus_evaluation_set_has_answerable_and_no_answer_cases() -> None:
    path = Path(__file__).parents[3] / "evals" / "questions.json"
    cases = load_evaluation_cases(path)

    assert len(cases) >= 20
    assert any(case["answerable"] for case in cases)
    assert any(not case["answerable"] for case in cases)
    assert all(case["expected_sources"] for case in cases if case["answerable"])
    assert all(not case["expected_sources"] for case in cases if not case["answerable"])


def test_labeled_answer_evaluation_covers_all_evidence_states() -> None:
    path = Path(__file__).parents[3] / "evals" / "answer_cases.json"
    cases = load_evaluation_cases(path)
    report = evaluate_answer_cases(cases)

    assert report["evidence_states"] == ["absent", "conflicting", "direct", "partial"]
    assert report["citation_precision"] == 1
    assert report["answer_groundedness"] == 1
    assert report["confidence_accuracy"] == 1
    assert report["no_answer_accuracy"] == 1
    assert report["passed"]
