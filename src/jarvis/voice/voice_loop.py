"""Main voice client loop with state machine."""

import asyncio
import time
from enum import Enum
from collections import deque

from jarvis.config import get_settings
from jarvis.utils.logging import get_logger
from jarvis.core.orchestrator import process_message
from jarvis.integrations.deepgram_stt import deepgram
from jarvis.integrations.deepgram_tts import deepgram_tts

from jarvis.voice.audio_capture import audio_capture, CHUNK_SIZE
from jarvis.voice.wake_word import wake_word_detector
from jarvis.voice.vad import vad
from jarvis.voice.audio_player import audio_player
from jarvis.voice.sounds import play_activation_beep, play_error_beep

logger = get_logger(__name__)

# Voice client user ID (distinct from Telegram)
VOICE_USER_ID = "voice_local"
MAX_HISTORY_SIZE = 20


class VoiceState(Enum):
    """Voice client states."""
    LISTENING_WAKE = "listening_wake"
    LISTENING_COMMAND = "listening_command"
    PROCESSING = "processing"
    SPEAKING = "speaking"


class VoiceClient:
    """
    Voice client with wake word detection and speech interaction.

    Flow:
    1. LISTENING_WAKE - Wait for "Jarvis" wake word
    2. LISTENING_COMMAND - Record user speech until silence
    3. PROCESSING - Transcribe and process with orchestrator
    4. SPEAKING - Play TTS response
    5. Return to LISTENING_WAKE
    """

    def __init__(self):
        self._state = VoiceState.LISTENING_WAKE
        self._settings = get_settings()
        self._conversation_history: deque = deque(maxlen=MAX_HISTORY_SIZE)
        self._running = False
        self._audio_buffer: list[bytes] = []

    async def start(self):
        """Start the voice client loop."""
        logger.info("Starting voice client...")

        # Validate configuration
        if not self._settings.deepgram_api_key:
            logger.error("DEEPGRAM_API_KEY not set")
            return

        # Initialize components
        try:
            wake_word_detector.initialize()
            audio_capture.start()
            deepgram.set_user_context(VOICE_USER_ID)
            deepgram_tts.set_user_context(VOICE_USER_ID)
        except Exception as e:
            logger.error(f"Failed to initialize voice client: {e}")
            return

        self._running = True
        logger.info("Voice client ready. Say 'Hey Jarvis' to activate.")

        try:
            await self._main_loop()
        except KeyboardInterrupt:
            logger.info("Voice client interrupted")
        finally:
            self._cleanup()

    async def _main_loop(self):
        """Main processing loop."""
        async for chunk in audio_capture.stream_chunks():
            if not self._running:
                break

            if self._state == VoiceState.LISTENING_WAKE:
                await self._handle_wake_word(chunk)

            elif self._state == VoiceState.LISTENING_COMMAND:
                await self._handle_command_recording(chunk)

    async def _handle_wake_word(self, chunk: bytes):
        """Listen for wake word."""
        if wake_word_detector.process(chunk):
            # Wake word detected!
            await play_activation_beep()
            self._state = VoiceState.LISTENING_COMMAND
            self._audio_buffer = []
            vad.reset()
            logger.info("Listening for command...")

    async def _handle_command_recording(self, chunk: bytes):
        """Record user command until silence."""
        self._audio_buffer.append(chunk)

        # Check for end of utterance
        is_speech, end_of_utterance = vad.process(chunk)

        # Check max recording time
        total_samples = len(self._audio_buffer) * CHUNK_SIZE
        recording_seconds = total_samples / 16000

        if end_of_utterance or recording_seconds >= self._settings.voice_max_recording:
            if recording_seconds >= self._settings.voice_max_recording:
                logger.warning("Max recording time reached")

            # Process the recorded audio
            self._state = VoiceState.PROCESSING
            await self._process_command()

    async def _process_command(self):
        """Transcribe and process the recorded command."""
        try:
            # Combine audio chunks
            audio_data = b"".join(self._audio_buffer)
            self._audio_buffer = []

            if len(audio_data) < 3200:  # Less than 0.1 seconds
                logger.debug("Audio too short, ignoring")
                self._state = VoiceState.LISTENING_WAKE
                return

            # Transcribe with Deepgram
            logger.info("Transcribing...")
            transcript = await deepgram.transcribe_bytes(
                audio_data=audio_data,
                filename="voice_command.wav",
                language="it",
                user_id=VOICE_USER_ID
            )

            if not transcript or transcript.strip() == "":
                logger.info("No speech detected")
                self._state = VoiceState.LISTENING_WAKE
                return

            logger.info(f"User said: {transcript}")

            # Build history for context
            history = list(self._conversation_history)

            # Process with orchestrator
            logger.info("Processing with orchestrator...")
            response = await process_message(
                user_id=VOICE_USER_ID,
                message=transcript,
                history=history
            )

            # Update conversation history
            self._conversation_history.append({
                "role": "user",
                "content": transcript
            })
            self._conversation_history.append({
                "role": "assistant",
                "content": response
            })

            # Speak the response
            await self._speak_response(response)

        except Exception as e:
            logger.error(f"Error processing command: {e}")
            await play_error_beep()

        finally:
            self._state = VoiceState.LISTENING_WAKE

    async def _speak_response(self, text: str):
        """Convert text to speech and play it."""
        self._state = VoiceState.SPEAKING

        try:
            logger.info(f"Generating TTS for: {text[:100]}...")

            # Synthesize with Deepgram TTS
            audio_data = await deepgram_tts.synthesize(
                text=text,
                user_id=VOICE_USER_ID,
                encoding="linear16",
                sample_rate=24000
            )

            # Play the audio
            await audio_player.play(audio_data, sample_rate=24000)

            logger.info("Response spoken")

        except Exception as e:
            logger.error(f"TTS error: {e}")
            await play_error_beep()

    def stop(self):
        """Stop the voice client."""
        self._running = False

    def _cleanup(self):
        """Cleanup resources."""
        audio_capture.stop()
        wake_word_detector.cleanup()
        logger.info("Voice client stopped")


async def run_voice_client():
    """Entry point to run the voice client."""
    client = VoiceClient()
    await client.start()
