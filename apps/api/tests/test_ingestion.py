from pathlib import Path

from app.ingestion import TextUnit, clean_text, extract_units, split_words


def test_clean_text_normalizes_whitespace() -> None:
    assert clean_text("One\n  two\tthree") == "One two three"


def test_split_words_uses_overlap() -> None:
    chunks = split_words("one two three four five six", max_words=4, overlap=2)
    assert chunks == ["one two three four", "three four five six"]


def test_markdown_extraction_keeps_heading_locator(tmp_path: Path) -> None:
    path = tmp_path / "example.md"
    path.write_text("# First section\nGrounded text.", encoding="utf-8")
    units, pages = extract_units(path)
    assert pages is None
    assert units == [TextUnit("Grounded text.", None, "First section")]
