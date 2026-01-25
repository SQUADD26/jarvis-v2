from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    # Gemini
    google_api_key: str = Field(..., alias="GOOGLE_API_KEY")

    # Google OAuth
    google_client_id: str = Field(..., alias="GOOGLE_CLIENT_ID")
    google_client_secret: str = Field(..., alias="GOOGLE_CLIENT_SECRET")
    google_refresh_token: str = Field(..., alias="GOOGLE_REFRESH_TOKEN")

    # OpenAI (for Whisper)
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")

    # Perplexity
    perplexity_api_key: str = Field(..., alias="PERPLEXITY_API_KEY")

    # Supabase
    supabase_url: str = Field(..., alias="SUPABASE_URL")
    supabase_key: str = Field(..., alias="SUPABASE_KEY")
    supabase_service_key: str = Field(..., alias="SUPABASE_SERVICE_KEY")
    supabase_postgres_url: str = Field(default="", alias="SUPABASE_POSTGRES_URL")  # For checkpointing

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    # Telegram
    telegram_bot_token: str = Field(..., alias="TELEGRAM_BOT_TOKEN")
    telegram_allowed_users: str = Field(default="", alias="TELEGRAM_ALLOWED_USERS")

    # App
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    environment: str = Field(default="development", alias="ENVIRONMENT")

    # Cache TTLs (seconds)
    cache_ttl_calendar: int = 300  # 5 minuti
    cache_ttl_email: int = 60      # 1 minuto
    cache_ttl_web: int = 3600      # 1 ora

    # LLM
    default_model: str = "gemini-2.0-flash"
    powerful_model: str = "gemini-2.5-pro-preview-05-06"

    # Worker
    worker_id: str = Field(default="worker-1", alias="WORKER_ID")
    worker_poll_interval_active: float = 0.5   # Polling ogni 500ms quando attivo
    worker_poll_interval_idle: float = 2.0     # Backoff a 2s quando idle
    worker_stale_timeout_minutes: int = 30     # Timeout per task bloccati

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    @property
    def telegram_allowed_users_list(self) -> list[int]:
        if isinstance(self.telegram_allowed_users, str) and self.telegram_allowed_users:
            return [int(x.strip()) for x in self.telegram_allowed_users.split(",") if x.strip()]
        return []


@lru_cache
def get_settings() -> Settings:
    return Settings()
