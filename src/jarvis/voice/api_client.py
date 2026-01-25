"""HTTP client for communicating with Jarvis API on VPS."""

import httpx
from jarvis.config import get_settings
from jarvis.utils.logging import get_logger

logger = get_logger(__name__)


class JarvisAPIClient:
    """Client for Jarvis API on VPS."""

    def __init__(self):
        self._settings = get_settings()

    async def chat(
        self,
        message: str,
        user_id: str = "voice_local",
        history: list[dict] | None = None
    ) -> str:
        """
        Send message to Jarvis API and get response.

        Args:
            message: User message text
            user_id: User identifier
            history: Conversation history

        Returns:
            Response text from Jarvis
        """
        if not self._settings.jarvis_api_url:
            raise ValueError("JARVIS_API_URL not configured")

        if not self._settings.jarvis_api_key:
            raise ValueError("JARVIS_API_KEY not configured")

        url = f"{self._settings.jarvis_api_url.rstrip('/')}/api/chat"

        payload = {
            "message": message,
            "user_id": user_id,
            "history": history or []
        }

        headers = {
            "X-API-Key": self._settings.jarvis_api_key,
            "Content-Type": "application/json"
        }

        logger.debug(f"Calling Jarvis API: {url}")

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        logger.debug(f"API response: {len(data.get('response', ''))} chars")
        return data["response"]

    async def health_check(self) -> bool:
        """Check if API is reachable."""
        if not self._settings.jarvis_api_url:
            return False

        url = f"{self._settings.jarvis_api_url.rstrip('/')}/health"

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url)
                return response.status_code == 200
        except Exception as e:
            logger.warning(f"API health check failed: {e}")
            return False


# Singleton
api_client = JarvisAPIClient()
