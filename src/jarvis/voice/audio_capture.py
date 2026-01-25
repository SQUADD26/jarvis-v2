"""Audio capture from microphone using PyAudio."""

import pyaudio
import asyncio
from typing import AsyncGenerator
from jarvis.utils.logging import get_logger

logger = get_logger(__name__)

# Audio settings for Porcupine/Deepgram compatibility
SAMPLE_RATE = 16000
CHANNELS = 1
FORMAT = pyaudio.paInt16
CHUNK_SIZE = 512  # Porcupine requires 512 frames at 16kHz


class AudioCapture:
    """Captures audio from microphone in chunks."""

    def __init__(self):
        self._pyaudio: pyaudio.PyAudio | None = None
        self._stream: pyaudio.Stream | None = None
        self._running = False

    def start(self):
        """Initialize PyAudio and open microphone stream."""
        if self._running:
            return

        self._pyaudio = pyaudio.PyAudio()
        self._stream = self._pyaudio.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=CHUNK_SIZE,
        )
        self._running = True
        logger.info("Audio capture started")

    def stop(self):
        """Stop and cleanup audio resources."""
        if not self._running:
            return

        self._running = False
        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
            self._stream = None
        if self._pyaudio:
            self._pyaudio.terminate()
            self._pyaudio = None
        logger.info("Audio capture stopped")

    def read_chunk(self) -> bytes:
        """Read a single chunk of audio data (blocking)."""
        if not self._stream:
            raise RuntimeError("Audio capture not started")
        return self._stream.read(CHUNK_SIZE, exception_on_overflow=False)

    async def stream_chunks(self) -> AsyncGenerator[bytes, None]:
        """Yield audio chunks asynchronously."""
        if not self._running:
            self.start()

        loop = asyncio.get_event_loop()
        while self._running:
            try:
                # Run blocking read in executor
                chunk = await loop.run_in_executor(None, self.read_chunk)
                yield chunk
            except Exception as e:
                logger.error(f"Error reading audio: {e}")
                break

    @property
    def is_running(self) -> bool:
        return self._running


# Singleton
audio_capture = AudioCapture()
