import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    file_name TEXT NOT NULL,
    title TEXT NOT NULL,
    relative_path TEXT NOT NULL UNIQUE,
    content_hash TEXT NOT NULL,
    media_type TEXT NOT NULL,
    page_count INTEGER,
    status TEXT NOT NULL,
    error TEXT,
    indexed_at TEXT
);

CREATE TABLE IF NOT EXISTS ingestion_jobs (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    result_json TEXT,
    created_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS chats (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    pinned INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    chat_id TEXT,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    model TEXT,
    retrieval_mode TEXT,
    citations_json TEXT,
    confidence_json TEXT,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(chat_id) REFERENCES chats(id) ON DELETE CASCADE
);
"""


class Database:
    def __init__(self, path: Path):
        self.path = path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(SCHEMA)
            chat_columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(chats)").fetchall()
            }
            if "pinned" not in chat_columns:
                connection.execute("ALTER TABLE chats ADD COLUMN pinned INTEGER NOT NULL DEFAULT 0")

    def find_document_by_path(self, relative_path: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM documents WHERE relative_path = ?", (relative_path,)
            ).fetchone()
        return dict(row) if row else None

    def find_document_by_hash(self, content_hash: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM documents WHERE content_hash = ? AND status = 'ready'",
                (content_hash,),
            ).fetchone()
        return dict(row) if row else None

    def upsert_document(self, record: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO documents (
                    id, file_name, title, relative_path, content_hash, media_type,
                    page_count, status, error, indexed_at
                ) VALUES (
                    :id, :file_name, :title, :relative_path, :content_hash, :media_type,
                    :page_count, :status, :error, :indexed_at
                )
                ON CONFLICT(relative_path) DO UPDATE SET
                    id = excluded.id,
                    file_name = excluded.file_name,
                    title = excluded.title,
                    content_hash = excluded.content_hash,
                    media_type = excluded.media_type,
                    page_count = excluded.page_count,
                    status = excluded.status,
                    error = excluded.error,
                    indexed_at = excluded.indexed_at
                """,
                record,
            )

    def list_documents(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, file_name, title, relative_path, media_type,
                       page_count, status, indexed_at
                FROM documents
                ORDER BY file_name COLLATE NOCASE
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def create_chat(
        self,
        chat_id: str,
        title: str,
        created_at: str,
    ) -> dict[str, Any]:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO chats (id, title, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (chat_id, title, created_at, created_at),
            )
        return {
            "id": chat_id,
            "title": title,
            "pinned": False,
            "created_at": created_at,
            "updated_at": created_at,
            "message_count": 0,
        }

    def get_chat(self, chat_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            chat = connection.execute(
                """
                SELECT chats.id, chats.title, chats.pinned,
                       chats.created_at, chats.updated_at,
                       COUNT(messages.id) AS message_count
                FROM chats
                LEFT JOIN messages ON messages.chat_id = chats.id
                WHERE chats.id = ?
                GROUP BY chats.id
                """,
                (chat_id,),
            ).fetchone()
            if not chat:
                return None
            messages = connection.execute(
                """
                SELECT id, role, content, model, retrieval_mode, citations_json,
                       confidence_json, status, created_at
                FROM messages
                WHERE chat_id = ?
                ORDER BY created_at, rowid
                """,
                (chat_id,),
            ).fetchall()

        result = dict(chat)
        result["pinned"] = bool(result["pinned"])
        result["messages"] = [_message_record(row) for row in messages]
        return result

    def list_chats(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT chats.id, chats.title, chats.pinned,
                       chats.created_at, chats.updated_at,
                       COUNT(messages.id) AS message_count
                FROM chats
                LEFT JOIN messages ON messages.chat_id = chats.id
                GROUP BY chats.id
                ORDER BY chats.pinned DESC, chats.updated_at DESC, chats.created_at DESC
                """
            ).fetchall()
        return [{**dict(row), "pinned": bool(row["pinned"])} for row in rows]

    def rename_chat(self, chat_id: str, title: str) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE chats SET title = ? WHERE id = ?",
                (title, chat_id),
            )
        return cursor.rowcount > 0

    def set_chat_pinned(self, chat_id: str, pinned: bool) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE chats SET pinned = ? WHERE id = ?",
                (int(pinned), chat_id),
            )
        return cursor.rowcount > 0

    def delete_chat(self, chat_id: str) -> bool:
        with self.connect() as connection:
            cursor = connection.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
        return cursor.rowcount > 0

    def save_user_message(
        self,
        message_id: str,
        chat_id: str,
        content: str,
        model: str,
        retrieval_mode: str,
        created_at: str,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO messages (
                    id, chat_id, role, content, model, retrieval_mode,
                    citations_json, confidence_json, status, created_at
                ) VALUES (?, ?, 'user', ?, ?, ?, '[]', NULL, 'completed', ?)
                """,
                (
                    message_id,
                    chat_id,
                    content,
                    model,
                    retrieval_mode,
                    created_at,
                ),
            )
            connection.execute(
                "UPDATE chats SET updated_at = ? WHERE id = ?",
                (created_at, chat_id),
            )

    def save_message_snapshot(
        self,
        message_id: str,
        chat_id: str,
        content: str,
        model: str,
        retrieval_mode: str,
        citations: list[dict[str, Any]],
        confidence: dict[str, Any],
        status: str,
        created_at: str,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO messages (
                    id, chat_id, role, content, model, retrieval_mode,
                    citations_json, confidence_json, status, created_at
                ) VALUES (?, ?, 'assistant', ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    chat_id,
                    content,
                    model,
                    retrieval_mode,
                    json.dumps(citations),
                    json.dumps(confidence),
                    status,
                    created_at,
                ),
            )
            connection.execute(
                "UPDATE chats SET updated_at = ? WHERE id = ?",
                (created_at, chat_id),
            )


def _message_record(row: sqlite3.Row) -> dict[str, Any]:
    record = dict(row)
    citations = json.loads(record.pop("citations_json") or "[]")
    confidence_json = record.pop("confidence_json")
    record["citations"] = citations
    record["confidence"] = json.loads(confidence_json) if confidence_json else None
    record["answered_from"] = _answered_from(citations)
    return record


def _answered_from(citations: list[dict[str, Any]]) -> list[dict[str, str]]:
    grouped: dict[tuple[str, str], list[str]] = {}
    for source in citations:
        page_start = source.get("page_start")
        page_end = source.get("page_end")
        if page_start is None:
            page_label = "Page unavailable"
        elif page_end and page_end != page_start:
            page_label = f"Pages {page_start}–{page_end}"
        else:
            page_label = f"Page {page_start}"
        key = (source["document_id"], source["document"])
        if page_label not in grouped.setdefault(key, []):
            grouped[key].append(page_label)
    return [
        {
            "document_id": document_id,
            "document": document,
            "pages": ", ".join(pages),
        }
        for (document_id, document), pages in grouped.items()
    ]
