"""Telegram notification service for worker."""

import httpx
from jarvis.config import get_settings
from jarvis.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class TelegramNotifier:
    """Sends notifications to users via Telegram."""

    def __init__(self):
        self.bot_token = settings.telegram_bot_token
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def send_message(
        self,
        chat_id: str,
        text: str,
        parse_mode: str = "HTML"
    ) -> bool:
        """Send a message to a Telegram chat."""
        try:
            client = await self._get_client()
            response = await client.post(
                f"{self.base_url}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": parse_mode
                }
            )
            response.raise_for_status()
            logger.debug(f"Sent notification to {chat_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to send notification to {chat_id}: {e}")
            return False

    async def notify_task_started(self, user_id: str, task_type: str, description: str = None):
        """Notify user that a task has started."""
        text = f"Sto lavorando su: <b>{task_type}</b>"
        if description:
            text += f"\n{description}"
        await self.send_message(user_id, text)

    async def notify_task_completed(
        self,
        user_id: str,
        task_type: str,
        result: str = None
    ):
        """Notify user that a task has completed."""
        text = f"Ho completato: <b>{task_type}</b>"
        if result:
            text += f"\n\n{result}"
        await self.send_message(user_id, text)

    async def notify_task_failed(
        self,
        user_id: str,
        task_type: str,
        error: str = None
    ):
        """Notify user that a task has failed."""
        text = f"Non sono riuscito a completare: <b>{task_type}</b>"
        if error:
            text += f"\nErrore: {error}"
        await self.send_message(user_id, text)

    async def notify_reminder(
        self,
        user_id: str,
        message: str
    ):
        """Send a reminder notification."""
        text = f"Promemoria: {message}"
        await self.send_message(user_id, text)

    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


# Singleton instance
notifier = TelegramNotifier()
