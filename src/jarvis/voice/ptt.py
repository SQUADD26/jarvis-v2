"""Push-to-Talk (PTT) activation using keyboard input."""

import asyncio
import sys
import threading
from jarvis.config import get_settings
from jarvis.utils.logging import get_logger

logger = get_logger(__name__)


class PushToTalk:
    """
    Push-to-Talk activation.

    Press Enter in the terminal to activate (most reliable cross-platform).
    Global hotkeys have compatibility issues with Python 3.14.
    """

    def __init__(self):
        self._activated = asyncio.Event()
        self._running = False
        self._settings = get_settings()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None

    def _input_listener(self):
        """Background thread that listens for Enter key."""
        while self._running:
            try:
                input()  # Blocks until Enter is pressed
                if self._running and self._loop:
                    self._loop.call_soon_threadsafe(self._activated.set)
                    logger.info("PTT activated!")
            except EOFError:
                break
            except Exception as e:
                logger.error(f"Input error: {e}")
                break

    def start(self, loop: asyncio.AbstractEventLoop):
        """Start listening for activation."""
        if self._running:
            return

        self._loop = loop
        self._running = True

        # Start input listener thread
        self._thread = threading.Thread(target=self._input_listener, daemon=True)
        self._thread.start()

        logger.info("PTT ready - Press ENTER to activate")

    def stop(self):
        """Stop listening."""
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
