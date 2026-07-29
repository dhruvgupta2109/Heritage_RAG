from io import BytesIO
from pathlib import Path

import pytest
from fastapi import UploadFile
from starlette.datastructures import Headers

from app.schemas import IndexResult
from app.upload_auth import InvalidUploadPassword, UploadAccess, UploadRateLimited
from app.uploads import DocumentUploadService, safe_file_name

PASSWORD_HASH = "$2b$12$hZAfbzIRTRpil8xgYFEVheOqFk/ba0R7RZ4zlb7iiIdOm6mid1tv6"


class FakeDatabase:
    duplicate: dict | None = None

    def find_document_by_hash(self, _: str) -> dict | None:
        return self.duplicate


class FakeVectorStore:
    def __init__(self) -> None:
        self.deleted: list[str] = []

    def delete_document(self, document_id: str) -> None:
        self.deleted.append(document_id)


class FakeIngestion:
    def __init__(self) -> None:
        self.indexed: list[Path] = []

    def index_file(self, path: Path) -> tuple[int, bool]:
        assert path.is_file()
        self.indexed.append(path)
        return 2, False


def text_upload(name: str, content: bytes = b"Grounded document text.") -> UploadFile:
    return UploadFile(
        file=BytesIO(content),
        filename=name,
        headers=Headers({"content-type": "text/plain"}),
    )


def binary_upload(name: str, content_type: str, content: bytes) -> UploadFile:
    return UploadFile(
        file=BytesIO(content),
        filename=name,
        headers=Headers({"content-type": content_type}),
    )


def test_upload_access_uses_password_hash_rate_limit_and_expiry() -> None:
    access = UploadAccess(
        password_hash=PASSWORD_HASH,
        session_ttl_seconds=600,
        max_attempts=2,
        attempt_window_seconds=600,
    )

    with pytest.raises(InvalidUploadPassword):
        access.unlock("wrong", "client", now=100)
    with pytest.raises(InvalidUploadPassword):
        access.unlock("also wrong", "client", now=101)
    with pytest.raises(UploadRateLimited):
        access.unlock("Password", "client", now=102)

    token = access.unlock("Password", "another-client", now=100)
    assert access.is_unlocked(token, now=699)
    assert not access.is_unlocked(token, now=700)
    assert not access.is_unlocked("not-a-session", now=100)


@pytest.mark.asyncio
async def test_text_upload_is_stored_and_indexed_immediately(tmp_path: Path) -> None:
    database = FakeDatabase()
    vector_store = FakeVectorStore()
    ingestion = FakeIngestion()
    service = DocumentUploadService(
        docs_dir=tmp_path,
        database=database,  # type: ignore[arg-type]
        vector_store=vector_store,  # type: ignore[arg-type]
        ingestion=ingestion,  # type: ignore[arg-type]
        max_file_bytes=1024,
    )

    result = await service.upload([text_upload("New Notes.txt")])

    assert result == IndexResult(
        indexed=["New Notes.txt"],
        skipped=[],
        failed={},
        chunk_count=2,
    )
    assert (tmp_path / "New Notes.txt").read_text() == "Grounded document text."
    assert ingestion.indexed == [tmp_path / "New Notes.txt"]


@pytest.mark.asyncio
async def test_duplicate_upload_is_skipped_without_writing_a_file(tmp_path: Path) -> None:
    database = FakeDatabase()
    database.duplicate = {"file_name": "Existing.txt"}
    service = DocumentUploadService(
        docs_dir=tmp_path,
        database=database,  # type: ignore[arg-type]
        vector_store=FakeVectorStore(),  # type: ignore[arg-type]
        ingestion=FakeIngestion(),  # type: ignore[arg-type]
        max_file_bytes=1024,
    )

    result = await service.upload([text_upload("Duplicate.txt")])

    assert result.indexed == []
    assert result.skipped == ["Duplicate.txt"]
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_upload_rejects_invalid_content_and_oversized_files(tmp_path: Path) -> None:
    service = DocumentUploadService(
        docs_dir=tmp_path,
        database=FakeDatabase(),  # type: ignore[arg-type]
        vector_store=FakeVectorStore(),  # type: ignore[arg-type]
        ingestion=FakeIngestion(),  # type: ignore[arg-type]
        max_file_bytes=16,
    )

    result = await service.upload(
        [
            binary_upload("Fake.pdf", "application/pdf", b"not a pdf"),
            text_upload("Large.txt", b"This content is over sixteen bytes."),
        ]
    )

    assert result.indexed == []
    assert "valid PDF" in result.failed["Fake.pdf"]
    assert "exceeds" in result.failed["Large.txt"]
    assert list(tmp_path.iterdir()) == []


def test_safe_file_name_blocks_traversal_and_unsupported_types() -> None:
    with pytest.raises(ValueError):
        safe_file_name("../secret.pdf")
    with pytest.raises(ValueError):
        safe_file_name("script.exe")
    assert safe_file_name("School | Notes.md") == "School _ Notes.md"
