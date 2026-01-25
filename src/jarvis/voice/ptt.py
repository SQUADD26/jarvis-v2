"""Push-to-Talk (PTT) activation using global hotkeys."""

import asyncio
import threading
from pynput import keyboard
from jarvis.config import get_settings
from jarvis.utils.logging import get_logger

logger = get_logger(__name__)


class PushToTalk:
    """
    Push-to-Talk activation using global hotkeys.

    Default hotkey: Cmd+Shift+J (configurable via VOICE_PTT_KEY)
    """

    def __init__(self):
        self._listener: keyboard.GlobalHotKeys | None = None
        self._activated = asyncio.Event()
        self._running = False
        self._settings = get_settings()
        self._loop: asyncio.AbstractEventLoop | None = None

    def _parse_hotkey(self) -> str:
        """Parse hotkey string for pynput format."""
        # VOICE_PTT_KEY format: "<cmd>+<shift>+j"
        return self._settings.voice_ptt_key

    def _on_activate(self):
        """Callback when hotkey is pressed."""
        logger.info("PTT activated!")
        if self._loop:
            self._loop.call_soon_threadsafe(self._activated.set)

    def start(self, loop: asyncio.AbstractEventLoop):
        """Start listening for hotkey."""
        if self._running:
            return

        self._loop = loop
        hotkey = self._parse_hotkey()

        self._listener = keyboard.GlobalHotKeys({
            hotkey: self._on_activate
        })
        self._listener.start()
        self._running = True
        logger.info(f"PTT listening for hotkey: {hotkey}")

    def stop(self):
        """Stop listening."""
        if self._listener:
            self._listener.stop()
            self._listener = None
        self._running = False
        self._loop = None
        logger.info("PTT stopped")

    async def wait_for_activation(self) -> bool:
        """
        Wait for PTT activation.

        Returns:
            True when activated
        """
        self._activated.clear()
        await self._activated.wait()
        return True

    def reset(self):
        """Reset activation state."""
        self._activated.clear()


# Singleton
ptt = PushToTalk()
