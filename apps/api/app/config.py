from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]

GROQ_MODELS = (
    {
        "id": "openai/gpt-oss-120b",
        "label": "GPT-OSS 120B",
        "description": "Best answer quality",
    },
    {
        "id": "openai/gpt-oss-20b",
        "label": "GPT-OSS 20B",
        "description": "Fastest responses",
    },
)
GROQ_MODEL_IDS = frozenset(model["id"] for model in GROQ_MODELS)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    groq_api_key: SecretStr | None = None
    groq_model: str = "openai/gpt-oss-120b"
    docs_dir: Path = PROJECT_ROOT / "DOCS"
    data_dir: Path = PROJECT_ROOT / "data"
    frontend_origin: str = "http://127.0.0.1:3000"
    collection_name: str = "heritage_documents_v1"
    retrieval_top_k: int = 7
    retrieval_candidate_k: int = 14
    minimum_relevance: float = 0.28

    @property
    def sqlite_path(self) -> Path:
        return self.data_dir / "heritage.db"

    @property
    def chroma_path(self) -> Path:
        return self.data_dir / "chroma"

    def ensure_directories(self) -> None:
        self.docs_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.chroma_path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
