import hashlib
import json
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

BACKUP_VERSION = 1


def create_backup(
    *,
    docs_dir: Path,
    sqlite_path: Path,
    chroma_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        raise FileExistsError(f"Backup already exists: {output_path}")

    with tempfile.TemporaryDirectory(prefix="heritage-backup-") as directory:
        staging = Path(directory)
        staged_database = staging / "heritage.db"
        if sqlite_path.exists():
            _backup_sqlite(sqlite_path, staged_database)

        entries: list[dict[str, Any]] = []
        with zipfile.ZipFile(output_path, "x", compression=zipfile.ZIP_DEFLATED) as archive:
            for root, prefix in (
                (docs_dir, "documents"),
                (chroma_path, "chroma"),
            ):
                if not root.exists():
                    continue
                for path in sorted(item for item in root.rglob("*") if item.is_file()):
                    archive_name = f"{prefix}/{path.relative_to(root).as_posix()}"
                    entries.append(_write_entry(archive, path, archive_name))
            if staged_database.exists():
                entries.append(_write_entry(archive, staged_database, "heritage.db"))

            manifest = {
                "version": BACKUP_VERSION,
                "created_at": datetime.now(UTC).isoformat(),
                "includes": {
                    "documents": any(item["path"].startswith("documents/") for item in entries),
                    "chroma": any(item["path"].startswith("chroma/") for item in entries),
                    "sqlite": any(item["path"] == "heritage.db" for item in entries),
                },
                "files": entries,
            }
            archive.writestr(
                "manifest.json",
                json.dumps(manifest, indent=2, ensure_ascii=False),
            )
    return {
        "path": str(output_path),
        "file_count": len(entries),
        "size_bytes": output_path.stat().st_size,
        "manifest": manifest,
    }


def inspect_backup(archive_path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        _validate_names(names)
        if "manifest.json" not in names:
            raise ValueError("Backup manifest is missing.")
        manifest = json.loads(archive.read("manifest.json"))
        if manifest.get("version") != BACKUP_VERSION:
            raise ValueError("Unsupported backup version.")
        expected = {entry["path"]: entry for entry in manifest.get("files", [])}
        for name, entry in expected.items():
            if name not in names:
                raise ValueError(f"Backup entry is missing: {name}")
            payload = archive.read(name)
            if hashlib.sha256(payload).hexdigest() != entry["sha256"]:
                raise ValueError(f"Backup checksum failed: {name}")
        return manifest


def restore_backup(
    *,
    archive_path: Path,
    docs_dir: Path,
    sqlite_path: Path,
    chroma_path: Path,
    replace: bool = False,
) -> dict[str, Any]:
    manifest = inspect_backup(archive_path)
    occupied = [
        path
        for path in (docs_dir, sqlite_path, chroma_path)
        if path.exists() and (path.is_file() or any(path.iterdir()))
    ]
    if occupied and not replace:
        raise FileExistsError(
            "Restore targets are not empty. Re-run with explicit replacement enabled."
        )

    with tempfile.TemporaryDirectory(prefix="heritage-restore-") as directory:
        staging = Path(directory)
        with zipfile.ZipFile(archive_path) as archive:
            for entry in manifest["files"]:
                destination = staging / entry["path"]
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(archive.read(entry["path"]))

        if replace:
            for path in (docs_dir, chroma_path):
                if path.exists():
                    shutil.rmtree(path)
            if sqlite_path.exists():
                sqlite_path.unlink()

        _copy_tree(staging / "documents", docs_dir)
        _copy_tree(staging / "chroma", chroma_path)
        if (staging / "heritage.db").exists():
            sqlite_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(staging / "heritage.db", sqlite_path)

    return {
        "restored": True,
        "file_count": len(manifest["files"]),
        "created_at": manifest["created_at"],
    }


def _backup_sqlite(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source) as source_connection:
        with sqlite3.connect(destination) as destination_connection:
            source_connection.backup(destination_connection)


def _write_entry(
    archive: zipfile.ZipFile,
    path: Path,
    archive_name: str,
) -> dict[str, Any]:
    payload = path.read_bytes()
    archive.writestr(archive_name, payload)
    return {
        "path": archive_name,
        "size_bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def _validate_names(names: list[str]) -> None:
    for name in names:
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError(f"Unsafe backup entry: {name}")


def _copy_tree(source: Path, destination: Path) -> None:
    if not source.exists():
        return
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination, dirs_exist_ok=True)
