import hashlib
import mimetypes
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from docx import Document
from pypdf import PdfReader

from .database import Database
from .schemas import IndexResult
from .vector_store import VectorStore

SUPPORTED_SUFFIXES = {".pdf", ".docx", ".txt", ".md"}
WHITESPACE = re.compile(r"\s+")


@dataclass
class TextUnit:
    text: str
    page: int | None
    section: str | None


def clean_text(text: str) -> str:
    return WHITESPACE.sub(" ", text).strip()


def split_words(text: str, max_words: int = 420, overlap: int = 60) -> list[str]:
    words = text.split()
    if not words:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = min(len(words), start + max_words)
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start = max(start + 1, end - overlap)
    return chunks


def extract_units(path: Path) -> tuple[list[TextUnit], int | None]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        reader = PdfReader(path)
        units = [
            TextUnit(text=clean_text(page.extract_text() or ""), page=index, section=None)
            for index, page in enumerate(reader.pages, start=1)
        ]
        return [unit for unit in units if unit.text], len(reader.pages)

    if suffix == ".docx":
        document = Document(path)
        units: list[TextUnit] = []
        section: str | None = None
        buffer: list[str] = []
        for paragraph in document.paragraphs:
            text = clean_text(paragraph.text)
            if not text:
                continue
            style = paragraph.style.name.lower() if paragraph.style else ""
            if style.startswith("heading"):
                if buffer:
                    units.append(TextUnit(" ".join(buffer), None, section))
                    buffer = []
                section = text
            else:
                buffer.append(text)
        if buffer:
            units.append(TextUnit(" ".join(buffer), None, section))
        return units, None

    raw = path.read_text(encoding="utf-8", errors="replace")
    if suffix == ".md":
        units = []
        section = None
        buffer = []
        for line in raw.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                if buffer:
                    units.append(TextUnit(clean_text(" ".join(buffer)), None, section))
                    buffer = []
                section = stripped.lstrip("#").strip() or section
            elif stripped:
                buffer.append(stripped)
        if buffer:
            units.append(TextUnit(clean_text(" ".join(buffer)), None, section))
        return units, None

    text = clean_text(raw)
    return ([TextUnit(text, None, "Text document")] if text else []), None


class IngestionService:
    def __init__(self, docs_dir: Path, database: Database, vector_store: VectorStore):
        self.docs_dir = docs_dir
        self.database = database
        self.vector_store = vector_store

    def index_all(self) -> IndexResult:
        indexed: list[str] = []
        skipped: list[str] = []
        failed: dict[str, str] = {}
        total_chunks = 0
        paths = sorted(
            path
            for path in self.docs_dir.rglob("*")
            if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
        )

        for path in paths:
            relative_path = path.relative_to(self.docs_dir).as_posix()
            try:
                chunk_count, was_skipped = self.index_file(path)
                if was_skipped:
                    skipped.append(relative_path)
                else:
                    indexed.append(relative_path)
                    total_chunks += chunk_count
            except Exception as exc:
                failed[relative_path] = str(exc)

        return IndexResult(
            indexed=indexed,
            skipped=skipped,
            failed=failed,
            chunk_count=total_chunks,
        )

    def index_file(self, path: Path) -> tuple[int, bool]:
        raw = path.read_bytes()
        content_hash = hashlib.sha256(raw).hexdigest()
        relative_path = path.relative_to(self.docs_dir).as_posix()
        existing = self.database.find_document_by_path(relative_path)
        if existing and existing["content_hash"] == content_hash and existing["status"] == "ready":
            return 0, True

        document_id = f"doc_{content_hash[:20]}"
        if existing and existing["id"] != document_id:
            self.vector_store.delete_document(existing["id"])

        units, page_count = extract_units(path)
        chunks = self._build_chunks(
            units=units,
            document_id=document_id,
            path=path,
            relative_path=relative_path,
            content_hash=content_hash,
        )
        if not chunks:
            raise ValueError("No readable text was found in this document.")

        self.vector_store.delete_document(document_id)
        self.vector_store.upsert(chunks)
        now = datetime.now(UTC).isoformat()
        self.database.upsert_document(
            {
                "id": document_id,
                "file_name": path.name,
                "title": path.stem,
                "relative_path": relative_path,
                "content_hash": content_hash,
                "media_type": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                "page_count": page_count,
                "status": "ready",
                "error": None,
                "indexed_at": now,
            }
        )
        return len(chunks), False

    @staticmethod
    def _build_chunks(
        units: list[TextUnit],
        document_id: str,
        path: Path,
        relative_path: str,
        content_hash: str,
    ) -> list[dict[str, Any]]:
        chunks: list[dict[str, Any]] = []
        sequence = 0
        for unit in units:
            for text in split_words(unit.text):
                sequence += 1
                chunks.append(
                    {
                        "chunk_id": f"{document_id}_c{sequence:05d}",
                        "document_id": document_id,
                        "file_name": path.name,
                        "title": path.stem,
                        "relative_path": relative_path,
                        "page_start": unit.page,
                        "page_end": unit.page,
                        "section": unit.section,
                        "text": text,
                        "content_hash": content_hash,
                    }
                )
        return chunks
