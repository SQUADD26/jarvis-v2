"""Deepgram Nova-3 integration for speech-to-text."""

import httpx
from pathlib import Path
from jarvis.config import get_settings
from jarvis.utils.logging import get_logger
from jarvis.utils.llm_logger import LLMLogEntry, llm_logger

logger = get_logger(__name__)

# Deepgram pricing: $0.0043/min for Nova-3
DEEPGRAM_COST_PER_MINUTE = 0.0043


class DeepgramClient:
    """Client for Deepgram Nova-3 speech-to-text."""

    def __init__(self):
        settings = get_settings()
        self.api_key = settings.deepgram_api_key
        self.model = "nova-3"
        self.base_url = "https://api.deepgram.com/v1/listen"
        self._current_user_id: str | None = None

    def set_user_context(self, user_id: str):
        """Set current user for logging context."""
        self._current_user_id = user_id

    def _get_content_type(self, ext: str) -> str:
        """Get content type from file extension."""
        content_types = {
            ".ogg": "audio/ogg",
            ".mp3": "audio/mpeg",
            ".m4a": "audio/mp4",
            ".wav": "audio/wav",
            ".webm": "audio/webm",
            ".flac": "audio/flac",
        }
        return content_types.get(ext.lower(), "audio/ogg")

    async def _transcribe_raw(
        self,
        audio_data: bytes,
        content_type: str,
        language: str,
        source_name: str,
        user_id: str | None
    ) -> str:
        """
        Internal method to transcribe raw audio bytes.

        Args:
            audio_data: Raw audio bytes
            content_type: MIME type of the audio
            language: Language code
            source_name: Name for logging (filename or description)
            user_id: User ID for logging

        Returns:
            Transcribed text
        """
        effective_user_id = user_id or self._current_user_id

        # Prepare log entry
        log_entry = LLMLogEntry(
            provider="deepgram",
            model=self.model,
            user_prompt=f"[AUDIO] {source_name}",
            user_id=effective_user_id,
            metadata={
                "type": "transcription",
                "language": language,
                "file_size": len(audio_data)
            }
        )
        log_entry.start_timer()

        try:
            # Build URL with parameters
            params = {
                "model": self.model,
                "language": language,
                "smart_format": "true",
                "punctuate": "true",
            }

            url = f"{self.base_url}?" + "&".join(f"{k}={v}" for k, v in params.items())

            # Make request directly with bytes (no temp file)
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    url,
                    headers={
                        "Authorization": f"Token {self.api_key}",
                        "Content-Type": content_type,
                    },
                    content=audio_data,
                )
                response.raise_for_status()
                result = response.json()

            # Extract transcript
            transcript = ""
            if result.get("results", {}).get("channels"):
                alternatives = result["results"]["channels"][0].get("alternatives", [])
                if alternatives:
                    transcript = alternatives[0].get("transcript", "")

            # Get duration for cost calculation
            duration_seconds = result.get("metadata", {}).get("duration", 0)
            duration_minutes = duration_seconds / 60 if duration_seconds else 0.1
            estimated_cost = duration_minutes * DEEPGRAM_COST_PER_MINUTE

            log_entry.stop_timer()
            log_entry.response = transcript
            log_entry.finish_reason = "stop"
            log_entry.metadata["duration_seconds"] = duration_seconds
            log_entry.metadata["estimated_minutes"] = duration_minutes
            log_entry.metadata["estimated_cost"] = estimated_cost

            await llm_logger.log(log_entry)

            logger.info(f"Transcribed audio: {len(transcript)} chars, {duration_seconds:.1f}s")
            return transcript

        except Exception as e:
            log_entry.stop_timer()
            log_entry.is_error = True
            log_entry.error_message = str(e)
            await llm_logger.log(log_entry)

            logger.error(f"Deepgram transcription failed: {e}")
            raise

    async def transcribe(
        self,
        audio_path: str | Path,
        language: str = "it",
        user_id: str = None
    ) -> str:
        """
        Transcribe audio file to text using Deepgram Nova-3.

        Args:
            audio_path: Path to audio file
            language: Language code (default: Italian)
            user_id: User ID for logging

        Returns:
            Transcribed text
        """
        audio_path = Path(audio_path)

        # Read audio file
        with open(audio_path, "rb") as f:
            audio_data = f.read()

        # Get content type from extension
        content_type = self._get_content_type(audio_path.suffix)

        return await self._transcribe_raw(
            audio_data=audio_data,
            content_type=content_type,
            language=language,
            source_name=audio_path.name,
            user_id=user_id
        )

    async def transcribe_bytes(
        self,
        audio_data: bytes,
        filename: str = "audio.ogg",
        language: str = "it",
        user_id: str = None
    ) -> str:
        """
        Transcribe audio bytes to text directly (no temp file).

        Args:
            audio_data: Raw audio bytes
            filename: Filename with extension for format detection
            language: Language code
            user_id: User ID for logging

        Returns:
            Transcribed text
        """
        # Get content type from filename extension
        ext = Path(filename).suffix or ".ogg"
        content_type = self._get_content_type(ext)

        return await self._transcribe_raw(
            audio_data=audio_data,
            content_type=content_type,
            language=language,
            source_name=filename,
            user_id=user_id
        )

    async def transcribe_pcm(
        self,
        audio_data: bytes,
        sample_rate: int = 16000,
        language: str = "it",
        user_id: str = None
    ) -> str:
        """
        Transcribe raw PCM audio (linear16) directly.

        Args:
            audio_data: Raw PCM bytes (16-bit signed, mono)
            sample_rate: Sample rate in Hz
            language: Language code
            user_id: User ID for logging

        Returns:
            Transcribed text
        """
        effective_user_id = user_id or self._current_user_id

        log_entry = LLMLogEntry(
            provider="deepgram",
            model=self.model,
            user_prompt=f"[AUDIO PCM] {len(audio_data)} bytes",
            user_id=effective_user_id,
            metadata={
                "type": "transcription",
                "language": language,
                "file_size": len(audio_data),
                "encoding": "linear16",
                "sample_rate": sample_rate,
            }
        )
        log_entry.start_timer()

        try:
            # Build URL with PCM-specific parameters
            params = {
                "model": self.model,
                "language": language,
                "encoding": "linear16",
                "sample_rate": str(sample_rate),
                "channels": "1",
                "smart_format": "true",
                "punctuate": "true",
            }

            url = f"{self.base_url}?" + "&".join(f"{k}={v}" for k, v in params.items())

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    url,
                    headers={
                        "Authorization": f"Token {self.api_key}",
                        "Content-Type": "audio/raw",
                    },
                    content=audio_data,
                )
                response.raise_for_status()
                result = response.json()

            # Extract transcript
            transcript = ""
            if result.get("results", {}).get("channels"):
                alternatives = result["results"]["channels"][0].get("alternatives", [])
                if alternatives:
                    transcript = alternatives[0].get("transcript", "")

            duration_seconds = result.get("metadata", {}).get("duration", 0)
            duration_minutes = duration_seconds / 60 if duration_seconds else 0.1
            estimated_cost = duration_minutes * DEEPGRAM_COST_PER_MINUTE

            log_entry.stop_timer()
            log_entry.response = transcript
            log_entry.finish_reason = "stop"
            log_entry.metadata["duration_seconds"] = duration_seconds
            log_entry.metadata["estimated_cost"] = estimated_cost

            await llm_logger.log(log_entry)

            logger.info(f"Transcribed PCM audio: {len(transcript)} chars, {duration_seconds:.1f}s")
            return transcript

        except Exception as e:
            log_entry.stop_timer()
            log_entry.is_error = True
            log_entry.error_message = str(e)
            await llm_logger.log(log_entry)

            logger.error(f"Deepgram PCM transcription failed: {e}")
            raise


# Singleton
deepgram = DeepgramClient()
