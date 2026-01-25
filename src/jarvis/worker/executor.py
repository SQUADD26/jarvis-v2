"""Task executor for background processing."""

import asyncio
from typing import Any
from datetime import datetime

from jarvis.config import get_settings
from jarvis.db.repositories import TaskRepository
from jarvis.worker.notifier import notifier
from jarvis.core.orchestrator import process_message
from jarvis.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class TaskExecutor:
    """Executes background tasks based on their type."""

    async def execute(self, task: dict) -> dict:
        """Execute a task and return the result."""
        task_id = task["id"]
        task_type = task["task_type"]
        user_id = task["user_id"]
        payload = task.get("payload", {})

        logger.info(f"Executing task {task_id} type={task_type} for user={user_id}")

        # Mark as running
        await TaskRepository.start_task(task_id)

        try:
            # Dispatch to appropriate handler
            handler = self._get_handler(task_type)
            result = await handler(user_id, payload)

            # Mark as completed
            await TaskRepository.complete_task(task_id, result)

            logger.info(f"Task {task_id} completed successfully")
            return {"success": True, "result": result}

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Task {task_id} failed: {error_msg}")

            # Mark as failed (may retry automatically)
            await TaskRepository.fail_task(task_id, error_msg)

            return {"success": False, "error": error_msg}

    def _get_handler(self, task_type: str):
        """Get the handler function for a task type."""
        handlers = {
            "reminder": self._handle_reminder,
            "scheduled_check": self._handle_scheduled_check,
            "long_running": self._handle_long_running,
        }
        return handlers.get(task_type, self._handle_unknown)

    async def _handle_reminder(self, user_id: str, payload: dict) -> dict:
        """Handle reminder tasks."""
        message = payload.get("message", "Promemoria senza messaggio")

        await notifier.notify_reminder(user_id, message)

        return {
            "type": "reminder",
            "message": message,
            "delivered_at": datetime.utcnow().isoformat()
        }

    async def _handle_scheduled_check(self, user_id: str, payload: dict) -> dict:
        """Handle scheduled check tasks (calendar, email, etc.)."""
        check_type = payload.get("check_type", "general")
        query = payload.get("query", "")

        # Use the orchestrator to process the query
        if query:
            response = await process_message(user_id, query)
            await notifier.notify_task_completed(user_id, f"Controllo {check_type}", response)
            return {
                "type": "scheduled_check",
                "check_type": check_type,
                "response": response
            }

        return {
            "type": "scheduled_check",
            "check_type": check_type,
            "status": "no_query"
        }

    async def _handle_long_running(self, user_id: str, payload: dict) -> dict:
        """Handle long-running tasks."""
        query = payload.get("query", "")
        notify_start = payload.get("notify_start", True)
        notify_complete = payload.get("notify_complete", True)

        if notify_start:
            description = payload.get("description", query[:50] + "..." if len(query) > 50 else query)
            await notifier.notify_task_started(user_id, "Elaborazione", description)

        # Process the query
        response = await process_message(user_id, query)

        if notify_complete:
            await notifier.notify_task_completed(user_id, "Elaborazione", response)

        return {
            "type": "long_running",
            "query": query,
            "response": response
        }

    async def _handle_unknown(self, user_id: str, payload: dict) -> dict:
        """Handle unknown task types."""
        logger.warning(f"Unknown task type for user {user_id}: {payload}")
        return {
            "type": "unknown",
            "status": "skipped",
            "reason": "Unknown task type"
        }


# Singleton instance
executor = TaskExecutor()
