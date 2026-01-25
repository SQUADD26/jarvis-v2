"""Deepgram Aura integration for text-to-speech."""

import httpx
from jarvis.config import get_settings
from jarvis.utils.logging import get_logger
from jarvis.utils.llm_logger import LLMLogEntry, llm_logger

logger = get_logger(__name__)

# Deepgram TTS pricing: $0.015/1000 characters
DEEPGRAM_TTS_COST_PER_CHAR = 0.015 / 1000


class DeepgramTTSClient:
    """Client for Deepgram Aura text-to-speech."""

    def __init__(self):
        settings = get_settings()
        self.api_key = settings.deepgram_api_key
        self.model = settings.deepgram_tts_model
        self.base_url = "https://api.deepgram.com/v1/speak"
        self._current_user_id: str | None = None

    def set_user_context(self, user_id: str):
        """Set current user for logging context."""
        self._current_user_id = user_id

    async def synthesize(
        self,
        text: str,
        user_id: str = None,
        encoding: str = "linear16",
        sample_rate: int = 24000,
    ) -> bytes:
        """
        Synthesize text to speech using Deepgram Aura.

        Args:
            text: Text to synthesize
            user_id: User ID for logging
            encoding: Audio encoding (linear16 for WAV)
            sample_rate: Sample rate in Hz

        Returns:
            Raw audio bytes (PCM linear16)
        """
        effective_user_id = user_id or self._current_user_id

        # Prepare log entry
        log_entry = LLMLogEntry(
            provider="deepgram",
            model=self.model,
            user_prompt=f"[TTS] {text[:100]}..." if len(text) > 100 else f"[TTS] {text}",
            user_id=effective_user_id,
            metadata={
                "type": "tts",
                "text_length": len(text),
                "encoding": encoding,
                "sample_rate": sample_rate,
            }
        )
        log_entry.start_timer()

        try:
            # Build URL with parameters
            params = {
                "model": self.model,
                "encoding": encoding,
                "sample_rate": str(sample_rate),
            }

            url = f"{self.base_url}?" + "&".join(f"{k}={v}" for k, v in params.items())

            # Make request
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    url,
                    headers={
                        "Authorization": f"Token {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={"text": text},
                )
                response.raise_for_status()
                audio_data = response.content

            # Calculate cost
            estimated_cost = len(text) * DEEPGRAM_TTS_COST_PER_CHAR

            log_entry.stop_timer()
            log_entry.response = f"[AUDIO] {len(audio_data)} bytes"
            log_entry.finish_reason = "stop"
            log_entry.metadata["audio_bytes"] = len(audio_data)
            log_entry.metadata["estimated_cost"] = estimated_cost

            await llm_logger.log(log_entry)

            logger.info(f"Synthesized TTS: {len(text)} chars -> {len(audio_data)} bytes")
            return audio_data

        except Exception as e:
            log_entry.stop_timer()
            log_entry.is_error = True
            log_entry.error_message = str(e)
            await llm_logger.log(log_entry)

            logger.error(f"Deepgram TTS failed: {e}")
            raise


# Singleton
deepgram_tts = DeepgramTTSClient()
