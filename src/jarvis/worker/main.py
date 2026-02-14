"""Main worker loop for background task processing."""

import asyncio
import signal
from datetime import datetime, timedelta

from jarvis.config import get_settings
from jarvis.db.repositories import TaskRepository
from jarvis.worker.executor import executor
from jarvis.worker.notifier import notifier
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

    async def _init_scheduled_tasks(self):
        """Initialize recurring scheduled tasks if not already queued."""
        if not settings.briefing_user_id:
            logger.info("No BRIEFING_USER_ID configured, skipping briefing init")
            return

        from jarvis.db.supabase_client import get_db, run_db
        from zoneinfo import ZoneInfo
        db = get_db()

        # Check if a daily_briefing task already exists
        existing = await run_db(lambda: db.table("task_queue")
            .select("id")
            .eq("task_type", "daily_briefing")
            .in_("status", ["pending", "claimed", "running"])
            .limit(1)
            .execute()
        )

        if not existing.data:
            tz = ZoneInfo(settings.briefing_timezone)
            now_local = datetime.utcnow().replace(tzinfo=ZoneInfo("UTC")).astimezone(tz)

            morning = now_local.replace(
                hour=settings.briefing_morning_hour,
                minute=settings.briefing_morning_minute,
                second=0, microsecond=0
            )
            evening = now_local.replace(
                hour=settings.briefing_evening_hour,
                minute=settings.briefing_evening_minute,
                second=0, microsecond=0
            )

            if now_local < morning:
                next_time, next_type = morning, "morning"
            elif now_local < evening:
                next_time, next_type = evening, "evening"
            else:
                next_time, next_type = morning + timedelta(days=1), "morning"

            next_utc = next_time.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)

            await TaskRepository.enqueue(
                user_id=settings.briefing_user_id,
                task_type="daily_briefing",
                payload={"briefing_type": next_type},
                scheduled_at=next_utc,
                priority=9,
            )
            logger.info(f"Initialized daily briefing: {next_type} at {next_utc.isoformat()} UTC")
        else:
            logger.info("Daily briefing already scheduled, skipping init")

        # Initialize email monitor if not already queued
        existing_email = await run_db(lambda: db.table("task_queue")
            .select("id")
            .eq("task_type", "email_monitor")
            .in_("status", ["pending", "claimed", "running"])
            .limit(1)
            .execute()
        )

        if not existing_email.data:
            next_check = datetime.utcnow() + timedelta(minutes=1)
            await TaskRepository.enqueue(
                user_id=settings.briefing_user_id,
                task_type="email_monitor",
                payload={},
                scheduled_at=next_check,
                priority=7,
            )
            logger.info("Initialized email monitor")
        else:
            logger.info("Email monitor already scheduled, skipping init")

    async def start(self):
        """Start the worker loop."""
        logger.info(f"Worker {self.worker_id} starting...")
        self._running = True

        # Set up signal handlers
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._handle_shutdown)

        logger.info(f"Worker {self.worker_id} ready, starting poll loop")

        await self._init_scheduled_tasks()

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
    import fcntl
    import sys

    # Prevent duplicate instances
    lock_file = open("/tmp/jarvis-worker.lock", "w")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("ERROR: Another instance of jarvis-worker is already running. Exiting.")
        sys.exit(1)

    try:
        worker = Worker()
        await worker.start()
    finally:
        fcntl.flock(lock_file, fcntl.LOCK_UN)
        lock_file.close()


if __name__ == "__main__":
    asyncio.run(run_worker())
