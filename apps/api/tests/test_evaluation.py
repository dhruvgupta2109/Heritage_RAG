from pathlib import Path

from app.evaluation import load_evaluation_cases


def test_corpus_evaluation_set_has_answerable_and_no_answer_cases() -> None:
    path = Path(__file__).parents[3] / "evals" / "questions.json"
    cases = load_evaluation_cases(path)

    assert len(cases) >= 20
    assert any(case["answerable"] for case in cases)
    assert any(not case["answerable"] for case in cases)
    assert all(case["expected_sources"] for case in cases if case["answerable"])
    assert all(not case["expected_sources"] for case in cases if not case["answerable"])
