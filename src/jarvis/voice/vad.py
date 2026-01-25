"""Voice Activity Detection using webrtcvad with audio buffering."""

import time
import webrtcvad
from jarvis.config import get_settings
from jarvis.utils.logging import get_logger

logger = get_logger(__name__)

# VAD settings
SAMPLE_RATE = 16000
FRAME_DURATION_MS = 30  # webrtcvad supports 10, 20, or 30 ms
# webrtcvad needs exactly 30ms frames at 16kHz = 480 samples = 960 bytes
VAD_FRAME_SAMPLES = int(SAMPLE_RATE * FRAME_DURATION_MS / 1000)  # 480 samples
VAD_FRAME_BYTES = VAD_FRAME_SAMPLES * 2  # 960 bytes (int16)


class VoiceActivityDetector:
    """
    Detects speech and end-of-utterance using WebRTC VAD.

    Buffers incoming audio chunks to form VAD-compatible frames
    since Porcupine uses 512 samples while VAD needs 480.
    """

    def __init__(self):
        self._vad = webrtcvad.Vad(3)  # Aggressiveness 3 (most aggressive)
        self._silence_start: float | None = None
        self._speech_started = False
        self._settings = get_settings()
        self._buffer = bytearray()

    def reset(self):
        """Reset state for new utterance."""
        self._silence_start = None
        self._speech_started = False
        self._buffer.clear()

    def process(self, audio_chunk: bytes) -> tuple[bool, bool]:
        """
        Process audio chunk and detect voice activity.

        Buffers incoming chunks and processes complete VAD frames.

        Args:
            audio_chunk: Raw PCM audio (any size, will be buffered)

        Returns:
            Tuple of (is_speech, end_of_utterance)
        """
        # Add chunk to buffer
        self._buffer.extend(audio_chunk)

        # Process all complete frames in buffer
        is_speech = False
        end_of_utterance = False

        while len(self._buffer) >= VAD_FRAME_BYTES:
            # Extract one frame
            frame = bytes(self._buffer[:VAD_FRAME_BYTES])
            del self._buffer[:VAD_FRAME_BYTES]

            # Process this frame
            frame_is_speech, frame_end = self._process_frame(frame)
            is_speech = is_speech or frame_is_speech
            end_of_utterance = end_of_utterance or frame_end

        return is_speech, end_of_utterance

    def _process_frame(self, frame: bytes) -> tuple[bool, bool]:
        """Process a single VAD frame."""
        is_speech = self._vad.is_speech(frame, SAMPLE_RATE)
        now = time.time()

        if is_speech:
            self._speech_started = True
            self._silence_start = None
            return True, False

        # Silence detected
        if self._speech_started:
            if self._silence_start is None:
                self._silence_start = now

            silence_duration = now - self._silence_start

            if silence_duration >= self._settings.voice_silence_timeout:
                logger.debug(f"End of utterance after {silence_duration:.1f}s silence")
                return False, True

        return False, False


# Singleton
vad = VoiceActivityDetector()
