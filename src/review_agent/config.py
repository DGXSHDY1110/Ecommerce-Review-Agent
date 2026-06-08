"""Application configuration loaded from environment variables."""

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Application settings loaded from .env file and environment variables."""

    # DeepSeek API
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    deepseek_base_url: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    deepseek_model: str = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")

    # LLM client tuning
    llm_timeout_seconds: int = int(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
    llm_max_retries: int = int(os.getenv("LLM_MAX_RETRIES", "1"))
    llm_mock_mode: bool = os.getenv("LLM_MOCK_MODE", "false").lower() in ("true", "1", "yes")

    # App server
    app_host: str = os.getenv("APP_HOST", "0.0.0.0")
    app_port: int = int(os.getenv("APP_PORT", "8000"))

    # Feishu webhook
    feishu_webhook_url: str = os.getenv("FEISHU_WEBHOOK_URL", "")

    # Guardrail thresholds
    confidence_threshold: float = float(os.getenv("CONFIDENCE_THRESHOLD", "0.6"))
    retry_max_attempts: int = int(os.getenv("RETRY_MAX_ATTEMPTS", "2"))
    low_rating_threshold: int = 2


def get_settings() -> Settings:
    """Return a Settings instance (new each call to pick up env changes)."""
    return Settings()


# Singleton for convenience
settings = Settings()
