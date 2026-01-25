"""Wake word detection using OpenWakeWord (free, no API key)."""

import numpy as np
from openwakeword.model import Model
from jarvis.config import get_settings
from jarvis.utils.logging import get_logger

logger = get_logger(__name__)

# OpenWakeWord uses 16kHz, 16-bit audio
# Frame size: 1280 samples (80ms) for best performance
FRAME_SIZE = 1280


class WakeWordDetector:
    """Detects 'Hey Jarvis' wake word using OpenWakeWord."""

    def __init__(self):
        self._model: Model | None = None
        self._initialized = False
        self._settings = get_settings()
        self._buffer = bytearray()

    def initialize(self):
        """Initialize OpenWakeWord with 'hey_jarvis' model."""
        if self._initialized:
            return

        # Load the pre-trained "hey jarvis" model
        self._model = Model(wakeword_models=["hey_jarvis"])
        self._initialized = True
        logger.info("Wake word detector initialized (OpenWakeWord - hey_jarvis)")

    def process(self, audio_chunk: bytes) -> bool:
        """
        Process audio chunk and detect wake word.

        Args:
            audio_chunk: Raw PCM audio bytes (16kHz, mono, int16)

        Returns:
            True if wake word detected
        """
        if not self._model:
            raise RuntimeError("Wake word detector not initialized")

        # Buffer audio for proper frame size
        self._buffer.extend(audio_chunk)

        # Process complete frames
        detected = False
        frame_bytes = FRAME_SIZE * 2  # 2 bytes per int16 sample

        while len(self._buffer) >= frame_bytes:
            # Extract frame
            frame_data = bytes(self._buffer[:frame_bytes])
            del self._buffer[:frame_bytes]

            # Convert to numpy array (int16 -> float32 normalized)
            audio_array = np.frombuffer(frame_data, dtype=np.int16).astype(np.float32) / 32768.0

            # Get predictions
            predictions = self._model.predict(audio_array)

            # Check if wake word detected
            for model_name, score in predictions.items():
                if score >= self._settings.wake_word_threshold:
                    logger.info(f"Wake word detected! ({model_name}: {score:.3f})")
                    self._model.reset()  # Reset state after detection
                    self._buffer.clear()
                    return True

        return detected

    def cleanup(self):
        """Release resources."""
        self._model = None
        self._initialized = False
        self._buffer.clear()
        logger.info("Wake word detector cleaned up")

    @property
    def frame_length(self) -> int:
        """Return required frame length."""
        return FRAME_SIZE


# Singleton
wake_word_detector = WakeWordDetector()
