"""OpenAI Whisper integration for speech-to-text."""

import time
from pathlib import Path
from openai import AsyncOpenAI
from jarvis.config import get_settings
from jarvis.utils.logging import get_logger
from jarvis.utils.llm_logger import LLMLogEntry, llm_logger

logger = get_logger(__name__)


class WhisperClient:
    """Client for OpenAI Whisper speech-to-text."""

    def __init__(self):
        settings = get_settings()
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = "whisper-1"
        self._current_user_id: str | None = None

    def set_user_context(self, user_id: str):
        """Set current user for logging context."""
        self._current_user_id = user_id

    async def transcribe(
        self,
        audio_path: str | Path,
        language: str = "it",
        user_id: str = None
    ) -> str:
        """
        Transcribe audio file to text.

        Args:
            audio_path: Path to audio file (mp3, mp4, mpeg, mpga, m4a, wav, webm, ogg)
            language: Language code (default: Italian)
            user_id: User ID for logging

        Returns:
            Transcribed text
        """
        effective_user_id = user_id or self._current_user_id
        audio_path = Path(audio_path)

        # Prepare log entry
        log_entry = LLMLogEntry(
            provider="openai",
            model=self.model,
            user_prompt=f"[AUDIO] {audio_path.name}",
            user_id=effective_user_id,
            metadata={
                "type": "transcription",
                "language": language,
                "file_size": audio_path.stat().st_size if audio_path.exists() else 0
            }
        )
        log_entry.start_timer()

        try:
            with open(audio_path, "rb") as audio_file:
                response = await self.client.audio.transcriptions.create(
                    model=self.model,
                    file=audio_file,
                    language=language,
                    response_format="text"
                )

            log_entry.stop_timer()
            log_entry.response = response
            log_entry.finish_reason = "stop"

            # Whisper pricing: $0.006 per minute
            # Estimate duration from file size (rough: 1MB ~= 1 minute for voice)
            file_size_mb = audio_path.stat().st_size / (1024 * 1024)
            estimated_minutes = max(file_size_mb, 0.1)  # Min 0.1 minutes
            estimated_cost = estimated_minutes * 0.006

            log_entry.metadata["estimated_minutes"] = estimated_minutes
            log_entry.metadata["estimated_cost"] = estimated_cost

            await llm_logger.log(log_entry)

            logger.info(f"Transcribed audio: {len(response)} chars, ~{estimated_minutes:.1f} min")
            return response

        except Exception as e:
            log_entry.stop_timer()
            log_entry.is_error = True
            log_entry.error_message = str(e)
            await llm_logger.log(log_entry)

            logger.error(f"Whisper transcription failed: {e}")
            raise

    async def transcribe_bytes(
        self,
        audio_data: bytes,
        filename: str = "audio.ogg",
        language: str = "it",
        user_id: str = None
    ) -> str:
        """
        Transcribe audio bytes to text.

        Args:
            audio_data: Raw audio bytes
            filename: Filename with extension for format detection
            language: Language code
            user_id: User ID for logging

        Returns:
            Transcribed text
        """
        import tempfile
        import os

        # Get extension from filename
        ext = Path(filename).suffix or ".ogg"

        # Write to temp file
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(audio_data)
            tmp_path = tmp.name

        try:
            return await self.transcribe(tmp_path, language, user_id)
        finally:
            # Clean up temp file
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


# Singleton
whisper = WhisperClient()
