"""Task executor for background processing."""

import asyncio
from typing import Any
from datetime import datetime

from jarvis.config import get_settings
from jarvis.db.repositories import TaskRepository
from jarvis.worker.notifier import notifier
from jarvis.core.orchestrator import process_message
from jarvis.rag.ingestion import ingestion_pipeline
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
            "rag_ingest": self._handle_rag_ingest,
            "rag_deep_crawl": self._handle_rag_deep_crawl,
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

    async def _handle_rag_ingest(self, user_id: str, payload: dict) -> dict:
        """Handle RAG URL ingestion tasks."""
        url = payload.get("url", "")
        title = payload.get("title")
        notify = payload.get("notify", True)

        if not url:
            return {"type": "rag_ingest", "success": False, "error": "URL mancante"}

        # Ingest the URL
        result = await ingestion_pipeline.ingest_url(
            url=url,
            user_id=user_id,
            title=title
        )

        if notify:
            if result.get("success"):
                await notifier.notify_task_completed(
                    user_id,
                    "📚 Importazione completata",
                    f"Ho importato '{result.get('title', url)}' con {result.get('chunks_count', 0)} chunk."
                )
            else:
                await notifier.notify_task_completed(
                    user_id,
                    "❌ Importazione fallita",
                    f"Errore: {result.get('error', 'Errore sconosciuto')}"
                )

        return {
            "type": "rag_ingest",
            **result
        }

    async def _handle_rag_deep_crawl(self, user_id: str, payload: dict) -> dict:
        """Handle RAG deep crawl tasks (multiple pages)."""
        from jarvis.integrations.crawl4ai_client import crawler

        url = payload.get("url", "")
        max_depth = payload.get("max_depth", 2)
        max_pages = payload.get("max_pages", 50)
        notify = payload.get("notify", True)

        if not url:
            return {"type": "rag_deep_crawl", "success": False, "error": "URL mancante"}

        if notify:
            await notifier.notify_task_started(
                user_id,
                "🕷️ Deep crawl avviato",
                f"Sto crawlando {url} (max {max_pages} pagine)..."
            )

        # Deep crawl
        crawl_result = await crawler.deep_crawl(
            url=url,
            max_depth=max_depth,
            max_pages=max_pages
        )

        if not crawl_result.get("success"):
            if notify:
                await notifier.notify_task_completed(
                    user_id,
                    "❌ Crawl fallito",
                    "Nessuna pagina trovata"
                )
            return {"type": "rag_deep_crawl", "success": False, "error": "Crawl fallito"}

        # Ingest each page
        pages = crawl_result.get("pages", [])
        success_count = 0
        total_chunks = 0

        for page in pages:
            if page.get("content") and len(page["content"]) > 100:
                result = await ingestion_pipeline.ingest_text(
                    text=page["content"],
                    user_id=user_id,
                    title=page.get("title", page.get("url", "Untitled")),
                    source_type="url",
                    custom_metadata={
                        "source_url": page.get("url"),
                        "crawl_depth": page.get("depth", 0)
                    }
                )
                if result.get("success"):
                    success_count += 1
                    total_chunks += result.get("chunks_count", 0)

        if notify:
            await notifier.notify_task_completed(
                user_id,
                "✅ Deep crawl completato",
                f"Importate {success_count}/{len(pages)} pagine con {total_chunks} chunk totali."
            )

        return {
            "type": "rag_deep_crawl",
            "success": True,
            "pages_crawled": len(pages),
            "pages_ingested": success_count,
            "total_chunks": total_chunks
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
