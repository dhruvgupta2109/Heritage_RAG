import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from app.database import Database


def test_chat_rename_pin_delete_and_ordering(tmp_path: Path) -> None:
    database = Database(tmp_path / "heritage.db")
    database.initialize()
    now = datetime.now(UTC).isoformat()
    database.create_chat("chat-one", "First", now)
    database.create_chat("chat-two", "Second", now)

    assert database.rename_chat("chat-one", "Renamed")
    assert database.set_chat_pinned("chat-one", True)
    chats = database.list_chats()

    assert [chat["id"] for chat in chats] == ["chat-one", "chat-two"]
    assert chats[0]["title"] == "Renamed"
    assert chats[0]["pinned"] is True
    assert database.delete_chat("chat-one")
    assert database.get_chat("chat-one") is None
    assert not database.delete_chat("missing")


def test_initialize_adds_pinned_to_an_existing_database(tmp_path: Path) -> None:
    path = tmp_path / "legacy.db"
    connection = sqlite3.connect(path)
    connection.execute(
        """
        CREATE TABLE chats (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    connection.commit()
    connection.close()

    database = Database(path)
    database.initialize()
    with database.connect() as migrated:
        columns = {row["name"] for row in migrated.execute("PRAGMA table_info(chats)").fetchall()}

    assert "pinned" in columns
