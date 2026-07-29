from app.providers.groq import _clean_title


def test_clean_title_removes_reasoning_and_markdown() -> None:
    assert (
        _clean_title("<think>internal reasoning</think>\n**Experiential Learning Components.**")
        == "Experiential Learning Components"
    )


def test_clean_title_is_capped_for_the_sidebar() -> None:
    assert len(_clean_title("A" * 100)) == 72
