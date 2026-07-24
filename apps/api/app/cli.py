import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from .backup import create_backup, inspect_backup, restore_backup
from .config import PROJECT_ROOT
from .evaluation import evaluate_answer_cases, evaluate_retrieval, load_evaluation_cases
from .main import database, ingestion, retrieval, settings
from .performance import benchmark_synthetic_corpus


def main() -> None:
    parser = argparse.ArgumentParser(description="Heritage RAG utilities")
    parser.add_argument(
        "command",
        choices=[
            "index",
            "evaluate",
            "evaluate-answers",
            "benchmark",
            "backup",
            "inspect-backup",
            "restore",
        ],
    )
    parser.add_argument(
        "--mode",
        choices=["quick", "medium", "deep"],
        default="medium",
    )
    parser.add_argument("--documents", type=int, default=300)
    parser.add_argument("--queries", type=int, default=24)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--archive", type=Path)
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Explicitly replace existing documents and runtime data during restore.",
    )
    args = parser.parse_args()
    database.initialize()
    if args.command == "index":
        result = ingestion.index_all()
        print(result.model_dump_json(indent=2))
    if args.command == "evaluate":
        cases = load_evaluation_cases(PROJECT_ROOT / "evals" / "questions.json")
        report = evaluate_retrieval(retrieval, cases, args.mode)
        print(json.dumps(report, indent=2))
    if args.command == "evaluate-answers":
        cases = load_evaluation_cases(PROJECT_ROOT / "evals" / "answer_cases.json")
        print(json.dumps(evaluate_answer_cases(cases), indent=2))
    if args.command == "benchmark":
        print(
            json.dumps(
                benchmark_synthetic_corpus(
                    document_count=args.documents,
                    query_count=args.queries,
                ),
                indent=2,
            )
        )
    if args.command == "backup":
        output = args.output or (
            PROJECT_ROOT
            / "backups"
            / f"heritage-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}.zip"
        )
        print(
            json.dumps(
                create_backup(
                    docs_dir=settings.docs_dir,
                    sqlite_path=settings.sqlite_path,
                    chroma_path=settings.chroma_path,
                    output_path=output,
                ),
                indent=2,
            )
        )
    if args.command == "inspect-backup":
        if not args.archive:
            parser.error("inspect-backup requires --archive")
        print(json.dumps(inspect_backup(args.archive), indent=2))
    if args.command == "restore":
        if not args.archive:
            parser.error("restore requires --archive")
        print(
            json.dumps(
                restore_backup(
                    archive_path=args.archive,
                    docs_dir=settings.docs_dir,
                    sqlite_path=settings.sqlite_path,
                    chroma_path=settings.chroma_path,
                    replace=args.replace,
                ),
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
