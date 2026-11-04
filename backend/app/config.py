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

    # NLP pipeline. "ml" = trained intent classifier, "rules" = regex baseline.
    nlu_mode: str = "ml"
    intent_features: str = "embedding"  # tfidf | embedding | combined
    # "hybrid" = embeddings fused with BM25 via RRF; "bm25" = keyword-only baseline.
    # With bm25_weight = 0 the ranking is pure embeddings, which won on the dev
    # set; BM25 is still used automatically if the embedding model can't load.
    retrieval_mode: str = "hybrid"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    model_cache_dir: Path = BASE_DIR / ".cache" / "models"
    nlu_train_file: Path = BASE_DIR / "data" / "nlu" / "train.jsonl"
    needs_action_file: Path = BASE_DIR / "data" / "nlu" / "needs_action.jsonl"
    # Tuned on eval/dev.jsonl with `python -m eval.tune` (never on the test set).
    action_threshold: float = 0.5
    bm25_weight: float = 0.0  # weight of the BM25 ranking inside the hybrid fusion
    confidence_intent_weight: float = 0.35  # offline provider: intent prob vs. retrieval relevance

    # Below this confidence the bot hands the conversation to a human.
    escalation_threshold: float = 0.35
    retrieval_top_k: int = 4
    seed_demo_data: bool = True

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"


@lru_cache
def get_settings() -> Settings:
    return Settings()
