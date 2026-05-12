from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_UPLOAD_PASSWORD_HASH = "$2b$12$hZAfbzIRTRpil8xgYFEVheOqFk/ba0R7RZ4zlb7iiIdOm6mid1tv6"

MODEL_CATALOG = (
    {
        "id": "openai/gpt-oss-120b",
        "provider": "groq",
        "provider_label": "Groq",
        "label": "GPT-OSS 120B",
        "description": "Best answer quality",
    },
    {
        "id": "openai/gpt-oss-20b",
        "provider": "groq",
        "provider_label": "Groq",
        "label": "GPT-OSS 20B",
        "description": "Fastest responses",
    },
    {
        "id": "gpt-5.6-terra",
        "provider": "openai",
        "provider_label": "OpenAI",
        "label": "GPT-5.6 Terra",
        "description": "Balanced intelligence and cost",
    },
    {
        "id": "gpt-5.6-luna",
        "provider": "openai",
        "provider_label": "OpenAI",
        "label": "GPT-5.6 Luna",
        "description": "Efficient, high-volume answers",
    },
    {
        "id": "gemini-3.6-flash",
        "provider": "gemini",
        "provider_label": "Gemini",
        "label": "Gemini 3.6 Flash",
        "description": "Strong speed and reasoning",
    },
    {
        "id": "gemini-3.5-flash-lite",
        "provider": "gemini",
        "provider_label": "Gemini",
        "label": "Gemini 3.5 Flash-Lite",
        "description": "Lowest latency and cost",
    },
)
MODEL_IDS = frozenset(model["id"] for model in MODEL_CATALOG)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    groq_api_key: SecretStr | None = None
    groq_model: str = "openai/gpt-oss-120b"
    openai_api_key: SecretStr | None = None
    gemini_api_key: SecretStr | None = None
    upload_password_hash: SecretStr = SecretStr(DEFAULT_UPLOAD_PASSWORD_HASH)
    upload_session_ttl_seconds: int = 600
    upload_max_attempts: int = 5
    upload_attempt_window_seconds: int = 600
    app_session_ttl_seconds: int = 12 * 60 * 60
    upload_max_file_bytes: int = 25 * 1024 * 1024
    docs_dir: Path = PROJECT_ROOT / "DOCS"
    data_dir: Path = PROJECT_ROOT / "data"
    frontend_origin: str = "http://127.0.0.1:3000"
    collection_name: str = "heritage_documents_v1"
    retrieval_top_k: int = 7
    retrieval_candidate_k: int = 14
    minimum_relevance: float = 0.28
    log_level: str = "INFO"

    @property
    def sqlite_path(self) -> Path:
        return self.data_dir / "heritage.db"

    @property
    def chroma_path(self) -> Path:
        return self.data_dir / "chroma"

    @property
    def log_path(self) -> Path:
        return self.data_dir / "logs" / "heritage.jsonl"

    def ensure_directories(self) -> None:
        self.docs_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.chroma_path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
