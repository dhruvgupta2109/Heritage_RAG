import argparse

from .main import database, ingestion


def main() -> None:
    parser = argparse.ArgumentParser(description="Heritage RAG utilities")
    parser.add_argument("command", choices=["index"])
    args = parser.parse_args()
    database.initialize()
    if args.command == "index":
        result = ingestion.index_all()
        print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
