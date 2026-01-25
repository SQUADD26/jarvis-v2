"""Main worker loop for background task processing."""

import asyncio
import signal
from datetime import datetime

from jarvis.config import get_settings
from jarvis.db.repositories import TaskRepository
from jarvis.worker.executor import executor
from jarvis.worker.notifier import notifier
from jarvis.core.router import router
from jarvis.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class Worker:
    """Background worker for processing tasks from the queue."""

    def __init__(self):
        self.worker_id = settings.worker_id
        self.poll_interval_active = settings.worker_poll_interval_active
        self.poll_interval_idle = settings.worker_poll_interval_idle
        self.stale_timeout = settings.worker_stale_timeout_minutes
        self._running = False
        self._idle_count = 0
        self._last_cleanup = datetime.utcnow()

    async def start(self):
        """Start the worker loop."""
        logger.info(f"Worker {self.worker_id} starting...")

        # Initialize router for semantic intent detection
        await router.initialize()

        self._running = True

        # Set up signal handlers
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._handle_shutdown)

        logger.info(f"Worker {self.worker_id} ready, starting poll loop")

        try:
            await self._poll_loop()
        except asyncio.CancelledError:
            logger.info("Worker cancelled")
        finally:
            await self._cleanup()

    def _handle_shutdown(self):
        """Handle shutdown signals."""
        logger.info(f"Worker {self.worker_id} received shutdown signal")
        self._running = False

    async def _poll_loop(self):
        """Main polling loop."""
        while self._running:
            try:
                # Try to claim a task
                task = await TaskRepository.claim_next(self.worker_id)

                if task:
                    # Reset idle counter
                    self._idle_count = 0

                    # Execute the task
                    await executor.execute(task)

                    # Use active polling interval
                    await asyncio.sleep(self.poll_interval_active)
                else:
                    # No task available, increase idle count
                    self._idle_count += 1

                    # Use idle polling interval (with backoff)
                    sleep_time = min(
                        self.poll_interval_idle * (1 + self._idle_count * 0.1),
                        5.0  # Max 5 seconds
                    )
                    await asyncio.sleep(sleep_time)

                # Periodic cleanup of stale tasks
                await self._maybe_cleanup_stale()

            except Exception as e:
                logger.error(f"Error in poll loop: {e}", exc_info=True)
                await asyncio.sleep(self.poll_interval_idle)

    async def _maybe_cleanup_stale(self):
        """Periodically clean up stale tasks."""
        now = datetime.utcnow()
        # Run cleanup every 5 minutes
        if (now - self._last_cleanup).total_seconds() > 300:
            try:
                cleaned = await TaskRepository.cleanup_stale_tasks(self.stale_timeout)
                if cleaned:
                    logger.info(f"Cleaned up {cleaned} stale tasks")
                self._last_cleanup = now
            except Exception as e:
                logger.warning(f"Failed to cleanup stale tasks: {e}")

    async def _cleanup(self):
        """Cleanup resources before shutdown."""
        logger.info(f"Worker {self.worker_id} cleaning up...")
        await notifier.close()
        logger.info(f"Worker {self.worker_id} stopped")


async def run_worker():
    """Entry point for running the worker."""
    worker = Worker()
    await worker.start()


if __name__ == "__main__":
    asyncio.run(run_worker())
