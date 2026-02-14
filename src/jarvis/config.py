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

    # OpenAI (for Whisper - legacy)
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")

    # Deepgram (for Nova-3 STT)
    deepgram_api_key: str = Field(default="", alias="DEEPGRAM_API_KEY")

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
    default_model: str = "gemini-2.5-flash"  # Upgraded from 2.0
    powerful_model: str = "gemini-2.5-pro-preview-05-06"
    embedding_model: str = "models/text-embedding-004"

    # Notion
    notion_api_key: str = Field(default="", alias="NOTION_API_KEY")
    notion_user_name: str = Field(default="", alias="NOTION_USER_NAME")
    notion_task_databases: str = Field(default="", alias="NOTION_TASK_DATABASES")  # comma-separated DB IDs

    @property
    def notion_task_database_ids(self) -> list[str]:
        if self.notion_task_databases:
            return [x.strip() for x in self.notion_task_databases.split(",") if x.strip()]
        return []

    # Apify (Google Search Scraper)
    apify_api_key: str = Field(default="", alias="APIFY_API_KEY")

    # Jarvis API (for voice client communication)
    jarvis_api_key: str = Field(default="", alias="JARVIS_API_KEY")
    jarvis_api_url: str = Field(default="", alias="JARVIS_API_URL")  # e.g. http://vps:8000

    # Voice (local client)
    porcupine_access_key: str = Field(default="", alias="PORCUPINE_ACCESS_KEY")
    voice_mode: str = Field(default="ptt", alias="VOICE_MODE")  # "ptt" or "wake_word"
    voice_ptt_key: str = Field(default="<cmd>+j", alias="VOICE_PTT_KEY")
    voice_sensitivity: float = Field(default=0.7, alias="VOICE_SENSITIVITY")  # Higher = more sensitive
    voice_silence_timeout: float = Field(default=1.0, alias="VOICE_SILENCE_TIMEOUT")  # Faster response
    voice_max_recording: float = Field(default=30.0, alias="VOICE_MAX_RECORDING")
    deepgram_tts_model: str = Field(default="aura-2-thalia-en", alias="DEEPGRAM_TTS_MODEL")  # English voice

    # Crawl4AI
    crawl4ai_url: str = Field(default="http://srv938822.hstgr.cloud:11235", alias="CRAWL4AI_URL")

    # Worker
    worker_id: str = Field(default="worker-1", alias="WORKER_ID")
    worker_poll_interval_active: float = 0.5   # Polling ogni 500ms quando attivo
    worker_poll_interval_idle: float = 2.0     # Backoff a 2s quando idle
    worker_stale_timeout_minutes: int = 30     # Timeout per task bloccati

    # Briefing
    briefing_morning_hour: int = 7
    briefing_morning_minute: int = 30
    briefing_evening_hour: int = 20
    briefing_evening_minute: int = 0
    briefing_user_id: str = Field(default="", alias="BRIEFING_USER_ID")
    briefing_timezone: str = Field(default="Europe/Rome", alias="BRIEFING_TIMEZONE")

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
