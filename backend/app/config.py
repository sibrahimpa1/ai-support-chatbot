"""Runtime configuration, loaded from environment variables or a `.env` file."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BASE_DIR.parent / ".env", BASE_DIR / ".env"),
        extra="ignore",
    )

    # "auto" uses Claude when ANTHROPIC_API_KEY is set, otherwise the offline mock provider.
    llm_provider: str = "auto"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-opus-5-5"
    anthropic_effort: str = "low"

    company_name: str = "Fernway Outdoor"
    knowledge_base_dir: Path = BASE_DIR / "data" / "knowledge_base"
    orders_file: Path = BASE_DIR / "data" / "orders.json"
    database_path: Path = BASE_DIR / "data" / "support.db"

    # Below this confidence the bot hands the conversation to a human.
    escalation_threshold: float = 0.45
    retrieval_top_k: int = 4
    seed_demo_data: bool = True

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"


@lru_cache
def get_settings() -> Settings:
    return Settings()
