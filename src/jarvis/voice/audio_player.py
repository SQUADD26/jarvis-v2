"""Audio playback using sounddevice."""

import asyncio
import numpy as np
import sounddevice as sd
from jarvis.utils.logging import get_logger

logger = get_logger(__name__)


class AudioPlayer:
    """Plays audio through speakers using sounddevice."""

    def __init__(self):
        self._playing = False

    async def play(
        self,
        audio_data: bytes,
        sample_rate: int = 24000,
        channels: int = 1,
        dtype: str = "int16"
    ):
        """
        Play raw PCM audio data.

        Args:
            audio_data: Raw PCM bytes (linear16)
            sample_rate: Sample rate in Hz
            channels: Number of channels
            dtype: Data type of samples
        """
        if not audio_data:
            logger.warning("No audio data to play")
            return

        self._playing = True

        try:
            # Convert bytes to numpy array
            audio_array = np.frombuffer(audio_data, dtype=np.int16)

            # Normalize to float32 for sounddevice
            audio_float = audio_array.astype(np.float32) / 32768.0

            # Play audio (blocking in executor)
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: sd.play(audio_float, sample_rate, blocking=True)
            )

            logger.debug(f"Played {len(audio_data)} bytes of audio")

        except Exception as e:
            logger.error(f"Error playing audio: {e}")
        finally:
            self._playing = False

    def stop(self):
        """Stop any currently playing audio."""
        sd.stop()
        self._playing = False

    @property
    def is_playing(self) -> bool:
        return self._playing


# Singleton
audio_player = AudioPlayer()
