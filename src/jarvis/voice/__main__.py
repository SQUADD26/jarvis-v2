"""Entry point for running the voice client: python -m jarvis.voice"""

import asyncio
from jarvis.voice.voice_loop import run_voice_client

if __name__ == "__main__":
    asyncio.run(run_voice_client())
