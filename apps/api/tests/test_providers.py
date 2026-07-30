import json

from app.providers.base import (
    GROUNDING_INSTRUCTIONS,
    _model_ids,
    clean_title,
    gemini_output_text,
    openai_output_text,
    parse_query_lines,
    provider_error,
)


def test_grounding_prompt_requires_adaptive_markdown_formatting() -> None:
    assert "GitHub-flavored Markdown" in GROUNDING_INSTRUCTIONS
    assert "bullets for an unordered set" in GROUNDING_INSTRUCTIONS
    assert "numbered list for ordered steps" in GROUNDING_INSTRUCTIONS
    assert "table for comparisons" in GROUNDING_INSTRUCTIONS
    assert "Do not force a table" in GROUNDING_INSTRUCTIONS
    assert "factual table row" in GROUNDING_INSTRUCTIONS


def test_openai_responses_text_is_extracted() -> None:
    payload = {
        "output": [
            {
                "type": "message",
                "content": [{"type": "output_text", "text": "Grounded answer [S1]."}],
            }
        ]
    }
    assert openai_output_text(payload) == "Grounded answer [S1]."


def test_gemini_candidate_text_is_extracted() -> None:
    payload = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"text": "Grounded "},
                        {"text": "answer [S1]."},
                    ]
                }
            }
        ]
    }
    assert gemini_output_text(payload) == "Grounded answer [S1]."


def test_provider_errors_do_not_expose_provider_body() -> None:
    body = json.dumps(
        {
            "error": {
                "code": "invalid_api_key",
                "message": "Incorrect key redacted-secret-value",
            }
        }
    )
    error = provider_error("OpenAI", 401, body)
    assert "rejected" in str(error)
    assert "redacted-secret-value" not in str(error)


def test_query_lines_are_cleaned_and_limited() -> None:
    assert parse_query_lines(
        "1. first query\n- second query\n* third query\nfourth query",
        "original",
    ) == ["first query", "second query", "third query"]


def test_shared_title_cleanup_removes_reasoning() -> None:
    assert clean_title("<think>hidden</think>\n**Calendar Events.**") == "Calendar Events"


def test_provider_model_lists_are_normalized() -> None:
    assert _model_ids({"data": [{"id": "gpt-5.6-terra"}]}) == ["gpt-5.6-terra"]
    assert _model_ids(
        {
            "models": [
                {
                    "name": "models/gemini-3.6-flash",
                    "baseModelId": "gemini-3.6-flash",
                }
            ]
        }
    ) == ["gemini-3.6-flash"]
