from supabase import create_client, Client
from typing import Optional
from jarvis.config import get_settings
from jarvis.utils.logging import get_logger

logger = get_logger(__name__)


class SupabaseClient:
    _instance: Optional["SupabaseClient"] = None
    _client: Optional[Client] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def connect(self) -> Client:
        if self._client is None:
            settings = get_settings()
            self._client = create_client(
                settings.supabase_url,
                settings.supabase_service_key
            )
            logger.info("Supabase connected")
        return self._client

    @property
    def client(self) -> Client:
        return self.connect()


# Singleton
supabase_client = SupabaseClient()


def get_db() -> Client:
    return supabase_client.client


def get_supabase_client() -> Client:
    """Alias for get_db(), used by API auth middleware."""
    return supabase_client.client


async def run_db(fn):
    """Run a synchronous Supabase call in a thread to avoid blocking the event loop."""
    import asyncio
    return await asyncio.to_thread(fn)
