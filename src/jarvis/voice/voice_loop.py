"""Main voice client loop with PTT and wake word support."""

import asyncio
from enum import Enum
from collections import deque

from jarvis.config import get_settings
from jarvis.utils.logging import get_logger
from jarvis.integrations.deepgram_stt import deepgram
from jarvis.integrations.deepgram_tts import deepgram_tts

from jarvis.voice.audio_capture import audio_capture, CHUNK_SIZE
from jarvis.voice.wake_word import wake_word_detector
from jarvis.voice.ptt import ptt
from jarvis.voice.vad import vad
from jarvis.voice.audio_player import audio_player
from jarvis.voice.sounds import play_activation_beep, play_error_beep
from jarvis.voice.api_client import api_client

logger = get_logger(__name__)

# Voice client user ID
VOICE_USER_ID = "voice_local"
MAX_HISTORY_SIZE = 20


class VoiceState(Enum):
    """Voice client states."""
    WAITING = "waiting"              # Waiting for activation (PTT or wake word)
    LISTENING_COMMAND = "listening"  # Recording user speech
    PROCESSING = "processing"        # Transcribing and calling API
    SPEAKING = "speaking"            # Playing TTS response


class VoiceClient:
    """
    Voice client with PTT and wake word support.

    Modes:
    - PTT (Push-to-Talk): Press hotkey to activate
    - Wake Word: Say "Jarvis" to activate (requires Porcupine API key)

    Flow:
    1. WAITING - Wait for PTT hotkey or wake word
    2. LISTENING_COMMAND - Record speech until silence
    3. PROCESSING - STT → API → get response
    4. SPEAKING - TTS → play audio
    5. Return to WAITING
    """

    def __init__(self):
        self._state = VoiceState.WAITING
        self._settings = get_settings()
        self._conversation_history: deque = deque(maxlen=MAX_HISTORY_SIZE)
        self._running = False
        self._audio_buffer: list[bytes] = []
        self._mode = self._settings.voice_mode  # "ptt" or "wake_word"

    async def start(self):
        """Start the voice client loop."""
        logger.info("Starting voice client...")

        # Validate configuration
        if not self._settings.deepgram_api_key:
            logger.error("DEEPGRAM_API_KEY not set")
            return

        if not self._settings.jarvis_api_url:
            logger.error("JARVIS_API_URL not set")
            return

        if not self._settings.jarvis_api_key:
            logger.error("JARVIS_API_KEY not set")
            return

        # Check API connectivity
        logger.info("Checking API connectivity...")
        if not await api_client.health_check():
            logger.error(f"Cannot reach Jarvis API at {self._settings.jarvis_api_url}")
            return

        logger.info("API connection OK")

        # Determine mode
        if self._mode == "wake_word":
            if not wake_word_detector.is_available:
                logger.warning("PORCUPINE_ACCESS_KEY not set, falling back to PTT mode")
                self._mode = "ptt"

        # Initialize components
        try:
            audio_capture.start()
            deepgram.set_user_context(VOICE_USER_ID)
            deepgram_tts.set_user_context(VOICE_USER_ID)

            if self._mode == "wake_word":
                wake_word_detector.initialize()
                logger.info("Mode: Wake Word - Say 'Jarvis' to activate")
            else:
                ptt.start(asyncio.get_event_loop())
                logger.info(f"Mode: PTT - Press {self._settings.voice_ptt_key} to activate")

        except Exception as e:
            logger.error(f"Failed to initialize voice client: {e}")
            return

        self._running = True
        print(f"\n{'='*50}")
        print(f"  JARVIS Voice Client Ready")
        print(f"  Mode: {self._mode.upper()}")
        if self._mode == "ptt":
            print(f"  Attivazione: Premi INVIO")
        else:
            print(f"  Wake word: 'Jarvis'")
        print(f"  API: {self._settings.jarvis_api_url}")
        print(f"{'='*50}\n")

        try:
            if self._mode == "ptt":
                await self._ptt_loop()
            else:
                await self._wake_word_loop()
        except KeyboardInterrupt:
            logger.info("Voice client interrupted")
        finally:
            self._cleanup()

    async def _ptt_loop(self):
        """Main loop for PTT mode."""
        while self._running:
            # Wait for PTT activation
            logger.debug("Waiting for PTT activation...")
            await ptt.wait_for_activation()

            if not self._running:
                break

            # Activated!
            await play_activation_beep()
            self._state = VoiceState.LISTENING_COMMAND
            self._audio_buffer = []
            vad.reset()

            logger.info("Listening... (speak now)")

            # Record until silence
            await self._record_until_silence()

            # Process
            await self._process_command()

            ptt.reset()

    async def _wake_word_loop(self):
        """Main loop for wake word mode."""
        async for chunk in audio_capture.stream_chunks():
            if not self._running:
                break

            if self._state == VoiceState.WAITING:
                if wake_word_detector.process(chunk):
                    await play_activation_beep()
                    self._state = VoiceState.LISTENING_COMMAND
                    self._audio_buffer = []
                    vad.reset()
                    logger.info("Listening for command...")

            elif self._state == VoiceState.LISTENING_COMMAND:
                await self._handle_command_recording(chunk)

    async def _record_until_silence(self):
        """Record audio until silence is detected."""
        start_time = asyncio.get_event_loop().time()

        async for chunk in audio_capture.stream_chunks():
            if not self._running:
                break

            self._audio_buffer.append(chunk)

            # Check for end of utterance
            is_speech, end_of_utterance = vad.process(chunk)

            # Check max recording time
            elapsed = asyncio.get_event_loop().time() - start_time

            if end_of_utterance:
                logger.debug("End of speech detected")
                break

            if elapsed >= self._settings.voice_max_recording:
                logger.warning("Max recording time reached")
                break

    async def _handle_command_recording(self, chunk: bytes):
        """Record user command until silence (wake word mode)."""
        self._audio_buffer.append(chunk)

        is_speech, end_of_utterance = vad.process(chunk)

        total_samples = len(self._audio_buffer) * CHUNK_SIZE
        recording_seconds = total_samples / 16000

        if end_of_utterance or recording_seconds >= self._settings.voice_max_recording:
            if recording_seconds >= self._settings.voice_max_recording:
                logger.warning("Max recording time reached")

            self._state = VoiceState.PROCESSING
            await self._process_command()
            self._state = VoiceState.WAITING

    async def _process_command(self):
        """Transcribe and process the recorded command."""
        try:
            # Combine audio chunks
            audio_data = b"".join(self._audio_buffer)
            self._audio_buffer = []

            if len(audio_data) < 3200:  # Less than 0.1 seconds
                logger.debug("Audio too short, ignoring")
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
                return

            logger.info(f"You said: {transcript}")
            print(f"\n> {transcript}")

            # Build history for context
            history = list(self._conversation_history)

            # Call Jarvis API
            logger.info("Calling Jarvis API...")
            response = await api_client.chat(
                message=transcript,
                user_id=VOICE_USER_ID,
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

            logger.info(f"Jarvis: {response[:100]}...")
            print(f"\nJarvis: {response}\n")

            # Speak the response
            await self._speak_response(response)

        except Exception as e:
            logger.error(f"Error processing command: {e}")
            print(f"\nError: {e}\n")
            await play_error_beep()

    async def _speak_response(self, text: str):
        """Convert text to speech and play it."""
        self._state = VoiceState.SPEAKING

        try:
            logger.info("Generating TTS...")

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
        if self._mode == "wake_word":
            wake_word_detector.cleanup()
        else:
            ptt.stop()
        logger.info("Voice client stopped")


async def run_voice_client():
    """Entry point to run the voice client."""
    client = VoiceClient()
    await client.start()
