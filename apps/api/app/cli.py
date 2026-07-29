import argparse
import json

from .config import PROJECT_ROOT
from .evaluation import evaluate_retrieval, load_evaluation_cases
from .main import database, ingestion, retrieval


def main() -> None:
    parser = argparse.ArgumentParser(description="Heritage RAG utilities")
    parser.add_argument("command", choices=["index", "evaluate"])
    parser.add_argument(
        "--mode",
        choices=["quick", "medium", "deep"],
        default="medium",
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


if __name__ == "__main__":
    main()
