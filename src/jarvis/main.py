import asyncio
from jarvis.utils.logging import setup_logging, get_logger
from jarvis.db.redis_client import redis_client
from jarvis.interfaces.telegram_bot import run_bot


async def main():
    import fcntl
    import sys

    # Prevent duplicate instances
    lock_file = open("/tmp/jarvis-bot.lock", "w")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("ERROR: Another instance of jarvis-bot is already running. Exiting.")
        sys.exit(1)

    # Setup logging
    setup_logging()
    logger = get_logger(__name__)

    logger.info("Starting Jarvis v2...")

    # Connect to Redis
    await redis_client.connect()

    try:
        # Run Telegram bot
        await run_bot()
    finally:
        # Cleanup
        await redis_client.disconnect()
        fcntl.flock(lock_file, fcntl.LOCK_UN)
        lock_file.close()
        logger.info("Jarvis shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
