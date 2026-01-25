"""Wake word detection using Porcupine."""

import struct
import pvporcupine
from jarvis.config import get_settings
from jarvis.utils.logging import get_logger

logger = get_logger(__name__)


class WakeWordDetector:
    """Detects 'Jarvis' wake word using Porcupine."""

    def __init__(self):
        self._porcupine: pvporcupine.Porcupine | None = None
        self._initialized = False

    def initialize(self):
        """Initialize Porcupine with 'Jarvis' keyword."""
        if self._initialized:
            return

        settings = get_settings()
        if not settings.porcupine_access_key:
            raise ValueError(
                "PORCUPINE_ACCESS_KEY not set. "
                "Get free key at https://console.picovoice.ai"
            )

        self._porcupine = pvporcupine.create(
            access_key=settings.porcupine_access_key,
            keywords=["jarvis"],
            sensitivities=[settings.voice_sensitivity],
        )
        self._initialized = True
        logger.info("Wake word detector initialized (Porcupine - 'Jarvis')")

    def process(self, audio_chunk: bytes) -> bool:
        """
        Process audio chunk and detect wake word.

        Args:
            audio_chunk: Raw PCM audio bytes (512 frames, 16kHz, mono, int16)

        Returns:
            True if wake word detected
        """
        if not self._porcupine:
            raise RuntimeError("Wake word detector not initialized")

        # Convert bytes to int16 array
        pcm = struct.unpack_from("h" * self._porcupine.frame_length, audio_chunk)

        # Process through Porcupine
        keyword_index = self._porcupine.process(pcm)

        if keyword_index >= 0:
            logger.info("Wake word 'Jarvis' detected!")
            return True
        return False

    def cleanup(self):
        """Release Porcupine resources."""
        if self._porcupine:
            self._porcupine.delete()
            self._porcupine = None
            self._initialized = False
            logger.info("Wake word detector cleaned up")

    @property
    def frame_length(self) -> int:
        """Return required frame length for Porcupine."""
        return self._porcupine.frame_length if self._porcupine else 512

    @property
    def is_available(self) -> bool:
        """Check if Porcupine can be initialized."""
        settings = get_settings()
        return bool(settings.porcupine_access_key)


# Singleton
wake_word_detector = WakeWordDetector()
