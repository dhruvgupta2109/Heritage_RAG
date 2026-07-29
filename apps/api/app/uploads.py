import hashlib
import re
import tempfile
import unicodedata
import zipfile
from pathlib import Path

from fastapi import UploadFile

from .database import Database
from .ingestion import SUPPORTED_SUFFIXES, IngestionService
from .schemas import IndexResult
from .vector_store import VectorStore

UPLOAD_CHUNK_BYTES = 1024 * 1024
MAX_UPLOAD_FILES = 20
SAFE_NAME_PATTERN = re.compile(r"[^\w .()\-]+", re.UNICODE)
ALLOWED_MEDIA_TYPES = {
    ".pdf": {"application/pdf", "application/x-pdf", "application/octet-stream"},
    ".docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/zip",
        "application/octet-stream",
    },
    ".txt": {"text/plain", "application/octet-stream"},
    ".md": {"text/markdown", "text/plain", "application/octet-stream"},
}


class DocumentUploadService:
    def __init__(
        self,
        docs_dir: Path,
        database: Database,
        vector_store: VectorStore,
        ingestion: IngestionService,
        max_file_bytes: int,
    ):
        self.docs_dir = docs_dir.resolve()
        self.database = database
        self.vector_store = vector_store
        self.ingestion = ingestion
        self.max_file_bytes = max_file_bytes

    async def upload(self, files: list[UploadFile]) -> IndexResult:
        indexed: list[str] = []
        skipped: list[str] = []
        failed: dict[str, str] = {}
        chunk_count = 0

        if not files:
            return IndexResult(
                indexed=[],
                skipped=[],
                failed={"upload": "Choose at least one document."},
                chunk_count=0,
            )
        if len(files) > MAX_UPLOAD_FILES:
            return IndexResult(
                indexed=[],
                skipped=[],
                failed={"upload": f"Upload at most {MAX_UPLOAD_FILES} documents at a time."},
                chunk_count=0,
            )

        for uploaded in files:
            original_name = uploaded.filename or "Unnamed document"
            try:
                safe_name = safe_file_name(original_name)
                self._validate_declared_type(safe_name, uploaded.content_type)
                result = await self._store_and_index(uploaded, safe_name)
                if result["duplicate"]:
                    skipped.append(original_name)
                else:
                    indexed.append(result["file_name"])
                    chunk_count += result["chunk_count"]
            except ValueError as exc:
                failed[original_name] = str(exc)
            except Exception:
                failed[original_name] = "Could not read and index this document."
            finally:
                await uploaded.close()

        return IndexResult(
            indexed=indexed,
            skipped=skipped,
            failed=failed,
            chunk_count=chunk_count,
        )

    async def _store_and_index(self, uploaded: UploadFile, safe_name: str) -> dict:
        temporary_path: Path | None = None
        destination: Path | None = None
        content_hash = ""
        try:
            with tempfile.NamedTemporaryFile(
                prefix=".heritage-upload-",
                suffix=".tmp",
                dir=self.docs_dir,
                delete=False,
            ) as temporary:
                temporary_path = Path(temporary.name)
                digest = hashlib.sha256()
                total_bytes = 0
                header = b""
                while chunk := await uploaded.read(UPLOAD_CHUNK_BYTES):
                    total_bytes += len(chunk)
                    if total_bytes > self.max_file_bytes:
                        raise ValueError(
                            f"File exceeds the {self.max_file_bytes // (1024 * 1024)} MB limit."
                        )
                    if len(header) < 4096:
                        header += chunk[: 4096 - len(header)]
                    digest.update(chunk)
                    temporary.write(chunk)
                if total_bytes == 0:
                    raise ValueError("The selected document is empty.")
                content_hash = digest.hexdigest()

            self._validate_content(temporary_path, Path(safe_name).suffix.lower(), header)
            duplicate = self.database.find_document_by_hash(content_hash)
            if duplicate:
                return {
                    "duplicate": True,
                    "file_name": duplicate["file_name"],
                    "chunk_count": 0,
                }

            destination = self._unique_destination(safe_name)
            temporary_path.replace(destination)
            temporary_path = None
            indexed_chunks, _ = self.ingestion.index_file(destination)
            return {
                "duplicate": False,
                "file_name": destination.name,
                "chunk_count": indexed_chunks,
            }
        except Exception:
            if content_hash:
                self.vector_store.delete_document(f"doc_{content_hash[:20]}")
            if destination and destination.exists():
                destination.unlink()
            raise
        finally:
            if temporary_path and temporary_path.exists():
                temporary_path.unlink()

    def _unique_destination(self, safe_name: str) -> Path:
        candidate = (self.docs_dir / safe_name).resolve()
        candidate.relative_to(self.docs_dir)
        if not candidate.exists():
            return candidate
        stem = candidate.stem
        suffix = candidate.suffix
        for sequence in range(2, 10_000):
            candidate = (self.docs_dir / f"{stem} ({sequence}){suffix}").resolve()
            candidate.relative_to(self.docs_dir)
            if not candidate.exists():
                return candidate
        raise ValueError("Could not create a unique file name.")

    @staticmethod
    def _validate_declared_type(file_name: str, content_type: str | None) -> None:
        suffix = Path(file_name).suffix.lower()
        if suffix not in SUPPORTED_SUFFIXES:
            raise ValueError("Supported document types are PDF, DOCX, TXT, and MD.")
        normalized_type = (content_type or "application/octet-stream").split(";", 1)[0].lower()
        if normalized_type not in ALLOWED_MEDIA_TYPES[suffix]:
            raise ValueError("The file type does not match its extension.")

    @staticmethod
    def _validate_content(path: Path, suffix: str, header: bytes) -> None:
        if suffix == ".pdf" and not header.startswith(b"%PDF-"):
            raise ValueError("This file is not a valid PDF.")
        if suffix == ".docx":
            if not header.startswith(b"PK"):
                raise ValueError("This file is not a valid DOCX document.")
            try:
                with zipfile.ZipFile(path) as archive:
                    names = set(archive.namelist())
                if "[Content_Types].xml" not in names or "word/document.xml" not in names:
                    raise ValueError("This file is not a valid DOCX document.")
            except zipfile.BadZipFile as exc:
                raise ValueError("This file is not a valid DOCX document.") from exc
        if suffix in {".txt", ".md"}:
            if b"\x00" in header:
                raise ValueError("This text document contains unsupported binary content.")
            try:
                path.read_text(encoding="utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError("Text documents must use UTF-8 encoding.") from exc


def safe_file_name(file_name: str) -> str:
    normalized = unicodedata.normalize("NFKC", file_name).strip()
    if not normalized or normalized in {".", ".."}:
        raise ValueError("The document name is invalid.")
    if Path(normalized).name != normalized or "/" in normalized or "\\" in normalized:
        raise ValueError("The document name is invalid.")
    cleaned = SAFE_NAME_PATTERN.sub("_", normalized).strip(" .")
    if not cleaned:
        raise ValueError("The document name is invalid.")
    suffix = Path(cleaned).suffix.lower()
    stem = Path(cleaned).stem.strip(" .")
    if suffix not in SUPPORTED_SUFFIXES or not stem:
        raise ValueError("Supported document types are PDF, DOCX, TXT, and MD.")
    maximum_stem_length = 170 - len(suffix)
    return f"{stem[:maximum_stem_length]}{suffix}"
