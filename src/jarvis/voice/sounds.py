"""Activation sounds for voice client with pre-cached audio."""

import asyncio
import numpy as np
import sounddevice as sd
from jarvis.utils.logging import get_logger

logger = get_logger(__name__)

SAMPLE_RATE = 24000


def _generate_beep(
    frequency: float,
    duration: float,
    volume: float = 0.3
) -> np.ndarray:
    """
    Generate a simple sine wave beep.

    Args:
        frequency: Beep frequency in Hz
        duration: Duration in seconds
        volume: Volume (0.0 to 1.0)

    Returns:
        Numpy array of audio samples
    """
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), False)
    # Generate sine wave with fade in/out
    beep = np.sin(2 * np.pi * frequency * t)

    # Apply fade in/out (10% of duration each)
    fade_samples = int(len(beep) * 0.1)
    beep[:fade_samples] *= np.linspace(0, 1, fade_samples)
    beep[-fade_samples:] *= np.linspace(1, 0, fade_samples)

    return (beep * volume).astype(np.float32)


# Pre-cache beeps at module load to avoid regeneration overhead
_ACTIVATION_BEEP = _generate_beep(frequency=880, duration=0.15)
_READY_BEEP = _generate_beep(frequency=660, duration=0.1)
_ERROR_BEEP = _generate_beep(frequency=220, duration=0.3)


async def play_activation_beep():
    """Play activation beep when wake word is detected."""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None,
        lambda: sd.play(_ACTIVATION_BEEP, SAMPLE_RATE, blocking=True)
    )
    logger.debug("Played activation beep")


async def play_ready_beep():
    """Play ready beep when listening starts."""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None,
        lambda: sd.play(_READY_BEEP, SAMPLE_RATE, blocking=True)
    )


async def play_error_beep():
    """Play error beep when something goes wrong."""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None,
        lambda: sd.play(_ERROR_BEEP, SAMPLE_RATE, blocking=True)
    )
